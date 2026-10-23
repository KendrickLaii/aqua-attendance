import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Query, Response
from sqlalchemy import func, select

from app.config import settings
from app.deps import AdminOnly, DB
from app.models.inventory import InventoryItem, InventoryMovement, InventoryStock
from app.models.inventory_invoicing import (
    InventoryCreditNote,
    InventoryInvoice,
    InventoryInvoiceLine,
    InventoryReceipt,
)
from app.models.inventory_purchasing import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseReturn,
    PurchaseReturnLine,
    Supplier,
)
from app.models.inventory_sales import (
    Customer,
    SalesOrder,
    SalesOrderLine,
)
from app.models.location import Location
from app.schemas.inventory_reports import (
    AlertsOut,
    InventoryDashboard,
    MovementSummaryReport,
    NotifyResult,
    PurchasesReport,
    ReceivablesReport,
    SalesReport,
    StockValuationReport,
    WriteOffsReport,
)
from app.services import audit_log as audit_log_svc
from app.services import inventory_alerts as alerts_svc
from app.utils import csv_export

router = APIRouter(prefix="/inventory", tags=["inventory-reports"])

WRITE_OFF_REASONS = ("damage", "loss", "gift", "sample", "internal_use")


def _to_float(value) -> float:
    return round(float(value), 2) if value is not None else 0.0


def _dt_range(field, date_from: date | None, date_to: date | None):
    clauses = []
    if date_from is not None:
        clauses.append(field >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to is not None:
        clauses.append(field < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc))
    return clauses


def _csv_response(filename: str, header: list[str], rows: list[list]) -> Response:
    return csv_export.csv_response(filename, header, rows)


def _bucket(days: int) -> str:
    if days <= 30:
        return "0-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return "90+"


# ---------- stock valuation ----------


@router.get("/reports/stock-valuation", response_model=StockValuationReport)
async def stock_valuation(
    _admin: AdminOnly,
    db: DB,
    location_id: uuid.UUID | None = None,
    format: str | None = Query(default=None),
):
    # NOTE: value uses the item's global avg_cost — costs are not tracked
    # per-location, so every location is valued at the same unit cost.
    q = (
        select(InventoryStock, InventoryItem, Location)
        .join(InventoryItem, InventoryItem.id == InventoryStock.item_id)
        .outerjoin(Location, Location.id == InventoryStock.location_id)
        .where((InventoryStock.quantity > 0) | (InventoryStock.reserved > 0))
    )
    if location_id:
        q = q.where(InventoryStock.location_id == location_id)
    q = q.order_by(InventoryItem.sku_code)
    rows = []
    location_totals: dict[str, dict] = {}
    grand = 0.0
    for stock, item, loc in (await db.execute(q)).all():
        value = _to_float(stock.quantity * (item.avg_cost or 0))
        loc_name = loc.name_en or loc.name_zh or loc.code if loc else None
        rows.append(
            {
                "item_id": str(item.id),
                "sku_code": item.sku_code,
                "name_zh": item.name_zh,
                "location_id": str(stock.location_id),
                "location_name": loc_name,
                "quantity": stock.quantity,
                "reserved": stock.reserved,
                "available": stock.quantity - stock.reserved,
                "avg_cost": _to_float(item.avg_cost),
                "value": value,
            }
        )
        lt = location_totals.setdefault(
            str(stock.location_id), {"location_id": str(stock.location_id), "location_name": loc_name, "value": 0.0}
        )
        lt["value"] = round(lt["value"] + value, 2)
        grand = round(grand + value, 2)

    if format == "csv":
        csv_rows = [
            [r["sku_code"], r["name_zh"], r["location_name"] or "", r["quantity"], r["reserved"], r["available"], f"{r['avg_cost']:.2f}", f"{r['value']:.2f}"]
            for r in rows
        ]
        csv_rows.append(["TOTAL", "", "", "", "", "", "", f"{grand:.2f}"])
        return _csv_response(
            "stock-valuation.csv",
            ["SKU", "Item", "Location", "Quantity", "Reserved", "Available", "Avg cost", "Value"],
            csv_rows,
        )
    return {"rows": rows, "location_totals": list(location_totals.values()), "grand_total": grand}


# ---------- movements summary ----------


