import calendar
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.deps import AdminOnly, DB, SuperAdminOnly
from app.models.payroll_record import PayrollRecord, PayrollStatus
from app.models.product import Product
from app.schemas.payroll_record import PayrollRecordCreate, PayrollRecordOut, PayrollRecordUpdate
from app.services import audit_log as audit_log_svc
from app.services.payroll_generator import generate_monthly_payroll
from app.services.payroll_status import can_transition_payroll_status

router = APIRouter(prefix="/payroll-records", tags=["payroll-records"])


def _record_to_out(record: PayrollRecord) -> PayrollRecordOut:
    out = PayrollRecordOut.model_validate(record)
    if record.product:
        out.product_name = record.product.full_name
        out.product_code = record.product.code
    return out


@router.get("", response_model=list[PayrollRecordOut])
async def list_payroll_records(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    product_id: uuid.UUID | None = None,
    status: str | None = None,
    product_type: str | None = None,
    year: int | None = None,
    month: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[PayrollRecordOut]:
    q = select(PayrollRecord).options(selectinload(PayrollRecord.product))
    count_q = select(func.count()).select_from(PayrollRecord)

    clauses = []
    if product_id:
        clauses.append(PayrollRecord.product_id == product_id)
    if status:
        clauses.append(PayrollRecord.status == status)
    if year and month:
        if not (1 <= month <= 12):
            raise HTTPException(status_code=422, detail="month must be 1-12")
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        clauses.append(PayrollRecord.payroll_period_start >= first_day)
        clauses.append(PayrollRecord.payroll_period_start <= last_day)

    needs_product_join = product_type is not None
    if product_type:
        clauses.append(Product.product_type == product_type)

    if clauses:
        if needs_product_join:
            q = q.join(PayrollRecord.product)
            count_q = count_q.join(PayrollRecord.product)
        q = q.where(*clauses)
        count_q = count_q.where(*clauses)

    total = (await db.execute(count_q)).scalar_one()
    q = (
        q.order_by(PayrollRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return [_record_to_out(r) for r in result.scalars().all()]


@router.post("", response_model=PayrollRecordOut, status_code=status.HTTP_201_CREATED)
async def create_payroll_record(
    body: PayrollRecordCreate, _admin: AdminOnly, db: DB
) -> PayrollRecordOut:
    record = PayrollRecord(**body.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    result = await db.execute(
        select(PayrollRecord)
        .options(selectinload(PayrollRecord.product))
        .where(PayrollRecord.id == record.id)
    )
    return _record_to_out(result.scalar_one())


@router.get("/{record_id}", response_model=PayrollRecordOut)
async def get_payroll_record(
    record_id: uuid.UUID, _admin: AdminOnly, db: DB
) -> PayrollRecordOut:
    result = await db.execute(
        select(PayrollRecord)
        .options(selectinload(PayrollRecord.product))
        .where(PayrollRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Payroll record not found")
    return _record_to_out(record)


@router.patch("/{record_id}", response_model=PayrollRecordOut)
async def update_payroll_record(
    record_id: uuid.UUID, body: PayrollRecordUpdate, admin: AdminOnly, db: DB
) -> PayrollRecordOut:
    result = await db.execute(
        select(PayrollRecord).where(PayrollRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Payroll record not found")

    update_data = body.model_dump(exclude_unset=True)

    if "status" in update_data:
        new_status = update_data["status"]
        if not can_transition_payroll_status(record.status, new_status):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot change payroll status from '{record.status}' to '{new_status}'"
                ),
            )

    # Approval logic: when status changes to approved
    if update_data.get("status") == PayrollStatus.approved.value:
        update_data["approval_date"] = datetime.now(timezone.utc)
        update_data["approved_by_user_id"] = admin.id

    # Payment logic: when status changes to paid
    if update_data.get("status") == PayrollStatus.paid.value:
        update_data["payment_date"] = datetime.now(timezone.utc)

    for field, value in update_data.items():
        setattr(record, field, value)
    await db.commit()
    await db.refresh(record)
    result = await db.execute(
        select(PayrollRecord)
        .options(selectinload(PayrollRecord.product))
        .where(PayrollRecord.id == record.id)
    )
    return _record_to_out(result.scalar_one())


@router.post("/generate", status_code=status.HTTP_200_OK)
async def generate_payroll_records(
    admin: AdminOnly,
    db: DB,
    year: int,
    month: int,
    product_type: str | None = "staff",
    product_ids: list[uuid.UUID] | None = Query(default=None),
) -> dict:
    """Manually generate payroll records for a month from attendance summaries.

    Admin selects year/month (and optionally specific products) → system
    aggregates daily attendance summaries per product and inserts/updates
    payroll records, calculating pay from staff pay-rate fields.
    """
    if not (1 <= month <= 12):
        raise HTTPException(status_code=422, detail="month must be 1-12")

    result = await generate_monthly_payroll(
        db, year=year, month=month, product_type=product_type, product_ids=product_ids
    )

    await audit_log_svc.log_audit(
        db,
        user_id=admin.id,
        action="DATA_EXPORT",
        table_name="payroll_records",
        description=f"Generated payroll records for {year}-{month:02d}: {result['created']} created, {result['updated']} updated, {result['skipped']} skipped",
    )

    return result


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payroll_record(record_id: uuid.UUID, _admin: SuperAdminOnly, db: DB) -> None:
    result = await db.execute(
        select(PayrollRecord).where(PayrollRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Payroll record not found")
    await db.delete(record)
    await db.commit()
