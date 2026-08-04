import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select

from app.deps import AdminOnly, DB
from app.models.course_spu import CourseSpu
from app.models.course_sku import CourseSku
from app.schemas.course_spu import CourseSpuCreate, CourseSpuOut, CourseSpuUpdate
from app.utils.search import ilike_contains

router = APIRouter(prefix="/course-spus", tags=["courses"])


@router.get("", response_model=list[CourseSpuOut])
async def list_course_spus(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[CourseSpu]:
    clauses = []
    if is_active is not None:
        clauses.append(CourseSpu.is_active == is_active)
    if search:
        clauses.append(
            or_(
                ilike_contains(CourseSpu.name_zh, search),
                ilike_contains(CourseSpu.name_en, search),
                ilike_contains(CourseSpu.code, search),
                ilike_contains(CourseSpu.subject, search),
            )
        )

    count_q = select(func.count()).select_from(CourseSpu)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(CourseSpu)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(CourseSpu.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return list(result.scalars().all())


@router.post("", response_model=CourseSpuOut, status_code=status.HTTP_201_CREATED)
async def create_course_spu(body: CourseSpuCreate, _admin: AdminOnly, db: DB) -> CourseSpu:
    exists = await db.execute(select(CourseSpu).where(CourseSpu.code == body.code))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Course code already exists")

    spu = CourseSpu(**body.model_dump())
    db.add(spu)
    await db.commit()
    await db.refresh(spu)
    return spu


@router.get("/{spu_id}", response_model=CourseSpuOut)
async def get_course_spu(spu_id: uuid.UUID, _admin: AdminOnly, db: DB) -> CourseSpu:
    result = await db.execute(select(CourseSpu).where(CourseSpu.id == spu_id))
    spu = result.scalar_one_or_none()
    if not spu:
        raise HTTPException(status_code=404, detail="Course not found")
    return spu


@router.patch("/{spu_id}", response_model=CourseSpuOut)
async def update_course_spu(spu_id: uuid.UUID, body: CourseSpuUpdate, _admin: AdminOnly, db: DB) -> CourseSpu:
    result = await db.execute(select(CourseSpu).where(CourseSpu.id == spu_id))
    spu = result.scalar_one_or_none()
    if not spu:
        raise HTTPException(status_code=404, detail="Course not found")

    update_data = body.model_dump(exclude_unset=True)
    new_code = update_data.get("code")
    if new_code:
        exists = await db.execute(select(CourseSpu).where(CourseSpu.code == new_code, CourseSpu.id != spu_id))
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Course code already exists")

    for field, value in update_data.items():
        setattr(spu, field, value)
    await db.commit()
    await db.refresh(spu)
    return spu


@router.delete("/{spu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course_spu(spu_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    result = await db.execute(select(CourseSpu).where(CourseSpu.id == spu_id))
    spu = result.scalar_one_or_none()
    if not spu:
        raise HTTPException(status_code=404, detail="Course not found")

    has_skus = await db.execute(select(CourseSku.id).where(CourseSku.spu_id == spu_id).limit(1))
    if has_skus.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Course has class offerings (SKUs). Set it inactive or remove the SKUs first.",
        )

    await db.delete(spu)
    await db.commit()
