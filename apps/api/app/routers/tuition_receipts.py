import calendar
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.deps import AdminOnly, DB
from app.models.location import Location
from app.models.tuition_invoice import TuitionInvoice, TuitionInvoiceLine, TuitionInvoiceStatus
from app.models.tuition_receipt import TuitionReceipt, TuitionReceiptInvoice, TuitionReceiptStatus
from app.models.unit import Unit
from app.schemas.tuition_invoice import TuitionInvoiceOut
from app.schemas.tuition_receipt import (
    TuitionReceiptAdjustment,
    TuitionReceiptCreate,
    TuitionReceiptLinkedInvoice,
    TuitionReceiptNextNo,
    TuitionReceiptOut,
    TuitionReceiptPrintLine,
)
from app.routers.tuition_invoices import _INVOICE_LOAD, _invoices_to_out
from app.services import audit_log as audit_log_svc

router = APIRouter(prefix="/tuition-receipts", tags=["tuition-receipts"])

_MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "June", "July", "Aug", "Sept", "Oct", "Nov", "Dec"]

_RECEIPT_LOAD = (
    selectinload(TuitionReceipt.unit),
    selectinload(TuitionReceipt.invoices)
    .selectinload(TuitionReceiptInvoice.invoice)
    .selectinload(TuitionInvoice.lines),
    selectinload(TuitionReceipt.invoices)
    .selectinload(TuitionReceiptInvoice.invoice)
    .selectinload(TuitionInvoice.unit),
)


def _money(value: object) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01")))


def _adjustments_out(raw: object) -> list[TuitionReceiptAdjustment]:
    if not raw:
        return []
    return [TuitionReceiptAdjustment.model_validate(row) for row in raw]


def _append_adjustment_lines(
    print_lines: list[TuitionReceiptPrintLine],
    adjustments: list[TuitionReceiptAdjustment],
) -> None:
    for row in adjustments:
        print_lines.append(
            TuitionReceiptPrintLine(
                month=row.month,
                course=row.course,
                fee=float(row.fee) if row.fee is not None else float(row.amount),
                qty=float(row.qty) if row.qty is not None else 1,
                amount=float(row.amount),
            )
        )


def _month_label(invoice: TuitionInvoice, line: TuitionInvoiceLine) -> str:
    if line.month_label:
        return line.month_label
    start = invoice.period_start
    return f"{_MONTH_LABELS[start.month - 1]}-{str(start.year)[2:]}"


def _receipt_no_base(receipt_date: date) -> str:
    return f"R{receipt_date.strftime('%y%m%d')}"


async def _next_receipt_no(db: DB, location_id: uuid.UUID, receipt_date: date) -> str:
    base = _receipt_no_base(receipt_date)
    result = await db.execute(
        select(TuitionReceipt.receipt_no).where(
            TuitionReceipt.location_id == location_id,
            TuitionReceipt.receipt_no.startswith(base),
        )
    )
    existing = set(result.scalars().all())
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


def _receipt_to_out(receipt: TuitionReceipt) -> TuitionReceiptOut:
    linked: list[TuitionReceiptLinkedInvoice] = []
    print_lines: list[TuitionReceiptPrintLine] = []
    for row in receipt.invoices:
        invoice = row.invoice
        linked.append(
            TuitionReceiptLinkedInvoice(
                invoice_id=row.invoice_id,
                invoice_no=invoice.invoice_no if invoice else None,
                amount=float(row.amount),
                invoice_total=float(invoice.total) if invoice else float(row.amount),
                status=invoice.status if invoice else "",
            )
        )
        if not invoice:
            continue
        for line in invoice.lines:
            print_lines.append(
                TuitionReceiptPrintLine(
                    month=_month_label(invoice, line),
                    course=line.name_zh or line.sku_code,
                    fee=float(line.unit_price),
                    qty=float(line.quantity),
                    amount=float(line.amount),
                    invoice_id=invoice.id,
                    invoice_no=invoice.invoice_no,
                )
            )

    adjustments = _adjustments_out(receipt.adjustments)
    _append_adjustment_lines(print_lines, adjustments)

    unit_name = None
    unit_code = None
    if receipt.unit:
        unit_name = receipt.unit.full_name
        unit_code = receipt.unit.code
    elif receipt.payer_name:
        unit_name = receipt.payer_name

    return TuitionReceiptOut(
        id=receipt.id,
        location_id=receipt.location_id,
        unit_id=receipt.unit_id,
        unit_name=unit_name,
        unit_code=unit_code,
        payer_name=receipt.payer_name,
        paid_by=receipt.paid_by,
        receipt_no=receipt.receipt_no,
        receipt_date=receipt.receipt_date,
        amount=float(receipt.amount),
        status=receipt.status,
        description=receipt.description,
        primary_url=receipt.primary_url,
        invoices=linked,
        print_lines=print_lines,
        adjustments=adjustments,
        created_at=receipt.created_at,
        updated_at=receipt.updated_at,
    )


