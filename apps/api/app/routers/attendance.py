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
from app.models.unit import Unit
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
from app.services import audit_log as audit_svc
from app.services.qr import verify_qr_token

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _event_to_out(event: AttendanceEvent) -> AttendanceOut:
    return AttendanceOut(
        id=event.id,
        unit_id=event.unit_id,
        unit_code=event.unit.code if event.unit else None,
        unit_name=event.unit.full_name if event.unit else None,
        unit_type=event.unit.unit_type if event.unit else None,
        event_type=event.event_type,
        source=event.source,
        recorded_at=event.recorded_at,
        created_at=event.created_at,
        attendance_status=event.unit.attendance_status if event.unit else None,
        qr_jti=event.qr_jti,
        recorded_by_user_id=event.recorded_by_user_id,
        client_device_id=event.client_device_id,
        location_id=event.location_id,
        location=event.location,
        notes=event.notes,
        voided_at=event.voided_at,
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


async def _reload_with_unit(db: AsyncSession, event_id: uuid.UUID) -> AttendanceEvent:
    result = await db.execute(
        select(AttendanceEvent)
        .options(selectinload(AttendanceEvent.unit))
        .where(AttendanceEvent.id == event_id)
    )
    return result.scalar_one()


def _raise_location_not_allowed(unit: Unit) -> None:
    allowed = [
        ScanAllowedLocation(
            id=loc.id,
            code=loc.code,
            name_zh=loc.name_zh,
            name_en=loc.name_en,
        )
        for loc in unit.scan_locations
    ]
    detail = ScanLocationNotAllowedDetail(
        message="Unit is not allowed to scan at this location",
        unit_name=unit.full_name,
        unit_code=unit.code,
        allowed_locations=allowed,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail.model_dump(mode="json"),
    )


async def _resolve_unit_for_scan(
    db: AsyncSession,
    *,
    qr_token: str,
    location_id: uuid.UUID | None,
    location_text: str | None = None,
) -> tuple[Unit, uuid.UUID, str | None, dict]:
    """Validate QR and location; return unit, location, and JWT payload. Does not record attendance."""
    try:
        payload = verify_qr_token(qr_token)
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid QR: {e}")

    try:
        target_unit_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR: bad subject")

    unit_query = (
        select(Unit)
        .options(selectinload(Unit.scan_locations))
        .where(Unit.id == target_unit_id)
    )
    # PostgreSQL only: row lock prevents concurrent scans of the same unit
    # from creating duplicate attendance events within the debounce window.
    if settings.DATABASE_URL.startswith("postgresql"):
        unit_query = unit_query.with_for_update()
    result = await db.execute(unit_query)
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    if not unit.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unit is inactive")

    if payload.get("ver") != unit.qr_token_version:
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
    if not any(loc.id == resolved_location_id for loc in unit.scan_locations):
        _raise_location_not_allowed(unit)
    return unit, resolved_location_id, location_name, payload


@router.post("/scan/preview", response_model=ScanPreviewOut)
async def scan_preview(body: ScanPreviewRequest, _admin: AdminOnly, db: DB) -> ScanPreviewOut:
    """Resolve QR to unit identity without recording attendance (for confirm UI)."""
    unit, _location_id, location_name, _payload = await _resolve_unit_for_scan(
        db,
        qr_token=body.qr_token,
        location_id=body.location_id,
    )
    return ScanPreviewOut(
        unit_id=unit.id,
        unit_code=unit.code,
        unit_name=unit.full_name,
        unit_type=unit.unit_type,
        attendance_status=unit.attendance_status,
        location=location_name,
    )


@router.post("/scan", response_model=AttendanceOut)
@limiter.limit(settings.SCAN_RATE_LIMIT)
async def scan(request: Request, body: ScanRequest, admin: AdminOnly, db: DB) -> AttendanceOut:
    """Scan a unit's QR.

    Pass ``event_type`` (``check_in`` or ``check_out``) to record that
    action explicitly.  When omitted, the server toggles based on the
    unit's current ``attendance_status``.  Rapid duplicate scans within
    ``SCAN_DEBOUNCE_SECONDS`` return the existing event (no duplicate row).
    """
    unit, location_id, location_name, payload = await _resolve_unit_for_scan(
        db,
        qr_token=body.qr_token,
        location_id=body.location_id,
        location_text=body.location,
    )

    explicit_type = body.event_type.value if body.event_type is not None else None

    event, _created = await att_svc.record_scan(
        db,
        unit=unit,
        jti=payload.get("jti"),
        recorded_by_user_id=admin.id,
        device_id=body.device_id,
        location_id=location_id,
        location=location_name,
        event_type=explicit_type,
    )

    event = await _reload_with_unit(db, event.id)
    return _event_to_out(event)


@router.get("/stats", response_model=AttendanceDayStatsOut)
async def attendance_day_stats(
    _admin: AdminOnly,
    db: DB,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_voided: bool = False,
) -> AttendanceDayStatsOut:
    """Aggregate event counts for a date range (dashboard stats)."""
    stats = await att_svc.event_day_stats(
        db,
        date_from=date_from,
        date_to=date_to,
        include_voided=include_voided,
    )
    return AttendanceDayStatsOut(**stats)


@router.get("", response_model=list[AttendanceOut])
async def list_attendance(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    unit_id: uuid.UUID | None = None,
    unit_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    event_type: str | None = None,
    source: str | None = None,
    include_voided: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[AttendanceOut]:
    """List attendance events (admin or superadmin only)."""
    events, total = await att_svc.list_events(
        db,
        unit_id=unit_id,
        unit_type=unit_type,
        date_from=date_from,
        date_to=date_to,
        event_type=event_type,
        source=source,
        include_voided=include_voided,
        page=page,
        page_size=page_size,
    )
    response.headers["X-Total-Count"] = str(total)
    return [_event_to_out(e) for e in events]


@router.post("/manual", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
async def create_manual_correction(
    body: ManualCorrectionRequest, admin: AdminOnly, db: DB, request: Request
) -> AttendanceOut:
    result = await db.execute(select(Unit).where(Unit.id == body.unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    location_id, location_name = await _resolve_location(db, body.location_id, body.location)

    event = await att_svc.manual_correction(
        db,
        unit=unit,
        event_type=body.event_type.value,
        recorded_at=body.recorded_at,
        location_id=location_id,
        location=location_name,
        notes=body.notes,
        recorded_by_user_id=admin.id,
    )
    event = await _reload_with_unit(db, event.id)

    await audit_svc.log_audit(
        db,
        user_id=admin.id,
        action="MANUAL_CORRECTION",
        table_name="attendance_events",
        record_id=event.id,
        new_values={"event_type": body.event_type.value, "unit_id": str(body.unit_id)},
        description=f"Manual correction for {unit.code}: {body.event_type.value}",
        request=request,
    )
    return _event_to_out(event)


@router.get("/export/csv")
async def export_csv(
    _admin: AdminOnly,
    db: DB,
    unit_id: uuid.UUID | None = None,
    unit_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_voided: bool = False,
) -> StreamingResponse:
    if date_from is None or date_to is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from and date_to are required for CSV export",
        )

    events, truncated = await att_svc.list_events_for_export(
        db,
        unit_id=unit_id,
        unit_type=unit_type,
        date_from=date_from,
        date_to=date_to,
        include_voided=include_voided,
    )
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id",
        "unit_id",
        "unit_code",
        "unit_name",
        "unit_type",
        "event_type",
        "source",
        "recorded_at",
        "created_at",
        "recorded_by_user_id",
        "device_id",
        "location_id",
        "location",
        "notes",
        "voided_at",
    ])
    for e in events:
        writer.writerow([
            str(e.id),
            str(e.unit_id),
            e.unit.code if e.unit else "",
            e.unit.full_name if e.unit else "",
            e.unit.unit_type if e.unit else "",
            e.event_type,
            e.source,
            e.recorded_at.isoformat(),
            e.created_at.isoformat(),
            str(e.recorded_by_user_id) if e.recorded_by_user_id else "",
            e.client_device_id or "",
            str(e.location_id) if e.location_id else "",
            e.location or "",
            e.notes or "",
            e.voided_at.isoformat() if e.voided_at else "",
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


@router.post("/{event_id}/void", response_model=AttendanceOut)
async def void_attendance_event(
    event_id: uuid.UUID, admin: AdminOnly, db: DB, request: Request
) -> AttendanceOut:
    """Void (soft-delete) an attendance event. Sets voided_at timestamp."""
    result = await db.execute(
        select(AttendanceEvent)
        .options(selectinload(AttendanceEvent.unit))
        .where(AttendanceEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Attendance event not found")
    if event.voided_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event is already voided",
        )

    event = await att_svc.void_event(db, event=event)
    event = await _reload_with_unit(db, event.id)

    await audit_svc.log_audit(
        db,
        user_id=admin.id,
        action="UPDATE",
        table_name="attendance_events",
        record_id=event.id,
        new_values={"voided_at": event.voided_at.isoformat() if event.voided_at else None},
        description=f"Voided attendance event {event_id}",
        request=request,
    )
    return _event_to_out(event)
