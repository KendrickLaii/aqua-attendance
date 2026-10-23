import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from tests.conftest import TestSessionLocal, _insert_test_user

pytestmark = pytest.mark.asyncio


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


async def _stock(client: AsyncClient, token: str, item_id: str, location_id: str) -> dict | None:
    resp = await client.get(
        f"/api/inventory/stocks?item_id={item_id}&location_id={location_id}",
        headers=_h(token),
    )
    stocks = resp.json()
    return stocks[0] if stocks else None


async def _confirmed_so(client, token, customer_id, location_id, lines, **so_extra) -> dict:
    body = {
        "customer_id": customer_id,
        "location_id": location_id,
        "order_date": "2026-10-16",
        "lines": lines,
        **so_extra,
    }
    resp = await client.post("/api/inventory/sales-orders", json=body, headers=_h(token))
    assert resp.status_code == 201, resp.text
    so = resp.json()
    resp = await client.post(
        f"/api/inventory/sales-orders/{so['id']}/confirm", headers=_h(token)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _so_line(item_id: str, qty: int, price: float = 10.0, **extra) -> dict:
    return {"item_id": item_id, "qty": qty, "unit_price": price, **extra}


async def _create_invoice(client, token, body: dict, expected: int = 201) -> dict:
    resp = await client.post("/api/inventory/invoices", json=body, headers=_h(token))
    assert resp.status_code == expected, resp.text
    return resp.json()


async def _issue_invoice(client, token, so_id, lines=None, **extra) -> dict:
    body = {"so_id": so_id, **extra}
    if lines is not None:
        body["lines"] = lines
    inv = await _create_invoice(client, token, body)
    resp = await client.post(
        f"/api/inventory/invoices/{inv['id']}/issue", headers=_h(token)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _get_invoice(client, token, inv_id) -> dict:
    resp = await client.get(f"/api/inventory/invoices/{inv_id}", headers=_h(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _confirmed_do(client, token, inv, lines=None) -> dict:
    body = {"invoice_id": inv["id"], "delivery_date": "2026-10-17"}
    if lines is not None:
        body["lines"] = lines
    resp = await client.post("/api/inventory/delivery-orders", json=body, headers=_h(token))
    assert resp.status_code == 201, resp.text
    do = resp.json()
    resp = await client.post(
        f"/api/inventory/delivery-orders/{do['id']}/confirm", headers=_h(token)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---- invoices ----


async def test_invoice_prefill_proration_math(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token, name_zh="發票客戶")
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    # SO: qty 10 @ 100, line discount 50, header discount 30 → line amount 950
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc,
        [_so_line(item["id"], 10, 100.0, discount_amount=50.0)],
        discount_amount=30.0,
    )
    # invoice 4 of the 10
    inv = await _create_invoice(
        client, admin_token,
        {"so_id": so["id"], "lines": [{"so_line_id": so["lines"][0]["id"], "qty": 4}]},
    )
    assert inv["status"] == "draft"
    assert inv["invoice_no"] is None
    line = inv["lines"][0]
    assert line["qty"] == 4
    assert line["delivered_qty"] == 0
    assert line["unit_price"] == pytest.approx(100.0)
    assert line["discount_amount"] == pytest.approx(20.0)  # 50 * 4/10
    assert line["amount"] == pytest.approx(380.0)
    assert inv["subtotal"] == pytest.approx(380.0)
    # header discount prorated: 30 * 380/950
    assert inv["discount_amount"] == pytest.approx(12.0)
    assert inv["total"] == pytest.approx(368.0)
    assert inv["payment_status"] == "unpaid"
    assert inv["balance"] == pytest.approx(inv["total"])
    assert inv["buyer_name"] == customer["name_zh"]
    assert inv["so_no"] == so["so_no"]


async def test_invoice_only_on_confirmed_so(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    resp = await client.post(
        "/api/inventory/sales-orders",
        json={
            "customer_id": customer["id"], "location_id": loc,
            "order_date": "2026-10-16", "lines": [_so_line(item["id"], 2)],
        },
        headers=_h(admin_token),
    )
    so = resp.json()  # draft
    await _create_invoice(client, admin_token, {"so_id": so["id"]}, expected=422)


async def test_partial_invoicing_and_over_remaining_rejected(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 10)]
    )
    so_line_id = so["lines"][0]["id"]

    inv1 = await _issue_invoice(
        client, admin_token, so["id"], [{"so_line_id": so_line_id, "qty": 4}]
    )
    assert inv1["lines"][0]["qty"] == 4

    # a draft invoice claims the remaining qty too — over-claim rejected
    draft = await _create_invoice(
        client, admin_token,
        {"so_id": so["id"], "lines": [{"so_line_id": so_line_id, "qty": 5}]},
    )
    await _create_invoice(
        client, admin_token,
        {"so_id": so["id"], "lines": [{"so_line_id": so_line_id, "qty": 2}]},
        expected=422,  # only 6 left, 5 already claimed by the draft
    )
    await client.delete(f"/api/inventory/invoices/{draft['id']}", headers=_h(admin_token))

    # issue the remainder → SO fulfilled
    inv2 = await _issue_invoice(
        client, admin_token, so["id"], [{"so_line_id": so_line_id, "qty": 6}]
    )
    assert inv2["lines"][0]["qty"] == 6
    so_now = (await client.get(
        f"/api/inventory/sales-orders/{so['id']}", headers=_h(admin_token)
    )).json()
    assert so_now["status"] == "fulfilled"
    assert so_now["lines"][0]["invoiced_qty"] == 10

    # nothing left
    await _create_invoice(
        client, admin_token,
        {"so_id": so["id"], "lines": [{"so_line_id": so_line_id, "qty": 1}]},
        expected=422,
    )


async def test_invoice_issue_deducts_stock_and_releases_reservation(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 6)]
    )

    # partial issue: 2 of 6 → stock -2, reserved 4, SO partial
    inv1 = await _issue_invoice(
        client, admin_token, so["id"], [{"so_line_id": so["lines"][0]["id"], "qty": 2}]
    )
    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 8 and stock["reserved"] == 4
    so_now = (await client.get(
        f"/api/inventory/sales-orders/{so['id']}", headers=_h(admin_token)
    )).json()
    assert so_now["status"] == "partial"
    assert so_now["lines"][0]["invoiced_qty"] == 2

    resp = await client.get(
        f"/api/inventory/movements?item_id={item['id']}&reason_code=sale",
        headers=_h(admin_token),
    )
    moves = resp.json()
    assert len(moves) == 1
    assert moves[0]["reference"].startswith(f"SI:{inv1['id']}:")
    assert moves[0]["type"] == "out"
    assert moves[0]["unit_cost"] is not None


async def test_invoice_issue_shortfall_is_atomic(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    """Stock can be drained between SO confirm and invoice issue — issue must
    fail atomically."""
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item1 = await _create_item(client, admin_token)
    item2 = await _create_item(client, admin_token)
    await _move(client, admin_token, item1["id"], loc, "in", 10)
    await _move(client, admin_token, item2["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc,
        [_so_line(item1["id"], 3), _so_line(item2["id"], 2)],
    )
    # simulate stock loss outside the guarded paths (physical shrinkage, data
    # fix): set on-hand to 0 while the reservation still says 2
    from app.models.inventory import InventoryStock

    async with TestSessionLocal() as session:
        row = (
            await session.execute(
                select(InventoryStock).where(
                    InventoryStock.item_id == uuid.UUID(item2["id"]),
                    InventoryStock.location_id == uuid.UUID(loc),
                )
            )
        ).scalar_one()
        row.quantity = 0
        await session.commit()

    inv = await _create_invoice(client, admin_token, {"so_id": so["id"]})
    resp = await client.post(
        f"/api/inventory/invoices/{inv['id']}/issue", headers=_h(admin_token)
    )
    assert resp.status_code == 422

    inv_now = await _get_invoice(client, admin_token, inv["id"])
    assert inv_now["status"] == "draft"
    s1 = await _stock(client, admin_token, item1["id"], loc)
    s2 = await _stock(client, admin_token, item2["id"], loc)
    assert s1["quantity"] == 10 and s1["reserved"] == 3  # line untouched
    assert s2["quantity"] == 0 and s2["reserved"] == 2  # still reserved, not shipped
    so_now = (await client.get(
        f"/api/inventory/sales-orders/{so['id']}", headers=_h(admin_token)
    )).json()
    assert so_now["status"] == "confirmed"
    assert all(l["invoiced_qty"] == 0 for l in so_now["lines"])


async def test_issue_revalidates_qty_after_draft_created(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    """Two drafts can't over-claim; and if another invoice issued in between,
    issue re-validates remaining."""
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 5)]
    )
    so_line_id = so["lines"][0]["id"]
    draft = await _create_invoice(
        client, admin_token,
        {"so_id": so["id"], "lines": [{"so_line_id": so_line_id, "qty": 5}]},
    )
    # the draft claims all 5 — a second draft for even 1 is rejected
    await _create_invoice(
        client, admin_token,
        {"so_id": so["id"], "lines": [{"so_line_id": so_line_id, "qty": 1}]},
        expected=422,
    )
    # the draft itself still issues fine (its claim is exclusive)
    resp = await client.post(
        f"/api/inventory/invoices/{draft['id']}/issue", headers=_h(admin_token)
    )
    assert resp.status_code == 200, resp.text

    # a second invoice can claim what the draft left and issue fine; the draft
    # then still issues because its claim was reserved (issue re-validates
    # against invoiced_qty only)
    so2 = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 5)]
    )
    line2 = so2["lines"][0]["id"]
    stale = await _create_invoice(
        client, admin_token,
        {"so_id": so2["id"], "lines": [{"so_line_id": line2, "qty": 3}]},
    )
    inv2 = await _issue_invoice(
        client, admin_token, so2["id"], [{"so_line_id": line2, "qty": 2}]
    )
    assert inv2["lines"][0]["qty"] == 2
    resp = await client.post(
        f"/api/inventory/invoices/{stale['id']}/issue", headers=_h(admin_token)
    )
    assert resp.status_code == 200


