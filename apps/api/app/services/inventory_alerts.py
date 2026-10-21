import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, text

from app.config import settings
from app.models.inventory import InventoryItem, InventoryStock
from app.models.inventory_invoicing import (
    InventoryCreditNote,
    InventoryInvoice,
    InventoryReceipt,
)
from app.models.inventory_purchasing import PurchaseOrder
from app.models.inventory_sales import SalesOrder
from app.models.notification import Notification
from app.models.user import User


async def _invoice_balance_map(db, invoice_ids: list[uuid.UUID]) -> dict[uuid.UUID, float]:
    if not invoice_ids:
        return {}
    paid_sq = (
        select(
            InventoryReceipt.invoice_id.label("invoice_id"),
            func.coalesce(func.sum(InventoryReceipt.amount), 0).label("paid"),
        )
        .where(InventoryReceipt.status == "posted", InventoryReceipt.invoice_id.in_(invoice_ids))
        .group_by(InventoryReceipt.invoice_id)
        .subquery()
    )
    cred_sq = (
        select(
            InventoryCreditNote.invoice_id.label("invoice_id"),
            func.coalesce(func.sum(InventoryCreditNote.total), 0).label("credited"),
        )
        .where(InventoryCreditNote.status == "confirmed", InventoryCreditNote.invoice_id.in_(invoice_ids))
        .group_by(InventoryCreditNote.invoice_id)
        .subquery()
    )
    q = (
        select(
            InventoryInvoice.id,
            InventoryInvoice.total,
            func.coalesce(paid_sq.c.paid, 0),
            func.coalesce(cred_sq.c.credited, 0),
        )
        .outerjoin(paid_sq, paid_sq.c.invoice_id == InventoryInvoice.id)
        .outerjoin(cred_sq, cred_sq.c.invoice_id == InventoryInvoice.id)
        .where(InventoryInvoice.id.in_(invoice_ids))
    )
    rows = (await db.execute(q)).all()
    return {row.id: max(float(row.total) - float(row[2]) - float(row[3]), 0.0) for row in rows}


async def compute_alerts(db, location_id: uuid.UUID | None = None) -> dict:
    """Live-computed inventory alerts; no persistence."""
    today = date.today()

    stock_q = (
        select(InventoryStock, InventoryItem)
        .join(InventoryItem, InventoryItem.id == InventoryStock.item_id)
        .where(
            InventoryItem.is_active.is_(True),
            InventoryItem.reorder_level > 0,
            InventoryStock.quantity <= InventoryItem.reorder_level,
        )
    )
    if location_id:
        stock_q = stock_q.where(InventoryStock.location_id == location_id)
    low_stock = [
        {
            "item_id": str(stock.item_id),
            "location_id": str(stock.location_id),
            "sku_code": item.sku_code,
            "name_zh": item.name_zh,
            "quantity": stock.quantity,
            "reorder_level": item.reorder_level,
        }
        for stock, item in (await db.execute(stock_q)).all()
    ]

    po_q = select(PurchaseOrder).where(
        PurchaseOrder.status.in_(["ordered", "partial"]),
        PurchaseOrder.expected_date.is_not(None),
        PurchaseOrder.expected_date < today,
    )
    if location_id:
        po_q = po_q.where(PurchaseOrder.location_id == location_id)
    overdue_purchase_orders = [
        {
            "id": str(po.id),
            "po_no": po.po_no,
            "expected_date": po.expected_date.isoformat() if po.expected_date else None,
            "status": po.status,
        }
        for po in (await db.execute(po_q)).scalars().all()
    ]

    cutoff = today - timedelta(days=settings.INVENTORY_INVOICE_OVERDUE_DAYS)
    inv_q = select(InventoryInvoice).where(
        InventoryInvoice.status == "issued",
        InventoryInvoice.issue_date.is_not(None),
        InventoryInvoice.issue_date < cutoff,
    )
    if location_id:
        inv_q = inv_q.where(InventoryInvoice.location_id == location_id)
    overdue_invs = (await db.execute(inv_q)).scalars().all()
    balances = await _invoice_balance_map(db, [inv.id for inv in overdue_invs])
    overdue_invoices = [
        {
            "id": str(inv.id),
            "invoice_no": inv.invoice_no,
            "buyer_name": inv.buyer_name,
            "issue_date": inv.issue_date.isoformat() if inv.issue_date else None,
            "balance": balances[inv.id],
        }
        for inv in overdue_invs
        if balances.get(inv.id, 0) > 0
    ]

    pf_q = select(SalesOrder).where(
        SalesOrder.status.in_(["draft", "confirmed"]),
        SalesOrder.pf_no.is_not(None),
        SalesOrder.pf_valid_until.is_not(None),
        SalesOrder.pf_valid_until < today,
    )
    if location_id:
        pf_q = pf_q.where(SalesOrder.location_id == location_id)
    expiring_proformas = [
        {
            "id": str(so.id),
            "so_no": so.so_no,
            "pf_no": so.pf_no,
            "pf_valid_until": so.pf_valid_until.isoformat() if so.pf_valid_until else None,
        }
        for so in (await db.execute(pf_q)).scalars().all()
    ]

    return {
        "low_stock": low_stock,
        "overdue_purchase_orders": overdue_purchase_orders,
        "overdue_invoices": overdue_invoices,
        "expiring_proformas": expiring_proformas,
    }