@router.get("/reports/movements-summary", response_model=MovementSummaryReport)
async def movements_summary(
    _admin: AdminOnly,
    db: DB,
    date_from: date | None = None,
    date_to: date | None = None,
    location_id: uuid.UUID | None = None,
    item_id: uuid.UUID | None = None,
    format: str | None = Query(default=None),
):
    clauses = _dt_range(InventoryMovement.created_at, date_from, date_to)
    if location_id:
        clauses.append(InventoryMovement.location_id == location_id)
    if item_id:
        clauses.append(InventoryMovement.item_id == item_id)

    rows_raw = (
        await db.execute(
            select(
                InventoryMovement.item_id,
                InventoryMovement.type,
                func.sum(InventoryMovement.quantity_delta),
            )
            .where(*clauses)
            .group_by(InventoryMovement.item_id, InventoryMovement.type)
        )
    ).all()
    reason_raw = (
        await db.execute(
            select(
                InventoryMovement.item_id,
                InventoryMovement.reason_code,
                func.sum(InventoryMovement.quantity_delta),
            )
            .where(*clauses)
            .group_by(InventoryMovement.item_id, InventoryMovement.reason_code)
        )
    ).all()

    per_item: dict[uuid.UUID, dict] = {}
    for iid, mtype, total in rows_raw:
        rec = per_item.setdefault(iid, {"qty_in": 0, "qty_out": 0, "qty_adjust": 0, "qty_transfer_in": 0, "qty_transfer_out": 0})
        rec[f"qty_{mtype}"] = int(total or 0)
    reasons: dict[uuid.UUID, dict[str, int]] = {}
    for iid, code, total in reason_raw:
        if code:
            reasons.setdefault(iid, {})[code] = int(total or 0)

    items = (
        await db.execute(select(InventoryItem).where(InventoryItem.id.in_(per_item.keys())))
    ).scalars().all() if per_item else []
    item_map = {i.id: i for i in items}

    rows = []
    totals = {"qty_in": 0, "qty_out": 0, "qty_adjust": 0, "qty_transfer_in": 0, "qty_transfer_out": 0, "net_change": 0}
    for iid, rec in sorted(per_item.items(), key=lambda kv: (item_map.get(kv[0]) and item_map[kv[0]].sku_code) or ""):
        net = sum(rec.values())
        item = item_map.get(iid)
        rows.append(
            {
                "item_id": str(iid),
                "sku_code": item.sku_code if item else str(iid),
                "name_zh": item.name_zh if item else "",
                **rec,
                "net_change": net,
                "reasons": reasons.get(iid, {}),
            }
        )
        for k in rec:
            totals[k] += rec[k]
        totals["net_change"] += net

    if format == "csv":
        csv_rows = [
            [
                r["sku_code"], r["name_zh"], r["qty_in"], r["qty_out"], r["qty_adjust"],
                r["qty_transfer_in"], r["qty_transfer_out"], r["net_change"],
                "; ".join(f"{k}:{v}" for k, v in r["reasons"].items()),
            ]
            for r in rows
        ]
        csv_rows.append(["TOTAL", "", totals["qty_in"], totals["qty_out"], totals["qty_adjust"], totals["qty_transfer_in"], totals["qty_transfer_out"], totals["net_change"], ""])
        return _csv_response(
            "movements-summary.csv",
            ["SKU", "Item", "In", "Out", "Adjust", "Transfer in", "Transfer out", "Net", "Reasons"],
            csv_rows,
        )
    return {"rows": rows, "totals": totals}


# ---------- purchases ----------


