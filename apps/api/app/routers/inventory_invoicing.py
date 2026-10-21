import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select

from app.deps import AdminOnly, DB
from app.models.inventory_invoicing import (
    InventoryCreditNote,
    InventoryCreditNoteLine,
    InventoryInvoice,
    InventoryInvoiceLine,
    InventoryReceipt,
)
from app.models.inventory_sales import (
    Customer,
    DeliveryOrder,
    DeliveryOrderLine,
    SalesOrder,
    SalesOrderLine,
)
from app.models.location import Location
from app.routers.inventory_sales import (
    _do_detail,
    _so_detail,
    confirm_do_tx,
    confirm_so_tx,
    create_do_tx,
)
from app.schemas.inventory_invoicing import (
    InventoryCreditNoteCreate,
    InventoryCreditNoteLineIn,
    InventoryCreditNoteLineOut,
    InventoryCreditNoteOut,
    InventoryCreditNotePrint,
    InventoryInvoiceCreate,
    InventoryInvoiceLineIn,
    InventoryInvoiceLineOut,
    InventoryInvoiceOut,
    InventoryInvoicePrint,
    InventoryInvoiceUpdate,
    InventoryReceiptCreate,
    InventoryReceiptOut,
    InventoryReceiptPrint,
    InventoryCreditNoteUpdate,
    QuickFulfillRequest,
    QuickFulfillResult,
)
from app.services import audit_log as audit_log_svc
from app.services import doc_numbers as doc_numbers_svc
from app.services import inventory as inventory_svc
from app.utils.search import ilike_contains

router = APIRouter(prefix="/inventory", tags=["inventory-invoicing"])


# ---------- helpers ----------


def _to_float(value) -> float:
    return float(value) if value is not None else 0.0


async def _get_invoice_or_404(db: DB, invoice_id: uuid.UUID) -> InventoryInvoice:
    result = await db.execute(
        select(InventoryInvoice).where(InventoryInvoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


async def _get_receipt_or_404(db: DB, receipt_id: uuid.UUID) -> InventoryReceipt:
    result = await db.execute(
        select(InventoryReceipt).where(InventoryReceipt.id == receipt_id)
    )
    rc = result.scalar_one_or_none()
    if rc is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return rc


async def _get_scn_or_404(db: DB, scn_id: uuid.UUID) -> InventoryCreditNote:
    result = await db.execute(
        select(InventoryCreditNote).where(InventoryCreditNote.id == scn_id)
    )
    scn = result.scalar_one_or_none()
    if scn is None:
        raise HTTPException(status_code=404, detail="Credit note not found")
    return scn


async def _get_do_or_404(db: DB, do_id: uuid.UUID) -> DeliveryOrder:
    result = await db.execute(select(DeliveryOrder).where(DeliveryOrder.id == do_id))
    do = result.scalar_one_or_none()
    if do is None:
        raise HTTPException(status_code=404, detail="Delivery order not found")
    return do


async def _inv_lines(db: DB, invoice_id: uuid.UUID) -> list[InventoryInvoiceLine]:
    result = await db.execute(
        select(InventoryInvoiceLine)
        .where(InventoryInvoiceLine.invoice_id == invoice_id)
        .order_by(InventoryInvoiceLine.id)
    )
    return list(result.scalars().all())


async def _scn_lines(db: DB, scn_id: uuid.UUID) -> list[InventoryCreditNoteLine]:
    result = await db.execute(
        select(InventoryCreditNoteLine).where(InventoryCreditNoteLine.scn_id == scn_id)
    )
    return list(result.scalars().all())


async def _paid_total(db: DB, invoice_id: uuid.UUID) -> float:
    result = await db.execute(
        select(func.coalesce(func.sum(InventoryReceipt.amount), 0)).where(
            InventoryReceipt.invoice_id == invoice_id,
            InventoryReceipt.status == "posted",
        )
    )
    return _to_float(result.scalar_one())


async def _credited_total(db: DB, invoice_id: uuid.UUID) -> float:
    result = await db.execute(
        select(func.coalesce(func.sum(InventoryCreditNote.total), 0)).where(
            InventoryCreditNote.invoice_id == invoice_id,
            InventoryCreditNote.status == "confirmed",
        )
    )
    return _to_float(result.scalar_one())


def _payment_status(inv: InventoryInvoice, paid: float, credited: float) -> str:
    if inv.status == "void":
        return "void"
    total = _to_float(inv.total)
    if total > 0 and paid + credited >= total:
        return "paid"
    if paid + credited > 0:
        return "partial"
    return "unpaid"


async def _invoiced_qty_for_do_line(db: DB, do_line_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(InventoryInvoiceLine.qty), 0))
        .select_from(InventoryInvoiceLine)
        .join(InventoryInvoice, InventoryInvoice.id == InventoryInvoiceLine.invoice_id)
        .where(
            InventoryInvoiceLine.do_line_id == do_line_id,
            InventoryInvoice.status != "void",
        )
    )
    return int(result.scalar_one() or 0)


async def _invoice_receipt_summaries(db: DB, invoice_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(InventoryReceipt)
        .where(InventoryReceipt.invoice_id == invoice_id)
        .order_by(InventoryReceipt.receipt_date, InventoryReceipt.receipt_no)
    )
    return [
        {
            "id": r.id,
            "receipt_no": r.receipt_no,
            "amount": _to_float(r.amount),
            "paid_by": r.paid_by,
            "receipt_date": r.receipt_date,
            "status": r.status,
        }
        for r in result.scalars().all()
    ]


async def _invoice_scn_summaries(db: DB, invoice_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(InventoryCreditNote)
        .where(InventoryCreditNote.invoice_id == invoice_id)
        .order_by(InventoryCreditNote.credit_date, InventoryCreditNote.scn_no)
    )
    return [
        {
            "id": s.id,
            "scn_no": s.scn_no,
            "total": _to_float(s.total),
            "credit_date": s.credit_date,
            "status": s.status,
        }
        for s in result.scalars().all()
    ]


