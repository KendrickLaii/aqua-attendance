import csv
import uuid
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.config import settings
from app.deps import DB, AdminOnly
from app.limiter import limiter
from app.models.attendance import AttendanceEvent
from app.models.unit import Unit
from app.schemas.attendance import (
    AttendanceDayStatsOut,
    AttendanceOut,
    ManualCorrectionRequest,
    ScanPreviewOut,
    ScanPreviewRequest,
    ScanRequest,
)
from app.services import attendance as att_svc
from app.services import audit_log as audit_svc
from app.services.attendance_scan import (
    event_to_out,
    reload_with_unit,
    resolve_location,
    resolve_unit_for_scan,
)
from app.services.unit import ensure_attendance_eligible

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/scan/preview", response_model=ScanPreviewOut)
async def scan_preview(body: ScanPreviewRequest, _admin: AdminOnly, db: DB) -> ScanPreviewOut:
    """Resolve QR to unit identity without recording attendance (for confirm UI)."""
    unit, _location_id, location_name, _payload = await resolve_unit_for_scan(
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
    unit, location_id, location_name, payload = await resolve_unit_for_scan(
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

    event = await reload_with_unit(db, event.id)
    return event_to_out(event)


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
    return [event_to_out(e) for e in events]


@router.post("/manual", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
async def create_manual_correction(
    body: ManualCorrectionRequest, admin: AdminOnly, db: DB, request: Request
) -> AttendanceOut:
    result = await db.execute(select(Unit).where(Unit.id == body.unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    ensure_attendance_eligible(unit)
    location_id, location_name = await resolve_location(db, body.location_id, body.location)

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
    event = await reload_with_unit(db, event.id)

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
    return event_to_out(event)


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
        "recorded_by_unit_id",
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
            str(e.recorded_by_unit_id) if e.recorded_by_unit_id else "",
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
    event = await reload_with_unit(db, event.id)

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
    return event_to_out(event)
