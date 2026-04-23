import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceEvent, EventType
from app.models.user import User


async def determine_event_type(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Toggle logic: first event today → check_in, then alternate."""
    today_start = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
    today_end = datetime.combine(date.today(), time.max, tzinfo=timezone.utc)
    result = await db.execute(
        select(func.count())
        .where(
            and_(
                AttendanceEvent.user_id == user_id,
                AttendanceEvent.recorded_at >= today_start,
                AttendanceEvent.recorded_at <= today_end,
                AttendanceEvent.event_type.in_([EventType.check_in.value, EventType.check_out.value]),
            )
        )
    )
    count = result.scalar_one()
    return EventType.check_out.value if count % 2 == 1 else EventType.check_in.value


async def find_by_jti(db: AsyncSession, jti: str) -> AttendanceEvent | None:
    result = await db.execute(select(AttendanceEvent).where(AttendanceEvent.qr_jti == jti))
    return result.scalar_one_or_none()


async def record_scan(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    jti: str,
    scanner_user_id: uuid.UUID | None = None,
    device_id: str | None = None,
) -> tuple[AttendanceEvent, bool]:
    """
    Record a scan.  Returns (event, created).
    If jti already exists → returns existing event and created=False (idempotent).
    """
    existing = await find_by_jti(db, jti)
    if existing:
        return existing, False

    event_type = await determine_event_type(db, user_id)
    event = AttendanceEvent(
        user_id=user_id,
        event_type=event_type,
        qr_jti=jti,
        scanner_user_id=scanner_user_id,
        client_device_id=device_id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event, True


async def list_events(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    event_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[AttendanceEvent], int]:
    """Return (events, total_count) with optional filters."""
    q = select(AttendanceEvent).join(User, AttendanceEvent.user_id == User.id)
    count_q = select(func.count()).select_from(AttendanceEvent)

    conditions = []
    if user_id:
        conditions.append(AttendanceEvent.user_id == user_id)
    if date_from:
        conditions.append(AttendanceEvent.recorded_at >= date_from)
    if date_to:
        conditions.append(AttendanceEvent.recorded_at <= date_to)
    if event_type:
        conditions.append(AttendanceEvent.event_type == event_type)

    if conditions:
        q = q.where(and_(*conditions))
        count_q = count_q.where(and_(*conditions))

    total = (await db.execute(count_q)).scalar_one()
    q = q.order_by(AttendanceEvent.recorded_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def manual_correction(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    event_type: str,
    recorded_at: datetime | None = None,
    notes: str | None = None,
    scanner_user_id: uuid.UUID | None = None,
) -> AttendanceEvent:
    event = AttendanceEvent(
        user_id=user_id,
        event_type=event_type,
        recorded_at=recorded_at or datetime.now(timezone.utc),
        notes=notes,
        scanner_user_id=scanner_user_id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event