async def _inv_detail(db: DB, inv: InventoryInvoice) -> dict:
    lines = await _inv_lines(db, inv.id)
    do = await _get_do_or_404(db, inv.do_id)
    so_result = await db.execute(select(SalesOrder).where(SalesOrder.id == inv.so_id))
    so = so_result.scalar_one()
    cust_result = await db.execute(select(Customer).where(Customer.id == inv.customer_id))
    customer = cust_result.scalar_one()
    paid = await _paid_total(db, inv.id)
    credited = await _credited_total(db, inv.id)
    total = _to_float(inv.total)
    subtotal = _to_float(sum(_to_float(line.amount) for line in lines))
    return {
        "id": inv.id,
        "invoice_no": inv.invoice_no,
        "do_id": inv.do_id,
        "do_no": do.do_no,
        "so_id": inv.so_id,
        "so_no": so.so_no,
        "customer_id": inv.customer_id,
        "customer_name": customer.name_zh or customer.name_en,
        "buyer_name": inv.buyer_name,
        "location_id": inv.location_id,
        "issue_date": inv.issue_date,
        "status": inv.status,
        "discount_amount": _to_float(inv.discount_amount),
        "subtotal": subtotal,
        "total": total,
        "paid_total": paid,
        "credited_total": credited,
        "balance": max(total - paid - credited, 0.0),
        "payment_status": _payment_status(inv, paid, credited),
        "notes": inv.notes,
        "issued_at": inv.issued_at,
        "created_by": inv.created_by,
        "created_at": inv.created_at,
        "updated_at": inv.updated_at,
        "lines": [InventoryInvoiceLineOut.model_validate(line).model_dump() for line in lines],
        "receipts": await _invoice_receipt_summaries(db, inv.id),
        "credit_notes": await _invoice_scn_summaries(db, inv.id),
    }


async def _rc_out(db: DB, rc: InventoryReceipt) -> dict:
    inv = await _get_invoice_or_404(db, rc.invoice_id)
    cust_result = await db.execute(select(Customer).where(Customer.id == rc.customer_id))
    customer = cust_result.scalar_one()
    return {
        "id": rc.id,
        "receipt_no": rc.receipt_no,
        "invoice_id": rc.invoice_id,
        "invoice_no": inv.invoice_no,
        "customer_id": rc.customer_id,
        "customer_name": customer.name_zh or customer.name_en,
        "location_id": rc.location_id,
        "amount": _to_float(rc.amount),
        "paid_by": rc.paid_by,
        "reference_no": rc.reference_no,
        "receipt_date": rc.receipt_date,
        "status": rc.status,
        "notes": rc.notes,
        "created_by": rc.created_by,
        "created_at": rc.created_at,
        "updated_at": rc.updated_at,
    }


async def _scn_out(db: DB, scn: InventoryCreditNote) -> dict:
    lines = await _scn_lines(db, scn.id)
    inv = await _get_invoice_or_404(db, scn.invoice_id)
    cust_result = await db.execute(select(Customer).where(Customer.id == scn.customer_id))
    customer = cust_result.scalar_one()
    line_outs = []
    for line in lines:
        inv_line_result = await db.execute(
            select(InventoryInvoiceLine).where(InventoryInvoiceLine.id == line.invoice_line_id)
        )
        inv_line = inv_line_result.scalar_one_or_none()
        out = InventoryCreditNoteLineOut.model_validate(line).model_dump()
        out["sku_code"] = inv_line.sku_code if inv_line else None
        out["name_zh"] = inv_line.name_zh if inv_line else None
        line_outs.append(out)
    return {
        "id": scn.id,
        "scn_no": scn.scn_no,
        "invoice_id": scn.invoice_id,
        "invoice_no": inv.invoice_no,
        "customer_id": scn.customer_id,
        "customer_name": customer.name_zh or customer.name_en,
        "location_id": scn.location_id,
        "credit_date": scn.credit_date,
        "reason": scn.reason,
        "status": scn.status,
        "total": _to_float(scn.total),
        "created_by": scn.created_by,
        "created_at": scn.created_at,
        "updated_at": scn.updated_at,
        "lines": line_outs,
    }


async def _invoice_balance(db: DB, inv: InventoryInvoice) -> float:
    paid = await _paid_total(db, inv.id)
    credited = await _credited_total(db, inv.id)
    return max(_to_float(inv.total) - paid - credited, 0.0)


# ---------- invoices ----------


