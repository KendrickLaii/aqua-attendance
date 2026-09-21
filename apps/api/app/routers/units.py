import uuid

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.deps import DB, AdminOnly
from app.models.attendance import AttendanceEvent
from app.models.course_enrollment import CourseEnrollment
from app.models.payroll_record import PayrollRecord
from app.models.tuition_invoice import TuitionInvoice
from app.models.unit import Unit
from app.models.staff_profile import StaffProfile
from app.models.student_profile import StudentProfile
from app.schemas.unit import UnitCreate, UnitOut, UnitUpdate
from app.services import unit as unit_svc
from app.services import audit_log as audit_svc
from app.utils.search import ilike_contains

router = APIRouter(prefix="/units", tags=["units"])

_VALID_ATTENDANCE_STATUSES = frozenset({"checked_in", "checked_out"})
_VALID_EMPLOYMENT_TYPES = frozenset({"part_time", "full_time"})

_UNIT_LOAD_OPTIONS = (
    selectinload(Unit.registered_location),
    selectinload(Unit.scan_locations),
    selectinload(Unit.student_profile),
    selectinload(Unit.staff_profile),
)


def _unit_filters(
    *,
    unit_type: str | None,
    is_active: bool | None,
    search: str | None,
    attendance_status: str | None,
    employment_type: str | None,
) -> list:
    clauses = []
    if unit_type:
        clauses.append(Unit.unit_type == unit_type)
    if is_active is not None:
        clauses.append(Unit.is_active == is_active)
    if search:
        clauses.append(
            or_(
                ilike_contains(Unit.code, search),
                ilike_contains(Unit.full_name, search),
                ilike_contains(Unit.english_name, search),
            )
        )
    if attendance_status:
        clauses.append(Unit.attendance_status == attendance_status)
    if employment_type:
        clauses.append(StaffProfile.employment_type == employment_type)
    return clauses


@router.get("", response_model=list[UnitOut])
async def list_units(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    unit_type: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    attendance_status: str | None = None,
    employment_type: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[UnitOut]:
    if attendance_status and attendance_status not in _VALID_ATTENDANCE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="attendance_status must be checked_in or checked_out",
        )
    if employment_type and employment_type not in _VALID_EMPLOYMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="employment_type must be part_time or full_time",
        )

    clauses = _unit_filters(
        unit_type=unit_type,
        is_active=is_active,
        search=search,
        attendance_status=attendance_status,
        employment_type=employment_type,
    )

    count_q = select(func.count()).select_from(Unit)
    q = select(Unit).options(*_UNIT_LOAD_OPTIONS)
    if employment_type:
        count_q = count_q.join(StaffProfile, StaffProfile.id == Unit.id)
        q = q.join(StaffProfile, StaffProfile.id == Unit.id)
    if clauses:
        count_q = count_q.where(*clauses)
        q = q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = q.order_by(Unit.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return [UnitOut.from_unit(unit) for unit in result.scalars().all()]


@router.post("", response_model=UnitOut, status_code=status.HTTP_201_CREATED)
async def create_unit(
    body: UnitCreate, admin: AdminOnly, db: DB, request: Request
) -> UnitOut:
    existing = await db.execute(select(Unit).where(Unit.code == body.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Unit code already exists")

    _registered, scan_locs = await unit_svc.resolve_unit_locations(
        db,
        registered_location_id=body.registered_location_id,
        scan_location_ids=body.scan_location_ids,
    )

    unit_data = body.model_dump(
        exclude={"scan_location_ids", "student_profile", "staff_profile"}
    )
    unit = Unit(**unit_data)
    unit.scan_locations = scan_locs
    db.add(unit)
    await db.flush()

    # Create corresponding profile in the same transaction
    if unit.unit_type == "student" and body.student_profile:
        db.add(StudentProfile(id=unit.id, **body.student_profile.model_dump()))
    elif unit.unit_type == "staff" and body.staff_profile:
        db.add(StaffProfile(id=unit.id, **body.staff_profile.model_dump()))

    await db.commit()

    # Audit log — fire-and-forget; separate DB call so it doesn't affect main tx
    await audit_svc.log_audit(
        db,
        user_id=admin.id,
        action="CREATE",
        table_name="units",
        record_id=unit.id,
        new_values=unit_data,
        description=f"Created {unit.unit_type} unit {unit.code}",
        request=request,
    )

    loaded = await unit_svc.load_unit_with_locations(db, unit.id)
    assert loaded is not None
    return UnitOut.from_unit(loaded)


@router.get("/{unit_id}", response_model=UnitOut)
async def get_unit(unit_id: uuid.UUID, _admin: AdminOnly, db: DB) -> UnitOut:
    unit = await unit_svc.load_unit_with_locations(db, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return UnitOut.from_unit(unit)


@router.patch("/{unit_id}", response_model=UnitOut)
async def update_unit(unit_id: uuid.UUID, body: UnitUpdate, _admin: AdminOnly, db: DB) -> UnitOut:
    result = await db.execute(
        select(Unit)
        .options(*_UNIT_LOAD_OPTIONS)
        .where(Unit.id == unit_id)
    )
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    update_data = body.model_dump(exclude_unset=True)
    scan_ids = update_data.pop("scan_location_ids", None)
    registered_location_id = update_data.pop("registered_location_id", None)

    if "code" in update_data:
        dup = await db.execute(
            select(Unit).where(Unit.code == update_data["code"], Unit.id != unit_id)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Unit code already exists")

    if registered_location_id is not None or scan_ids is not None:
        resolved_registered_id = (
            registered_location_id if registered_location_id is not None else unit.registered_location_id
        )
        resolved_scan_ids = (
            scan_ids
            if scan_ids is not None
            else [loc.id for loc in unit.scan_locations]
        )
        _registered, scan_locs = await unit_svc.resolve_unit_locations(
            db,
            registered_location_id=resolved_registered_id,
            scan_location_ids=resolved_scan_ids,
        )
        unit.registered_location_id = resolved_registered_id
        await unit_svc.replace_scan_locations(unit, scan_locs)

    for field, value in update_data.items():
        setattr(unit, field, value)
    await db.commit()

    loaded = await unit_svc.load_unit_with_locations(db, unit_id)
    assert loaded is not None
    return UnitOut.from_unit(loaded)


@router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unit(unit_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    result = await db.execute(select(Unit).where(Unit.id == unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    has_events = await db.execute(
        select(AttendanceEvent.id).where(AttendanceEvent.unit_id == unit_id).limit(1)
    )
    if has_events.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Unit has attendance records. Set it inactive instead of deleting.",
        )

    has_enrollments = await db.execute(
        select(CourseEnrollment.id).where(CourseEnrollment.unit_id == unit_id).limit(1)
    )
    if has_enrollments.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Unit has course enrollments. Set it inactive instead of deleting.",
        )

    has_invoices = await db.execute(
        select(TuitionInvoice.id).where(TuitionInvoice.unit_id == unit_id).limit(1)
    )
    if has_invoices.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Unit has tuition invoices. Set it inactive instead of deleting.",
        )

    has_payroll = await db.execute(
        select(PayrollRecord.id).where(PayrollRecord.unit_id == unit_id).limit(1)
    )
    if has_payroll.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Unit has payroll records. Set it inactive instead of deleting.",
        )

    await db.delete(unit)
    await db.commit()
