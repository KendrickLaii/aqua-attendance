import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.notification import Notification
from tests.conftest import TestSessionLocal, _insert_test_user

pytestmark = pytest.mark.asyncio

TODAY = date.today()


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_item(client: AsyncClient, token: str, **overrides) -> dict:
    body = {"sku_code": f"ITM-{uuid.uuid4().hex[:6]}", "name_zh": "課本", **overrides}
    resp = await client.post("/api/inventory/items", json=body, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_customer(client: AsyncClient, token: str, **overrides) -> dict:
    body = {"code": f"CUS-{uuid.uuid4().hex[:6]}", "name_zh": "客戶", **overrides}
    resp = await client.post("/api/inventory/customers", json=body, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_supplier(client: AsyncClient, token: str, **overrides) -> dict:
    body = {"code": f"SUP-{uuid.uuid4().hex[:6]}", "name_zh": "供應商", **overrides}
    resp = await client.post("/api/inventory/suppliers", json=body, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _move(client, token, item_id, location_id, type, quantity, **extra) -> dict:
    resp = await client.post(
        "/api/inventory/movements",
        json={
            "item_id": item_id,
            "location_id": location_id,
            "type": type,
            "quantity": quantity,
            **extra,
        },
        headers=_h(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_location(client: AsyncClient, token: str) -> dict:
    resp = await client.post(
        "/api/locations",
        json={"name_en": f"Loc-{uuid.uuid4().hex[:6]}", "code": f"L{uuid.uuid4().hex[:4]}"},
        headers=_h(token),
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


async def _quick_invoice(
    client, token, customer_id, location_id, item_id, qty, price, issue_date, **so_extra
) -> dict:
    """SO confirm → DO confirm → invoice → issue, in the given issue_date."""
    resp = await client.post(
        "/api/inventory/sales-orders",
        json={
            "customer_id": customer_id,
            "location_id": location_id,
            "order_date": issue_date,
            "lines": [{"item_id": item_id, "qty": qty, "unit_price": price, **so_extra}],
        },
        headers=_h(token),
    )
    assert resp.status_code == 201, resp.text
    so = resp.json()
    resp = await client.post(f"/api/inventory/sales-orders/{so['id']}/confirm", headers=_h(token))
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        "/api/inventory/delivery-orders",
        json={"so_id": so["id"], "delivery_date": issue_date},
        headers=_h(token),
    )
    assert resp.status_code == 201, resp.text
    do = resp.json()
    resp = await client.post(f"/api/inventory/delivery-orders/{do['id']}/confirm", headers=_h(token))
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        "/api/inventory/invoices",
        json={"do_id": do["id"], "issue_date": issue_date},
        headers=_h(token),
    )
    assert resp.status_code == 201, resp.text
    inv = resp.json()
    resp = await client.post(f"/api/inventory/invoices/{inv['id']}/issue", headers=_h(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---- stock valuation ----


async def test_stock_valuation_math_and_location_filter(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    loc2 = await _create_location(client, admin_token)
    item = await _create_item(client, admin_token, cost_price=10.0)
    # in movements don't set avg_cost — set it via GRN or direct? use purchase GRN to set avg_cost=10
    supplier = await _create_supplier(client, admin_token)
    po = await client.post(
        "/api/inventory/purchase-orders",
        json={
            "supplier_id": supplier["id"], "location_id": loc,
            "order_date": "2026-10-01",
            "lines": [{"item_id": item["id"], "ordered_qty": 5, "unit_cost": 10.0}],
        },
        headers=_h(admin_token),
    )
    po = po.json()
    await client.post(f"/api/inventory/purchase-orders/{po['id']}/order", headers=_h(admin_token))
    grn = await client.post(
        "/api/inventory/goods-receipts",
        json={"supplier_id": supplier["id"], "location_id": loc, "receipt_date": "2026-10-02", "po_id": po["id"]},
        headers=_h(admin_token),
    )
    grn = grn.json()
    await client.post(f"/api/inventory/goods-receipts/{grn['id']}/confirm", headers=_h(admin_token))
    await _move(client, admin_token, item["id"], loc2["id"], "in", 3)

    resp = await client.get("/api/inventory/reports/stock-valuation", headers=_h(admin_token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    our = [r for r in data["rows"] if r["item_id"] == item["id"]]
    assert len(our) == 2  # two locations
    row_loc = next(r for r in our if r["location_id"] == loc)
    assert row_loc["quantity"] == 5
    assert row_loc["avg_cost"] == pytest.approx(10.0)
    assert row_loc["value"] == pytest.approx(50.0)
    row_loc2 = next(r for r in our if r["location_id"] == loc2["id"])
    assert row_loc2["value"] == pytest.approx(30.0)

    resp = await client.get(
        f"/api/inventory/reports/stock-valuation?location_id={loc2['id']}", headers=_h(admin_token)
    )
    ours = [r for r in resp.json()["rows"] if r["item_id"] == item["id"]]
    assert len(ours) == 1 and ours[0]["quantity"] == 3

    # CSV export
    resp = await client.get(
        "/api/inventory/reports/stock-valuation?format=csv", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    text = resp.content.decode("utf-8-sig")
    lines = [l for l in text.strip().splitlines() if l]
    assert lines[0].startswith("SKU")
    assert lines[-1].startswith("TOTAL")
    assert any(item["sku_code"] in l for l in lines)


# ---- movements summary ----


async def test_movements_summary_types_and_reasons(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10, reason_code="opening")
    await _move(client, admin_token, item["id"], loc, "out", 3, reason_code="damage", reason="broken")
    await _move(client, admin_token, item["id"], loc, "out", 2, reason_code="sale")
    await _move(client, admin_token, item["id"], loc, "adjust", 4)

    resp = await client.get(
        f"/api/inventory/reports/movements-summary?item_id={item['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 200, resp.text
    rows = [r for r in resp.json()["rows"] if r["item_id"] == item["id"]]
    assert len(rows) == 1
    r = rows[0]
    assert r["qty_in"] == 10
    assert r["qty_out"] == -5
    assert r["qty_adjust"] == -1  # adjust to 4 from 5
    assert r["net_change"] == 4
    assert r["reasons"]["damage"] == -3
    assert r["reasons"]["sale"] == -2
    assert r["reasons"]["opening"] == 10

    # date range: today only should still include them (created today)
    resp = await client.get(
        f"/api/inventory/reports/movements-summary?item_id={item['id']}&date_from={TODAY.isoformat()}&date_to={TODAY.isoformat()}",
        headers=_h(admin_token),
    )
    assert any(r["item_id"] == item["id"] for r in resp.json()["rows"])
    # a range in the future excludes them
    future = (TODAY + timedelta(days=30)).isoformat()
    resp = await client.get(
        f"/api/inventory/reports/movements-summary?item_id={item['id']}&date_from={future}",
        headers=_h(admin_token),
    )
    assert not any(r["item_id"] == item["id"] for r in resp.json()["rows"])


# ---- purchases report ----


async def test_purchases_net_of_returns_and_open_orders(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    supplier = await _create_supplier(client, admin_token, name_zh="報表供應商")
    item = await _create_item(client, admin_token)
    today = TODAY.isoformat()

    po = await client.post(
        "/api/inventory/purchase-orders",
        json={
            "supplier_id": supplier["id"], "location_id": loc,
            "order_date": today, "expected_date": "2020-01-01",
            "lines": [{"item_id": item["id"], "ordered_qty": 10, "unit_cost": 20.0}],
        },
        headers=_h(admin_token),
    )
    po = po.json()
    await client.post(f"/api/inventory/purchase-orders/{po['id']}/order", headers=_h(admin_token))

    # receive 6 of 10
    grn = await client.post(
        "/api/inventory/goods-receipts",
        json={
            "supplier_id": supplier["id"], "location_id": loc, "receipt_date": today,
            "po_id": po["id"],
            "lines": [{"po_line_id": po["lines"][0]["id"], "item_id": item["id"], "qty": 6, "unit_cost": 20.0}],
        },
        headers=_h(admin_token),
    )
    grn = grn.json()
    await client.post(f"/api/inventory/goods-receipts/{grn['id']}/confirm", headers=_h(admin_token))

    # return 2
    prt = await client.post(
        "/api/inventory/purchase-returns",
        json={
            "supplier_id": supplier["id"], "location_id": loc, "return_date": today,
            "grn_id": grn["id"],
            "lines": [{"item_id": item["id"], "qty": 2, "unit_cost": 20.0}],
        },
        headers=_h(admin_token),
    )
    assert prt.status_code == 201, prt.text
    prt = prt.json()
    await client.post(f"/api/inventory/purchase-returns/{prt['id']}/confirm", headers=_h(admin_token))

    resp = await client.get(
        f"/api/inventory/reports/purchases?supplier_id={supplier['id']}&date_from={today}&date_to={today}",
        headers=_h(admin_token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    row = next(r for r in data["rows"] if r["item_id"] == item["id"])
    assert row["qty_received"] == 6
    assert row["value_received"] == pytest.approx(120.0)
    assert row["qty_returned"] == 2
    assert row["value_returned"] == pytest.approx(40.0)
    assert row["net_qty"] == 4
    assert row["net_value"] == pytest.approx(80.0)

    open_po = next(o for o in data["open_orders"] if o["po_id"] == po["id"])
    assert open_po["outstanding_qty"] == 4
    assert open_po["outstanding_value"] == pytest.approx(80.0)
    assert open_po["overdue"] is True  # expected_date 2020


# ---- sales report ----


async def test_sales_report_invoiced_credited_payments(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token, name_zh="報表客戶")
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 20)
    today = TODAY.isoformat()

    inv = await _quick_invoice(client, admin_token, customer["id"], loc, item["id"], 4, 100.0, today)
    # partial credit 1
    resp = await client.post(
        "/api/inventory/credit-notes",
        json={
            "invoice_id": inv["id"], "reason": "r", "credit_date": today,
            "lines": [{"invoice_line_id": inv["lines"][0]["id"], "qty": 1, "restock": False}],
        },
        headers=_h(admin_token),
    )
    scn = resp.json()
    await client.post(f"/api/inventory/credit-notes/{scn['id']}/confirm", headers=_h(admin_token))
    # payment 200
    await client.post(
        "/api/inventory/receipts",
        json={"invoice_id": inv["id"], "amount": 200.0, "paid_by": "cash", "receipt_date": today},
        headers=_h(admin_token),
    )

    resp = await client.get(
        f"/api/inventory/reports/sales?customer_id={customer['id']}&date_from={today}&date_to={today}",
        headers=_h(admin_token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["totals"]["invoiced"] == pytest.approx(400.0)
    assert data["totals"]["credited"] == pytest.approx(100.0)
    assert data["totals"]["net_sales"] == pytest.approx(300.0)
    assert data["totals"]["payments"] == pytest.approx(200.0)
    row = next(r for r in data["rows"] if r["item_id"] == item["id"])
    assert row["qty"] == 4
    assert row["amount"] == pytest.approx(400.0)

    # outside range → nothing
    old = "2020-01-01"
    resp = await client.get(
        f"/api/inventory/reports/sales?customer_id={customer['id']}&date_from={old}&date_to={old}",
        headers=_h(admin_token),
    )
    assert resp.json()["totals"]["invoiced"] == 0


# ---- receivables ----


async def _make_unpaid_invoice(client, token, customer_id, loc, qty=1, days_ago=0) -> dict:
    item = await _create_item(client, token)
    await _move(client, token, item["id"], loc, "in", qty + 5)
    issue_date = (TODAY - timedelta(days=days_ago)).isoformat()
    return await _quick_invoice(client, token, customer_id, loc, item["id"], qty, 100.0, issue_date)


async def test_receivables_aging_buckets_and_as_of(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    as_of = TODAY
    for days in (30, 31, 60, 61, 90, 91):
        await _make_unpaid_invoice(client, admin_token, customer["id"], loc, days_ago=days)

    resp = await client.get(
        f"/api/inventory/reports/receivables?as_of={as_of.isoformat()}&customer_id={customer['id']}",
        headers=_h(admin_token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    rows = data["rows"]
    assert len(rows) == 6
    by_days = {r["days_outstanding"]: r["bucket"] for r in rows}
    assert by_days[30] == "0-30"
    assert by_days[31] == "31-60"
    assert by_days[60] == "31-60"
    assert by_days[61] == "61-90"
    assert by_days[90] == "61-90"
    assert by_days[91] == "90+"
    assert data["grand_total"] == pytest.approx(600.0)
    assert data["buckets"]["0-30"] == pytest.approx(100.0)
    assert data["buckets"]["90+"] == pytest.approx(100.0)
    assert data["customer_totals"][0]["balance"] == pytest.approx(600.0)

    # partial payment reduces balance
    inv30 = next(r for r in rows if r["days_outstanding"] == 30)
    await client.post(
        "/api/inventory/receipts",
        json={"invoice_id": inv30["invoice_id"], "amount": 40.0, "paid_by": "cash"},
        headers=_h(admin_token),
    )
    resp = await client.get(
        f"/api/inventory/reports/receivables?as_of={as_of.isoformat()}&customer_id={customer['id']}",
        headers=_h(admin_token),
    )
    data = resp.json()
    row = next(r for r in data["rows"] if r["invoice_id"] == inv30["invoice_id"])
    assert row["paid"] == pytest.approx(40.0)
    assert row["balance"] == pytest.approx(60.0)
    assert data["grand_total"] == pytest.approx(560.0)

    # CSV
    resp = await client.get(
        "/api/inventory/reports/receivables?format=csv", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    text = resp.content.decode("utf-8-sig")
    lines = [l for l in text.strip().splitlines() if l]
    assert lines[0].startswith("Invoice")
    assert lines[-1].startswith("TOTAL")


# ---- write-offs ----


async def test_write_offs_reason_filter_cost_and_missing(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    item = await _create_item(client, admin_token)
    # receive 6 @ 8 via GRN so avg_cost = 8 and out movements snapshot it
    supplier = await _create_supplier(client, admin_token)
    po = await client.post(
        "/api/inventory/purchase-orders",
        json={
            "supplier_id": supplier["id"], "location_id": loc,
            "order_date": "2026-10-01",
            "lines": [{"item_id": item["id"], "ordered_qty": 6, "unit_cost": 8.0}],
        },
        headers=_h(admin_token),
    )
    po = po.json()
    await client.post(f"/api/inventory/purchase-orders/{po['id']}/order", headers=_h(admin_token))
    grn = await client.post(
        "/api/inventory/goods-receipts",
        json={"supplier_id": supplier["id"], "location_id": loc, "receipt_date": "2026-10-02", "po_id": po["id"]},
        headers=_h(admin_token),
    )
    await client.post(f"/api/inventory/goods-receipts/{grn.json()['id']}/confirm", headers=_h(admin_token))

    await _move(client, admin_token, item["id"], loc, "out", 2, reason_code="damage", reason="x")
    await _move(client, admin_token, item["id"], loc, "out", 1, reason_code="sample")
    # excluded reasons
    await _move(client, admin_token, item["id"], loc, "out", 1, reason_code="other")
    await _move(client, admin_token, item["id"], loc, "out", 1, reason_code="internal_use")

    resp = await client.get(
        f"/api/inventory/reports/write-offs?location_id={loc}", headers=_h(admin_token)
    )
    assert resp.status_code == 200, resp.text
    rows = [r for r in resp.json()["rows"] if r["item_id"] == item["id"]]
    codes = {r["reason_code"] for r in rows}
    assert codes == {"damage", "sample", "internal_use"}
    damage = next(r for r in rows if r["reason_code"] == "damage")
    assert damage["qty"] == 2
    assert damage["cost"] == pytest.approx(16.0)  # 2 * 8
    assert damage["cost_missing"] == 0


# ---- dashboard ----


async def test_dashboard_numbers(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token, reorder_level=100)
    await _move(client, admin_token, item["id"], loc, "in", 5)
    inv = await _quick_invoice(client, admin_token, customer["id"], loc, item["id"], 2, 50.0, TODAY.isoformat())

    resp = await client.get(
        f"/api/inventory/dashboard?location_id={loc}", headers=_h(admin_token)
    )
    assert resp.status_code == 200, resp.text
    d = resp.json()
    assert d["tracked_items"] >= 1
    assert d["low_stock_count"] >= 1  # 5 <= 100? quantity 5-2=3 <= 100
    assert d["unpaid_invoice_count"] >= 1
    assert d["receivable_balance"] >= 100.0
    assert d["month_sales"] >= 100.0


# ---- alerts ----


async def test_alerts_compute_and_notify_dedupe(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    item = await _create_item(client, admin_token, reorder_level=10)
    await _move(client, admin_token, item["id"], loc, "in", 2)

    resp = await client.get("/api/inventory/alerts", headers=_h(admin_token))
    assert resp.status_code == 200, resp.text
    alerts = resp.json()
    assert any(a["item_id"] == item["id"] for a in alerts["low_stock"])

    # first notify creates notifications for all admin users
    resp = await client.post("/api/inventory/alerts/notify", headers=_h(admin_token))
    assert resp.status_code == 200, resp.text
    r1 = resp.json()
    assert r1["created"] >= 1

    # second run dedupes
    resp = await client.post("/api/inventory/alerts/notify", headers=_h(admin_token))
    r2 = resp.json()
    assert r2["created"] == 0
    assert r2["skipped"] == r1["created"]

    async with TestSessionLocal() as session:
        rows = (
            await session.execute(select(Notification))
        ).scalars().all()
    rows = [n for n in rows if (n.extra_data or {}).get("inventory_alert") == "low_stock"]
    assert rows
    assert all(n.notification_type == "reminder" for n in rows)
    assert all(n.action_url == "/attendance/inventory" for n in rows)


async def test_reports_non_admin_403(client: AsyncClient, admin_token: str):
    uname = f"staff_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", role="staff")
    resp = await client.post(
        "/api/auth/login", json={"username": uname, "password": "admin123"}
    )
    staff = _h(resp.json()["access_token"])

    for path in (
        "/api/inventory/reports/stock-valuation",
        "/api/inventory/reports/movements-summary",
        "/api/inventory/reports/purchases",
        "/api/inventory/reports/sales",
        "/api/inventory/reports/receivables",
        "/api/inventory/reports/write-offs",
        "/api/inventory/dashboard",
        "/api/inventory/alerts",
    ):
        resp = await client.get(path, headers=staff)
        assert resp.status_code == 403, path
    resp = await client.post("/api/inventory/alerts/notify", headers=staff)
    assert resp.status_code == 403


async def test_notify_dedupe_window_after_read(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    """Within the 7-day dedupe window a read notification still suppresses a
    re-send for the same alert."""
    loc = sample_location["id"]
    item = await _create_item(client, admin_token, reorder_level=50)
    await _move(client, admin_token, item["id"], loc, "in", 1)

    r1 = (await client.post("/api/inventory/alerts/notify", headers=_h(admin_token))).json()
    assert r1["created"] >= 1

    # Admin reads the notification, then re-notifies — still skipped
    async with TestSessionLocal() as session:
        rows = (
            await session.execute(
                select(Notification).where(Notification.is_read.is_(False))
            )
        ).scalars().all()
        for n in rows:
            if (n.extra_data or {}).get("inventory_alert"):
                n.is_read = True
        await session.commit()

    r2 = (await client.post("/api/inventory/alerts/notify", headers=_h(admin_token))).json()
    assert r2["created"] == 0
    assert r2["skipped"] >= 1