@router.get("/invoices", response_model=list[InventoryInvoiceOut])
async def list_invoices(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    customer_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    payment_status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
) -> list[dict]:
    paid_sq = (
        select(
            InventoryReceipt.invoice_id.label("invoice_id"),
            func.coalesce(func.sum(InventoryReceipt.amount), 0).label("paid"),
        )
        .where(InventoryReceipt.status == "posted")
        .group_by(InventoryReceipt.invoice_id)
        .subquery()
    )
    cred_sq = (
        select(
            InventoryCreditNote.invoice_id.label("invoice_id"),
            func.coalesce(func.sum(InventoryCreditNote.total), 0).label("credited"),
        )
        .where(InventoryCreditNote.status == "confirmed")
        .group_by(InventoryCreditNote.invoice_id)
        .subquery()
    )
    paid_col = func.coalesce(paid_sq.c.paid, 0)
    cred_col = func.coalesce(cred_sq.c.credited, 0)

    q = (
        select(InventoryInvoice)
        .outerjoin(paid_sq, paid_sq.c.invoice_id == InventoryInvoice.id)
        .outerjoin(cred_sq, cred_sq.c.invoice_id == InventoryInvoice.id)
    )
    count_q = (
        select(func.count())
        .select_from(InventoryInvoice)
        .outerjoin(paid_sq, paid_sq.c.invoice_id == InventoryInvoice.id)
        .outerjoin(cred_sq, cred_sq.c.invoice_id == InventoryInvoice.id)
    )
    if customer_id:
        q = q.where(InventoryInvoice.customer_id == customer_id)
        count_q = count_q.where(InventoryInvoice.customer_id == customer_id)
    if location_id:
        q = q.where(InventoryInvoice.location_id == location_id)
        count_q = count_q.where(InventoryInvoice.location_id == location_id)
    if status_filter:
        q = q.where(InventoryInvoice.status == status_filter)
        count_q = count_q.where(InventoryInvoice.status == status_filter)
    if date_from:
        q = q.where(InventoryInvoice.issue_date >= date_from)
        count_q = count_q.where(InventoryInvoice.issue_date >= date_from)
    if date_to:
        q = q.where(InventoryInvoice.issue_date <= date_to)
        count_q = count_q.where(InventoryInvoice.issue_date <= date_to)
    if search:
        cond = or_(
            ilike_contains(InventoryInvoice.invoice_no, search),
            ilike_contains(InventoryInvoice.buyer_name, search),
        )
        q = q.where(cond)
        count_q = count_q.where(cond)
    if payment_status:
        issued = InventoryInvoice.status == "issued"
        if payment_status == "void":
            cond = InventoryInvoice.status == "void"
        elif payment_status == "paid":
            cond = issued & (InventoryInvoice.total > 0) & (paid_col + cred_col >= InventoryInvoice.total)
        elif payment_status == "partial":
            cond = issued & (paid_col + cred_col > 0) & (paid_col + cred_col < InventoryInvoice.total)
        else:  # unpaid
            cond = issued & (paid_col + cred_col == 0)
        q = q.where(cond)
        count_q = count_q.where(cond)

    total = (await db.execute(count_q)).scalar_one()
    response.headers["X-Total-Count"] = str(total)
    q = q.order_by(InventoryInvoice.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()
    return [await _inv_detail(db, inv) for inv in rows]


async def _build_invoice_lines(
    db: DB,
    do: DeliveryOrder,
    so: SalesOrder,
    line_inputs: list[InventoryInvoiceLineIn],
) -> list[dict]:
    """Validate inputs against the DO and return frozen line dicts."""
    do_lines = (
        await db.execute(select(DeliveryOrderLine).where(DeliveryOrderLine.do_id == do.id))
    ).scalars().all()
    do_line_by_id = {line.id: line for line in do_lines}
    so_lines = (
        await db.execute(select(SalesOrderLine).where(SalesOrderLine.so_id == so.id))
    ).scalars().all()
    so_line_by_id = {line.id: line for line in so_lines}

    seen: set[uuid.UUID] = set()
    built: list[dict] = []
    for inp in line_inputs:
        if inp.do_line_id in seen:
            raise HTTPException(status_code=422, detail="duplicate do_line_id in invoice lines")
        seen.add(inp.do_line_id)
        do_line = do_line_by_id.get(inp.do_line_id)
        if do_line is None:
            raise HTTPException(status_code=422, detail=f"do_line_id {inp.do_line_id} not on this DO")
        so_line = so_line_by_id.get(do_line.so_line_id)
        if so_line is None:
            raise HTTPException(status_code=422, detail="DO line references a removed SO line")
        already = await _invoiced_qty_for_do_line(db, do_line.id)
        if already + inp.qty > do_line.qty:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"over-invoicing DO line {so_line.sku_code}: delivered {do_line.qty}, "
                    f"already invoiced {already}, this invoice {inp.qty}"
                ),
            )
        unit_price = _to_float(so_line.unit_price) if inp.unit_price is None else inp.unit_price
        if inp.unit_price is None and inp.discount_amount == 0:
            discount = round(_to_float(so_line.discount_amount) * inp.qty / so_line.qty, 2)
        else:
            discount = inp.discount_amount
        amount = max(round(inp.qty * unit_price - discount, 2), 0.0)
        built.append(
            {
                "do_line_id": do_line.id,
                "so_line_id": so_line.id,
                "item_id": do_line.item_id,
                "sku_code": so_line.sku_code,
                "name_zh": so_line.name_zh,
                "unit_price": unit_price,
                "qty": inp.qty,
                "discount_amount": discount,
                "amount": amount,
            }
        )
    return built


async def _create_invoice_tx(
    db: DB,
    do: DeliveryOrder,
    *,
    issue_date: date | None,
    discount_amount: float | None,
    notes: str | None,
    line_inputs: list[InventoryInvoiceLineIn],
    user,
) -> InventoryInvoice:
    if do.status != "confirmed":
        raise HTTPException(status_code=422, detail=f"delivery order is {do.status}; cannot invoice")

    so_result = await db.execute(select(SalesOrder).where(SalesOrder.id == do.so_id))
    so = so_result.scalar_one()

    if not line_inputs:
        do_lines = (
            await db.execute(
                select(DeliveryOrderLine).where(DeliveryOrderLine.do_id == do.id)
            )
        ).scalars().all()
        line_inputs = []
        for do_line in do_lines:
            remaining = do_line.qty - await _invoiced_qty_for_do_line(db, do_line.id)
            if remaining > 0:
                line_inputs.append(InventoryInvoiceLineIn(do_line_id=do_line.id, qty=remaining))
        if not line_inputs:
            raise HTTPException(status_code=422, detail="DO is fully invoiced")

    built = await _build_invoice_lines(db, do, so, line_inputs)
    if not built:
        raise HTTPException(status_code=422, detail="invoice has no lines")

    subtotal = round(sum(line["amount"] for line in built), 2)
    if discount_amount is not None:
        header_discount = discount_amount
    else:
        so_subtotal = _to_float(so.total) + _to_float(so.discount_amount)
        header_discount = (
            round(_to_float(so.discount_amount) * subtotal / so_subtotal, 2)
            if so_subtotal > 0
            else 0.0
        )
    total = max(round(subtotal - header_discount, 2), 0.0)

    inv = InventoryInvoice(
        do_id=do.id,
        so_id=so.id,
        customer_id=do.customer_id,
        buyer_name=so.buyer_name,
        location_id=do.location_id,
        issue_date=issue_date,
        discount_amount=header_discount,
        total=total,
        notes=notes,
        created_by=user.id,
    )
    db.add(inv)
    for line in built:
        db.add(InventoryInvoiceLine(invoice=inv, **line))
    await db.flush()
    return inv


