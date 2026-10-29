"""Staff mobile scanner: permitted staff scan other units' QR codes."""

import uuid
from datetime import datetime, time

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from app.attendance_tz import ATTENDANCE_TZ, attendance_today
from app.config import settings
from app.deps import DB, ScannerStaff
from app.limiter import limiter
from app.models.unit import Unit
from app.schemas.attendance import (
    AttendanceOut,
    ScanPreviewOut,
    ScanPreviewRequest,
    ScanRequest,
)
from app.services import attendance as att_svc
from app.services.attendance_scan import (
    event_to_out,
    reload_with_unit,
    resolve_unit_for_scan,
)
from app.services.staff_shifts import allowed_location_ids

router = APIRouter(prefix="/staff-shifts/attendance", tags=["staff-attendance"])


async def _assert_staff_scan_location(db: DB, staff: Unit, location_id: uuid.UUID | None) -> None:
    """The scan location must be one of the staff member's own allowed locations."""
    if location_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="location_id is required for scan",
        )
    if location_id not in await allowed_location_ids(db, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location not allowed for this staff",
        )


@router.post("/scan/preview", response_model=ScanPreviewOut)
async def staff_scan_preview(
    body: ScanPreviewRequest, staff: ScannerStaff, db: DB
) -> ScanPreviewOut:
    """Resolve QR to unit identity without recording attendance (for confirm UI)."""
    await _assert_staff_scan_location(db, staff, body.location_id)
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
async def staff_scan(
    request: Request, body: ScanRequest, staff: ScannerStaff, db: DB
) -> AttendanceOut:
    """Staff scans another unit's QR at one of the staff's allowed locations."""
    await _assert_staff_scan_location(db, staff, body.location_id)
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
        recorded_by_user_id=None,
        recorded_by_unit_id=staff.id,
        device_id=body.device_id,
        location_id=location_id,
        location=location_name,
        event_type=explicit_type,
    )

    event = await reload_with_unit(db, event.id)
    return event_to_out(event)


@router.get("", response_model=list[AttendanceOut])
async def staff_list_attendance(
    staff: ScannerStaff,
    db: DB,
    response: Response,
    event_type: str | None = None,
    include_voided: bool = True,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[AttendanceOut]:
    """List today's events scanned by this staff member (Hong Kong day)."""
    today = attendance_today()
    date_from = datetime.combine(today, time.min, tzinfo=ATTENDANCE_TZ)
    date_to = datetime.combine(today, time.max, tzinfo=ATTENDANCE_TZ)
    events, total = await att_svc.list_events(
        db,
        date_from=date_from,
        date_to=date_to,
        event_type=event_type,
        recorded_by_unit_id=staff.id,
        include_voided=include_voided,
        page=page,
        page_size=page_size,
    )
    response.headers["X-Total-Count"] = str(total)
    return [event_to_out(e) for e in events]
