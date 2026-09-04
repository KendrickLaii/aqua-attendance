import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select

from app.deps import AdminOnly, DB
from app.models.course_enrollment import CourseEnrollment
from app.models.course_sku import CourseSku
from app.models.course_spu import CourseSpu
from app.models.location import Location
from app.schemas.course_sku import CourseSkuCreate, CourseSkuOut, CourseSkuUpdate
from app.utils.search import ilike_contains

router = APIRouter(prefix="/course-skus", tags=["courses"])


async def _assert_spu_exists(db: DB, spu_id: uuid.UUID) -> None:
    result = await db.execute(select(CourseSpu.id).where(CourseSpu.id == spu_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=422, detail="spu_id does not reference an existing course")


async def _assert_location_exists(db: DB, location_id: uuid.UUID | None) -> None:
    if location_id is None:
        return
    result = await db.execute(select(Location.id).where(Location.id == location_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=422, detail="location_id does not reference an existing location")


@router.get("", response_model=list[CourseSkuOut])
async def list_course_skus(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    spu_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[CourseSku]:
    clauses = []
    if spu_id is not None:
        clauses.append(CourseSku.spu_id == spu_id)
    if is_active is not None:
        clauses.append(CourseSku.is_active == is_active)
    if search:
        clauses.append(
            or_(
                ilike_contains(CourseSku.name_zh, search),
                ilike_contains(CourseSku.name_en, search),
                ilike_contains(CourseSku.code, search),
                ilike_contains(CourseSku.level, search),
            )
        )

    count_q = select(func.count()).select_from(CourseSku)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(CourseSku)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(CourseSku.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return list(result.scalars().all())


@router.post("", response_model=CourseSkuOut, status_code=status.HTTP_201_CREATED)
async def create_course_sku(body: CourseSkuCreate, _admin: AdminOnly, db: DB) -> CourseSku:
    await _assert_spu_exists(db, body.spu_id)
    await _assert_location_exists(db, body.location_id)

    exists = await db.execute(select(CourseSku).where(CourseSku.code == body.code))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="SKU code already exists")

    sku = CourseSku(**body.model_dump())
    db.add(sku)
    await db.commit()
    await db.refresh(sku)
    return sku


@router.get("/{sku_id}", response_model=CourseSkuOut)
async def get_course_sku(sku_id: uuid.UUID, _admin: AdminOnly, db: DB) -> CourseSku:
    result = await db.execute(select(CourseSku).where(CourseSku.id == sku_id))
    sku = result.scalar_one_or_none()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    return sku


@router.patch("/{sku_id}", response_model=CourseSkuOut)
async def update_course_sku(sku_id: uuid.UUID, body: CourseSkuUpdate, _admin: AdminOnly, db: DB) -> CourseSku:
    result = await db.execute(select(CourseSku).where(CourseSku.id == sku_id))
    sku = result.scalar_one_or_none()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")

    update_data = body.model_dump(exclude_unset=True)
    if "spu_id" in update_data:
        await _assert_spu_exists(db, update_data["spu_id"])
    if "location_id" in update_data:
        await _assert_location_exists(db, update_data["location_id"])

    new_code = update_data.get("code")
    if new_code:
        exists = await db.execute(select(CourseSku).where(CourseSku.code == new_code, CourseSku.id != sku_id))
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="SKU code already exists")

    for field, value in update_data.items():
        setattr(sku, field, value)
    await db.commit()
    await db.refresh(sku)
    return sku


@router.delete("/{sku_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course_sku(sku_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    result = await db.execute(select(CourseSku).where(CourseSku.id == sku_id))
    sku = result.scalar_one_or_none()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")

    has_enrollments = await db.execute(
        select(CourseEnrollment.id).where(CourseEnrollment.sku_id == sku_id).limit(1)
    )
    if has_enrollments.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="SKU has student enrollments. Set it inactive instead of deleting.",
        )

    await db.delete(sku)
    await db.commit()
