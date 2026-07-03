import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import selectinload

from app.deps import AdminOnly, DB
from app.models.attendance_summary import AttendanceSummary
from app.models.product import Product
from app.schemas.attendance_summary import (
    AttendanceSummaryCreate,
    AttendanceSummaryOut,
    AttendanceSummaryOverviewOut,
)
from app.services import audit_log as audit_log_svc
from app.services.summary_generator import generate_monthly_summaries
from app.utils.search import ilike_contains

router = APIRouter(prefix="/attendance-summaries", tags=["attendance-summaries"])


def _summary_to_out(summary: AttendanceSummary) -> AttendanceSummaryOut:
    out = AttendanceSummaryOut.model_validate(summary)
    if summary.product:
        out.product_name = summary.product.full_name
        out.product_code = summary.product.code
    return out


@router.get("", response_model=list[AttendanceSummaryOut])
async def list_attendance_summaries(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    product_id: uuid.UUID | None = None,
    summary_date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    product_type: str | None = None,
    is_complete: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[AttendanceSummaryOut]:
    q = select(AttendanceSummary).options(selectinload(AttendanceSummary.product))
    count_q = select(func.count()).select_from(AttendanceSummary)

    clauses = []
    if product_id:
        clauses.append(AttendanceSummary.product_id == product_id)
    if summary_date:
        clauses.append(AttendanceSummary.summary_date == summary_date)
    if date_from:
        clauses.append(AttendanceSummary.summary_date >= date_from)
    if date_to:
        clauses.append(AttendanceSummary.summary_date <= date_to)
    if is_complete is not None:
        clauses.append(AttendanceSummary.is_complete.is_(is_complete))

    if product_type:
        q = q.join(AttendanceSummary.product).where(Product.product_type == product_type)
        count_q = count_q.join(AttendanceSummary.product).where(Product.product_type == product_type)

    if clauses:
        q = q.where(*clauses)
        count_q = count_q.where(*clauses)

    total = (await db.execute(count_q)).scalar_one()
    q = (
        q.order_by(AttendanceSummary.product_id.asc(), AttendanceSummary.summary_date.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return [_summary_to_out(s) for s in result.scalars().all()]


@router.get("/overview", response_model=list[AttendanceSummaryOverviewOut])
async def list_attendance_summary_overview(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    date_from: date,
    date_to: date,
    product_type: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[AttendanceSummaryOverviewOut]:
    clauses = [
        AttendanceSummary.summary_date >= date_from,
        AttendanceSummary.summary_date <= date_to,
    ]

    q = (
        select(
            Product.id.label("product_id"),
            Product.full_name.label("product_name"),
            Product.code.label("product_code"),
            Product.product_type.label("product_type"),
            func.count(AttendanceSummary.id).label("days_present"),
            func.sum(
                case((AttendanceSummary.is_complete.is_(True), 1), else_=0)
            ).label("days_complete"),
            func.sum(
                case((AttendanceSummary.is_complete.is_(False), 1), else_=0)
            ).label("days_incomplete"),
            func.coalesce(func.sum(AttendanceSummary.regular_hours), 0).label(
                "total_regular_hours"
            ),
            func.coalesce(func.sum(AttendanceSummary.overtime_hours), 0).label(
                "total_overtime_hours"
            ),
            func.coalesce(func.sum(AttendanceSummary.total_break_minutes), 0).label(
                "total_break_minutes"
            ),
            func.min(AttendanceSummary.summary_date).label("first_date"),
            func.max(AttendanceSummary.summary_date).label("last_date"),
        )
        .select_from(AttendanceSummary)
        .join(AttendanceSummary.product)
    )
    count_q = (
        select(func.count(func.distinct(AttendanceSummary.product_id)))
        .select_from(AttendanceSummary)
        .join(AttendanceSummary.product)
    )

    if product_type:
        clauses.append(Product.product_type == product_type)
    if search:
        clauses.append(
            or_(
                ilike_contains(Product.code, search),
                ilike_contains(Product.full_name, search),
                ilike_contains(Product.english_name, search),
            )
        )

    q = (
        q.where(*clauses)
        .group_by(Product.id, Product.full_name, Product.code, Product.product_type)
        .order_by(Product.code.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    count_q = count_q.where(*clauses)

    total = (await db.execute(count_q)).scalar_one()
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)

    return [
        AttendanceSummaryOverviewOut(
            product_id=row.product_id,
            product_name=row.product_name,
            product_code=row.product_code,
            product_type=row.product_type,
            days_present=row.days_present,
            days_complete=row.days_complete or 0,
            days_incomplete=row.days_incomplete or 0,
            total_regular_hours=float(row.total_regular_hours or 0),
            total_overtime_hours=float(row.total_overtime_hours or 0),
            total_break_minutes=int(row.total_break_minutes or 0),
            first_date=row.first_date,
            last_date=row.last_date,
        )
        for row in result.all()
    ]


@router.post("", response_model=AttendanceSummaryOut, status_code=status.HTTP_201_CREATED)
async def create_attendance_summary(
    body: AttendanceSummaryCreate, _admin: AdminOnly, db: DB
) -> AttendanceSummaryOut:
    summary = AttendanceSummary(**body.model_dump())
    db.add(summary)
    await db.commit()
    await db.refresh(summary)
    result = await db.execute(
        select(AttendanceSummary)
        .options(selectinload(AttendanceSummary.product))
        .where(AttendanceSummary.id == summary.id)
    )
    return _summary_to_out(result.scalar_one())


@router.get("/{summary_id}", response_model=AttendanceSummaryOut)
async def get_attendance_summary(
    summary_id: uuid.UUID, _admin: AdminOnly, db: DB
) -> AttendanceSummaryOut:
    result = await db.execute(
        select(AttendanceSummary)
        .options(selectinload(AttendanceSummary.product))
        .where(AttendanceSummary.id == summary_id)
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(status_code=404, detail="Attendance summary not found")
    return _summary_to_out(summary)


@router.post("/generate", status_code=status.HTTP_200_OK)
async def generate_summaries(
    admin: AdminOnly,
    db: DB,
    year: int,
    month: int,
) -> dict:
    """Manually generate attendance summaries for a month.

    Admin selects year/month → system calculates daily summaries
    for every product from attendance_events and inserts/updates rows.
    """
    if not (1 <= month <= 12):
        raise HTTPException(status_code=422, detail="month must be 1-12")

    result = await generate_monthly_summaries(db, year=year, month=month)

    await audit_log_svc.log_audit(
        db,
        user_id=admin.id,
        action="DATA_EXPORT",
        table_name="attendance_summaries",
        description=f"Generated summaries for {year}-{month:02d}: {result['created']} created, {result['updated']} updated",
    )

    return result
