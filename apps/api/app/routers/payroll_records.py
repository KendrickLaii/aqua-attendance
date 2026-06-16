import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.deps import AdminOnly, DB, SuperAdminOnly
from app.models.payroll_record import PayrollRecord, PayrollStatus
from app.schemas.payroll_record import PayrollRecordCreate, PayrollRecordOut, PayrollRecordUpdate

router = APIRouter(prefix="/payroll-records", tags=["payroll-records"])


@router.get("", response_model=list[PayrollRecordOut])
async def list_payroll_records(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    product_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[PayrollRecordOut]:
    q = select(PayrollRecord)
    count_q = select(func.count()).select_from(PayrollRecord)

    clauses = []
    if product_id:
        clauses.append(PayrollRecord.product_id == product_id)
    if status:
        clauses.append(PayrollRecord.status == status)

    if clauses:
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
    return list(result.scalars().all())


@router.post("", response_model=PayrollRecordOut, status_code=status.HTTP_201_CREATED)
async def create_payroll_record(
    body: PayrollRecordCreate, _admin: AdminOnly, db: DB
) -> PayrollRecordOut:
    record = PayrollRecord(**body.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return PayrollRecordOut.model_validate(record)


@router.get("/{record_id}", response_model=PayrollRecordOut)
async def get_payroll_record(
    record_id: uuid.UUID, _admin: AdminOnly, db: DB
) -> PayrollRecordOut:
    result = await db.execute(
        select(PayrollRecord).where(PayrollRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Payroll record not found")
    return PayrollRecordOut.model_validate(record)


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
    return PayrollRecordOut.model_validate(record)


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
