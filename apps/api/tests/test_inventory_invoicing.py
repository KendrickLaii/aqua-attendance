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


async def _shipped_so(
    client, token, customer_id, location_id, lines, do_qtys=None, **so_extra
) -> tuple[dict, dict]:
    """Create + confirm an SO, then create + confirm a DO. Returns (so, do).

    do_qtys: list of qtys per line index; None ships everything remaining.
    """
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
    so = resp.json()

    do_body = {"so_id": so["id"], "delivery_date": "2026-10-17"}
    if do_qtys is not None:
        do_body["lines"] = [
            {
                "so_line_id": so["lines"][i]["id"],
                "item_id": so["lines"][i]["item_id"],
                "qty": q,
            }
            for i, q in enumerate(do_qtys)
            if q
        ]
    resp = await client.post("/api/inventory/delivery-orders", json=do_body, headers=_h(token))
    assert resp.status_code == 201, resp.text
    do = resp.json()
    resp = await client.post(
        f"/api/inventory/delivery-orders/{do['id']}/confirm", headers=_h(token)
    )
    assert resp.status_code == 200, resp.text
    return so, resp.json()


def _so_line(item_id: str, qty: int, price: float = 10.0, **extra) -> dict:
    return {"item_id": item_id, "qty": qty, "unit_price": price, **extra}


async def _issue_invoice(client, token, do_id, **extra) -> dict:
    resp = await client.post(
        "/api/inventory/invoices", json={"do_id": do_id, **extra}, headers=_h(token)
    )
    assert resp.status_code == 201, resp.text
    inv = resp.json()
    resp = await client.post(
        f"/api/inventory/invoices/{inv['id']}/issue", headers=_h(token)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _get_invoice(client, token, inv_id) -> dict:
    resp = await client.get(f"/api/inventory/invoices/{inv_id}", headers=_h(token))
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
    # SO: qty 10 @ 100, line discount 50, header discount 30 → line amount 950, total 920
    so, do = await _shipped_so(
        client, admin_token, customer["id"], loc,
        [_so_line(item["id"], 10, 100.0, discount_amount=50.0)],
        do_qtys=[4],
        discount_amount=30.0,
    )
    inv_resp = await client.post(
        "/api/inventory/invoices", json={"do_id": do["id"]}, headers=_h(admin_token)
    )
    assert inv_resp.status_code == 201, inv_resp.text
    inv = inv_resp.json()
    assert inv["status"] == "draft"
    assert inv["invoice_no"] is None
    line = inv["lines"][0]
    assert line["qty"] == 4
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
    assert inv["do_no"] == do["do_no"]


async def test_invoice_cumulative_do_qty_guard(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    so, do = await _shipped_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 10)]
    )
    do_line_id = do["lines"][0]["id"]

    inv1 = await _issue_invoice(client, admin_token, do["id"], lines=[{"do_line_id": do_line_id, "qty": 4}])
    assert inv1["lines"][0]["qty"] == 4
    inv2 = await _issue_invoice(client, admin_token, do["id"], lines=[{"do_line_id": do_line_id, "qty": 4}])
    assert inv2["lines"][0]["qty"] == 4

    # remaining is 2; asking for 3 → 422
    resp = await client.post(
        "/api/inventory/invoices",
        json={"do_id": do["id"], "lines": [{"do_line_id": do_line_id, "qty": 3}]},
        headers=_h(admin_token),
    )
    assert resp.status_code == 422

    # voiding inv2 frees qty — a draft invoice for qty 5 then works
    resp = await client.post(
        f"/api/inventory/invoices/{inv2['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    resp = await client.post(
        "/api/inventory/invoices",
        json={"do_id": do["id"], "lines": [{"do_line_id": do_line_id, "qty": 5}]},
        headers=_h(admin_token),
    )
    assert resp.status_code == 201


