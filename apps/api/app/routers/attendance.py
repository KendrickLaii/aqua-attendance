import uuid
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import DB, AdminOnly, CurrentUser, StaffOrAdmin
from app.models.attendance import AttendanceEvent, EventType
from app.models.user import Role
from app.schemas.attendance import AttendanceOut, ManualCorrectionRequest, ScanRequest
from app.services import attendance as att_svc
from app.services.qr import verify_qr_token

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _event_to_out(event: AttendanceEvent) -> AttendanceOut:
    return AttendanceOut(
        id=event.id,
        user_id=event.user_id,
        username=event.user.username if event.user else None,
        full_name=event.user.full_name if event.user else None,
        event_type=event.event_type,
        recorded_at=event.recorded_at,
        qr_jti=event.qr_jti,
        scanner_user_id=event.scanner_user_id,
        client_device_id=event.client_device_id,
        notes=event.notes,
    )


async def _reload_with_user(db, event_id: uuid.UUID) -> AttendanceEvent:
    result = await db.execute(
        select(AttendanceEvent)
        .options(selectinload(AttendanceEvent.user))
        .where(AttendanceEvent.id == event_id)
    )
    return result.scalar_one()


@router.post("/scan", response_model=AttendanceOut)
async def scan(body: ScanRequest, scanner: StaffOrAdmin, db: DB) -> AttendanceOut:
    """
    Scanner endpoint: staff/admin scans a student's QR code.
    Idempotent on jti — scanning the same token twice returns the original event.
    """
    try:
        payload = verify_qr_token(body.qr_token)
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid QR: {e}")

    target_user_id = uuid.UUID(payload["sub"])
    jti = payload["jti"]

    event, _created = await att_svc.record_scan(
        db,
        user_id=target_user_id,
        jti=jti,
        scanner_user_id=scanner.id,
        device_id=body.device_id,
    )

    event = await _reload_with_user(db, event.id)
    return _event_to_out(event)


@router.get("", response_model=list[AttendanceOut])
async def list_attendance(
    user: CurrentUser,
    db: DB,
    target_user_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    event_type: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[AttendanceOut]:
    """
    List attendance events.
    - Students can only see their own records.
    - Staff/admin can see all (optionally filtered).
    """
    effective_user_id = target_user_id
    if user.role == Role.student.value:
        effective_user_id = user.id

    events, _total = await att_svc.list_events(
        db,
        user_id=effective_user_id,
        date_from=date_from,
        date_to=date_to,
        event_type=event_type,
        page=page,
        page_size=page_size,
    )
    return [_event_to_out(e) for e in events]


@router.post("/manual", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
async def create_manual_correction(
    body: ManualCorrectionRequest, admin: AdminOnly, db: DB
) -> AttendanceOut:
    event = await att_svc.manual_correction(
        db,
        user_id=body.user_id,
        event_type=body.event_type.value if hasattr(body.event_type, 'value') else body.event_type,
        recorded_at=body.recorded_at,
        notes=body.notes,
        scanner_user_id=admin.id,
    )
    event = await _reload_with_user(db, event.id)
    return _event_to_out(event)


@router.get("/export/csv")
async def export_csv(
    _admin: StaffOrAdmin,
    db: DB,
    target_user_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> StreamingResponse:
    events, _ = await att_svc.list_events(
        db, user_id=target_user_id, date_from=date_from, date_to=date_to, page=1, page_size=10000
    )
    buf = StringIO()
    buf.write("id,user_id,username,full_name,event_type,recorded_at,scanner_user_id,device_id,notes\n")
    for e in events:
        uname = e.user.username if e.user else ""
        fname = e.user.full_name if e.user else ""
        buf.write(
            f"{e.id},{e.user_id},{uname},{fname},{e.event_type},"
            f"{e.recorded_at.isoformat()},{e.scanner_user_id or ''},{e.client_device_id or ''},{e.notes or ''}\n"
        )
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance_export.csv"},
    )
