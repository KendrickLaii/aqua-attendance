import calendar
import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.deps import AdminOnly, DB
from app.models.tuition_invoice import TuitionInvoice, TuitionInvoiceStatus
from app.schemas.tuition_invoice import (
    TuitionInvoiceGenerateResult,
    TuitionInvoiceOut,
    TuitionInvoiceUpdate,
)
from app.services import audit_log as audit_log_svc
from app.services.tuition_invoice_generator import generate_monthly_tuition_invoices

router = APIRouter(prefix="/tuition-invoices", tags=["tuition-invoices"])

_ALLOWED_STATUS = {
    TuitionInvoiceStatus.draft.value: {TuitionInvoiceStatus.issued.value, TuitionInvoiceStatus.void.value},
    TuitionInvoiceStatus.issued.value: {TuitionInvoiceStatus.paid.value, TuitionInvoiceStatus.void.value},
    TuitionInvoiceStatus.paid.value: set(),
    TuitionInvoiceStatus.void.value: set(),
}


def _invoice_to_out(invoice: TuitionInvoice) -> TuitionInvoiceOut:
    out = TuitionInvoiceOut.model_validate(invoice)
    if invoice.unit:
        out.unit_name = invoice.unit.full_name
        out.unit_code = invoice.unit.code
    return out


_INVOICE_LOAD = (
    selectinload(TuitionInvoice.unit),
    selectinload(TuitionInvoice.lines),
)


@router.get("", response_model=list[TuitionInvoiceOut])
async def list_tuition_invoices(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    year: int | None = None,
    month: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[TuitionInvoiceOut]:
    clauses = []
    if year is not None and month is not None:
        if not (1 <= month <= 12):
            raise HTTPException(status_code=422, detail="month must be 1-12")
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        clauses.append(TuitionInvoice.period_start == first_day)
        clauses.append(TuitionInvoice.period_end == last_day)
    if status_filter is not None:
        clauses.append(TuitionInvoice.status == status_filter)

    count_q = select(func.count()).select_from(TuitionInvoice)
    q = select(TuitionInvoice).options(*_INVOICE_LOAD)
    if clauses:
        count_q = count_q.where(*clauses)
        q = q.where(*clauses)

    total = await db.scalar(count_q) or 0
    q = q.order_by(TuitionInvoice.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return [_invoice_to_out(invoice) for invoice in result.scalars().all()]


@router.post("/generate", response_model=TuitionInvoiceGenerateResult)
async def generate_tuition_invoices(
    admin: AdminOnly,
    db: DB,
    year: int,
    month: int,
) -> TuitionInvoiceGenerateResult:
    if not (1 <= month <= 12):
        raise HTTPException(status_code=422, detail="month must be 1-12")

    try:
        result = await generate_monthly_tuition_invoices(db, year=year, month=month)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invoice already exists for this student and period",
        )
    await audit_log_svc.log_audit(
        db,
        user_id=admin.id,
        action="DATA_EXPORT",
        table_name="tuition_invoices",
        description=(
            f"Generated tuition invoices for {year}-{month:02d}: "
            f"{result['created']} created, {result['updated']} updated, "
            f"{result['skipped']} skipped, {result['deleted']} deleted"
        ),
    )
    return TuitionInvoiceGenerateResult(**result)


@router.get("/{invoice_id}", response_model=TuitionInvoiceOut)
async def get_tuition_invoice(invoice_id: uuid.UUID, _admin: AdminOnly, db: DB) -> TuitionInvoiceOut:
    result = await db.execute(
        select(TuitionInvoice).options(*_INVOICE_LOAD).where(TuitionInvoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _invoice_to_out(invoice)


@router.patch("/{invoice_id}", response_model=TuitionInvoiceOut)
async def update_tuition_invoice(
    invoice_id: uuid.UUID, body: TuitionInvoiceUpdate, _admin: AdminOnly, db: DB
) -> TuitionInvoiceOut:
    result = await db.execute(
        select(TuitionInvoice).options(*_INVOICE_LOAD).where(TuitionInvoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    update_data = body.model_dump(exclude_unset=True)
    new_status = update_data.get("status")
    if new_status is not None:
        allowed = _ALLOWED_STATUS.get(invoice.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot change invoice status from '{invoice.status}' to '{new_status}'",
            )

    for field, value in update_data.items():
        setattr(invoice, field, value)
    await db.commit()
    await db.refresh(invoice)
    result = await db.execute(
        select(TuitionInvoice).options(*_INVOICE_LOAD).where(TuitionInvoice.id == invoice.id)
    )
    return _invoice_to_out(result.scalar_one())
