import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.deps import AdminOnly, DB
from app.models.attendance_summary import AttendanceSummary
from app.schemas.attendance_summary import AttendanceSummaryCreate, AttendanceSummaryOut

router = APIRouter(prefix="/attendance-summaries", tags=["attendance-summaries"])


@router.get("", response_model=list[AttendanceSummaryOut])
async def list_attendance_summaries(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    product_id: uuid.UUID | None = None,
    summary_date: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[AttendanceSummaryOut]:
    q = select(AttendanceSummary)
    count_q = select(func.count()).select_from(AttendanceSummary)

    clauses = []
    if product_id:
        clauses.append(AttendanceSummary.product_id == product_id)
    if summary_date:
        clauses.append(AttendanceSummary.summary_date == summary_date)

    if clauses:
        q = q.where(*clauses)
        count_q = count_q.where(*clauses)

    total = (await db.execute(count_q)).scalar_one()
    q = (
        q.order_by(AttendanceSummary.summary_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return list(result.scalars().all())


@router.post("", response_model=AttendanceSummaryOut, status_code=status.HTTP_201_CREATED)
async def create_attendance_summary(
    body: AttendanceSummaryCreate, _admin: AdminOnly, db: DB
) -> AttendanceSummaryOut:
    summary = AttendanceSummary(**body.model_dump())
    db.add(summary)
    await db.commit()
    await db.refresh(summary)
    return AttendanceSummaryOut.model_validate(summary)


@router.get("/{summary_id}", response_model=AttendanceSummaryOut)
async def get_attendance_summary(
    summary_id: uuid.UUID, _admin: AdminOnly, db: DB
) -> AttendanceSummaryOut:
    result = await db.execute(
        select(AttendanceSummary).where(AttendanceSummary.id == summary_id)
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(status_code=404, detail="Attendance summary not found")
    return AttendanceSummaryOut.model_validate(summary)
