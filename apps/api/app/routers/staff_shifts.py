import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from app.auth_cookies import clear_staff_shift_cookie, set_staff_shift_cookie
from app.config import settings
from app.deps import AdminOnly, CurrentStaff, DB
from app.limiter import limiter
from app.models.location import Location
from app.models.shift import Shift, ShiftTemplate
from app.models.shift_request import ShiftRequest, ShiftRequestStatus
from app.models.staff_profile import StaffProfile
from app.models.unit import Unit, UnitStatus
from app.schemas.shift import (
    ShiftRequestCreate,
    ShiftRequestOut,
    ShiftRequestReject,
    ShiftTemplateOut,
    StaffLocationOut,
    StaffShiftLogin,
    StaffShiftLoginOut,
    StaffShiftMe,
    StaffShiftWeek,
)
from app.services import audit_log as audit_log_svc
from app.services.auth import create_staff_shift_token, hash_password, verify_password
from app.services.staff_shifts import assert_request_slot, copy_request_to_shift, mark_reviewed

router = APIRouter(prefix="/staff-shifts", tags=["staff-shifts"])
admin_router = APIRouter(prefix="/shift-requests", tags=["shift-requests"])

MAX_RANGE_DAYS = 62


def _request_out(row: ShiftRequest, unit: Unit | None = None) -> ShiftRequestOut:
    data = ShiftRequestOut.model_validate(row)
    if unit is not None:
        data.unit_code = unit.code
        data.unit_name = unit.full_name
    return data