async def _issue_invoice_tx(
    db: DB, inv: InventoryInvoice, issue_date: date | None = None
) -> None:
    """Allocate the invoice number and mark issued. Caller commits."""
    lines = await _inv_lines(db, inv.id)
    if not lines:
        raise HTTPException(status_code=422, detail="invoice has no lines")
    for line in lines:
        do_line_result = await db.execute(
            select(DeliveryOrderLine).where(DeliveryOrderLine.id == line.do_line_id)
        )
        do_line = do_line_result.scalar_one()
        already = await _invoiced_qty_for_do_line(db, line.do_line_id)
        # 'already' includes this invoice's own qty
        if already > do_line.qty:
            raise HTTPException(
                status_code=422,
                detail=f"over-invoicing DO line {line.sku_code}: delivered {do_line.qty}, invoiced {already}",
            )
    if not inv.invoice_no:
        inv.invoice_no = await doc_numbers_svc.allocate_doc_no(
            db, location_id=inv.location_id, doc_type="SI"
        )
    inv.status = "issued"
    inv.issue_date = issue_date or inv.issue_date or date.today()
    inv.issued_at = datetime.now(timezone.utc)
    await db.flush()


@router.post("/invoices", response_model=InventoryInvoiceOut, status_code=status.HTTP_201_CREATED)
async def create_invoice(body: InventoryInvoiceCreate, _admin: AdminOnly, db: DB) -> dict:
    do = await _get_do_or_404(db, body.do_id)
    inv = await _create_invoice_tx(
        db,
        do,
        issue_date=body.issue_date,
        discount_amount=body.discount_amount,
        notes=body.notes,
        line_inputs=list(body.lines),
        user=_admin,
    )
    inv_id = inv.id
    await db.commit()
    result = await db.execute(select(InventoryInvoice).where(InventoryInvoice.id == inv_id))
    inv = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="inventory_invoices",
        record_id=inv_id,
        new_values={"do_id": str(body.do_id), "total": _to_float(inv.total)},
        description=f"Created draft invoice for DO {do.do_no}",
    )
    return await _inv_detail(db, inv)


@router.get("/invoices/{invoice_id}", response_model=InventoryInvoiceOut)
async def get_invoice(invoice_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    return await _inv_detail(db, await _get_invoice_or_404(db, invoice_id))


@router.patch("/invoices/{invoice_id}", response_model=InventoryInvoiceOut)
async def update_invoice(
    invoice_id: uuid.UUID, body: InventoryInvoiceUpdate, _admin: AdminOnly, db: DB
) -> dict:
    inv = await _get_invoice_or_404(db, invoice_id)
    if inv.status != "draft":
        raise HTTPException(status_code=409, detail=f"invoice is {inv.status}; only drafts can be edited")

    if body.issue_date is not None:
        inv.issue_date = body.issue_date
    if body.notes is not None:
        inv.notes = body.notes

    if body.lines is not None:
        do = await _get_do_or_404(db, inv.do_id)
        so_result = await db.execute(select(SalesOrder).where(SalesOrder.id == inv.so_id))
        so = so_result.scalar_one()
        old_lines = await _inv_lines(db, inv.id)
        for line in old_lines:
            await db.delete(line)
        await db.flush()
        built = await _build_invoice_lines(db, do, so, list(body.lines))
        if not built:
            raise HTTPException(status_code=422, detail="invoice must have at least one line")
        for line in built:
            db.add(InventoryInvoiceLine(invoice=inv, **line))
        await db.flush()
        subtotal = round(sum(line["amount"] for line in built), 2)
    else:
        subtotal = round(
            sum(_to_float(line.amount) for line in await _inv_lines(db, inv.id)), 2
        )

    if body.discount_amount is not None:
        inv.discount_amount = body.discount_amount
    inv.total = max(round(subtotal - _to_float(inv.discount_amount), 2), 0.0)
    await db.commit()
    result = await db.execute(select(InventoryInvoice).where(InventoryInvoice.id == invoice_id))
    inv = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_invoices",
        record_id=invoice_id,
        new_values={"total": inv.total},
        description="Updated draft invoice",
    )
    return await _inv_detail(db, inv)


@router.delete("/invoices/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(invoice_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    inv = await _get_invoice_or_404(db, invoice_id)
    if inv.status != "draft":
        raise HTTPException(status_code=409, detail=f"invoice is {inv.status}; only drafts can be deleted")
    await db.delete(inv)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="DELETE",
        table_name="inventory_invoices",
        record_id=invoice_id,
        description="Deleted draft invoice",
    )


@router.post("/invoices/{invoice_id}/issue", response_model=InventoryInvoiceOut)
async def issue_invoice(invoice_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    inv = await _get_invoice_or_404(db, invoice_id)
    if inv.status == "issued":
        return await _inv_detail(db, inv)
    if inv.status != "draft":
        raise HTTPException(status_code=409, detail=f"invoice is {inv.status}; cannot issue")
    await _issue_invoice_tx(db, inv)
    invoice_no = inv.invoice_no
    await db.commit()
    result = await db.execute(select(InventoryInvoice).where(InventoryInvoice.id == invoice_id))
    inv = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_invoices",
        record_id=invoice_id,
        old_values={"status": "draft"},
        new_values={"status": "issued", "invoice_no": invoice_no},
        description=f"Issued invoice {invoice_no}",
    )
    return await _inv_detail(db, inv)