async def test_invoice_draft_edit_delete_and_issue_rules(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 5)]
    )
    inv = await _create_invoice(
        client, admin_token,
        {"so_id": so["id"], "lines": [{"so_line_id": so["lines"][0]["id"], "qty": 4}]},
    )

    resp = await client.patch(
        f"/api/inventory/invoices/{inv['id']}",
        json={"notes": "updated", "discount_amount": 5.0},
        headers=_h(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "updated"

    resp = await client.post(
        f"/api/inventory/invoices/{inv['id']}/issue", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    issued = resp.json()
    assert issued["invoice_no"].startswith("SI-")
    assert issued["issue_date"] is not None

    # idempotent re-issue
    resp = await client.post(
        f"/api/inventory/invoices/{inv['id']}/issue", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["invoice_no"] == issued["invoice_no"]

    # issued invoice immutable
    resp = await client.patch(
        f"/api/inventory/invoices/{inv['id']}", json={"notes": "x"}, headers=_h(admin_token)
    )
    assert resp.status_code == 409
    resp = await client.delete(
        f"/api/inventory/invoices/{inv['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 409

    # draft invoice can be deleted
    draft = await _create_invoice(client, admin_token, {"so_id": so["id"]})
    resp = await client.delete(
        f"/api/inventory/invoices/{draft['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 204


async def test_invoice_numbering_and_void_rules(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 20)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 6)]
    )
    inv1 = await _issue_invoice(
        client, admin_token, so["id"], [{"so_line_id": so["lines"][0]["id"], "qty": 2}]
    )
    inv2 = await _issue_invoice(
        client, admin_token, so["id"], [{"so_line_id": so["lines"][0]["id"], "qty": 2}]
    )
    assert inv1["invoice_no"] != inv2["invoice_no"]
    assert inv1["invoice_no"].startswith("SI-") and inv2["invoice_no"].startswith("SI-")

    # void draft → 409
    draft = await _create_invoice(client, admin_token, {"so_id": so["id"]})
    resp = await client.post(
        f"/api/inventory/invoices/{draft['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 409
    await client.delete(f"/api/inventory/invoices/{draft['id']}", headers=_h(admin_token))

    # void blocked by a posted receipt
    resp = await client.post(
        "/api/inventory/receipts",
        json={"invoice_id": inv1["id"], "amount": 10.0, "paid_by": "cash"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 201
    receipt = resp.json()
    resp = await client.post(
        f"/api/inventory/invoices/{inv1['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 409
    assert "receipt" in resp.json()["detail"].lower()

    # void the receipt → invoice void now allowed
    await client.post(f"/api/inventory/receipts/{receipt['id']}/void", headers=_h(admin_token))
    resp = await client.post(
        f"/api/inventory/invoices/{inv1['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "void"
    assert resp.json()["payment_status"] == "void"


async def test_invoice_void_restocks_and_rereserves(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 6)]
    )
    inv = await _issue_invoice(
        client, admin_token, so["id"], [{"so_line_id": so["lines"][0]["id"], "qty": 2}]
    )
    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 8 and stock["reserved"] == 4

    resp = await client.post(
        f"/api/inventory/invoices/{inv['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 10  # restocked
    assert stock["reserved"] == 6   # re-reserved on the (still confirmed) SO

    resp = await client.get(
        f"/api/inventory/movements?item_id={item['id']}", headers=_h(admin_token)
    )
    assert any(
        (m["reference"] or "").startswith(f"SI-VOID:{inv['id']}:")
        for m in resp.json()
    )
    so_now = (await client.get(
        f"/api/inventory/sales-orders/{so['id']}", headers=_h(admin_token)
    )).json()
    assert so_now["status"] == "confirmed"
    assert so_now["lines"][0]["invoiced_qty"] == 0


async def test_invoice_void_blocked_by_delivery_order(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 4)]
    )
    inv = await _issue_invoice(client, admin_token, so["id"])
    do = await _confirmed_do(client, admin_token, inv)

    resp = await client.post(
        f"/api/inventory/invoices/{inv['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 409
    assert "delivery" in resp.json()["detail"].lower()

    # void the DO → invoice void allowed
    resp = await client.post(
        f"/api/inventory/delivery-orders/{do['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    resp = await client.post(
        f"/api/inventory/invoices/{inv['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 200


async def test_invoice_void_blocked_by_credit_note(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 4)]
    )
    inv = await _issue_invoice(client, admin_token, so["id"])
    resp = await client.post(
        "/api/inventory/credit-notes",
        json={
            "invoice_id": inv["id"], "reason": "x",
            "lines": [{"invoice_line_id": inv["lines"][0]["id"], "qty": 1}],
        },
        headers=_h(admin_token),
    )
    scn = resp.json()
    await client.post(
        f"/api/inventory/credit-notes/{scn['id']}/confirm", headers=_h(admin_token)
    )
    resp = await client.post(
        f"/api/inventory/invoices/{inv['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 409
    assert "credit" in resp.json()["detail"].lower()


# ---- receipts ----


async def test_receipt_payments_and_status_transitions(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 2, 100.0)]
    )
    inv = await _issue_invoice(client, admin_token, so["id"])
    assert inv["total"] == pytest.approx(200.0)

    resp = await client.post(
        "/api/inventory/receipts",
        json={"invoice_id": inv["id"], "amount": 80.0, "paid_by": "cash"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 201, resp.text
    r1 = resp.json()
    assert r1["receipt_no"].startswith("SR-")
    assert r1["status"] == "posted"

    inv = await _get_invoice(client, admin_token, inv["id"])
    assert inv["payment_status"] == "partial"
    assert inv["paid_total"] == pytest.approx(80.0)
    assert inv["balance"] == pytest.approx(120.0)
    assert len(inv["receipts"]) == 1

    # overpay → 422
    resp = await client.post(
        "/api/inventory/receipts",
        json={"invoice_id": inv["id"], "amount": 121.0, "paid_by": "card"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 422

    resp = await client.post(
        "/api/inventory/receipts",
        json={"invoice_id": inv["id"], "amount": 120.0, "paid_by": "bank_transfer", "reference_no": "TX-1"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 201
    inv = await _get_invoice(client, admin_token, inv["id"])
    assert inv["payment_status"] == "paid"
    assert inv["balance"] == 0

    # voiding a receipt restores balance
    resp = await client.post(
        f"/api/inventory/receipts/{r1['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "void"
    # idempotent
    resp = await client.post(
        f"/api/inventory/receipts/{r1['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    inv = await _get_invoice(client, admin_token, inv["id"])
    assert inv["payment_status"] == "partial"
    assert inv["balance"] == pytest.approx(80.0)


async def test_receipt_exact_balance_with_decimal_arithmetic(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    """Float balance math produced dust like 4.930000000000007 — an exact
    balance payment must succeed, and balance + 0.01 must fail."""
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    items = [await _create_item(client, admin_token) for _ in range(3)]
    for it in items:
        await _move(client, admin_token, it["id"], loc, "in", 10)
    # three lines with a prorated header discount → total 107.93
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc,
        [_so_line(it["id"], 1, 38.31) for it in items],
        discount_amount=7.0,
    )
    inv = await _issue_invoice(client, admin_token, so["id"])
    assert inv["total"] == pytest.approx(107.93)

    for amt in (60.0, 40.0):
        resp = await client.post(
            "/api/inventory/receipts",
            json={"invoice_id": inv["id"], "amount": amt, "paid_by": "cash"},
            headers=_h(admin_token),
        )
        assert resp.status_code == 201, resp.text
    inv = await _get_invoice(client, admin_token, inv["id"])
    assert inv["balance"] == pytest.approx(7.93)
    assert inv["payment_status"] == "partial"

    # pay the exact remaining balance → must succeed (no float dust)
    resp = await client.post(
        "/api/inventory/receipts",
        json={"invoice_id": inv["id"], "amount": inv["balance"], "paid_by": "cash"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 201, resp.text
    inv = await _get_invoice(client, admin_token, inv["id"])
    assert inv["balance"] == 0
    assert inv["payment_status"] == "paid"

    # balance + 0.01 → rejected
    resp = await client.post(
        "/api/inventory/receipts",
        json={"invoice_id": inv["id"], "amount": 0.01, "paid_by": "cash"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 422


async def test_receipt_on_draft_invoice_422_and_payment_status_filter(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 1, 50.0)]
    )
    draft = await _create_invoice(client, admin_token, {"so_id": so["id"]})
    resp = await client.post(
        "/api/inventory/receipts",
        json={"invoice_id": draft["id"], "amount": 10.0, "paid_by": "cash"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 422

    # draft still claims the qty — delete it before re-invoicing
    resp = await client.delete(
        f"/api/inventory/invoices/{draft['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 204
    inv = await _issue_invoice(client, admin_token, so["id"], issue_date="2026-10-16")
    # unpaid
    resp = await client.get(
        "/api/inventory/invoices?payment_status=unpaid", headers=_h(admin_token)
    )
    assert int(resp.headers["x-total-count"]) >= 1
    assert any(i["id"] == inv["id"] for i in resp.json())
    resp = await client.get(
        "/api/inventory/invoices?payment_status=paid", headers=_h(admin_token)
    )
    assert all(i["id"] != inv["id"] for i in resp.json())
    # pay it fully → appears under paid
    await client.post(
        "/api/inventory/receipts",
        json={"invoice_id": inv["id"], "amount": inv["total"], "paid_by": "cash"},
        headers=_h(admin_token),
    )
    resp = await client.get(
        "/api/inventory/invoices?payment_status=paid", headers=_h(admin_token)
    )
    assert any(i["id"] == inv["id"] for i in resp.json())
    # list search
    resp = await client.get(
        f"/api/inventory/receipts?search=SR-", headers=_h(admin_token)
    )
    assert int(resp.headers["x-total-count"]) >= 1


# ---- credit notes ----


async def test_credit_note_confirm_restock_and_qty_guard(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 5, 100.0)]
    )
    inv = await _issue_invoice(client, admin_token, so["id"])
    inv_line = inv["lines"][0]
    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 5  # stock left at issue, not delivery

    resp = await client.post(
        "/api/inventory/credit-notes",
        json={
            "invoice_id": inv["id"],
            "reason": "defective",
            "lines": [{"invoice_line_id": inv_line["id"], "qty": 2}],
        },
        headers=_h(admin_token),
    )
    assert resp.status_code == 201, resp.text
    scn = resp.json()
    assert scn["scn_no"].startswith("SCN-")
    assert scn["status"] == "draft"
    assert scn["lines"][0]["unit_amount"] == pytest.approx(100.0)
    assert scn["total"] == pytest.approx(200.0)

    resp = await client.post(
        f"/api/inventory/credit-notes/{scn['id']}/confirm", headers=_h(admin_token)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "confirmed"

    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 7  # restocked 2

    resp = await client.get(
        f"/api/inventory/movements?item_id={item['id']}&reason_code=sales_return",
        headers=_h(admin_token),
    )
    moves = resp.json()
    assert len(moves) == 1
    assert moves[0]["reference"].startswith(f"SCN:{scn['id']}:")

    inv = await _get_invoice(client, admin_token, inv["id"])
    assert inv["lines"][0]["credited_qty"] == 2
    assert inv["credited_total"] == pytest.approx(200.0)
    assert inv["payment_status"] == "partial"

    # over-credit → 422 (only 3 left)
    resp = await client.post(
        "/api/inventory/credit-notes",
        json={
            "invoice_id": inv["id"],
            "reason": "x",
            "lines": [{"invoice_line_id": inv_line["id"], "qty": 4}],
        },
        headers=_h(admin_token),
    )
    assert resp.status_code == 201  # creation ok
    resp = await client.post(
        f"/api/inventory/credit-notes/{resp.json()['id']}/confirm", headers=_h(admin_token)
    )
    assert resp.status_code == 422

    # idempotent re-confirm
    resp = await client.post(
        f"/api/inventory/credit-notes/{scn['id']}/confirm", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"


async def test_credit_note_balance_cap_and_restock_flag(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 3, 100.0)]
    )
    inv = await _issue_invoice(client, admin_token, so["id"])
    inv_line = inv["lines"][0]

    # pay in full first
    await client.post(
        "/api/inventory/receipts",
        json={"invoice_id": inv["id"], "amount": inv["total"], "paid_by": "cash"},
        headers=_h(admin_token),
    )
    # credit exceeding unpaid balance → 422 on confirm
    resp = await client.post(
        "/api/inventory/credit-notes",
        json={
            "invoice_id": inv["id"],
            "reason": "x",
            "lines": [{"invoice_line_id": inv_line["id"], "qty": 1}],
        },
        headers=_h(admin_token),
    )
    assert resp.status_code == 201
    scn = resp.json()
    resp = await client.post(
        f"/api/inventory/credit-notes/{scn['id']}/confirm", headers=_h(admin_token)
    )
    assert resp.status_code == 422
    assert "unpaid balance" in resp.json()["detail"]

    # restock=false does not create a movement
    resp = await client.post(
        "/api/inventory/credit-notes",
        json={
            "invoice_id": inv["id"],
            "reason": "goodwill",
            "lines": [{"invoice_line_id": inv_line["id"], "qty": 1, "restock": False}],
        },
        headers=_h(admin_token),
    )
    scn2 = resp.json()
    # still blocked by balance cap (total 100 > balance 0)
    resp = await client.post(
        f"/api/inventory/credit-notes/{scn2['id']}/confirm", headers=_h(admin_token)
    )
    assert resp.status_code == 422

    # void the receipt → balance freed; confirm scn2 now ok, no stock change
    receipts = (await _get_invoice(client, admin_token, inv["id"]))["receipts"]
    await client.post(
        f"/api/inventory/receipts/{receipts[0]['id']}/void", headers=_h(admin_token)
    )
    stock = await _stock(client, admin_token, item["id"], loc)
    qty_before = stock["quantity"]
    resp = await client.post(
        f"/api/inventory/credit-notes/{scn2['id']}/confirm", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == qty_before


async def test_credit_note_void_atomicity(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 5, 50.0)]
    )
    inv = await _issue_invoice(client, admin_token, so["id"])
    inv_line = inv["lines"][0]
    resp = await client.post(
        "/api/inventory/credit-notes",
        json={
            "invoice_id": inv["id"],
            "reason": "return",
            "lines": [{"invoice_line_id": inv_line["id"], "qty": 4}],
        },
        headers=_h(admin_token),
    )
    scn = resp.json()
    await client.post(
        f"/api/inventory/credit-notes/{scn['id']}/confirm", headers=_h(admin_token)
    )
    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 9

    # drain stock below what the void would restore → void fails atomically
    await _move(client, admin_token, item["id"], loc, "out", 7, reason_code="other", reason="sold")
    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 2
    resp = await client.post(
        f"/api/inventory/credit-notes/{scn['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 422
    inv = await _get_invoice(client, admin_token, inv["id"])
    assert inv["lines"][0]["credited_qty"] == 4  # unchanged
    scn_now = await client.get(
        f"/api/inventory/credit-notes/{scn['id']}", headers=_h(admin_token)
    )
    assert scn_now.json()["status"] == "confirmed"

    # restock enough → void works, credited_qty back to 0
    await _move(client, admin_token, item["id"], loc, "in", 10)
    resp = await client.post(
        f"/api/inventory/credit-notes/{scn['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "void"
    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 8
    inv = await _get_invoice(client, admin_token, inv["id"])
    assert inv["lines"][0]["credited_qty"] == 0


async def test_credit_note_draft_rules(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 2, 50.0)]
    )
    inv = await _issue_invoice(client, admin_token, so["id"])
    inv_line = inv["lines"][0]

    resp = await client.post(
        "/api/inventory/credit-notes",
        json={
            "invoice_id": inv["id"],
            "reason": "x",
            "lines": [{"invoice_line_id": inv_line["id"], "qty": 1}],
        },
        headers=_h(admin_token),
    )
    scn = resp.json()
    resp = await client.patch(
        f"/api/inventory/credit-notes/{scn['id']}",
        json={"reason": "changed", "lines": [{"invoice_line_id": inv_line["id"], "qty": 2, "restock": False}]},
        headers=_h(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == pytest.approx(100.0)

    await client.post(
        f"/api/inventory/credit-notes/{scn['id']}/confirm", headers=_h(admin_token)
    )
    # confirmed → patch/delete 409
    resp = await client.patch(
        f"/api/inventory/credit-notes/{scn['id']}", json={"reason": "y"}, headers=_h(admin_token)
    )
    assert resp.status_code == 409
    resp = await client.delete(
        f"/api/inventory/credit-notes/{scn['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 409

    # draft deletable
    resp = await client.post(
        "/api/inventory/credit-notes",
        json={
            "invoice_id": inv["id"],
            "reason": "x",
            "lines": [{"invoice_line_id": inv_line["id"], "qty": 1}],
        },
        headers=_h(admin_token),
    )
    resp = await client.delete(
        f"/api/inventory/credit-notes/{resp.json()['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 204


async def test_credit_note_reduces_deliverable(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    """Crediting undelivered qty reduces what DOs can deliver."""
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 5)]
    )
    inv = await _issue_invoice(client, admin_token, so["id"])
    inv_line = inv["lines"][0]

    # credit 2 of the 5 (nothing delivered yet)
    resp = await client.post(
        "/api/inventory/credit-notes",
        json={
            "invoice_id": inv["id"], "reason": "x",
            "lines": [{"invoice_line_id": inv_line["id"], "qty": 2}],
        },
        headers=_h(admin_token),
    )
    await client.post(
        f"/api/inventory/credit-notes/{resp.json()['id']}/confirm",
        headers=_h(admin_token),
    )

    # only 3 deliverable now
    do = await _confirmed_do(client, admin_token, inv)
    assert do["lines"][0]["qty"] == 3
    resp = await client.post(
        "/api/inventory/delivery-orders",
        json={
            "invoice_id": inv["id"], "delivery_date": "2026-10-18",
            "lines": [{"invoice_line_id": inv_line["id"], "qty": 1}],
        },
        headers=_h(admin_token),
    )
    assert resp.status_code == 422  # nothing left to deliver


# ---- quick fulfill ----


async def test_quick_fulfill_success_with_delivery_and_payment(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)

    resp = await client.post(
        "/api/inventory/sales-orders",
        json={
            "customer_id": customer["id"],
            "location_id": loc,
            "order_date": "2026-10-16",
            "lines": [_so_line(item["id"], 3, 100.0)],
        },
        headers=_h(admin_token),
    )
    so = resp.json()

    resp = await client.post(
        f"/api/inventory/sales-orders/{so['id']}/quick-fulfill",
        json={"deliver_now": True, "pay": {"amount": 300.0, "paid_by": "cash"}},
        headers=_h(admin_token),
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["so"]["status"] == "fulfilled"
    assert result["invoice"]["status"] == "issued"
    assert result["invoice"]["invoice_no"].startswith("SI-")
    assert result["invoice"]["payment_status"] == "paid"
    assert result["delivery_order"]["status"] == "confirmed"
    assert result["receipt"]["receipt_no"].startswith("SR-")
    assert result["receipt"]["amount"] == pytest.approx(300.0)

    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 7  # deducted at issue
    assert stock["reserved"] == 0


async def test_quick_fulfill_without_delivery(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 5)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 2)]
    )
    resp = await client.post(
        f"/api/inventory/sales-orders/{so['id']}/quick-fulfill",
        json={"deliver_now": False},
        headers=_h(admin_token),
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["delivery_order"] is None
    assert result["receipt"] is None
    assert result["invoice"]["status"] == "issued"
    inv = await _get_invoice(client, admin_token, result["invoice"]["id"])
    assert inv["lines"][0]["delivered_qty"] == 0


async def test_quick_fulfill_atomic_on_shortfall(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 2)

    resp = await client.post(
        "/api/inventory/sales-orders",
        json={
            "customer_id": customer["id"],
            "location_id": loc,
            "order_date": "2026-10-16",
            "lines": [_so_line(item["id"], 5)],
        },
        headers=_h(admin_token),
    )
    so = resp.json()

    resp = await client.post(
        f"/api/inventory/sales-orders/{so['id']}/quick-fulfill",
        json={},
        headers=_h(admin_token),
    )
    assert resp.status_code == 422
    so_now = await client.get(
        f"/api/inventory/sales-orders/{so['id']}", headers=_h(admin_token)
    )
    assert so_now.json()["status"] == "draft"  # reservation rolled back
    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 2 and stock["reserved"] == 0

    # no stray documents were left behind
    resp = await client.get(
        "/api/inventory/invoices?so_id=" + so["id"], headers=_h(admin_token)
    )
    assert all(i["so_id"] != so["id"] for i in resp.json())


async def test_quick_fulfill_on_confirmed_so(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 5)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 5)]
    )
    # partially invoiced SO still works — invoices the remaining 3
    await _issue_invoice(
        client, admin_token, so["id"], [{"so_line_id": so["lines"][0]["id"], "qty": 2}]
    )
    resp = await client.post(
        f"/api/inventory/sales-orders/{so['id']}/quick-fulfill",
        json={},
        headers=_h(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["so"]["status"] == "fulfilled"
    assert resp.json()["invoice"]["total"] == pytest.approx(30.0)  # 3 * 10

    # fulfilled SO → 422
    resp = await client.post(
        f"/api/inventory/sales-orders/{so['id']}/quick-fulfill",
        json={},
        headers=_h(admin_token),
    )
    assert resp.status_code == 422


async def test_invoicing_non_admin_403(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 5)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 1)]
    )
    inv = await _issue_invoice(client, admin_token, so["id"])

    uname = f"staff_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", role="staff")
    resp = await client.post(
        "/api/auth/login", json={"username": uname, "password": "admin123"}
    )
    staff = _h(resp.json()["access_token"])
    assert (await client.get("/api/inventory/invoices", headers=staff)).status_code == 403
    assert (await client.get("/api/inventory/receipts", headers=staff)).status_code == 403
    assert (await client.get("/api/inventory/credit-notes", headers=staff)).status_code == 403
    assert (
        await client.post(
            "/api/inventory/invoices", json={"so_id": so["id"]}, headers=staff
        )
    ).status_code == 403
    assert (
        await client.post(
            "/api/inventory/receipts",
            json={"invoice_id": inv["id"], "amount": 1, "paid_by": "cash"},
            headers=staff,
        )
    ).status_code == 403
    assert (
        await client.post(
            "/api/inventory/credit-notes",
            json={"invoice_id": inv["id"], "reason": "x", "lines": []},
            headers=staff,
        )
    ).status_code in (403, 422)


async def test_invoicing_writes_are_audited(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 5)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 1)]
    )
    inv = await _issue_invoice(client, admin_token, so["id"])
    await client.post(
        "/api/inventory/receipts",
        json={"invoice_id": inv["id"], "amount": 10.0, "paid_by": "cash"},
        headers=_h(admin_token),
    )
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.table_name.in_(
                    ["inventory_invoices", "inventory_receipts", "inventory_credit_notes"]
                )
            )
        )
        logs = result.scalars().all()
    tables = {log.table_name for log in logs}
    assert "inventory_invoices" in tables
    assert "inventory_receipts" in tables


# ---- review-fix coverage ----


async def test_receipt_plus_credit_cannot_exceed_balance(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 5)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 1, 100.0)]
    )
    inv = await _issue_invoice(client, admin_token, so["id"])
    assert inv["total"] == 100.0

    resp = await client.post(
        "/api/inventory/receipts",
        json={"invoice_id": inv["id"], "amount": 60.0, "paid_by": "cash"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 201, resp.text

    # Crediting the whole line (100) would exceed the remaining balance (40)
    resp = await client.post(
        "/api/inventory/credit-notes",
        json={
            "invoice_id": inv["id"],
            "reason": "return",
            "lines": [
                {"invoice_line_id": inv["lines"][0]["id"], "qty": 1, "restock": False}
            ],
        },
        headers=_h(admin_token),
    )
    assert resp.status_code == 201, resp.text
    scn = resp.json()
    resp = await client.post(
        f"/api/inventory/credit-notes/{scn['id']}/confirm", headers=_h(admin_token)
    )
    assert resp.status_code == 422, resp.text
    assert "balance" in resp.json()["detail"].lower()
    state = (
        await client.get(f"/api/inventory/credit-notes/{scn['id']}", headers=_h(admin_token))
    ).json()
    assert state["status"] == "draft"


async def test_zero_total_issued_invoice_is_paid(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 5)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 1, 0.0)]
    )
    inv = await _issue_invoice(client, admin_token, so["id"])
    assert inv["total"] == 0
    assert inv["payment_status"] == "paid"

    resp = await client.get(
        "/api/inventory/invoices?payment_status=paid", headers=_h(admin_token)
    )
    assert any(r["id"] == inv["id"] for r in resp.json())
    resp = await client.get(
        "/api/inventory/invoices?payment_status=unpaid", headers=_h(admin_token)
    )
    assert not any(r["id"] == inv["id"] for r in resp.json())


async def test_invoice_void_on_cancelled_so_no_rereserve(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    """Voiding an invoice on a cancelled SO restocks but does not re-reserve."""
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 6)]
    )
    # invoice 2 → reserved drops to 4; cancel releases the remaining 4
    inv = await _issue_invoice(
        client, admin_token, so["id"], [{"so_line_id": so["lines"][0]["id"], "qty": 2}]
    )
    resp = await client.post(
        f"/api/inventory/sales-orders/{so['id']}/cancel", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 8 and stock["reserved"] == 0

    resp = await client.post(
        f"/api/inventory/invoices/{inv['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 10
    assert stock["reserved"] == 0  # SO cancelled — nothing re-reserved