@router.get("/reports/purchases", response_model=PurchasesReport)
async def purchases_report(
    _admin: AdminOnly,
    db: DB,
    date_from: date | None = None,
    date_to: date | None = None,
    supplier_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    format: str | None = Query(default=None),
):
    rcv_clauses = [GoodsReceipt.status == "confirmed"]
    if date_from:
        rcv_clauses.append(GoodsReceipt.receipt_date >= date_from)
    if date_to:
        rcv_clauses.append(GoodsReceipt.receipt_date <= date_to)
    if supplier_id:
        rcv_clauses.append(GoodsReceipt.supplier_id == supplier_id)
    if location_id:
        rcv_clauses.append(GoodsReceipt.location_id == location_id)

    receipts = (
        await db.execute(
            select(
                GoodsReceipt.supplier_id,
                GoodsReceiptLine.item_id,
                func.sum(GoodsReceiptLine.qty),
                func.sum(GoodsReceiptLine.qty * GoodsReceiptLine.unit_cost),
            )
            .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.grn_id)
            .where(*rcv_clauses)
            .group_by(GoodsReceipt.supplier_id, GoodsReceiptLine.item_id)
        )
    ).all()

    ret_clauses = [PurchaseReturn.status == "confirmed"]
    if date_from:
        ret_clauses.append(PurchaseReturn.return_date >= date_from)
    if date_to:
        ret_clauses.append(PurchaseReturn.return_date <= date_to)
    if supplier_id:
        ret_clauses.append(PurchaseReturn.supplier_id == supplier_id)
    if location_id:
        ret_clauses.append(PurchaseReturn.location_id == location_id)

    returns = (
        await db.execute(
            select(
                PurchaseReturn.supplier_id,
                PurchaseReturnLine.item_id,
                func.sum(PurchaseReturnLine.qty),
                func.sum(PurchaseReturnLine.qty * PurchaseReturnLine.unit_cost),
            )
            .join(PurchaseReturn, PurchaseReturn.id == PurchaseReturnLine.prt_id)
            .where(*ret_clauses)
            .group_by(PurchaseReturn.supplier_id, PurchaseReturnLine.item_id)
        )
    ).all()

    agg: dict[tuple, dict] = {}
    for sid, iid, qty, val in receipts:
        rec = agg.setdefault((sid, iid), {"qty_received": 0, "value_received": 0.0, "qty_returned": 0, "value_returned": 0.0})
        rec["qty_received"] += int(qty or 0)
        rec["value_received"] += _to_float(val)
    for sid, iid, qty, val in returns:
        rec = agg.setdefault((sid, iid), {"qty_received": 0, "value_received": 0.0, "qty_returned": 0, "value_returned": 0.0})
        rec["qty_returned"] += int(qty or 0)
        rec["value_returned"] += _to_float(val)

    supplier_ids = {k[0] for k in agg}
    item_ids = {k[1] for k in agg}
    suppliers = (
        await db.execute(select(Supplier).where(Supplier.id.in_(supplier_ids)))
    ).scalars().all() if supplier_ids else []
    items = (
        await db.execute(select(InventoryItem).where(InventoryItem.id.in_(item_ids)))
    ).scalars().all() if item_ids else []
    sup_map = {s.id: s for s in suppliers}
    item_map = {i.id: i for i in items}

    rows = []
    totals = {"qty_received": 0, "value_received": 0.0, "qty_returned": 0, "value_returned": 0.0, "net_qty": 0, "net_value": 0.0}
    for (sid, iid), rec in sorted(agg.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        sup = sup_map.get(sid)
        item = item_map.get(iid)
        row = {
            "supplier_id": str(sid),
            "supplier_name": (sup.name_zh or sup.name_en) if sup else None,
            "item_id": str(iid),
            "sku_code": item.sku_code if item else str(iid),
            "name_zh": item.name_zh if item else "",
            **rec,
            "net_qty": rec["qty_received"] - rec["qty_returned"],
            "net_value": round(rec["value_received"] - rec["value_returned"], 2),
        }
        rows.append(row)
        for k in ("qty_received", "qty_returned"):
            totals[k] += row[k]
        for k in ("value_received", "value_returned"):
            totals[k] = round(totals[k] + row[k], 2)
        totals["net_qty"] += row["net_qty"]
        totals["net_value"] = round(totals["net_value"] + row["net_value"], 2)

    # open POs with outstanding qty
    po_clauses = [PurchaseOrder.status.in_(["ordered", "partial"])]
    if supplier_id:
        po_clauses.append(PurchaseOrder.supplier_id == supplier_id)
    if location_id:
        po_clauses.append(PurchaseOrder.location_id == location_id)
    open_pos = (
        await db.execute(
            select(
                PurchaseOrder,
                func.sum(PurchaseOrderLine.ordered_qty - PurchaseOrderLine.received_qty).label("oqty"),
                func.sum((PurchaseOrderLine.ordered_qty - PurchaseOrderLine.received_qty) * PurchaseOrderLine.unit_cost).label("oval"),
            )
            .join(PurchaseOrderLine, PurchaseOrderLine.po_id == PurchaseOrder.id)
            .where(*po_clauses)
            .group_by(PurchaseOrder.id)
        )
    ).all()
    sup_ids = {po.supplier_id for po, *_ in open_pos}
    po_sup = (
        await db.execute(select(Supplier).where(Supplier.id.in_(sup_ids)))
    ).scalars().all() if sup_ids else []
    po_sup_map = {s.id: s for s in po_sup}
    today = date.today()
    open_orders = [
        {
            "po_id": str(po.id),
            "po_no": po.po_no,
            "supplier_id": str(po.supplier_id),
            "supplier_name": (po_sup_map[po.supplier_id].name_zh or po_sup_map[po.supplier_id].name_en) if po.supplier_id in po_sup_map else None,
            "location_id": str(po.location_id),
            "order_date": po.order_date,
            "expected_date": po.expected_date,
            "status": po.status,
            "outstanding_qty": int(oqty or 0),
            "outstanding_value": _to_float(oval),
            "overdue": bool(po.expected_date and po.expected_date < today),
        }
        for po, oqty, oval in open_pos
        if int(oqty or 0) > 0
    ]

    if format == "csv":
        csv_rows = [
            [r["supplier_name"] or "", r["sku_code"], r["name_zh"], r["qty_received"], f"{r['value_received']:.2f}", r["qty_returned"], f"{r['value_returned']:.2f}", r["net_qty"], f"{r['net_value']:.2f}"]
            for r in rows
        ]
        csv_rows.append(["TOTAL", "", "", totals["qty_received"], f"{totals['value_received']:.2f}", totals["qty_returned"], f"{totals['value_returned']:.2f}", totals["net_qty"], f"{totals['net_value']:.2f}"])
        return _csv_response(
            "purchases.csv",
            ["Supplier", "SKU", "Item", "Qty received", "Value received", "Qty returned", "Value returned", "Net qty", "Net value"],
            csv_rows,
        )
    return {"rows": rows, "totals": totals, "open_orders": open_orders}


# ---------- sales ----------


@router.get("/reports/sales", response_model=SalesReport)
async def sales_report(
    _admin: AdminOnly,
    db: DB,
    date_from: date | None = None,
    date_to: date | None = None,
    customer_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    format: str | None = Query(default=None),
):
    inv_clauses = [InventoryInvoice.status == "issued"]
    if date_from:
        inv_clauses.append(InventoryInvoice.issue_date >= date_from)
    if date_to:
        inv_clauses.append(InventoryInvoice.issue_date <= date_to)
    if customer_id:
        inv_clauses.append(InventoryInvoice.customer_id == customer_id)
    if location_id:
        inv_clauses.append(InventoryInvoice.location_id == location_id)

    line_rows = (
        await db.execute(
            select(
                InventoryInvoice.issue_date,
                InventoryInvoice.customer_id,
                InventoryInvoiceLine.item_id,
                InventoryInvoiceLine.sku_code,
                InventoryInvoiceLine.name_zh,
                func.count(func.distinct(InventoryInvoice.id)),
                func.sum(InventoryInvoiceLine.qty),
                func.sum(InventoryInvoiceLine.amount),
            )
            .join(InventoryInvoiceLine, InventoryInvoiceLine.invoice_id == InventoryInvoice.id)
            .where(*inv_clauses)
            .group_by(
                InventoryInvoice.issue_date,
                InventoryInvoice.customer_id,
                InventoryInvoiceLine.item_id,
                InventoryInvoiceLine.sku_code,
                InventoryInvoiceLine.name_zh,
            )
        )
    ).all()

    invoiced_total = _to_float(
        (
            await db.execute(
                select(func.coalesce(func.sum(InventoryInvoice.total), 0)).where(*inv_clauses)
            )
        ).scalar_one()
    )
    # Row amounts are line-based (before invoice-level discount); the header
    # discount is reported separately so rows reconcile: invoiced = sum(rows)
    # - header_discounts.
    header_discounts = _to_float(
        (
            await db.execute(
                select(func.coalesce(func.sum(InventoryInvoice.discount_amount), 0)).where(
                    *inv_clauses
                )
            )
        ).scalar_one()
    )

    cn_clauses = [InventoryCreditNote.status == "confirmed"]
    if date_from:
        cn_clauses.append(InventoryCreditNote.credit_date >= date_from)
    if date_to:
        cn_clauses.append(InventoryCreditNote.credit_date <= date_to)
    if customer_id:
        cn_clauses.append(InventoryCreditNote.customer_id == customer_id)
    if location_id:
        cn_clauses.append(InventoryCreditNote.location_id == location_id)
    credited_total = _to_float(
        (
            await db.execute(
                select(func.coalesce(func.sum(InventoryCreditNote.total), 0)).where(*cn_clauses)
            )
        ).scalar_one()
    )

    rc_clauses = [InventoryReceipt.status == "posted"]
    if date_from:
        rc_clauses.append(InventoryReceipt.receipt_date >= date_from)
    if date_to:
        rc_clauses.append(InventoryReceipt.receipt_date <= date_to)
    if customer_id:
        rc_clauses.append(InventoryReceipt.customer_id == customer_id)
    if location_id:
        rc_clauses.append(InventoryReceipt.location_id == location_id)
    payments_total = _to_float(
        (
            await db.execute(
                select(func.coalesce(func.sum(InventoryReceipt.amount), 0)).where(*rc_clauses)
            )
        ).scalar_one()
    )

    cust_ids = {r[1] for r in line_rows}
    custs = (
        await db.execute(select(Customer).where(Customer.id.in_(cust_ids)))
    ).scalars().all() if cust_ids else []
    cust_map = {c.id: c for c in custs}

    rows = [
        {
            "date": r[0],
            "customer_id": str(r[1]),
            "customer_name": (cust_map[r[1]].name_zh or cust_map[r[1]].name_en) if r[1] in cust_map else None,
            "item_id": str(r[2]),
            "sku_code": r[3],
            "name_zh": r[4],
            "invoice_count": int(r[5] or 0),
            "qty": int(r[6] or 0),
            "amount": _to_float(r[7]),
        }
        for r in sorted(line_rows, key=lambda x: (x[0] or date.min, str(x[1]), x[3]))
    ]
    totals = {
        "invoiced": invoiced_total,
        "header_discounts": header_discounts,
        "credited": credited_total,
        "net_sales": round(invoiced_total - credited_total, 2),
        "payments": payments_total,
        "qty": sum(r["qty"] for r in rows),
        "invoice_count": sum(r["invoice_count"] for r in rows),
    }

    if format == "csv":
        csv_rows = [
            [r["date"].isoformat() if r["date"] else "", r["customer_name"] or "", r["sku_code"], r["name_zh"], r["invoice_count"], r["qty"], f"{r['amount']:.2f}"]
            for r in rows
        ]
        if header_discounts:
            csv_rows.append(["Header discounts", "", "", "", "", "", f"{-header_discounts:.2f}"])
        csv_rows.append(["TOTAL", "", "", "", totals["invoice_count"], totals["qty"], f"{totals['invoiced']:.2f}"])
        return _csv_response(
            "sales.csv",
            ["Date", "Customer", "SKU", "Item", "Invoices", "Qty", "Amount"],
            csv_rows,
        )
    return {"rows": rows, "totals": totals}


# ---------- receivables ----------


@router.get("/reports/receivables", response_model=ReceivablesReport)
async def receivables_report(
    _admin: AdminOnly,
    db: DB,
    as_of: date | None = None,
    customer_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    format: str | None = Query(default=None),
):
    as_of = as_of or date.today()
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
    balance_expr = InventoryInvoice.total - paid_col - cred_col

    q = (
        select(InventoryInvoice, paid_col.label("paid"), cred_col.label("credited"), balance_expr.label("balance"))
        .outerjoin(paid_sq, paid_sq.c.invoice_id == InventoryInvoice.id)
        .outerjoin(cred_sq, cred_sq.c.invoice_id == InventoryInvoice.id)
        .where(InventoryInvoice.status == "issued", balance_expr > 0)
    )
    if customer_id:
        q = q.where(InventoryInvoice.customer_id == customer_id)
    if location_id:
        q = q.where(InventoryInvoice.location_id == location_id)
    results = (await db.execute(q)).all()

    cust_ids = {r[0].customer_id for r in results}
    custs = (
        await db.execute(select(Customer).where(Customer.id.in_(cust_ids)))
    ).scalars().all() if cust_ids else []
    cust_map = {c.id: c for c in custs}

    rows = []
    customer_totals: dict[str, dict] = {}
    buckets = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
    grand = 0.0
    for inv, paid, credited, balance in sorted(results, key=lambda r: (r[0].issue_date or date.min, r[0].invoice_no or "")):
        days = (as_of - inv.issue_date).days if inv.issue_date else 0
        bucket = _bucket(days)
        cust = cust_map.get(inv.customer_id)
        cust_name = (cust.name_zh or cust.name_en) if cust else None
        bal = _to_float(balance)
        rows.append(
            {
                "invoice_id": str(inv.id),
                "invoice_no": inv.invoice_no,
                "customer_id": str(inv.customer_id),
                "customer_name": cust_name,
                "location_id": str(inv.location_id),
                "issue_date": inv.issue_date,
                "total": _to_float(inv.total),
                "paid": _to_float(paid),
                "credited": _to_float(credited),
                "balance": bal,
                "days_outstanding": days,
                "bucket": bucket,
            }
        )
        ct = customer_totals.setdefault(
            str(inv.customer_id), {"customer_id": str(inv.customer_id), "customer_name": cust_name, "balance": 0.0, "count": 0}
        )
        ct["balance"] = round(ct["balance"] + bal, 2)
        ct["count"] += 1
        buckets[bucket] = round(buckets[bucket] + bal, 2)
        grand = round(grand + bal, 2)

    if format == "csv":
        csv_rows = [
            [r["invoice_no"], r["customer_name"] or "", r["issue_date"].isoformat() if r["issue_date"] else "", f"{r['total']:.2f}", f"{r['paid']:.2f}", f"{r['credited']:.2f}", f"{r['balance']:.2f}", r["days_outstanding"], r["bucket"]]
            for r in rows
        ]
        csv_rows.append(["TOTAL", "", "", "", "", "", f"{grand:.2f}", "", ""])
        return _csv_response(
            "receivables.csv",
            ["Invoice", "Customer", "Issue date", "Total", "Paid", "Credited", "Balance", "Days", "Bucket"],
            csv_rows,
        )
    return {
        "rows": rows,
        "customer_totals": list(customer_totals.values()),
        "buckets": buckets,
        "grand_total": grand,
    }


# ---------- write-offs ----------


@router.get("/reports/write-offs", response_model=WriteOffsReport)
async def write_offs_report(
    _admin: AdminOnly,
    db: DB,
    date_from: date | None = None,
    date_to: date | None = None,
    location_id: uuid.UUID | None = None,
    format: str | None = Query(default=None),
):
    clauses = _dt_range(InventoryMovement.created_at, date_from, date_to)
    clauses += [
        InventoryMovement.type == "out",
        InventoryMovement.reason_code.in_(WRITE_OFF_REASONS),
    ]
    if location_id:
        clauses.append(InventoryMovement.location_id == location_id)

    raw = (
        await db.execute(
            select(
                InventoryMovement.reason_code,
                InventoryMovement.item_id,
                func.sum(-InventoryMovement.quantity_delta),
                func.sum(-InventoryMovement.quantity_delta * InventoryMovement.unit_cost),
            )
            .where(*clauses)
            .group_by(InventoryMovement.reason_code, InventoryMovement.item_id)
        )
    ).all()
    missing = (
        await db.execute(
            select(
                InventoryMovement.item_id,
                func.count(),
            )
            .where(*clauses, InventoryMovement.unit_cost.is_(None))
            .group_by(InventoryMovement.item_id)
        )
    ).all()
    missing_map = {iid: int(c) for iid, c in missing}

    item_ids = {r[1] for r in raw}
    items = (
        await db.execute(select(InventoryItem).where(InventoryItem.id.in_(item_ids)))
    ).scalars().all() if item_ids else []
    item_map = {i.id: i for i in items}

    rows = []
    totals = {"qty": 0, "cost": 0.0, "cost_missing": 0}
    for code, iid, qty, cost in sorted(raw, key=lambda r: (r[0], str(r[1]))):
        item = item_map.get(iid)
        row = {
            "reason_code": code,
            "item_id": str(iid),
            "sku_code": item.sku_code if item else str(iid),
            "name_zh": item.name_zh if item else "",
            "qty": int(qty or 0),
            "cost": _to_float(cost),
            "cost_missing": missing_map.get(iid, 0),
        }
        rows.append(row)
        totals["qty"] += row["qty"]
        totals["cost"] = round(totals["cost"] + row["cost"], 2)
        totals["cost_missing"] += row["cost_missing"]

    if format == "csv":
        csv_rows = [
            [r["reason_code"], r["sku_code"], r["name_zh"], r["qty"], f"{r['cost']:.2f}", r["cost_missing"]]
            for r in rows
        ]
        csv_rows.append(["TOTAL", "", "", totals["qty"], f"{totals['cost']:.2f}", totals["cost_missing"]])
        return _csv_response(
            "write-offs.csv",
            ["Reason", "SKU", "Item", "Qty", "Cost", "Cost missing"],
            csv_rows,
        )
    return {"rows": rows, "totals": totals}


# ---------- dashboard ----------


def _month_start(today: date) -> date:
    return today.replace(day=1)


@router.get("/dashboard", response_model=InventoryDashboard)
async def inventory_dashboard(
    _admin: AdminOnly,
    db: DB,
    location_id: uuid.UUID | None = None,
):
    today = date.today()
    month_start = _month_start(today)

    tracked = (
        await db.execute(select(func.count()).select_from(InventoryItem).where(InventoryItem.is_active.is_(True)))
    ).scalar_one()

    low_q = (
        select(func.count())
        .select_from(InventoryStock)
        .join(InventoryItem, InventoryItem.id == InventoryStock.item_id)
        .where(
            InventoryItem.is_active.is_(True),
            InventoryItem.reorder_level > 0,
            InventoryStock.quantity <= InventoryItem.reorder_level,
        )
    )
    if location_id:
        low_q = low_q.where(InventoryStock.location_id == location_id)
    low_stock = (await db.execute(low_q)).scalar_one()

    val_q = (
        select(func.coalesce(func.sum(InventoryStock.quantity * InventoryItem.avg_cost), 0))
        .select_from(InventoryStock)
        .join(InventoryItem, InventoryItem.id == InventoryStock.item_id)
    )
    if location_id:
        val_q = val_q.where(InventoryStock.location_id == location_id)
    stock_value = _to_float((await db.execute(val_q)).scalar_one())

    po_q = select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.status.in_(["ordered", "partial"]))
    po_overdue_q = po_q.where(PurchaseOrder.expected_date.is_not(None), PurchaseOrder.expected_date < today)
    if location_id:
        po_q = po_q.where(PurchaseOrder.location_id == location_id)
        po_overdue_q = po_overdue_q.where(PurchaseOrder.location_id == location_id)
    open_pos = (await db.execute(po_q)).scalar_one()
    overdue_pos = (await db.execute(po_overdue_q)).scalar_one()

    so_q = select(func.count()).select_from(SalesOrder).where(SalesOrder.status.in_(["confirmed", "partial"]))
    if location_id:
        so_q = so_q.where(SalesOrder.location_id == location_id)
    open_sos = (await db.execute(so_q)).scalar_one()

    uninvoiced_q = (
        select(func.coalesce(func.sum(SalesOrderLine.qty - SalesOrderLine.invoiced_qty), 0))
        .select_from(SalesOrderLine)
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.so_id)
        .where(SalesOrder.status.in_(["confirmed", "partial"]))
    )
    if location_id:
        uninvoiced_q = uninvoiced_q.where(SalesOrder.location_id == location_id)
    uninvoiced = int((await db.execute(uninvoiced_q)).scalar_one() or 0)

    # Issued invoices with something still undelivered (credits count as
    # settling undelivered goods first).
    undelivered_expr = InventoryInvoiceLine.qty - InventoryInvoiceLine.credited_qty - InventoryInvoiceLine.delivered_qty
    undel_q = (
        select(func.count(func.distinct(InventoryInvoice.id)), func.coalesce(func.sum(undelivered_expr), 0))
        .select_from(InventoryInvoiceLine)
        .join(InventoryInvoice, InventoryInvoice.id == InventoryInvoiceLine.invoice_id)
        .where(InventoryInvoice.status == "issued", undelivered_expr > 0)
    )
    if location_id:
        undel_q = undel_q.where(InventoryInvoice.location_id == location_id)
    undel_count, undel_qty_raw = (await db.execute(undel_q)).one()
    undelivered_invoice_count = int(undel_count or 0)
    undelivered_qty = int(undel_qty_raw or 0)

    paid_sq = (
        select(InventoryReceipt.invoice_id.label("iid"), func.coalesce(func.sum(InventoryReceipt.amount), 0).label("paid"))
        .where(InventoryReceipt.status == "posted")
        .group_by(InventoryReceipt.invoice_id)
        .subquery()
    )
    cred_sq = (
        select(InventoryCreditNote.invoice_id.label("iid"), func.coalesce(func.sum(InventoryCreditNote.total), 0).label("cred"))
        .where(InventoryCreditNote.status == "confirmed")
        .group_by(InventoryCreditNote.invoice_id)
        .subquery()
    )
    bal = InventoryInvoice.total - func.coalesce(paid_sq.c.paid, 0) - func.coalesce(cred_sq.c.cred, 0)
    recv_q = (
        select(func.count(), func.coalesce(func.sum(bal), 0))
        .select_from(InventoryInvoice)
        .outerjoin(paid_sq, paid_sq.c.iid == InventoryInvoice.id)
        .outerjoin(cred_sq, cred_sq.c.iid == InventoryInvoice.id)
        .where(InventoryInvoice.status == "issued", bal > 0)
    )
    if location_id:
        recv_q = recv_q.where(InventoryInvoice.location_id == location_id)
    unpaid_count, receivable = (await db.execute(recv_q)).one()

    cutoff = today - timedelta(days=settings.INVENTORY_INVOICE_OVERDUE_DAYS)
    overdue_recv_q = (
        select(func.coalesce(func.sum(bal), 0))
        .select_from(InventoryInvoice)
        .outerjoin(paid_sq, paid_sq.c.iid == InventoryInvoice.id)
        .outerjoin(cred_sq, cred_sq.c.iid == InventoryInvoice.id)
        .where(InventoryInvoice.status == "issued", bal > 0, InventoryInvoice.issue_date < cutoff)
    )
    if location_id:
        overdue_recv_q = overdue_recv_q.where(InventoryInvoice.location_id == location_id)
    overdue_receivable = _to_float((await db.execute(overdue_recv_q)).scalar_one())

    ms_q = select(func.coalesce(func.sum(InventoryInvoice.total), 0)).where(
        InventoryInvoice.status == "issued", InventoryInvoice.issue_date >= month_start
    )
    mc_q = select(func.coalesce(func.sum(InventoryCreditNote.total), 0)).where(
        InventoryCreditNote.status == "confirmed", InventoryCreditNote.credit_date >= month_start
    )
    mp_q = (
        select(func.coalesce(func.sum(GoodsReceiptLine.qty * GoodsReceiptLine.unit_cost), 0))
        .select_from(GoodsReceiptLine)
        .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.grn_id)
        .where(GoodsReceipt.status == "confirmed", GoodsReceipt.receipt_date >= month_start)
    )
    mr_q = (
        select(func.coalesce(func.sum(PurchaseReturnLine.qty * PurchaseReturnLine.unit_cost), 0))
        .select_from(PurchaseReturnLine)
        .join(PurchaseReturn, PurchaseReturn.id == PurchaseReturnLine.prt_id)
        .where(PurchaseReturn.status == "confirmed", PurchaseReturn.return_date >= month_start)
    )
    if location_id:
        ms_q = ms_q.where(InventoryInvoice.location_id == location_id)
        mc_q = mc_q.where(InventoryCreditNote.location_id == location_id)
        mp_q = mp_q.where(GoodsReceipt.location_id == location_id)
        mr_q = mr_q.where(PurchaseReturn.location_id == location_id)
    month_invoiced = _to_float((await db.execute(ms_q)).scalar_one())
    month_credited = _to_float((await db.execute(mc_q)).scalar_one())
    month_purchases_gross = _to_float((await db.execute(mp_q)).scalar_one())
    month_purchase_returns = _to_float((await db.execute(mr_q)).scalar_one())
    month_sales = month_invoiced - month_credited
    month_purchases = month_purchases_gross - month_purchase_returns

    return {
        "tracked_items": int(tracked),
        "low_stock_count": int(low_stock),
        "stock_value": stock_value,
        "open_purchase_orders": int(open_pos),
        "overdue_purchase_orders": int(overdue_pos),
        "open_sales_orders": int(open_sos),
        "uninvoiced_qty": uninvoiced,
        "undelivered_invoice_count": undelivered_invoice_count,
        "undelivered_qty": undelivered_qty,
        "unpaid_invoice_count": int(unpaid_count or 0),
        "receivable_balance": _to_float(receivable),
        "overdue_receivable_balance": overdue_receivable,
        "month_sales": round(month_sales, 2),
        "month_purchases": round(month_purchases, 2),
        "month_invoiced": round(month_invoiced, 2),
        "month_credited": round(month_credited, 2),
        "month_purchases_gross": round(month_purchases_gross, 2),
        "month_purchase_returns": round(month_purchase_returns, 2),
    }


# ---------- alerts ----------


@router.get("/alerts", response_model=AlertsOut)
async def get_alerts(
    _admin: AdminOnly,
    db: DB,
    location_id: uuid.UUID | None = None,
):
    return await alerts_svc.compute_alerts(db, location_id=location_id)


@router.post("/alerts/notify", response_model=NotifyResult)
async def notify_alerts_now(
    _admin: AdminOnly,
    db: DB,
    location_id: uuid.UUID | None = None,
):
    result = await alerts_svc.notify_alerts(db, location_id=location_id)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="notifications",
        record_id=None,
        new_values=result,
        description=f"Inventory alerts notify: {result['created']} created, {result['skipped']} skipped",
    )
    return result