async def _load_request(db: DB, request_id: uuid.UUID) -> tuple[ShiftRequest, Unit]:
    result = await db.execute(
        select(ShiftRequest, Unit)
        .join(Unit, Unit.id == ShiftRequest.unit_id)
        .where(ShiftRequest.id == request_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Shift request not found")
    return row


@router.post("/login", response_model=StaffShiftLoginOut)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def staff_login(request: Request, response: Response, body: StaffShiftLogin, db: DB) -> StaffShiftLoginOut:
    result = await db.execute(
        select(Unit).where(func.lower(Unit.code) == body.code.strip().lower(), Unit.unit_type == "staff")
    )
    unit = result.scalar_one_or_none()
    profile = await db.get(StaffProfile, unit.id) if unit else None
    if (
        not unit
        or not profile
        or not profile.shift_pin_hash
        or not verify_password(body.pin, profile.shift_pin_hash)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not unit.is_active or unit.status != UnitStatus.active.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    token = create_staff_shift_token(str(unit.id))
    set_staff_shift_cookie(response, token)
    return StaffShiftLoginOut(
        access_token=token,
        unit=StaffShiftMe(id=unit.id, code=unit.code, full_name=unit.full_name),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def staff_logout(response: Response) -> None:
    clear_staff_shift_cookie(response)


@router.get("/me", response_model=StaffShiftMe)
async def staff_me(staff: CurrentStaff) -> StaffShiftMe:
    return StaffShiftMe(id=staff.id, code=staff.code, full_name=staff.full_name)


@router.get("/templates", response_model=list[ShiftTemplateOut])
async def staff_templates(_staff: CurrentStaff, db: DB) -> list[ShiftTemplate]:
    result = await db.execute(
        select(ShiftTemplate).order_by(ShiftTemplate.sort_order, ShiftTemplate.start_time, ShiftTemplate.name)
    )
    return list(result.scalars().all())


@router.get("/locations", response_model=list[StaffLocationOut])
async def staff_locations(staff: CurrentStaff, db: DB) -> list[Location]:
    from app.services.staff_shifts import allowed_location_ids

    ids = await allowed_location_ids(db, staff)
    result = await db.execute(select(Location).where(Location.id.in_(ids)).order_by(Location.name_en))
    return list(result.scalars().all())


@router.get("/week", response_model=StaffShiftWeek)
async def staff_week(
    staff: CurrentStaff,
    db: DB,
    start: date = Query(description="First day (inclusive)"),
    end: date = Query(description="Last day (inclusive)"),
) -> StaffShiftWeek:
    if end < start:
        raise HTTPException(status_code=422, detail="end must be on or after start")
    if (end - start).days >= MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail=f"Date range cannot exceed {MAX_RANGE_DAYS} days")

    shifts = await db.scalars(
        select(Shift)
        .where(Shift.unit_id == staff.id, Shift.shift_date >= start, Shift.shift_date <= end)
        .order_by(Shift.shift_date, Shift.start_time)
    )
    requests = await db.scalars(
        select(ShiftRequest)
        .where(
            ShiftRequest.unit_id == staff.id,
            ShiftRequest.shift_date >= start,
            ShiftRequest.shift_date <= end,
            ShiftRequest.status.in_([ShiftRequestStatus.pending.value, ShiftRequestStatus.rejected.value]),
        )
        .order_by(ShiftRequest.shift_date, ShiftRequest.start_time)
    )
    return StaffShiftWeek(
        shifts=list(shifts.all()),
        requests=[_request_out(row, staff) for row in requests.all()],
    )


@router.post("/requests", response_model=ShiftRequestOut, status_code=status.HTTP_201_CREATED)
async def create_request(body: ShiftRequestCreate, staff: CurrentStaff, db: DB) -> ShiftRequestOut:
    await assert_request_slot(
        db,
        unit=staff,
        location_id=body.location_id,
        shift_date=body.shift_date,
        start_time=body.start_time,
        end_time=body.end_time,
        template_id=body.template_id,
    )
    row = ShiftRequest(unit_id=staff.id, status=ShiftRequestStatus.pending.value, **body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await audit_log_svc.log_audit(
        db,
        user_id=None,
        action="CREATE",
        table_name="shift_requests",
        record_id=row.id,
        new_values=body.model_dump(),
        description=f"Staff {staff.code} ({staff.full_name}) created shift request for {body.shift_date}",
    )
    return _request_out(row, staff)


@router.delete("/requests/{request_id}", response_model=ShiftRequestOut)
async def cancel_request(request_id: uuid.UUID, staff: CurrentStaff, db: DB) -> ShiftRequestOut:
    row, unit = await _load_request(db, request_id)
    if row.unit_id != staff.id:
        raise HTTPException(status_code=404, detail="Shift request not found")
    if row.status != ShiftRequestStatus.pending.value:
        raise HTTPException(status_code=409, detail="Only a pending request can be cancelled")
    row.status = ShiftRequestStatus.cancelled.value
    await db.commit()
    await db.refresh(row)
    await audit_log_svc.log_audit(
        db,
        user_id=None,
        action="UPDATE",
        table_name="shift_requests",
        record_id=request_id,
        old_values={"status": ShiftRequestStatus.pending.value},
        new_values={"status": row.status},
        description=f"Staff {staff.code} ({staff.full_name}) cancelled shift request {request_id}",
    )
    return _request_out(row, unit)


@admin_router.get("", response_model=list[ShiftRequestOut])
async def list_shift_requests(
    _admin: AdminOnly,
    db: DB,
    status_filter: str | None = Query(default=ShiftRequestStatus.pending.value, alias="status"),
) -> list[ShiftRequestOut]:
    if status_filter and status_filter not in {s.value for s in ShiftRequestStatus}:
        raise HTTPException(status_code=422, detail="Unknown request status")
    q = (
        select(ShiftRequest, Unit)
        .join(Unit, Unit.id == ShiftRequest.unit_id)
        .order_by(ShiftRequest.shift_date, ShiftRequest.start_time)
    )
    if status_filter:
        q = q.where(ShiftRequest.status == status_filter)
    result = await db.execute(q)
    return [_request_out(row, unit) for row, unit in result.all()]


@admin_router.post("/{request_id}/approve", response_model=ShiftRequestOut)
async def approve_shift_request(request_id: uuid.UUID, admin: AdminOnly, db: DB) -> ShiftRequestOut:
    row, unit = await _load_request(db, request_id)
    if row.status != ShiftRequestStatus.pending.value:
        raise HTTPException(status_code=409, detail="Only a pending request can be approved")
    try:
        await assert_request_slot(
            db,
            unit=unit,
            location_id=row.location_id,
            shift_date=row.shift_date,
            start_time=row.start_time,
            end_time=row.end_time,
        template_id=row.template_id,
        exclude_request_id=row.id,
    )
    except HTTPException as exc:
        if exc.status_code == 409:
            raise
        raise HTTPException(status_code=409, detail=exc.detail) from exc
    shift = copy_request_to_shift(row, admin_id=admin.id)
    db.add(shift)
    await db.flush()
    row.shift_id = shift.id
    mark_reviewed(row, admin_id=admin.id, status=ShiftRequestStatus.approved.value)
    await db.commit()
    await db.refresh(row)
    await audit_log_svc.log_audit(
        db,
        user_id=admin.id,
        action="UPDATE",
        table_name="shift_requests",
        record_id=request_id,
        old_values={"status": ShiftRequestStatus.pending.value},
        new_values={"status": row.status},
        description=f"Approved shift request {request_id}",
    )
    return _request_out(row, unit)


@admin_router.post("/{request_id}/reject", response_model=ShiftRequestOut)
async def reject_shift_request(
    request_id: uuid.UUID, body: ShiftRequestReject, admin: AdminOnly, db: DB
) -> ShiftRequestOut:
    row, unit = await _load_request(db, request_id)
    if row.status != ShiftRequestStatus.pending.value:
        raise HTTPException(status_code=409, detail="Only a pending request can be rejected")
    reason = body.reason.strip() if body.reason else None
    mark_reviewed(row, admin_id=admin.id, status=ShiftRequestStatus.rejected.value, reason=reason or None)
    await db.commit()
    await db.refresh(row)
    await audit_log_svc.log_audit(
        db,
        user_id=admin.id,
        action="UPDATE",
        table_name="shift_requests",
        record_id=request_id,
        old_values={"status": ShiftRequestStatus.pending.value},
        new_values={"status": row.status, "reason": reason},
        description=f"Rejected shift request {request_id}" + (f": {reason}" if reason else ""),
    )
    return _request_out(row, unit)
