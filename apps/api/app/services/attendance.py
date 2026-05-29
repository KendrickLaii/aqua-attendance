import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.attendance import AttendanceEvent, EventType
from app.models.product import AttendanceStatus, Product


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """Coerce a datetime to UTC, treating naive values as already-UTC.

    SQLite has no native timezone storage so columns declared as
    ``DateTime(timezone=True)`` may come back naive in tests; we still want
    correct date comparisons.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_same_utc_day(a: datetime, b: datetime) -> bool:
    return _as_utc(a).date() == _as_utc(b).date()


def _normalize_location(location: str | None) -> str | None:
    if location is None:
        return None
    trimmed = location.strip()
    return trimmed[:255] if trimmed else None


def _next_event_type(product: Product, now: datetime) -> str:
    """Decide check_in vs check_out based on the product's current attendance status.

    If the last event was on a previous UTC day, treat the product as
    checked_out regardless of stored status so the new day starts fresh.
    """
    if (
        product.attendance_status == AttendanceStatus.checked_in.value
        and product.last_event_at is not None
        and _is_same_utc_day(product.last_event_at, now)
    ):
        return EventType.check_out.value
    return EventType.check_in.value


async def find_recent_event(
    db: AsyncSession, *, product_id: uuid.UUID, within_seconds: int
) -> AttendanceEvent | None:
    """Return the latest scan event for this product within the debounce window."""
    if within_seconds <= 0:
        return None
    cutoff = _now() - timedelta(seconds=within_seconds)
    result = await db.execute(
        select(AttendanceEvent)
        .where(
            and_(
                AttendanceEvent.product_id == product_id,
                AttendanceEvent.recorded_at >= cutoff,
                AttendanceEvent.event_type.in_(
                    [EventType.check_in.value, EventType.check_out.value]
                ),
            )
        )
        .order_by(AttendanceEvent.recorded_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def record_scan(
    db: AsyncSession,
    *,
    product: Product,
    jti: str | None,
    recorded_by_user_id: uuid.UUID | None = None,
    device_id: str | None = None,
    location_id: uuid.UUID | None = None,
    location: str | None = None,
    event_type: str | None = None,
) -> tuple[AttendanceEvent, bool]:
    """Record a scan and update the product's attendance status.

    When ``event_type`` is omitted, check-in vs check-out is inferred from
    the product's current status (toggle).  Callers may pass an explicit
    ``check_in`` or ``check_out`` so kiosk staff choose the action.

    Returns (event, created). If a scan landed within the debounce window
    for this product, returns the existing event with created=False so
    rapid double-taps at a kiosk do not produce duplicate rows.
    """
    debounce = getattr(settings, "SCAN_DEBOUNCE_SECONDS", 3)
    recent = await find_recent_event(db, product_id=product.id, within_seconds=debounce)
    if recent is not None:
        return recent, False

    now = _now()
    if event_type in (EventType.check_in.value, EventType.check_out.value):
        resolved_event_type = event_type
    else:
        resolved_event_type = _next_event_type(product, now)
    loc = _normalize_location(location)

    event = AttendanceEvent(
        product_id=product.id,
        event_type=resolved_event_type,
        recorded_at=now,
        qr_jti=jti,
        recorded_by_user_id=recorded_by_user_id,
        client_device_id=device_id,
        location_id=location_id,
        location=loc,
    )
    db.add(event)

    product.attendance_status = (
        AttendanceStatus.checked_in.value
        if resolved_event_type == EventType.check_in.value
        else AttendanceStatus.checked_out.value
    )
    product.last_event_at = now
    product.last_event_location_id = location_id
    product.last_event_location = loc

    await db.commit()
    await db.refresh(event)
    return event, True


async def list_events(
    db: AsyncSession,
    *,
    product_id: uuid.UUID | None = None,
    product_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    event_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[AttendanceEvent], int]:
    """Return (events, total_count) with optional filters."""
    q = (
        select(AttendanceEvent)
        .join(Product, AttendanceEvent.product_id == Product.id)
        .options(selectinload(AttendanceEvent.product))
    )
    count_q = select(func.count()).select_from(AttendanceEvent)

    conditions = []
    if product_id:
        conditions.append(AttendanceEvent.product_id == product_id)
    if product_type:
        conditions.append(Product.product_type == product_type)
    if date_from:
        conditions.append(AttendanceEvent.recorded_at >= date_from)
    if date_to:
        conditions.append(AttendanceEvent.recorded_at <= date_to)
    if event_type:
        conditions.append(AttendanceEvent.event_type == event_type)

    if conditions:
        q = q.where(and_(*conditions))
        count_q_with_join = select(func.count()).select_from(AttendanceEvent).join(
            Product, AttendanceEvent.product_id == Product.id
        ).where(and_(*conditions))
        total = (await db.execute(count_q_with_join)).scalar_one()
    else:
        total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(AttendanceEvent.recorded_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def manual_correction(
    db: AsyncSession,
    *,
    product: Product,
    event_type: str,
    recorded_at: datetime | None = None,
    location_id: uuid.UUID | None = None,
    location: str | None = None,
    notes: str | None = None,
    recorded_by_user_id: uuid.UUID | None = None,
) -> AttendanceEvent:
    """Insert a manual correction.  If the correction is an explicit
    check_in/check_out, also update the product's attendance_status so the
    next scan continues the toggle from the corrected state.
    """
    when = recorded_at or _now()
    loc = _normalize_location(location)
    event = AttendanceEvent(
        product_id=product.id,
        event_type=event_type,
        recorded_at=when,
        location_id=location_id,
        location=loc,
        notes=notes,
        recorded_by_user_id=recorded_by_user_id,
    )
    db.add(event)

    if event_type == EventType.check_in.value:
        product.attendance_status = AttendanceStatus.checked_in.value
        product.last_event_at = when
        product.last_event_location_id = location_id
        product.last_event_location = loc
    elif event_type == EventType.check_out.value:
        product.attendance_status = AttendanceStatus.checked_out.value
        product.last_event_at = when
        product.last_event_location_id = location_id
        product.last_event_location = loc

    await db.commit()
    await db.refresh(event)
    return event


async def rotate_product_qr(db: AsyncSession, *, product: Product) -> Product:
    """Invalidate any existing QR for this product by bumping its token version."""
    product.qr_token_version = (product.qr_token_version or 0) + 1
    await db.commit()
    await db.refresh(product)
    return product
