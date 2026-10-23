import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select

from app.deps import AdminOnly, DB
from app.models.inventory import InventoryItem
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
    SalesOrder,
    SalesOrderLine,
)
from app.models.location import Location
from app.routers.inventory_sales import (
    _do_detail,
    _invoice_lines_map,
    _lock_or_404,
    _recompute_so_status,
    _so_detail,
    _so_lines,
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


_CENT = Decimal("0.01")
_ZERO = Decimal("0.00")


def _money(value) -> Decimal:
    """Exact 2-decimal money value — all balance/total arithmetic uses this."""
    if value is None:
        return _ZERO
    return Decimal(str(value)).quantize(_CENT, rounding=ROUND_HALF_UP)


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


async def _paid_total(db: DB, invoice_id: uuid.UUID) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(InventoryReceipt.amount), 0)).where(
            InventoryReceipt.invoice_id == invoice_id,
            InventoryReceipt.status == "posted",
        )
    )
    return _money(result.scalar_one())


async def _credited_total(db: DB, invoice_id: uuid.UUID) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(InventoryCreditNote.total), 0)).where(
            InventoryCreditNote.invoice_id == invoice_id,
            InventoryCreditNote.status == "confirmed",
        )
    )
    return _money(result.scalar_one())


def _payment_status(inv: InventoryInvoice, paid: Decimal, credited: Decimal) -> str:
    if inv.status == "void":
        return "void"
    total = _money(inv.total)
    if paid + credited >= total:  # zero-total issued invoices count as paid
        return "paid"
    if paid + credited > 0:
        return "partial"
    return "unpaid"


async def _draft_invoice_claims(
    db: DB, so_line_id: uuid.UUID, exclude_invoice_id: uuid.UUID | None = None
) -> int:
    """Qty claimed by other draft (not yet issued, not void) invoices on an SO line."""
    q = (
        select(func.coalesce(func.sum(InventoryInvoiceLine.qty), 0))
        .select_from(InventoryInvoiceLine)
        .join(InventoryInvoice, InventoryInvoice.id == InventoryInvoiceLine.invoice_id)
        .where(
            InventoryInvoiceLine.so_line_id == so_line_id,
            InventoryInvoice.status == "draft",
        )
    )
    if exclude_invoice_id is not None:
        q = q.where(InventoryInvoice.id != exclude_invoice_id)
    return int((await db.execute(q)).scalar_one() or 0)