def _integrity_detail(exc: IntegrityError) -> str:
    orig = str(getattr(exc, "orig", exc)).lower()
    if (
        "uq_tuition_receipts_location_receipt_no" in orig
        or "tuition_receipts.receipt_no" in orig
    ):
        return "Receipt number already in use"
    return "One or more invoices are already on a receipt"


async def _get_receipt(db: DB, receipt_id: uuid.UUID, *, for_update: bool = False) -> TuitionReceipt:
    q = select(TuitionReceipt).options(*_RECEIPT_LOAD).where(TuitionReceipt.id == receipt_id)
    if for_update:
        q = q.with_for_update()
    result = await db.execute(q)
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


@router.get("", response_model=list[TuitionReceiptOut])
async def list_tuition_receipts(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    year: int | None = None,
    month: int | None = None,
    location_id: uuid.UUID | None = None,
    unit_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[TuitionReceiptOut]:
    clauses = []
    if year is not None and month is not None:
        if not (1 <= month <= 12):
            raise HTTPException(status_code=422, detail="month must be 1-12")
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        clauses.append(TuitionReceipt.receipt_date >= first_day)
        clauses.append(TuitionReceipt.receipt_date <= last_day)
    if location_id is not None:
        clauses.append(TuitionReceipt.location_id == location_id)
    if unit_id is not None:
        clauses.append(TuitionReceipt.unit_id == unit_id)

    count_q = select(func.count()).select_from(TuitionReceipt)
    q = select(TuitionReceipt).options(*_RECEIPT_LOAD)
    if clauses:
        count_q = count_q.where(*clauses)
        q = q.where(*clauses)
    total = await db.scalar(count_q) or 0
    q = q.order_by(TuitionReceipt.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return [_receipt_to_out(row) for row in result.scalars().unique().all()]


@router.get("/next-no", response_model=TuitionReceiptNextNo)
async def next_receipt_no(
    _admin: AdminOnly,
    db: DB,
    location_id: uuid.UUID,
    date_value: date = Query(alias="date"),
) -> TuitionReceiptNextNo:
    return TuitionReceiptNextNo(next_no=await _next_receipt_no(db, location_id, date_value))


@router.get("/open-invoices", response_model=list[TuitionInvoiceOut])
async def list_open_invoices(
    _admin: AdminOnly,
    db: DB,
    location_id: uuid.UUID,
    unit_id: uuid.UUID | None = None,
    invoice_id: uuid.UUID | None = None,
) -> list[TuitionInvoiceOut]:
    seed: TuitionInvoice | None = None
    if invoice_id is not None:
        result = await db.execute(
            select(TuitionInvoice).options(*_INVOICE_LOAD).where(TuitionInvoice.id == invoice_id)
        )
        seed = result.scalar_one_or_none()
        if not seed:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if seed.status != TuitionInvoiceStatus.issued.value:
            raise HTTPException(status_code=422, detail="Invoice is not issued")
        location_id = seed.location_id
        unit_id = seed.unit_id
        # Walk-in names are not unique — only return the seed invoice.
        if seed.unit_id is None:
            return await _invoices_to_out(db, [seed])

    if unit_id is None and seed is None:
        raise HTTPException(status_code=422, detail="unit_id or invoice_id is required")

    clauses = [
        TuitionInvoice.location_id == location_id,
        TuitionInvoice.status == TuitionInvoiceStatus.issued.value,
        TuitionInvoice.unit_id == unit_id,
    ]

    result = await db.execute(
        select(TuitionInvoice).options(*_INVOICE_LOAD).where(*clauses).order_by(TuitionInvoice.created_at.asc())
    )
    return await _invoices_to_out(db, list(result.scalars().all()))


@router.get("/{receipt_id}", response_model=TuitionReceiptOut)
async def get_tuition_receipt(receipt_id: uuid.UUID, _admin: AdminOnly, db: DB) -> TuitionReceiptOut:
    return _receipt_to_out(await _get_receipt(db, receipt_id))


@router.post("", response_model=TuitionReceiptOut, status_code=status.HTTP_201_CREATED)
async def create_tuition_receipt(
    body: TuitionReceiptCreate,
    admin: AdminOnly,
    db: DB,
) -> TuitionReceiptOut:
    location = await db.get(Location, body.location_id)
    if not location:
        raise HTTPException(status_code=422, detail="location_id does not reference an existing location")

    if body.unit_id is not None:
        unit = await db.get(Unit, body.unit_id)
        if not unit:
            raise HTTPException(status_code=422, detail="unit_id does not reference an existing unit")

    result = await db.execute(
        select(TuitionInvoice)
        .options(*_INVOICE_LOAD)
        .where(TuitionInvoice.id.in_(body.invoice_ids))
        .with_for_update()
    )
    invoices = list(result.scalars().unique().all())
    by_id = {invoice.id: invoice for invoice in invoices}
    if len(by_id) != len(body.invoice_ids):
        raise HTTPException(status_code=422, detail="One or more invoices were not found")
    ordered = [by_id[invoice_id] for invoice_id in body.invoice_ids]

    if any(invoice.location_id != body.location_id for invoice in ordered):
        raise HTTPException(status_code=422, detail="All invoices must belong to the same location")
    if any(invoice.status != TuitionInvoiceStatus.issued.value for invoice in ordered):
        raise HTTPException(status_code=422, detail="Only issued invoices can be paid")

    unit_ids = {invoice.unit_id for invoice in ordered}
    if body.unit_id is not None:
        if unit_ids != {body.unit_id}:
            raise HTTPException(status_code=422, detail="All invoices must belong to the same student")
    else:
        if any(invoice.unit_id is not None for invoice in ordered):
            raise HTTPException(status_code=422, detail="Walk-in receipts cannot include registered students")
        names = {(invoice.manual_student_name or "").strip() for invoice in ordered}
        if len(names) != 1 or not next(iter(names)):
            raise HTTPException(status_code=422, detail="All invoices must belong to the same student")

    payer_name = body.payer_name
    if body.unit_id is not None:
        unit = ordered[0].unit
        payer_name = payer_name or (unit.full_name if unit else None)
    else:
        payer_name = payer_name or (ordered[0].manual_student_name or "").strip()

    invoice_total = _money(sum(float(invoice.total) for invoice in ordered))
    adjustments = list(body.adjustments)
    expected = _money(invoice_total + sum(row.amount for row in adjustments))
    amount = expected if body.amount is None else _money(body.amount)
    if amount != expected:
        raise HTTPException(
            status_code=422,
            detail=f"Amount does not match invoices plus adjustments (expected {expected:.2f})",
        )
    receipt_no = await _next_receipt_no(db, body.location_id, body.receipt_date)
    receipt = TuitionReceipt(
        location_id=body.location_id,
        unit_id=body.unit_id,
        payer_name=payer_name,
        paid_by=body.paid_by,
        receipt_no=receipt_no,
        receipt_date=body.receipt_date,
        amount=amount,
        status=TuitionReceiptStatus.posted.value,
        description=body.description,
        adjustments=[row.model_dump() for row in adjustments],
    )
    db.add(receipt)
    await db.flush()
    for invoice in ordered:
        db.add(
            TuitionReceiptInvoice(
                receipt_id=receipt.id,
                invoice_id=invoice.id,
                amount=invoice.total,
                is_posted=True,
            )
        )
        invoice.status = TuitionInvoiceStatus.paid.value

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=_integrity_detail(exc))

    await audit_log_svc.log_audit(
        db,
        user_id=admin.id,
        action="UPDATE",
        table_name="tuition_receipts",
        record_id=receipt.id,
        description=f"Created receipt {receipt_no} for {len(ordered)} invoice(s)",
    )
    return _receipt_to_out(await _get_receipt(db, receipt.id))


@router.post("/{receipt_id}/void", response_model=TuitionReceiptOut)
async def void_tuition_receipt(
    receipt_id: uuid.UUID,
    admin: AdminOnly,
    db: DB,
) -> TuitionReceiptOut:
    receipt = await _get_receipt(db, receipt_id, for_update=True)
    if receipt.status != TuitionReceiptStatus.posted.value:
        raise HTTPException(status_code=422, detail="Receipt is already void")

    invoice_ids = [row.invoice_id for row in receipt.invoices]
    if invoice_ids:
        await db.execute(
            select(TuitionInvoice).where(TuitionInvoice.id.in_(invoice_ids)).with_for_update()
        )

    receipt.status = TuitionReceiptStatus.void.value
    for row in receipt.invoices:
        row.is_posted = False
        if row.invoice and row.invoice.status == TuitionInvoiceStatus.paid.value:
            row.invoice.status = TuitionInvoiceStatus.issued.value

    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=admin.id,
        action="UPDATE",
        table_name="tuition_receipts",
        record_id=receipt.id,
        description=f"Voided receipt {receipt.receipt_no}",
    )
    return _receipt_to_out(await _get_receipt(db, receipt.id))
