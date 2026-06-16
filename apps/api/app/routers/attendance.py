import csv
import uuid
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
import jwt
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import DB, AdminOnly
from app.limiter import limiter
from app.models.attendance import AttendanceEvent
from app.models.location import Location
from app.models.product import Product
from app.schemas.attendance import (
    AttendanceDayStatsOut,
    AttendanceOut,
    ManualCorrectionRequest,
    ScanAllowedLocation,
    ScanLocationNotAllowedDetail,
    ScanPreviewOut,
    ScanPreviewRequest,
    ScanRequest,
)
from app.services import attendance as att_svc
from app.services.qr import verify_qr_token

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _event_to_out(event: AttendanceEvent) -> AttendanceOut:
    return AttendanceOut(
        id=event.id,
        product_id=event.product_id,
        product_code=event.product.code if event.product else None,
        product_name=event.product.full_name if event.product else None,
        product_type=event.product.product_type if event.product else None,
        event_type=event.event_type,
        source=event.source,
        recorded_at=event.recorded_at,
        attendance_status=event.product.attendance_status if event.product else None,
        qr_jti=event.qr_jti,
        recorded_by_user_id=event.recorded_by_user_id,
        client_device_id=event.client_device_id,
        location_id=event.location_id,
        location=event.location,
        notes=event.notes,
    )


async def _resolve_location(db: DB, location_id: uuid.UUID | None, location_text: str | None) -> tuple[uuid.UUID | None, str | None]:
    if location_id is None:
        return None, location_text
    result = await db.execute(select(Location).where(Location.id == location_id))
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    if not location.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Location is inactive")
    display_name = location.name_en or location.name_zh or ""
    return location.id, display_name


async def _reload_with_product(db: AsyncSession, event_id: uuid.UUID) -> AttendanceEvent:
    result = await db.execute(
        select(AttendanceEvent)
        .options(selectinload(AttendanceEvent.product))
        .where(AttendanceEvent.id == event_id)
    )
    return result.scalar_one()


def _raise_location_not_allowed(product: Product) -> None:
    allowed = [
        ScanAllowedLocation(
            id=loc.id,
            code=loc.code,
            name_zh=loc.name_zh,
            name_en=loc.name_en,
        )
        for loc in product.scan_locations
    ]
    detail = ScanLocationNotAllowedDetail(
        message="Product is not allowed to scan at this location",
        product_name=product.full_name,
        product_code=product.code,
        allowed_locations=allowed,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail.model_dump(mode="json"),
    )


async def _resolve_product_for_scan(
    db: AsyncSession,
    *,
    qr_token: str,
    location_id: uuid.UUID | None,
    location_text: str | None = None,
) -> tuple[Product, uuid.UUID, str | None, dict]:
    """Validate QR and location; return product, location, and JWT payload. Does not record attendance."""
    try:
        payload = verify_qr_token(qr_token)
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid QR: {e}")

    try:
        target_product_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR: bad subject")

    product_query = (
        select(Product)
        .options(selectinload(Product.scan_locations))
        .where(Product.id == target_product_id)
    )
    # PostgreSQL only: row lock prevents concurrent scans of the same product
    # from creating duplicate attendance events within the debounce window.
    if settings.DATABASE_URL.startswith("postgresql"):
        product_query = product_query.with_for_update()
    result = await db.execute(product_query)
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if not product.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product is inactive")

    if payload.get("ver") != product.qr_token_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid QR: token has been rotated, please refresh the QR",
        )

    resolved_location_id, location_name = await _resolve_location(db, location_id, location_text)
    if resolved_location_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="location_id is required for scan",
        )
    if not any(loc.id == resolved_location_id for loc in product.scan_locations):
        _raise_location_not_allowed(product)
    return product, resolved_location_id, location_name, payload


@router.post("/scan/preview", response_model=ScanPreviewOut)
async def scan_preview(body: ScanPreviewRequest, _admin: AdminOnly, db: DB) -> ScanPreviewOut:
    """Resolve QR to product identity without recording attendance (for confirm UI)."""
    product, _location_id, location_name, _payload = await _resolve_product_for_scan(
        db,
        qr_token=body.qr_token,
        location_id=body.location_id,
    )
    return ScanPreviewOut(
        product_id=product.id,
        product_code=product.code,
        product_name=product.full_name,
        product_type=product.product_type,
        attendance_status=product.attendance_status,
        location=location_name,
    )