@router.post("/invoices/{invoice_id}/void", response_model=InventoryInvoiceOut)
async def void_invoice(invoice_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    inv = await _get_invoice_or_404(db, invoice_id)
    if inv.status == "void":
        return await _inv_detail(db, inv)
    if inv.status != "issued":
        raise HTTPException(
            status_code=409, detail=f"invoice is {inv.status}; only issued invoices can be voided"
        )
    posted = (
        await db.execute(
            select(func.count())
            .select_from(InventoryReceipt)
            .where(
                InventoryReceipt.invoice_id == inv.id,
                InventoryReceipt.status == "posted",
            )
        )
    ).scalar_one()
    if posted:
        raise HTTPException(status_code=409, detail="invoice has posted receipts; void them first")
    confirmed_scn = (
        await db.execute(
            select(func.count())
            .select_from(InventoryCreditNote)
            .where(
                InventoryCreditNote.invoice_id == inv.id,
                InventoryCreditNote.status == "confirmed",
            )
        )
    ).scalar_one()
    if confirmed_scn:
        raise HTTPException(status_code=409, detail="invoice has confirmed credit notes; void them first")
    inv.status = "void"
    await db.commit()
    result = await db.execute(select(InventoryInvoice).where(InventoryInvoice.id == invoice_id))
    inv = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_invoices",
        record_id=invoice_id,
        old_values={"status": "issued"},
        new_values={"status": "void"},
        description=f"Voided invoice {inv.invoice_no}",
    )
    return await _inv_detail(db, inv)


