import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.deps import AdminOnly, DB
from app.models.course_enrollment import CourseEnrollment, EnrollmentStatus
from app.models.course_sku import CourseSku
from app.models.unit import Unit, UnitStatus
from app.schemas.course_enrollment import (
    CourseEnrollmentCreate,
    CourseEnrollmentOut,
    CourseEnrollmentUpdate,
    _require_start_on_or_before_end,
)

router = APIRouter(prefix="/course-enrollments", tags=["courses"])


async def _require_enrollable_sku(
    db: DB, sku: CourseSku, *, exclude_enrollment_id: uuid.UUID | None = None
) -> None:
    if not sku.is_active:
        raise HTTPException(status_code=422, detail="Cannot enroll in an inactive class")
    if sku.capacity is None:
        return
    clauses = [
        CourseEnrollment.sku_id == sku.id,
        CourseEnrollment.status == EnrollmentStatus.active.value,
    ]
    if exclude_enrollment_id is not None:
        clauses.append(CourseEnrollment.id != exclude_enrollment_id)
    count = await db.scalar(select(func.count()).select_from(CourseEnrollment).where(*clauses)) or 0
    if count >= sku.capacity:
        raise HTTPException(status_code=422, detail="Class is at capacity")


def _require_enrollable_student(unit: Unit) -> None:
    if unit.unit_type != "student":
        raise HTTPException(status_code=422, detail="Only student units can enroll in courses")
    if not unit.is_active or unit.status != UnitStatus.active.value:
        raise HTTPException(status_code=422, detail="Cannot enroll an inactive or former student")


def _require_purchased_quantity_for_per_session(sku: CourseSku, purchased_quantity: int | None) -> None:
    if sku.billing_unit == "per_session" and purchased_quantity is None:
        raise HTTPException(
            status_code=422, detail="purchased_quantity is required when enrolling in a per_session class"
        )


@router.get("", response_model=list[CourseEnrollmentOut])
async def list_course_enrollments(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    unit_id: uuid.UUID | None = None,
    sku_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[CourseEnrollment]:
    clauses = []
    if unit_id is not None:
        clauses.append(CourseEnrollment.unit_id == unit_id)
    if sku_id is not None:
        clauses.append(CourseEnrollment.sku_id == sku_id)
    if status_filter is not None:
        clauses.append(CourseEnrollment.status == status_filter)

    count_q = select(func.count()).select_from(CourseEnrollment)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(CourseEnrollment)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(CourseEnrollment.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return list(result.scalars().all())


@router.post("", response_model=CourseEnrollmentOut, status_code=status.HTTP_201_CREATED)
async def create_course_enrollment(body: CourseEnrollmentCreate, _admin: AdminOnly, db: DB) -> CourseEnrollment:
    unit_result = await db.execute(select(Unit).where(Unit.id == body.unit_id))
    unit = unit_result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    _require_enrollable_student(unit)

    sku_result = await db.execute(select(CourseSku).where(CourseSku.id == body.sku_id))
    sku = sku_result.scalar_one_or_none()
    if not sku:
        raise HTTPException(status_code=404, detail="Course SKU not found")
    await _require_enrollable_sku(db, sku)
    _require_purchased_quantity_for_per_session(sku, body.purchased_quantity)

    enrollment = CourseEnrollment(**body.model_dump())
    db.add(enrollment)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This student is already enrolled in this course")
    await db.refresh(enrollment)
    return enrollment


@router.get("/{enrollment_id}", response_model=CourseEnrollmentOut)
async def get_course_enrollment(enrollment_id: uuid.UUID, _admin: AdminOnly, db: DB) -> CourseEnrollment:
    result = await db.execute(select(CourseEnrollment).where(CourseEnrollment.id == enrollment_id))
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return enrollment


@router.patch("/{enrollment_id}", response_model=CourseEnrollmentOut)
async def update_course_enrollment(
    enrollment_id: uuid.UUID, body: CourseEnrollmentUpdate, _admin: AdminOnly, db: DB
) -> CourseEnrollment:
    result = await db.execute(select(CourseEnrollment).where(CourseEnrollment.id == enrollment_id))
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    update_data = body.model_dump(exclude_unset=True)
    new_start = update_data["start_date"] if "start_date" in update_data else enrollment.start_date
    new_end = update_data["end_date"] if "end_date" in update_data else enrollment.end_date
    try:
        _require_start_on_or_before_end(new_start, new_end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    new_status = update_data.get("status", enrollment.status)
    if new_status == EnrollmentStatus.active.value and enrollment.status != EnrollmentStatus.active.value:
        unit_result = await db.execute(select(Unit).where(Unit.id == enrollment.unit_id))
        unit = unit_result.scalar_one_or_none()
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")
        _require_enrollable_student(unit)
        sku_result = await db.execute(select(CourseSku).where(CourseSku.id == enrollment.sku_id))
        sku = sku_result.scalar_one_or_none()
        if not sku:
            raise HTTPException(status_code=404, detail="Course SKU not found")
        await _require_enrollable_sku(db, sku, exclude_enrollment_id=enrollment.id)
        new_quantity = update_data.get("purchased_quantity", enrollment.purchased_quantity)
        _require_purchased_quantity_for_per_session(sku, new_quantity)
    for field, value in update_data.items():
        setattr(enrollment, field, value)
    await db.commit()
    await db.refresh(enrollment)
    return enrollment


@router.delete("/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course_enrollment(enrollment_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    result = await db.execute(select(CourseEnrollment).where(CourseEnrollment.id == enrollment_id))
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    await db.delete(enrollment)
    await db.commit()