@router.post("/scan", response_model=AttendanceOut)
@limiter.limit(settings.SCAN_RATE_LIMIT)
async def scan(request: Request, body: ScanRequest, admin: AdminOnly, db: DB) -> AttendanceOut:
    """Scan a product's QR.

    Pass ``event_type`` (``check_in`` or ``check_out``) to record that
    action explicitly.  When omitted, the server toggles based on the
    product's current ``attendance_status``.  Rapid duplicate scans within
    ``SCAN_DEBOUNCE_SECONDS`` return the existing event (no duplicate row).
    """
    product, location_id, location_name, payload = await _resolve_product_for_scan(
        db,
        qr_token=body.qr_token,
        location_id=body.location_id,
        location_text=body.location,
    )

    explicit_type = body.event_type.value if body.event_type is not None else None

    event, _created = await att_svc.record_scan(
        db,
        product=product,
        jti=payload.get("jti"),
        recorded_by_user_id=admin.id,
        device_id=body.device_id,
        location_id=location_id,
        location=location_name,
        event_type=explicit_type,
    )

    event = await _reload_with_product(db, event.id)
    return _event_to_out(event)


@router.get("/stats", response_model=AttendanceDayStatsOut)
async def attendance_day_stats(
    _admin: AdminOnly,
    db: DB,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AttendanceDayStatsOut:
    """Aggregate event counts for a date range (dashboard stats)."""
    stats = await att_svc.event_day_stats(db, date_from=date_from, date_to=date_to)
    return AttendanceDayStatsOut(**stats)


@router.get("", response_model=list[AttendanceOut])
async def list_attendance(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    product_id: uuid.UUID | None = None,
    product_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    event_type: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[AttendanceOut]:
    """List attendance events (admin or superadmin only)."""
    events, total = await att_svc.list_events(
        db,
        product_id=product_id,
        product_type=product_type,
        date_from=date_from,
        date_to=date_to,
        event_type=event_type,
        page=page,
        page_size=page_size,
    )
    response.headers["X-Total-Count"] = str(total)
    return [_event_to_out(e) for e in events]


@router.post("/manual", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
async def create_manual_correction(
    body: ManualCorrectionRequest, admin: AdminOnly, db: DB
) -> AttendanceOut:
    result = await db.execute(select(Product).where(Product.id == body.product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    location_id, location_name = await _resolve_location(db, body.location_id, body.location)

    event = await att_svc.manual_correction(
        db,
        product=product,
        event_type=body.event_type.value,
        recorded_at=body.recorded_at,
        location_id=location_id,
        location=location_name,
        notes=body.notes,
        recorded_by_user_id=admin.id,
    )
    event = await _reload_with_product(db, event.id)
    return _event_to_out(event)


@router.get("/export/csv")
async def export_csv(
    _admin: AdminOnly,
    db: DB,
    product_id: uuid.UUID | None = None,
    product_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> StreamingResponse:
    if date_from is None or date_to is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from and date_to are required for CSV export",
        )

    events, truncated = await att_svc.list_events_for_export(
        db,
        product_id=product_id,
        product_type=product_type,
        date_from=date_from,
        date_to=date_to,
    )
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id",
        "product_id",
        "product_code",
        "product_name",
        "product_type",
        "event_type",
        "recorded_at",
        "recorded_by_user_id",
        "device_id",
        "location_id",
        "location",
        "notes",
    ])
    for e in events:
        writer.writerow([
            str(e.id),
            str(e.product_id),
            e.product.code if e.product else "",
            e.product.full_name if e.product else "",
            e.product.product_type if e.product else "",
            e.event_type,
            e.recorded_at.isoformat(),
            str(e.recorded_by_user_id) if e.recorded_by_user_id else "",
            e.client_device_id or "",
            str(e.location_id) if e.location_id else "",
            e.location or "",
            e.notes or "",
        ])
    buf.seek(0)
    headers = {"Content-Disposition": "attachment; filename=attendance_export.csv"}
    if truncated:
        headers["X-Export-Truncated"] = "true"
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers=headers,
    )