async def _invoice_do_summaries(db: DB, invoice_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(DeliveryOrder)
        .where(DeliveryOrder.invoice_id == invoice_id)
        .order_by(DeliveryOrder.delivery_date, DeliveryOrder.do_no)
    )
    return [
        {"id": d.id, "do_no": d.do_no, "delivery_date": d.delivery_date, "status": d.status}
        for d in result.scalars().all()
    ]


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
    so_result = await db.execute(select(SalesOrder).where(SalesOrder.id == inv.so_id))
    so = so_result.scalar_one()
    cust_result = await db.execute(select(Customer).where(Customer.id == inv.customer_id))
    customer = cust_result.scalar_one()
    paid = await _paid_total(db, inv.id)
    credited = await _credited_total(db, inv.id)
    total = _money(inv.total)
    subtotal = sum((_money(line.amount) for line in lines), _ZERO)
    return {
        "id": inv.id,
        "invoice_no": inv.invoice_no,
        "so_id": inv.so_id,
        "so_no": so.so_no,
        "customer_id": inv.customer_id,
        "customer_name": customer.name_zh or customer.name_en,
        "buyer_name": inv.buyer_name,
        "location_id": inv.location_id,
        "issue_date": inv.issue_date,
        "status": inv.status,
        "discount_amount": _money(inv.discount_amount),
        "subtotal": subtotal,
        "total": total,
        "paid_total": paid,
        "credited_total": credited,
        "balance": max(total - paid - credited, _ZERO),
        "payment_status": _payment_status(inv, paid, credited),
        "notes": inv.notes,
        "issued_at": inv.issued_at,
        "created_by": inv.created_by,
        "created_at": inv.created_at,
        "updated_at": inv.updated_at,
        "lines": [InventoryInvoiceLineOut.model_validate(line).model_dump() for line in lines],
        "receipts": await _invoice_receipt_summaries(db, inv.id),
        "credit_notes": await _invoice_scn_summaries(db, inv.id),
        "delivery_orders": await _invoice_do_summaries(db, inv.id),
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


async def _assert_item_active_for_restock(db: DB, item_id: uuid.UUID) -> None:
    item = await db.get(InventoryItem, item_id)
    if item is None or not item.is_active:
        raise HTTPException(status_code=422, detail="item is inactive or unknown")


async def _invoice_balance(db: DB, inv: InventoryInvoice) -> Decimal:
    paid = await _paid_total(db, inv.id)
    credited = await _credited_total(db, inv.id)
    return max(_money(inv.total) - paid - credited, _ZERO)


# Batched builders for list endpoints — same payload as the per-row helpers
# but with IN-queries per relation instead of a query per row.


async def _inv_details_batch(db: DB, rows: list[InventoryInvoice]) -> list[dict]:
    if not rows:
        return []
    inv_ids = [inv.id for inv in rows]
    lines_all = (
        await db.execute(
            select(InventoryInvoiceLine)
            .where(InventoryInvoiceLine.invoice_id.in_(inv_ids))
            .order_by(InventoryInvoiceLine.id)
        )
    ).scalars().all()
    lines_by_inv: dict[uuid.UUID, list[InventoryInvoiceLine]] = {}
    for line in lines_all:
        lines_by_inv.setdefault(line.invoice_id, []).append(line)

    dos_by_inv: dict[uuid.UUID, list[DeliveryOrder]] = {}
    for d in (
        await db.execute(
            select(DeliveryOrder)
            .where(DeliveryOrder.invoice_id.in_(inv_ids))
            .order_by(DeliveryOrder.delivery_date, DeliveryOrder.do_no)
        )
    ).scalars().all():
        dos_by_inv.setdefault(d.invoice_id, []).append(d)
    sos = {
        s.id: s
        for s in (
            await db.execute(
                select(SalesOrder).where(SalesOrder.id.in_({inv.so_id for inv in rows}))
            )
        ).scalars().all()
    }
    custs = {
        c.id: c
        for c in (
            await db.execute(
                select(Customer).where(Customer.id.in_({inv.customer_id for inv in rows}))
            )
        ).scalars().all()
    }
    paid_map = {
        inv_id: _money(amount)
        for inv_id, amount in (
            await db.execute(
                select(InventoryReceipt.invoice_id, func.sum(InventoryReceipt.amount))
                .where(
                    InventoryReceipt.invoice_id.in_(inv_ids),
                    InventoryReceipt.status == "posted",
                )
                .group_by(InventoryReceipt.invoice_id)
            )
        ).all()
    }
    cred_map = {
        inv_id: _money(amount)
        for inv_id, amount in (
            await db.execute(
                select(InventoryCreditNote.invoice_id, func.sum(InventoryCreditNote.total))
                .where(
                    InventoryCreditNote.invoice_id.in_(inv_ids),
                    InventoryCreditNote.status == "confirmed",
                )
                .group_by(InventoryCreditNote.invoice_id)
            )
        ).all()
    }
    receipts_by_inv: dict[uuid.UUID, list[InventoryReceipt]] = {}
    for rc in (
        await db.execute(
            select(InventoryReceipt)
            .where(InventoryReceipt.invoice_id.in_(inv_ids))
            .order_by(InventoryReceipt.receipt_date, InventoryReceipt.receipt_no)
        )
    ).scalars().all():
        receipts_by_inv.setdefault(rc.invoice_id, []).append(rc)
    scns_by_inv: dict[uuid.UUID, list[InventoryCreditNote]] = {}
    for s in (
        await db.execute(
            select(InventoryCreditNote)
            .where(InventoryCreditNote.invoice_id.in_(inv_ids))
            .order_by(InventoryCreditNote.credit_date, InventoryCreditNote.scn_no)
        )
    ).scalars().all():
        scns_by_inv.setdefault(s.invoice_id, []).append(s)

    out = []
    for inv in rows:
        lines = lines_by_inv.get(inv.id, [])
        so = sos.get(inv.so_id)
        customer = custs.get(inv.customer_id)
        paid = paid_map.get(inv.id, _ZERO)
        credited = cred_map.get(inv.id, _ZERO)
        total = _money(inv.total)
        out.append(
            {
                "id": inv.id,
                "invoice_no": inv.invoice_no,
                "so_id": inv.so_id,
                "so_no": so.so_no if so else None,
                "customer_id": inv.customer_id,
                "customer_name": (customer.name_zh or customer.name_en) if customer else None,
                "buyer_name": inv.buyer_name,
                "location_id": inv.location_id,
                "issue_date": inv.issue_date,
                "status": inv.status,
                "discount_amount": _money(inv.discount_amount),
                "subtotal": sum((_money(line.amount) for line in lines), _ZERO),
                "total": total,
                "paid_total": paid,
                "credited_total": credited,
                "balance": max(total - paid - credited, _ZERO),
                "payment_status": _payment_status(inv, paid, credited),
                "notes": inv.notes,
                "issued_at": inv.issued_at,
                "created_by": inv.created_by,
                "created_at": inv.created_at,
                "updated_at": inv.updated_at,
                "lines": [
                    InventoryInvoiceLineOut.model_validate(line).model_dump() for line in lines
                ],
                "receipts": [
                    {
                        "id": r.id,
                        "receipt_no": r.receipt_no,
                        "amount": _to_float(r.amount),
                        "paid_by": r.paid_by,
                        "receipt_date": r.receipt_date,
                        "status": r.status,
                    }
                    for r in receipts_by_inv.get(inv.id, [])
                ],
                "credit_notes": [
                    {
                        "id": s.id,
                        "scn_no": s.scn_no,
                        "total": _to_float(s.total),
                        "credit_date": s.credit_date,
                        "status": s.status,
                    }
                    for s in scns_by_inv.get(inv.id, [])
                ],
                "delivery_orders": [
                    {
                        "id": d.id,
                        "do_no": d.do_no,
                        "delivery_date": d.delivery_date,
                        "status": d.status,
                    }
                    for d in dos_by_inv.get(inv.id, [])
                ],
            }
        )
    return out


async def _rc_outs_batch(db: DB, rows: list[InventoryReceipt]) -> list[dict]:
    if not rows:
        return []
    invs = {
        inv.id: inv
        for inv in (
            await db.execute(
                select(InventoryInvoice).where(InventoryInvoice.id.in_({rc.invoice_id for rc in rows}))
            )
        ).scalars().all()
    }
    custs = {
        c.id: c
        for c in (
            await db.execute(
                select(Customer).where(Customer.id.in_({rc.customer_id for rc in rows}))
            )
        ).scalars().all()
    }
    return [
        {
            "id": rc.id,
            "receipt_no": rc.receipt_no,
            "invoice_id": rc.invoice_id,
            "invoice_no": invs[rc.invoice_id].invoice_no if rc.invoice_id in invs else None,
            "customer_id": rc.customer_id,
            "customer_name": (
                (custs[rc.customer_id].name_zh or custs[rc.customer_id].name_en)
                if rc.customer_id in custs
                else None
            ),
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
        for rc in rows
    ]


async def _scn_outs_batch(db: DB, rows: list[InventoryCreditNote]) -> list[dict]:
    if not rows:
        return []
    scn_ids = [scn.id for scn in rows]
    lines_all = (
        await db.execute(
            select(InventoryCreditNoteLine)
            .where(InventoryCreditNoteLine.scn_id.in_(scn_ids))
            .order_by(InventoryCreditNoteLine.id)
        )
    ).scalars().all()
    lines_by_scn: dict[uuid.UUID, list[InventoryCreditNoteLine]] = {}
    for line in lines_all:
        lines_by_scn.setdefault(line.scn_id, []).append(line)
    inv_line_ids = {line.invoice_line_id for line in lines_all}
    inv_lines = {
        l.id: l
        for l in (
            await db.execute(
                select(InventoryInvoiceLine).where(InventoryInvoiceLine.id.in_(inv_line_ids))
            )
        ).scalars().all()
    } if inv_line_ids else {}
    invs = {
        inv.id: inv
        for inv in (
            await db.execute(
                select(InventoryInvoice).where(
                    InventoryInvoice.id.in_({scn.invoice_id for scn in rows})
                )
            )
        ).scalars().all()
    }
    custs = {
        c.id: c
        for c in (
            await db.execute(
                select(Customer).where(Customer.id.in_({scn.customer_id for scn in rows}))
            )
        ).scalars().all()
    }
    out = []
    for scn in rows:
        inv = invs.get(scn.invoice_id)
        customer = custs.get(scn.customer_id)
        line_outs = []
        for line in lines_by_scn.get(scn.id, []):
            inv_line = inv_lines.get(line.invoice_line_id)
            line_out = InventoryCreditNoteLineOut.model_validate(line).model_dump()
            line_out["sku_code"] = inv_line.sku_code if inv_line else None
            line_out["name_zh"] = inv_line.name_zh if inv_line else None
            line_outs.append(line_out)
        out.append(
            {
                "id": scn.id,
                "scn_no": scn.scn_no,
                "invoice_id": scn.invoice_id,
                "invoice_no": inv.invoice_no if inv else None,
                "customer_id": scn.customer_id,
                "customer_name": (customer.name_zh or customer.name_en) if customer else None,
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
        )
    return out


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
            cond = issued & (paid_col + cred_col >= InventoryInvoice.total)
        elif payment_status == "partial":
            cond = issued & (paid_col + cred_col > 0) & (paid_col + cred_col < InventoryInvoice.total)
        else:  # unpaid — zero-total issued invoices count as paid, not unpaid
            cond = issued & (paid_col + cred_col < InventoryInvoice.total)
        q = q.where(cond)
        count_q = count_q.where(cond)

    total = (await db.execute(count_q)).scalar_one()
    response.headers["X-Total-Count"] = str(total)
    q = q.order_by(InventoryInvoice.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()
    return await _inv_details_batch(db, rows)


async def _remaining_for_so_line(
    db: DB, so_line: SalesOrderLine, exclude_invoice_id: uuid.UUID | None = None
) -> int:
    """Qty still invoiceable: ordered minus issued-invoiced minus other draft claims."""
    claimed = await _draft_invoice_claims(db, so_line.id, exclude_invoice_id)
    return so_line.qty - so_line.invoiced_qty - claimed


async def _build_invoice_lines(
    db: DB,
    so: SalesOrder,
    line_inputs: list[InventoryInvoiceLineIn],
    exclude_invoice_id: uuid.UUID | None = None,
) -> list[dict]:
    """Validate inputs against the SO and return frozen line dicts."""
    so_lines = await _so_lines(db, so.id)
    so_line_by_id = {line.id: line for line in so_lines}

    seen: set[uuid.UUID] = set()
    built: list[dict] = []
    for inp in line_inputs:
        if inp.so_line_id in seen:
            raise HTTPException(status_code=422, detail="duplicate so_line_id in invoice lines")
        seen.add(inp.so_line_id)
        so_line = so_line_by_id.get(inp.so_line_id)
        if so_line is None:
            raise HTTPException(status_code=422, detail=f"so_line_id {inp.so_line_id} not on this SO")
        remaining = await _remaining_for_so_line(db, so_line, exclude_invoice_id)
        if inp.qty > remaining:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"over-invoicing SO line {so_line.sku_code}: ordered {so_line.qty}, "
                    f"invoiced {so_line.invoiced_qty}, this invoice {inp.qty}"
                ),
            )
        unit_price = _money(so_line.unit_price)
        discount = _money(_money(so_line.discount_amount) * inp.qty / so_line.qty)
        amount = max(_money(inp.qty * unit_price - discount), _ZERO)
        built.append(
            {
                "so_line_id": so_line.id,
                "item_id": so_line.item_id,
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
    so: SalesOrder,
    *,
    issue_date: date | None,
    discount_amount: float | None,
    notes: str | None,
    line_inputs: list[InventoryInvoiceLineIn],
    user,
) -> InventoryInvoice:
    if so.status not in ("confirmed", "partial"):
        raise HTTPException(status_code=422, detail=f"SO {so.so_no} is {so.status}; cannot invoice")

    if not line_inputs:
        line_inputs = []
        for so_line in await _so_lines(db, so.id):
            remaining = await _remaining_for_so_line(db, so_line)
            if remaining > 0:
                line_inputs.append(InventoryInvoiceLineIn(so_line_id=so_line.id, qty=remaining))
        if not line_inputs:
            raise HTTPException(status_code=422, detail="SO is fully invoiced")

    built = await _build_invoice_lines(db, so, line_inputs)
    if not built:
        raise HTTPException(status_code=422, detail="invoice has no lines")

    subtotal = sum((line["amount"] for line in built), _ZERO)
    if discount_amount is not None:
        header_discount = _money(discount_amount)
    else:
        so_subtotal = _money(so.total) + _money(so.discount_amount)
        header_discount = (
            _money(_money(so.discount_amount) * subtotal / so_subtotal)
            if so_subtotal > 0
            else _ZERO
        )
    total = max(subtotal - header_discount, _ZERO)

    inv = InventoryInvoice(
        so_id=so.id,
        customer_id=so.customer_id,
        buyer_name=so.buyer_name,
        location_id=so.location_id,
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
    db: DB, inv: InventoryInvoice, user, issue_date: date | None = None
) -> None:
    """Issue the invoice: deduct stock + release reservations. Caller commits.

    Locks the invoice row, the SO row, and the SO lines (FOR UPDATE) before
    re-validating quantities so concurrent issues can't over-invoice. Any
    stock shortfall aborts the whole issue — nothing is written.
    """
    lines = await _inv_lines(db, inv.id)
    if not lines:
        raise HTTPException(status_code=422, detail="invoice has no lines")

    so = await _lock_or_404(db, SalesOrder, inv.so_id, "Sales order")
    so_lines = {
        line.id: line
        for line in (
            await db.execute(
                select(SalesOrderLine)
                .where(SalesOrderLine.so_id == so.id)
                .order_by(SalesOrderLine.id)
                .with_for_update()
            )
        ).scalars().all()
    }

    for line in lines:
        so_line = so_lines.get(line.so_line_id)
        if so_line is None:
            raise HTTPException(status_code=422, detail="invoice line references a removed SO line")
        if line.qty > so_line.qty - so_line.invoiced_qty:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"over-invoicing SO line {so_line.sku_code}: ordered {so_line.qty}, "
                    f"invoiced {so_line.invoiced_qty}, this invoice {line.qty}"
                ),
            )

    for line in lines:
        so_line = so_lines[line.so_line_id]
        # Release whatever is still reserved for this line before the 'out'
        # (an 'out' may not push on-hand below the reserved amount). Skipped
        # for a cancelled SO, whose reservations were already released.
        if so.status != "cancelled":
            to_release = min(line.qty, so_line.qty - so_line.invoiced_qty)
            if to_release > 0:
                await inventory_svc.release(
                    db, item_id=line.item_id, location_id=inv.location_id, quantity=to_release
                )
        await inventory_svc.apply_movement(
            db,
            item_id=line.item_id,
            location_id=inv.location_id,
            type="out",
            quantity=line.qty,
            reason=f"sales invoice {inv.invoice_no or inv.id}",
            reason_code="sale",
            reference=f"SI:{inv.id}:{line.id}",
            user=user,
        )
        so_line.invoiced_qty += line.qty
    await _recompute_so_status(db, so)

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
    result = await db.execute(select(SalesOrder).where(SalesOrder.id == body.so_id))
    so = result.scalar_one_or_none()
    if so is None:
        raise HTTPException(status_code=404, detail="Sales order not found")
    inv = await _create_invoice_tx(
        db,
        so,
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
        new_values={"so_id": str(body.so_id), "total": _to_float(inv.total)},
        description=f"Created draft invoice for SO {so.so_no}",
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
        so_result = await db.execute(select(SalesOrder).where(SalesOrder.id == inv.so_id))
        so = so_result.scalar_one()
        old_lines = await _inv_lines(db, inv.id)
        for line in old_lines:
            await db.delete(line)
        await db.flush()
        built = await _build_invoice_lines(db, so, list(body.lines), exclude_invoice_id=inv.id)
        if not built:
            raise HTTPException(status_code=422, detail="invoice must have at least one line")
        for line in built:
            db.add(InventoryInvoiceLine(invoice=inv, **line))
        await db.flush()
        subtotal = sum((line["amount"] for line in built), _ZERO)
    else:
        subtotal = sum(
            (_money(line.amount) for line in await _inv_lines(db, inv.id)), _ZERO
        )

    if body.discount_amount is not None:
        inv.discount_amount = _money(body.discount_amount)
    inv.total = max(subtotal - _money(inv.discount_amount), _ZERO)
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
    inv = await _lock_or_404(db, InventoryInvoice, invoice_id, "Invoice")
    if inv.status == "issued":
        return await _inv_detail(db, inv)
    if inv.status != "draft":
        raise HTTPException(status_code=409, detail=f"invoice is {inv.status}; cannot issue")
    await _issue_invoice_tx(db, inv, _admin)
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
    inv = await _lock_or_404(db, InventoryInvoice, invoice_id, "Invoice")
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
    open_dos = (
        await db.execute(
            select(func.count())
            .select_from(DeliveryOrder)
            .where(
                DeliveryOrder.invoice_id == inv.id,
                DeliveryOrder.status != "void",
            )
        )
    ).scalar_one()
    if open_dos:
        raise HTTPException(status_code=409, detail="invoice has delivery orders; void or delete them first")

    so = await _lock_or_404(db, SalesOrder, inv.so_id, "Sales order")
    so_lines = {line.id: line for line in await _so_lines(db, so.id)}
    for line in await _inv_lines(db, inv.id):
        # Stock already left at issue, so voiding always returns it to stock,
        # then re-reserves for the SO when it is still open.
        await inventory_svc.apply_movement(
            db,
            item_id=line.item_id,
            location_id=inv.location_id,
            type="in",
            quantity=line.qty,
            reason=f"void invoice {inv.invoice_no}",
            reason_code="other",
            reference=f"SI-VOID:{inv.id}:{line.id}",
            user=_admin,
        )
        so_line = so_lines.get(line.so_line_id)
        if so_line is not None:
            so_line.invoiced_qty = max(0, so_line.invoiced_qty - line.qty)
        if so.status != "cancelled":
            await inventory_svc.reserve(
                db, item_id=line.item_id, location_id=inv.location_id, quantity=line.qty
            )
    await _recompute_so_status(db, so)

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
    return await _rc_outs_batch(db, rows)


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
    amount = _money(amount)
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
    rc = await _lock_or_404(db, InventoryReceipt, receipt_id, "Receipt")
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
        "invoice_total": _money(inv.total),
        "invoice_paid_total": paid,
        "invoice_balance": max(_money(inv.total) - paid - credited, _ZERO),
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
    return await _scn_outs_batch(db, rows)


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
        if inv_line.qty > 0:
            unit_amount = _money(_money(inv_line.amount) / inv_line.qty)
        else:
            unit_amount = _ZERO
        built.append(
            {
                "invoice_line_id": inv_line.id,
                "item_id": inv_line.item_id,
                "qty": inp.qty,
                "unit_amount": unit_amount,
                "amount": _money(inp.qty * unit_amount),
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
        total=sum((line["amount"] for line in built), _ZERO),
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
        scn.total = sum((line["amount"] for line in built), _ZERO)
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
    scn = await _lock_or_404(db, InventoryCreditNote, scn_id, "Credit note")
    if scn.status == "confirmed":
        return await _scn_out(db, scn)
    if scn.status != "draft":
        raise HTTPException(status_code=409, detail=f"credit note is {scn.status}; cannot confirm")

    inv = await _lock_or_404(db, InventoryInvoice, scn.invoice_id, "Invoice")
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
    if _money(scn.total) > balance:
        raise HTTPException(
            status_code=422,
            detail="credit exceeds unpaid balance; void the receipt first",
        )

    for line in lines:
        inv_line = inv_lines[line.invoice_line_id]
        if line.restock:
            await _assert_item_active_for_restock(db, line.item_id)
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
    scn = await _lock_or_404(db, InventoryCreditNote, scn_id, "Credit note")
    if scn.status == "void":
        return await _scn_out(db, scn)
    if scn.status != "confirmed":
        raise HTTPException(status_code=409, detail=f"credit note is {scn.status}; cannot void")

    await _lock_or_404(db, InventoryInvoice, scn.invoice_id, "Invoice")
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

    inv = await _create_invoice_tx(
        db,
        so,
        issue_date=body.issue_date,
        discount_amount=None,
        notes=None,
        line_inputs=[],
        user=_admin,
    )
    actions.append({"action": "CREATE", "table": "inventory_invoices", "desc": f"Created invoice for {so.so_no}"})
    await _issue_invoice_tx(db, inv, _admin, issue_date=body.issue_date)
    actions.append({"action": "UPDATE", "table": "inventory_invoices", "desc": f"Issued invoice {inv.invoice_no}"})

    do = None
    if body.deliver_now:
        do = await create_do_tx(
            db,
            inv,
            delivery_date=body.issue_date or date.today(),
            notes="quick fulfill",
            line_inputs=[],
            user=_admin,
        )
        actions.append({"action": "CREATE", "table": "delivery_orders", "desc": f"Created delivery order {do.do_no} for invoice {inv.invoice_no}"})
        await confirm_do_tx(db, do, _admin)
        actions.append({"action": "UPDATE", "table": "delivery_orders", "desc": f"Confirmed delivery order {do.do_no}"})

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

    so_id_v, do_id, inv_id = so.id, (do.id if do else None), inv.id
    receipt_id = receipt.id if receipt else None
    await db.commit()

    so = (await db.execute(select(SalesOrder).where(SalesOrder.id == so_id_v))).scalar_one()
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
    do_out = None
    if do_id:
        do = (await db.execute(select(DeliveryOrder).where(DeliveryOrder.id == do_id))).scalar_one()
        do_out = await _do_detail(db, do)
    receipt_out = None
    if receipt_id:
        rc = (await db.execute(select(InventoryReceipt).where(InventoryReceipt.id == receipt_id))).scalar_one()
        receipt_out = await _rc_out(db, rc)
    return {
        "so": await _so_detail(db, so),
        "delivery_order": do_out,
        "invoice": await _inv_detail(db, inv),
        "receipt": receipt_out,
    }