@router.get("/invoices/{invoice_id}/print", response_model=InventoryInvoicePrint)
async def print_invoice(invoice_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    inv = await _get_invoice_or_404(db, invoice_id)
    detail = await _inv_detail(db, inv)
    cust_result = await db.execute(select(Customer).where(Customer.id == inv.customer_id))
    customer = cust_result.scalar_one()
    loc_result = await db.execute(select(Location).where(Location.id == inv.location_id))
    loc = loc_result.scalar_one()
    return {
        "invoice_no": inv.invoice_no,
        "issue_date": inv.issue_date,
        "issued_at": inv.issued_at,
        "buyer_name": inv.buyer_name,
        "customer_code": customer.code,
        "customer_name_zh": customer.name_zh,
        "customer_name_en": customer.name_en,
        "customer_contact": customer.contact_name,
        "customer_phone": customer.phone,
        "customer_email": customer.email,
        "customer_address": customer.address,
        "location_name_zh": loc.name_zh,
        "location_name_en": loc.name_en,
        "location_address": loc.address,
        "location_phone": loc.phone,
        "so_no": detail["so_no"],
        "do_no": detail["do_no"],
        "lines": detail["lines"],
        "discount_amount": detail["discount_amount"],
        "subtotal": detail["subtotal"],
        "total": detail["total"],
        "paid_total": detail["paid_total"],
        "credited_total": detail["credited_total"],
        "balance": detail["balance"],
        "payment_status": detail["payment_status"],
        "notes": inv.notes,
    }


# ---------- receipts ----------


@router.get("/receipts", response_model=list[InventoryReceiptOut])
async def list_receipts(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    invoice_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
) -> list[dict]:
    q = select(InventoryReceipt)
    count_q = select(func.count()).select_from(InventoryReceipt)
    if invoice_id:
        q = q.where(InventoryReceipt.invoice_id == invoice_id)
        count_q = count_q.where(InventoryReceipt.invoice_id == invoice_id)
    if customer_id:
        q = q.where(InventoryReceipt.customer_id == customer_id)
        count_q = count_q.where(InventoryReceipt.customer_id == customer_id)
    if location_id:
        q = q.where(InventoryReceipt.location_id == location_id)
        count_q = count_q.where(InventoryReceipt.location_id == location_id)
    if status_filter:
        q = q.where(InventoryReceipt.status == status_filter)
        count_q = count_q.where(InventoryReceipt.status == status_filter)
    if date_from:
        q = q.where(InventoryReceipt.receipt_date >= date_from)
        count_q = count_q.where(InventoryReceipt.receipt_date >= date_from)
    if date_to:
        q = q.where(InventoryReceipt.receipt_date <= date_to)
        count_q = count_q.where(InventoryReceipt.receipt_date <= date_to)
    if search:
        q = q.where(ilike_contains(InventoryReceipt.receipt_no, search))
        count_q = count_q.where(ilike_contains(InventoryReceipt.receipt_no, search))
    total = (await db.execute(count_q)).scalar_one()
    response.headers["X-Total-Count"] = str(total)
    q = q.order_by(InventoryReceipt.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()
    return [await _rc_out(db, rc) for rc in rows]


async def _create_receipt_tx(
    db: DB,
    invoice_id: uuid.UUID,
    *,
    amount: float,
    paid_by: str,
    reference_no: str | None,
    receipt_date: date | None,
    notes: str | None,
    user,
) -> InventoryReceipt:
    inv_result = await db.execute(
        select(InventoryInvoice).where(InventoryInvoice.id == invoice_id).with_for_update()
    )
    inv = inv_result.scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status != "issued":
        raise HTTPException(status_code=422, detail=f"invoice is {inv.status}; cannot post receipt")
    balance = await _invoice_balance(db, inv)
    if amount > balance:
        raise HTTPException(
            status_code=422, detail=f"receipt amount {amount} exceeds invoice balance {balance}"
        )
    receipt_no = await doc_numbers_svc.allocate_doc_no(
        db, location_id=inv.location_id, doc_type="SR"
    )
    rc = InventoryReceipt(
        receipt_no=receipt_no,
        invoice_id=inv.id,
        customer_id=inv.customer_id,
        location_id=inv.location_id,
        amount=amount,
        paid_by=paid_by,
        reference_no=reference_no,
        receipt_date=receipt_date or date.today(),
        notes=notes,
        created_by=user.id,
    )
    db.add(rc)
    await db.flush()
    return rc


@router.post("/receipts", response_model=InventoryReceiptOut, status_code=status.HTTP_201_CREATED)
async def create_receipt(body: InventoryReceiptCreate, _admin: AdminOnly, db: DB) -> dict:
    rc = await _create_receipt_tx(
        db,
        body.invoice_id,
        amount=body.amount,
        paid_by=body.paid_by,
        reference_no=body.reference_no,
        receipt_date=body.receipt_date,
        notes=body.notes,
        user=_admin,
    )
    rc_id = rc.id
    await db.commit()
    result = await db.execute(select(InventoryReceipt).where(InventoryReceipt.id == rc_id))
    rc = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="inventory_receipts",
        record_id=rc_id,
        new_values={"receipt_no": rc.receipt_no, "amount": body.amount},
        description=f"Posted receipt {rc.receipt_no}",
    )
    return await _rc_out(db, rc)


@router.get("/receipts/{receipt_id}", response_model=InventoryReceiptOut)
async def get_receipt(receipt_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    return await _rc_out(db, await _get_receipt_or_404(db, receipt_id))


@router.post("/receipts/{receipt_id}/void", response_model=InventoryReceiptOut)
async def void_receipt(receipt_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    rc = await _get_receipt_or_404(db, receipt_id)
    if rc.status == "void":
        return await _rc_out(db, rc)
    rc.status = "void"
    await db.commit()
    result = await db.execute(select(InventoryReceipt).where(InventoryReceipt.id == receipt_id))
    rc = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_receipts",
        record_id=receipt_id,
        old_values={"status": "posted"},
        new_values={"status": "void"},
        description=f"Voided receipt {rc.receipt_no}",
    )
    return await _rc_out(db, rc)


@router.get("/receipts/{receipt_id}/print", response_model=InventoryReceiptPrint)
async def print_receipt(receipt_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    rc = await _get_receipt_or_404(db, receipt_id)
    inv = await _get_invoice_or_404(db, rc.invoice_id)
    paid = await _paid_total(db, inv.id)
    credited = await _credited_total(db, inv.id)
    cust_result = await db.execute(select(Customer).where(Customer.id == rc.customer_id))
    customer = cust_result.scalar_one()
    loc_result = await db.execute(select(Location).where(Location.id == rc.location_id))
    loc = loc_result.scalar_one()
    return {
        "receipt_no": rc.receipt_no,
        "receipt_date": rc.receipt_date,
        "status": rc.status,
        "invoice_no": inv.invoice_no,
        "invoice_total": _to_float(inv.total),
        "invoice_paid_total": paid,
        "invoice_balance": max(_to_float(inv.total) - paid - credited, 0.0),
        "buyer_name": inv.buyer_name,
        "customer_code": customer.code,
        "customer_name_zh": customer.name_zh,
        "customer_name_en": customer.name_en,
        "location_name_zh": loc.name_zh,
        "location_name_en": loc.name_en,
        "location_address": loc.address,
        "location_phone": loc.phone,
        "amount": _to_float(rc.amount),
        "paid_by": rc.paid_by,
        "reference_no": rc.reference_no,
        "notes": rc.notes,
    }


# ---------- credit notes ----------


@router.get("/credit-notes", response_model=list[InventoryCreditNoteOut])
async def list_credit_notes(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    invoice_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
) -> list[dict]:
    q = select(InventoryCreditNote)
    count_q = select(func.count()).select_from(InventoryCreditNote)
    if invoice_id:
        q = q.where(InventoryCreditNote.invoice_id == invoice_id)
        count_q = count_q.where(InventoryCreditNote.invoice_id == invoice_id)
    if customer_id:
        q = q.where(InventoryCreditNote.customer_id == customer_id)
        count_q = count_q.where(InventoryCreditNote.customer_id == customer_id)
    if location_id:
        q = q.where(InventoryCreditNote.location_id == location_id)
        count_q = count_q.where(InventoryCreditNote.location_id == location_id)
    if status_filter:
        q = q.where(InventoryCreditNote.status == status_filter)
        count_q = count_q.where(InventoryCreditNote.status == status_filter)
    if date_from:
        q = q.where(InventoryCreditNote.credit_date >= date_from)
        count_q = count_q.where(InventoryCreditNote.credit_date >= date_from)
    if date_to:
        q = q.where(InventoryCreditNote.credit_date <= date_to)
        count_q = count_q.where(InventoryCreditNote.credit_date <= date_to)
    if search:
        q = q.where(ilike_contains(InventoryCreditNote.scn_no, search))
        count_q = count_q.where(ilike_contains(InventoryCreditNote.scn_no, search))
    total = (await db.execute(count_q)).scalar_one()
    response.headers["X-Total-Count"] = str(total)
    q = q.order_by(InventoryCreditNote.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()
    return [await _scn_out(db, scn) for scn in rows]


async def _build_scn_lines(
    db: DB,
    inv: InventoryInvoice,
    line_inputs: list[InventoryCreditNoteLineIn],
) -> list[dict]:
    seen: set[uuid.UUID] = set()
    built: list[dict] = []
    for inp in line_inputs:
        if inp.invoice_line_id in seen:
            raise HTTPException(status_code=422, detail="duplicate invoice_line_id")
        seen.add(inp.invoice_line_id)
        inv_line_result = await db.execute(
            select(InventoryInvoiceLine).where(InventoryInvoiceLine.id == inp.invoice_line_id)
        )
        inv_line = inv_line_result.scalar_one_or_none()
        if inv_line is None or inv_line.invoice_id != inv.id:
            raise HTTPException(status_code=422, detail="invoice_line_id not on this invoice")
        if inv_line.qty > 0 and _to_float(inv_line.amount) is not None:
            unit_amount = round(_to_float(inv_line.amount) / inv_line.qty, 2)
        else:
            unit_amount = 0.0
        built.append(
            {
                "invoice_line_id": inv_line.id,
                "item_id": inv_line.item_id,
                "qty": inp.qty,
                "unit_amount": unit_amount,
                "amount": round(inp.qty * unit_amount, 2),
                "restock": inp.restock,
            }
        )
    return built


@router.post("/credit-notes", response_model=InventoryCreditNoteOut, status_code=status.HTTP_201_CREATED)
async def create_credit_note(body: InventoryCreditNoteCreate, _admin: AdminOnly, db: DB) -> dict:
    inv = await _get_invoice_or_404(db, body.invoice_id)
    if inv.status != "issued":
        raise HTTPException(status_code=422, detail=f"invoice is {inv.status}; cannot credit")
    built = await _build_scn_lines(db, inv, list(body.lines))
    scn_no = await doc_numbers_svc.allocate_doc_no(db, location_id=inv.location_id, doc_type="SCN")
    scn = InventoryCreditNote(
        scn_no=scn_no,
        invoice_id=inv.id,
        customer_id=inv.customer_id,
        location_id=inv.location_id,
        credit_date=body.credit_date or date.today(),
        reason=body.reason,
        total=round(sum(line["amount"] for line in built), 2),
        created_by=_admin.id,
    )
    db.add(scn)
    for line in built:
        db.add(InventoryCreditNoteLine(scn=scn, **line))
    await db.flush()
    scn_id = scn.id
    await db.commit()
    result = await db.execute(select(InventoryCreditNote).where(InventoryCreditNote.id == scn_id))
    scn = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="inventory_credit_notes",
        record_id=scn_id,
        new_values={"scn_no": scn_no, "total": _to_float(scn.total)},
        description=f"Created credit note {scn_no}",
    )
    return await _scn_out(db, scn)


@router.get("/credit-notes/{scn_id}", response_model=InventoryCreditNoteOut)
async def get_credit_note(scn_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    return await _scn_out(db, await _get_scn_or_404(db, scn_id))


@router.patch("/credit-notes/{scn_id}", response_model=InventoryCreditNoteOut)
async def update_credit_note(
    scn_id: uuid.UUID, body: InventoryCreditNoteUpdate, _admin: AdminOnly, db: DB
) -> dict:
    scn = await _get_scn_or_404(db, scn_id)
    if scn.status != "draft":
        raise HTTPException(status_code=409, detail=f"credit note is {scn.status}; only drafts can be edited")
    if body.credit_date is not None:
        scn.credit_date = body.credit_date
    if body.reason is not None:
        scn.reason = body.reason
    if body.lines is not None:
        inv = await _get_invoice_or_404(db, scn.invoice_id)
        for line in await _scn_lines(db, scn.id):
            await db.delete(line)
        await db.flush()
        built = await _build_scn_lines(db, inv, list(body.lines))
        for line in built:
            db.add(InventoryCreditNoteLine(scn=scn, **line))
        await db.flush()
        scn.total = round(sum(line["amount"] for line in built), 2)
    await db.commit()
    result = await db.execute(select(InventoryCreditNote).where(InventoryCreditNote.id == scn_id))
    scn = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_credit_notes",
        record_id=scn_id,
        new_values={"total": _to_float(scn.total)},
        description=f"Updated credit note {scn.scn_no}",
    )
    return await _scn_out(db, scn)


@router.delete("/credit-notes/{scn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credit_note(scn_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    scn = await _get_scn_or_404(db, scn_id)
    if scn.status != "draft":
        raise HTTPException(status_code=409, detail=f"credit note is {scn.status}; only drafts can be deleted")
    scn_no = scn.scn_no
    await db.delete(scn)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="DELETE",
        table_name="inventory_credit_notes",
        record_id=scn_id,
        description=f"Deleted draft credit note {scn_no}",
    )


@router.post("/credit-notes/{scn_id}/confirm", response_model=InventoryCreditNoteOut)
async def confirm_credit_note(scn_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    scn = await _get_scn_or_404(db, scn_id)
    if scn.status == "confirmed":
        return await _scn_out(db, scn)
    if scn.status != "draft":
        raise HTTPException(status_code=409, detail=f"credit note is {scn.status}; cannot confirm")

    inv = await _get_invoice_or_404(db, scn.invoice_id)
    if inv.status != "issued":
        raise HTTPException(status_code=422, detail=f"invoice is {inv.status}; cannot credit")

    lines = await _scn_lines(db, scn.id)
    inv_lines = {line.id: line for line in await _inv_lines(db, inv.id)}
    for line in lines:
        inv_line = inv_lines.get(line.invoice_line_id)
        if inv_line is None:
            raise HTTPException(status_code=422, detail="credit note references a removed invoice line")
        if line.qty > inv_line.qty - inv_line.credited_qty:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"over-credit for {inv_line.sku_code}: invoiced {inv_line.qty}, "
                    f"already credited {inv_line.credited_qty}, this note {line.qty}"
                ),
            )
    balance = await _invoice_balance(db, inv)
    if _to_float(scn.total) > balance:
        raise HTTPException(
            status_code=422,
            detail="credit exceeds unpaid balance; void the receipt first",
        )

    for line in lines:
        inv_line = inv_lines[line.invoice_line_id]
        if line.restock:
            await inventory_svc.apply_movement(
                db,
                item_id=line.item_id,
                location_id=scn.location_id,
                type="in",
                quantity=line.qty,
                reason=f"credit note {scn.scn_no}",
                reason_code="sales_return",
                reference=f"SCN:{scn.id}:{line.id}",
                user=_admin,
            )
        inv_line.credited_qty += line.qty

    scn.status = "confirmed"
    await db.commit()
    result = await db.execute(select(InventoryCreditNote).where(InventoryCreditNote.id == scn_id))
    scn = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_credit_notes",
        record_id=scn_id,
        old_values={"status": "draft"},
        new_values={"status": "confirmed"},
        description=f"Confirmed credit note {scn.scn_no}",
    )
    return await _scn_out(db, scn)


@router.post("/credit-notes/{scn_id}/void", response_model=InventoryCreditNoteOut)
async def void_credit_note(scn_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    scn = await _get_scn_or_404(db, scn_id)
    if scn.status == "void":
        return await _scn_out(db, scn)
    if scn.status != "confirmed":
        raise HTTPException(status_code=409, detail=f"credit note is {scn.status}; cannot void")

    lines = await _scn_lines(db, scn.id)
    inv_lines = {
        line.id: line
        for line in await _inv_lines(db, scn.invoice_id)
    }
    for line in lines:
        if line.restock:
            await inventory_svc.apply_movement(
                db,
                item_id=line.item_id,
                location_id=scn.location_id,
                type="out",
                quantity=line.qty,
                reason=f"void credit note {scn.scn_no}",
                reason_code="other",
                reference=f"SCN-VOID:{scn.id}:{line.id}",
                user=_admin,
            )
        inv_line = inv_lines.get(line.invoice_line_id)
        if inv_line is not None:
            inv_line.credited_qty -= line.qty

    scn.status = "void"
    await db.commit()
    result = await db.execute(select(InventoryCreditNote).where(InventoryCreditNote.id == scn_id))
    scn = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_credit_notes",
        record_id=scn_id,
        old_values={"status": "confirmed"},
        new_values={"status": "void"},
        description=f"Voided credit note {scn.scn_no}",
    )
    return await _scn_out(db, scn)


@router.get("/credit-notes/{scn_id}/print", response_model=InventoryCreditNotePrint)
async def print_credit_note(scn_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    scn = await _get_scn_or_404(db, scn_id)
    detail = await _scn_out(db, scn)
    inv = await _get_invoice_or_404(db, scn.invoice_id)
    cust_result = await db.execute(select(Customer).where(Customer.id == scn.customer_id))
    customer = cust_result.scalar_one()
    loc_result = await db.execute(select(Location).where(Location.id == scn.location_id))
    loc = loc_result.scalar_one()
    return {
        "scn_no": scn.scn_no,
        "credit_date": scn.credit_date,
        "status": scn.status,
        "invoice_no": inv.invoice_no,
        "buyer_name": inv.buyer_name,
        "customer_code": customer.code,
        "customer_name_zh": customer.name_zh,
        "customer_name_en": customer.name_en,
        "location_name_zh": loc.name_zh,
        "location_name_en": loc.name_en,
        "location_address": loc.address,
        "location_phone": loc.phone,
        "reason": scn.reason,
        "lines": detail["lines"],
        "total": detail["total"],
    }


# ---------- quick fulfill ----------


@router.post("/sales-orders/{so_id}/quick-fulfill", response_model=QuickFulfillResult)
async def quick_fulfill(so_id: uuid.UUID, body: QuickFulfillRequest, _admin: AdminOnly, db: DB) -> dict:
    so_result = await db.execute(select(SalesOrder).where(SalesOrder.id == so_id))
    so = so_result.scalar_one_or_none()
    if so is None:
        raise HTTPException(status_code=404, detail="Sales order not found")
    if so.status not in ("draft", "confirmed", "partial"):
        raise HTTPException(status_code=422, detail=f"SO {so.so_no} is {so.status}; cannot quick-fulfill")

    actions: list[dict] = []
    was_draft = so.status == "draft"
    if was_draft:
        await confirm_so_tx(db, so)
        actions.append({"action": "UPDATE", "table": "sales_orders", "desc": f"Confirmed sales order {so.so_no}"})

    do = await create_do_tx(
        db,
        so,
        delivery_date=body.issue_date or date.today(),
        notes="quick fulfill",
        line_inputs=[],
        user=_admin,
    )
    actions.append({"action": "CREATE", "table": "delivery_orders", "desc": f"Created delivery order {do.do_no} for {so.so_no}"})
    await confirm_do_tx(db, do, _admin)
    actions.append({"action": "UPDATE", "table": "delivery_orders", "desc": f"Confirmed delivery order {do.do_no}"})

    inv = await _create_invoice_tx(
        db,
        do,
        issue_date=body.issue_date,
        discount_amount=None,
        notes=None,
        line_inputs=[],
        user=_admin,
    )
    actions.append({"action": "CREATE", "table": "inventory_invoices", "desc": f"Created invoice for DO {do.do_no}"})
    await _issue_invoice_tx(db, inv)
    actions.append({"action": "UPDATE", "table": "inventory_invoices", "desc": f"Issued invoice {inv.invoice_no}"})

    receipt = None
    if body.pay is not None:
        receipt = await _create_receipt_tx(
            db,
            inv.id,
            amount=body.pay.amount,
            paid_by=body.pay.paid_by,
            reference_no=body.pay.reference_no,
            receipt_date=body.issue_date,
            notes="quick fulfill",
            user=_admin,
        )
        actions.append({"action": "CREATE", "table": "inventory_receipts", "desc": f"Posted receipt {receipt.receipt_no}"})

    so_id_v, do_id, inv_id = so.id, do.id, inv.id
    receipt_id = receipt.id if receipt else None
    await db.commit()

    so = (await db.execute(select(SalesOrder).where(SalesOrder.id == so_id_v))).scalar_one()
    do = (await db.execute(select(DeliveryOrder).where(DeliveryOrder.id == do_id))).scalar_one()
    inv = (await db.execute(select(InventoryInvoice).where(InventoryInvoice.id == inv_id))).scalar_one()
    for entry in actions:
        await audit_log_svc.log_audit(
            db,
            user_id=_admin.id,
            action=entry["action"],
            table_name=entry["table"],
            record_id={
                "sales_orders": so_id_v,
                "delivery_orders": do_id,
                "inventory_invoices": inv_id,
                "inventory_receipts": receipt_id,
            }[entry["table"]],
            description=entry["desc"],
        )
    receipt_out = None
    if receipt_id:
        rc = (await db.execute(select(InventoryReceipt).where(InventoryReceipt.id == receipt_id))).scalar_one()
        receipt_out = await _rc_out(db, rc)
    return {
        "so": await _so_detail(db, so),
        "delivery_order": await _do_detail(db, do),
        "invoice": await _inv_detail(db, inv),
        "receipt": receipt_out,
    }
