import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.deps import AdminOnly, DB
from app.models.course_enrollment import CourseEnrollment
from app.models.course_sku import CourseSku
from app.models.unit import Unit
from app.schemas.course_enrollment import CourseEnrollmentCreate, CourseEnrollmentOut, CourseEnrollmentUpdate

router = APIRouter(prefix="/course-enrollments", tags=["courses"])


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
    if unit.unit_type != "student":
        raise HTTPException(status_code=422, detail="Only student units can enroll in courses")

    sku_result = await db.execute(select(CourseSku.id).where(CourseSku.id == body.sku_id))
    if not sku_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Course SKU not found")

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