_KINDS = {
    "low_stock": ("medium", "/attendance/inventory"),
    "overdue_purchase_orders": ("medium", "/attendance/inventory/purchase-orders"),
    "overdue_invoices": ("high", "/attendance/inventory/invoices"),
    "expiring_proformas": ("medium", "/attendance/inventory/sales-orders"),
}

_TITLES = {
    "low_stock": "Low stock",
    "overdue_purchase_orders": "Overdue purchase order",
    "overdue_invoices": "Overdue invoice",
    "expiring_proformas": "Expiring proforma",
}


def _describe(kind: str, item: dict) -> tuple[str, str]:
    if kind == "low_stock":
        return item["sku_code"], f"{item['sku_code']} {item['name_zh']}: {item['quantity']} on hand (reorder level {item['reorder_level']})"
    if kind == "overdue_purchase_orders":
        return item["id"], f"{item['po_no']} was expected {item['expected_date']} (status {item['status']})"
    if kind == "overdue_invoices":
        return item["id"], f"{item['invoice_no']} for {item['buyer_name']} has balance {item['balance']:.2f} since {item['issue_date']}"
    return item["id"], f"{item['pf_no']} ({item['so_no']}) expired {item['pf_valid_until']}"


# Transaction-scoped advisory lock key for notify_alerts (Postgres only);
# serializes the loop + manual /alerts/notify across app workers.
_ADVISORY_LOCK_KEY = 727401
# An alert for the same (user, kind, ref) is not re-sent within this window
# even if the earlier notification was already read.
DEDUPE_WINDOW_DAYS = 7


async def notify_alerts(db, location_id: uuid.UUID | None = None) -> dict:
    """Create one notification per alert item per active admin user.

    Deduped on extra_data {"inventory_alert": kind, "ref": ref}: skipped when
    an unread notification exists or one was created within
    DEDUPE_WINDOW_DAYS. On Postgres a transaction-scoped advisory lock
    serializes concurrent runs across workers; a loser returns early with
    ``locked=True``. Caller commits.
    """
    if db.get_bind().dialect.name == "postgresql":
        acquired = (
            await db.execute(
                text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": _ADVISORY_LOCK_KEY}
            )
        ).scalar()
        if not acquired:
            return {"created": 0, "skipped": 0, "locked": True}

    alerts = await compute_alerts(db, location_id=location_id)
    users = (
        await db.execute(
            select(User).where(User.is_active.is_(True), User.role.in_(["admin", "superadmin"]))
        )
    ).scalars().all()

    # Load unread inventory-alert notifications plus all alert notifications
    # from the dedupe window; match kind+ref in Python (extra_data is generic
    # JSON — astext is not portable across dialects).
    window_start = datetime.now(timezone.utc) - timedelta(days=DEDUPE_WINDOW_DAYS)
    existing_rows = (
        await db.execute(
            select(Notification.user_id, Notification.extra_data).where(
                (Notification.is_read.is_(False)) | (Notification.created_at >= window_start),
                Notification.user_id.in_([u.id for u in users]) if users else Notification.user_id.is_(None),
            )
        )
    ).all()
    seen = {
        (user_id, (extra or {}).get("inventory_alert"), (extra or {}).get("ref"))
        for user_id, extra in existing_rows
        if extra and extra.get("inventory_alert")
    }

    created = 0
    skipped = 0
    for kind, items in alerts.items():
        priority, action_url = _KINDS[kind]
        title = _TITLES[kind]
        for item in items:
            _ref, message = _describe(kind, item)
            ref = str(item.get("id") or f"{item.get('item_id')}:{item.get('location_id')}")
            for user in users:
                if (user.id, kind, ref) in seen:
                    skipped += 1
                    continue
                seen.add((user.id, kind, ref))
                db.add(
                    Notification(
                        user_id=user.id,
                        title=f"{title}: {item.get('sku_code') or item.get('po_no') or item.get('invoice_no') or item.get('pf_no')}",
                        message=message,
                        notification_type="reminder",
                        priority=priority,
                        action_url=action_url,
                        extra_data={"inventory_alert": kind, "ref": ref},
                    )
                )
                created += 1
    if created:
        await db.flush()
    return {"created": created, "skipped": skipped, "locked": False}
