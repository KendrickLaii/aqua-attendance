import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select

from app.deps import DB, OfficeOnly
from app.services.team_access import assigned_team_ids, require_team, team_filter
from app.models.course_spu import CourseSpu
from app.models.course_sku import CourseSku
from app.schemas.course_spu import CourseSpuCreate, CourseSpuOut, CourseSpuUpdate
from app.services import audit_log as audit_log_svc
from app.utils.search import ilike_contains

router = APIRouter(prefix="/course-spus", tags=["courses"])


@router.get("", response_model=list[CourseSpuOut])
async def list_course_spus(
    actor: OfficeOnly,
    db: DB,
    response: Response,
    location_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[CourseSpu]:
    clauses = []
    if location_id is not None:
        await require_team(db, actor, location_id)
        clauses.append(CourseSpu.location_id == location_id)
    else:
        limited = team_filter(CourseSpu.location_id, await assigned_team_ids(db, actor))
        if limited is not None:
            clauses.append(limited)
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
async def create_course_spu(body: CourseSpuCreate, _admin: OfficeOnly, db: DB) -> CourseSpu:
    await require_team(db, _admin, body.location_id)
    exists = await db.execute(
        select(CourseSpu).where(CourseSpu.location_id == body.location_id, CourseSpu.code == body.code)
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Course code already exists")

    spu = CourseSpu(**body.model_dump())
    db.add(spu)
    await db.commit()
    await db.refresh(spu)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="course_spus",
        record_id=spu.id,
        new_values=body.model_dump(),
        description=f"Created course SPU {spu.code or spu.name_en or spu.id}",
    )
    return spu


@router.get("/{spu_id}", response_model=CourseSpuOut)
async def get_course_spu(spu_id: uuid.UUID, _admin: OfficeOnly, db: DB) -> CourseSpu:
    result = await db.execute(select(CourseSpu).where(CourseSpu.id == spu_id))
    spu = result.scalar_one_or_none()
    if not spu:
        raise HTTPException(status_code=404, detail="Course not found")
    await require_team(db, _admin, spu.location_id)
    return spu


@router.patch("/{spu_id}", response_model=CourseSpuOut)
async def update_course_spu(spu_id: uuid.UUID, body: CourseSpuUpdate, _admin: OfficeOnly, db: DB) -> CourseSpu:
    result = await db.execute(select(CourseSpu).where(CourseSpu.id == spu_id))
    spu = result.scalar_one_or_none()
    if not spu:
        raise HTTPException(status_code=404, detail="Course not found")
    await require_team(db, _admin, spu.location_id)

    update_data = body.model_dump(exclude_unset=True)
    if "location_id" in update_data:
        await require_team(db, _admin, update_data["location_id"])
    next_code = update_data.get("code", spu.code)
    next_location = update_data.get("location_id", spu.location_id)
    if "code" in update_data or "location_id" in update_data:
        exists = await db.execute(
            select(CourseSpu).where(
                CourseSpu.code == next_code,
                CourseSpu.location_id == next_location,
                CourseSpu.id != spu_id,
            )
        )
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Course code already exists")

    old_values = {field: getattr(spu, field) for field in update_data}
    for field, value in update_data.items():
        setattr(spu, field, value)
    await db.commit()
    await db.refresh(spu)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="course_spus",
        record_id=spu_id,
        old_values=old_values,
        new_values=update_data,
        description=f"Updated course SPU {spu.code or spu.name_en or spu_id}",
    )
    return spu


@router.delete("/{spu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course_spu(spu_id: uuid.UUID, _admin: OfficeOnly, db: DB) -> None:
    result = await db.execute(select(CourseSpu).where(CourseSpu.id == spu_id))
    spu = result.scalar_one_or_none()
    if not spu:
        raise HTTPException(status_code=404, detail="Course not found")
    await require_team(db, _admin, spu.location_id)

    has_skus = await db.execute(select(CourseSku.id).where(CourseSku.spu_id == spu_id).limit(1))
    if has_skus.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Course has class offerings (SKUs). Set it inactive or remove the SKUs first.",
        )

    await db.delete(spu)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="DELETE",
        table_name="course_spus",
        record_id=spu_id,
        description=f"Deleted course SPU {spu.code or spu.name_en or spu_id}",
    )