async def test_invoice_draft_edit_delete_and_issue_rules(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    _, do = await _shipped_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 5)]
    )
    resp = await client.post(
        "/api/inventory/invoices",
        json={"do_id": do["id"], "lines": [{"do_line_id": do["lines"][0]["id"], "qty": 4}]},
        headers=_h(admin_token),
    )
    inv = resp.json()

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
    resp = await client.post(
        "/api/inventory/invoices", json={"do_id": do["id"]}, headers=_h(admin_token)
    )
    draft = resp.json()
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
    so, do = await _shipped_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 6)]
    )
    inv1 = await _issue_invoice(client, admin_token, do["id"], lines=[{"do_line_id": do["lines"][0]["id"], "qty": 2}])
    inv2 = await _issue_invoice(client, admin_token, do["id"], lines=[{"do_line_id": do["lines"][0]["id"], "qty": 2}])
    assert inv1["invoice_no"] != inv2["invoice_no"]
    assert inv1["invoice_no"].startswith("SI-") and inv2["invoice_no"].startswith("SI-")

    # void draft → 409
    resp = await client.post(
        "/api/inventory/invoices", json={"do_id": do["id"]}, headers=_h(admin_token)
    )
    draft = resp.json()
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

    # void the receipt → invoice void now allowed
    await client.post(f"/api/inventory/receipts/{receipt['id']}/void", headers=_h(admin_token))
    resp = await client.post(
        f"/api/inventory/invoices/{inv1['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "void"
    assert resp.json()["payment_status"] == "void"


# ---- receipts ----


async def test_receipt_payments_and_status_transitions(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    _, do = await _shipped_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 2, 100.0)]
    )
    inv = await _issue_invoice(client, admin_token, do["id"])
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


async def test_receipt_on_draft_invoice_422_and_payment_status_filter(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 10)
    _, do = await _shipped_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 1, 50.0)]
    )
    resp = await client.post(
        "/api/inventory/invoices", json={"do_id": do["id"]}, headers=_h(admin_token)
    )
    draft = resp.json()
    resp = await client.post(
        "/api/inventory/receipts",
        json={"invoice_id": draft["id"], "amount": 10.0, "paid_by": "cash"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 422

    # draft still counts toward the cumulative DO qty — delete it before re-invoicing
    resp = await client.delete(
        f"/api/inventory/invoices/{draft['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 204
    inv = await _issue_invoice(client, admin_token, do["id"], issue_date="2026-10-16")
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
    _, do = await _shipped_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 5, 100.0)]
    )
    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 5
    inv = await _issue_invoice(client, admin_token, do["id"])
    inv_line = inv["lines"][0]

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
    _, do = await _shipped_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 3, 100.0)]
    )
    inv = await _issue_invoice(client, admin_token, do["id"])
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
    _, do = await _shipped_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 5, 50.0)]
    )
    inv = await _issue_invoice(client, admin_token, do["id"])
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
    _, do = await _shipped_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 2, 50.0)]
    )
    inv = await _issue_invoice(client, admin_token, do["id"])
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


# ---- quick fulfill ----


async def test_quick_fulfill_success(
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
        json={"pay": {"amount": 300.0, "paid_by": "cash"}},
        headers=_h(admin_token),
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["so"]["status"] == "fulfilled"
    assert result["delivery_order"]["status"] == "confirmed"
    assert result["invoice"]["status"] == "issued"
    assert result["invoice"]["invoice_no"].startswith("SI-")
    assert result["invoice"]["payment_status"] == "paid"
    assert result["receipt"]["receipt_no"].startswith("SR-")
    assert result["receipt"]["amount"] == pytest.approx(300.0)

    stock = await _stock(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 7
    assert stock["reserved"] == 0


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

    resp = await client.get(
        "/api/inventory/delivery-orders?so_id=" + so["id"], headers=_h(admin_token)
    )
    assert resp.json() == [] or all(
        d["so_id"] != so["id"] for d in resp.json()
    )


async def test_quick_fulfill_on_confirmed_so(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 5)
    so, _do = await _shipped_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 5)], do_qtys=[2]
    )
    # partially shipped SO still works — fulfills the remaining 3
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
    _, do = await _shipped_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 1)]
    )
    inv = await _issue_invoice(client, admin_token, do["id"])

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
            "/api/inventory/invoices", json={"do_id": do["id"]}, headers=staff
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
    _, do = await _shipped_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 1)]
    )
    inv = await _issue_invoice(client, admin_token, do["id"])
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
