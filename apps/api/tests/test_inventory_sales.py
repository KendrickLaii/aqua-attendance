import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

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


async def _create_so(
    client: AsyncClient,
    token: str,
    customer_id: str,
    location_id: str,
    lines: list[dict],
    **overrides,
) -> dict:
    body = {
        "customer_id": customer_id,
        "location_id": location_id,
        "order_date": "2026-10-16",
        "lines": lines,
        **overrides,
    }
    resp = await client.post("/api/inventory/sales-orders", json=body, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _so_line(item_id: str, qty: int, price: float = 10.0, **extra) -> dict:
    return {"item_id": item_id, "qty": qty, "unit_price": price, **extra}


async def _get_so(client: AsyncClient, token: str, so_id: str) -> dict:
    resp = await client.get(f"/api/inventory/sales-orders/{so_id}", headers=_h(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _create_do(client: AsyncClient, token: str, body: dict, expected: int = 201) -> dict:
    resp = await client.post("/api/inventory/delivery-orders", json=body, headers=_h(token))
    assert resp.status_code == expected, resp.text
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


async def _confirmed_so(client, token, customer_id, location_id, lines) -> dict:
    so = await _create_so(client, token, customer_id, location_id, lines)
    resp = await client.post(
        f"/api/inventory/sales-orders/{so['id']}/confirm", headers=_h(token)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _issued_invoice(
    client: AsyncClient, token: str, so: dict, lines: list[dict] | None = None
) -> dict:
    body: dict = {"so_id": so["id"]}
    if lines is not None:
        body["lines"] = lines
    resp = await client.post("/api/inventory/invoices", json=body, headers=_h(token))
    assert resp.status_code == 201, resp.text
    inv = resp.json()
    resp = await client.post(
        f"/api/inventory/invoices/{inv['id']}/issue", headers=_h(token)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---- Customers ----


async def test_customer_crud(client: AsyncClient, admin_token: str):
    customer = await _create_customer(
        client, admin_token, name_zh="陳大文", name_en="Chan Tai Man", type="company",
        contact_name="陳生", phone="91234567",
    )
    assert customer["code"].startswith("CUS-")
    assert customer["type"] == "company"

    resp = await client.get(f"/api/inventory/customers/{customer['id']}", headers=_h(admin_token))
    assert resp.status_code == 200
    assert resp.json()["contact_name"] == "陳生"

    resp = await client.patch(
        f"/api/inventory/customers/{customer['id']}",
        json={"email": "chan@example.com", "is_active": False},
        headers=_h(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "chan@example.com"
    assert resp.json()["is_active"] is False

    resp = await client.get("/api/inventory/customers?search=陳大文", headers=_h(admin_token))
    assert int(resp.headers["x-total-count"]) >= 1
    assert any(c["id"] == customer["id"] for c in resp.json())

    resp = await client.get("/api/inventory/customers?type=company", headers=_h(admin_token))
    assert all(c["type"] == "company" for c in resp.json())


async def test_customer_duplicate_code_409(client: AsyncClient, admin_token: str):
    customer = await _create_customer(client, admin_token)
    resp = await client.post(
        "/api/inventory/customers",
        json={"code": customer["code"], "name_zh": "另一個"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 409


async def test_customer_from_student_idempotent(
    client: AsyncClient, admin_token: str, sample_unit: dict
):
    resp = await client.post(
        f"/api/inventory/customers/from-student/{sample_unit['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 200, resp.text
    c1 = resp.json()
    assert c1["student_unit_id"] == sample_unit["id"]
    assert c1["name_zh"] == sample_unit["full_name"]
    assert c1["code"].startswith("C-")

    resp = await client.post(
        f"/api/inventory/customers/from-student/{sample_unit['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == c1["id"]


async def test_customer_from_student_rejects_non_student(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    resp = await client.post(
        "/api/units",
        json={
            "code": f"STF-{uuid.uuid4().hex[:6]}",
            "full_name": "Staff Member",
            "unit_type": "staff",
            "registered_location_id": sample_location["id"],
            "scan_location_ids": [sample_location["id"]],
        },
        headers=_h(admin_token),
    )
    assert resp.status_code == 201
    staff = resp.json()

    resp = await client.post(
        f"/api/inventory/customers/from-student/{staff['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 422


# ---- Sales orders ----


async def test_so_amount_math_and_discounts(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    customer = await _create_customer(client, admin_token)
    item1 = await _create_item(client, admin_token)
    item2 = await _create_item(client, admin_token)
    so = await _create_so(
        client,
        admin_token,
        customer["id"],
        sample_location["id"],
        [
            _so_line(item1["id"], 10, 100.0, discount_amount=50.0),  # 950
            _so_line(item2["id"], 5, 40.0, discount_amount=100.0),   # 100
        ],
        discount_amount=50.0,
    )
    assert so["status"] == "draft"
    assert so["total"] == pytest.approx(1000.0)
    assert sorted(l["amount"] for l in so["lines"]) == [100.0, 950.0]
    assert so["lines"][0]["sku_code"]
    assert so["buyer_name"] == customer["name_zh"]

    # floor at zero
    so2 = await _create_so(
        client, admin_token, customer["id"], sample_location["id"],
        [_so_line(item1["id"], 1, 10.0)], discount_amount=999.0,
    )
    assert so2["total"] == 0


async def test_so_confirm_reserves_stock(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 10)

    so = await _confirmed_so(
        client, admin_token, customer["id"], sample_location["id"],
        [_so_line(item["id"], 4)],
    )
    assert so["status"] == "confirmed"
    stock = await _stock(client, admin_token, item["id"], sample_location["id"])
    assert stock["quantity"] == 10
    assert stock["reserved"] == 4
    assert stock["available"] == 6


async def test_so_confirm_shortfall_is_atomic(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    customer = await _create_customer(client, admin_token)
    item1 = await _create_item(client, admin_token)
    item2 = await _create_item(client, admin_token)
    await _move(client, admin_token, item1["id"], sample_location["id"], "in", 10)
    await _move(client, admin_token, item2["id"], sample_location["id"], "in", 2)

    so = await _create_so(
        client, admin_token, customer["id"], sample_location["id"],
        [_so_line(item1["id"], 5), _so_line(item2["id"], 5)],  # 2nd line short
    )
    resp = await client.post(
        f"/api/inventory/sales-orders/{so['id']}/confirm", headers=_h(admin_token)
    )
    assert resp.status_code == 422

    # zero side effects: SO still draft, no reservation on item1 either
    so = await _get_so(client, admin_token, so["id"])
    assert so["status"] == "draft"
    s1 = await _stock(client, admin_token, item1["id"], sample_location["id"])
    s2 = await _stock(client, admin_token, item2["id"], sample_location["id"])
    assert s1["reserved"] == 0
    assert s2["reserved"] == 0


async def test_so_cancel_releases_remaining(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 10)

    so = await _confirmed_so(
        client, admin_token, customer["id"], sample_location["id"],
        [_so_line(item["id"], 6)],
    )
    # invoice 2 of 6 first — issue deducts stock + releases that reservation
    await _issued_invoice(
        client, admin_token, so,
        [{"so_line_id": so["lines"][0]["id"], "qty": 2}],
    )
    stock = await _stock(client, admin_token, item["id"], sample_location["id"])
    assert stock["quantity"] == 8 and stock["reserved"] == 4

    resp = await client.post(
        f"/api/inventory/sales-orders/{so['id']}/cancel", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
    stock = await _stock(client, admin_token, item["id"], sample_location["id"])
    assert stock["reserved"] == 0  # remaining 4 released


async def test_so_confirm_no_lines_422_and_fulfilled_cancel_409(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 2)

    empty = await _create_so(client, admin_token, customer["id"], sample_location["id"], [])
    resp = await client.post(
        f"/api/inventory/sales-orders/{empty['id']}/confirm", headers=_h(admin_token)
    )
    assert resp.status_code == 422

    so = await _confirmed_so(
        client, admin_token, customer["id"], sample_location["id"], [_so_line(item["id"], 2)]
    )
    await _issued_invoice(client, admin_token, so)
    resp = await client.post(
        f"/api/inventory/sales-orders/{so['id']}/cancel", headers=_h(admin_token)
    )
    assert resp.status_code == 409  # fulfilled


async def test_proforma_numbering_and_payload(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    customer = await _create_customer(client, admin_token, name_zh="李客戶")
    item = await _create_item(client, admin_token)
    so = await _create_so(
        client, admin_token, customer["id"], sample_location["id"],
        [_so_line(item["id"], 2, 100.0)], discount_amount=10.0,
    )
    resp = await client.post(
        f"/api/inventory/sales-orders/{so['id']}/proforma",
        json={"pf_valid_until": "2026-11-30"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 200, resp.text
    pf_no = resp.json()["pf_no"]
    assert pf_no.startswith("PF-")

    # repeat call returns the same pf_no
    resp = await client.post(
        f"/api/inventory/sales-orders/{so['id']}/proforma", json={}, headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["pf_no"] == pf_no

    resp = await client.get(
        f"/api/inventory/sales-orders/{so['id']}/proforma", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["pf_no"] == pf_no
    assert doc["so_no"] == so["so_no"]
    assert doc["customer_name"] == "李客戶"
    assert doc["total"] == pytest.approx(190.0)
    assert doc["subtotal"] == pytest.approx(200.0)
    assert doc["discount_amount"] == pytest.approx(10.0)
    assert doc["valid_until"] == "2026-11-30"
    assert len(doc["lines"]) == 1

    # GET before issue → 409
    so2 = await _create_so(
        client, admin_token, customer["id"], sample_location["id"], [_so_line(item["id"], 1)]
    )
    resp = await client.get(
        f"/api/inventory/sales-orders/{so2['id']}/proforma", headers=_h(admin_token)
    )
    assert resp.status_code == 409


# ---- Delivery orders ----


async def test_do_partial_deliveries_on_one_invoice(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    """One invoice can have several DOs (partial delivery); delivered_qty
    accumulates and stock is untouched by DOs."""
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 10)

    so = await _confirmed_so(
        client, admin_token, customer["id"], sample_location["id"], [_so_line(item["id"], 6)]
    )
    inv = await _issued_invoice(client, admin_token, so)
    inv_line = inv["lines"][0]
    stock = await _stock(client, admin_token, item["id"], sample_location["id"])
    assert stock["quantity"] == 4 and stock["reserved"] == 0  # issue already deducted

    do1 = await _create_do(
        client, admin_token,
        {"invoice_id": inv["id"], "delivery_date": "2026-10-17",
         "lines": [{"invoice_line_id": inv_line["id"], "qty": 2}]},
    )
    assert do1["status"] == "draft"
    assert do1["invoice_id"] == inv["id"]
    assert do1["invoice_no"] == inv["invoice_no"]
    await client.post(
        f"/api/inventory/delivery-orders/{do1['id']}/confirm", headers=_h(admin_token)
    )

    inv = (await client.get(f"/api/inventory/invoices/{inv['id']}", headers=_h(admin_token))).json()
    assert inv["lines"][0]["delivered_qty"] == 2
    stock = await _stock(client, admin_token, item["id"], sample_location["id"])
    assert stock["quantity"] == 4 and stock["reserved"] == 0  # no stock effect

    # second DO prefills the remaining 4
    do2 = await _create_do(
        client, admin_token, {"invoice_id": inv["id"], "delivery_date": "2026-10-18"}
    )
    assert do2["lines"][0]["qty"] == 4
    await client.post(
        f"/api/inventory/delivery-orders/{do2['id']}/confirm", headers=_h(admin_token)
    )
    inv = (await client.get(f"/api/inventory/invoices/{inv['id']}", headers=_h(admin_token))).json()
    assert inv["lines"][0]["delivered_qty"] == 6
    assert {d["do_no"] for d in inv["delivery_orders"]} == {do1["do_no"], do2["do_no"]}

    # fully delivered now
    await _create_do(
        client, admin_token,
        {"invoice_id": inv["id"], "delivery_date": "2026-10-19"},
        expected=422,
    )


async def test_do_only_on_issued_invoice(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], sample_location["id"], [_so_line(item["id"], 3)]
    )
    resp = await client.post(
        "/api/inventory/invoices", json={"so_id": so["id"]}, headers=_h(admin_token)
    )
    draft_inv = resp.json()
    await _create_do(
        client, admin_token,
        {"invoice_id": draft_inv["id"], "delivery_date": "2026-10-17"},
        expected=422,  # draft invoice — not deliverable yet
    )


async def test_do_over_delivery_rejected(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], sample_location["id"], [_so_line(item["id"], 3)]
    )
    inv = await _issued_invoice(client, admin_token, so)
    inv_line = inv["lines"][0]

    # over-deliverable rejected at creation
    await _create_do(
        client, admin_token,
        {"invoice_id": inv["id"], "delivery_date": "2026-10-17",
         "lines": [{"invoice_line_id": inv_line["id"], "qty": 4}]},
        expected=422,
    )
    # a second draft may not over-claim together with the first
    do1 = await _create_do(
        client, admin_token,
        {"invoice_id": inv["id"], "delivery_date": "2026-10-17",
         "lines": [{"invoice_line_id": inv_line["id"], "qty": 2}]},
    )
    await _create_do(
        client, admin_token,
        {"invoice_id": inv["id"], "delivery_date": "2026-10-17",
         "lines": [{"invoice_line_id": inv_line["id"], "qty": 2}]},
        expected=422,  # 2 already claimed by do1, only 1 deliverable
    )
    # but confirm re-validates only what is actually delivered
    await client.post(
        f"/api/inventory/delivery-orders/{do1['id']}/confirm", headers=_h(admin_token)
    )
    inv = (await client.get(f"/api/inventory/invoices/{inv['id']}", headers=_h(admin_token))).json()
    assert inv["lines"][0]["delivered_qty"] == 2


async def test_do_confirm_void_move_no_stock(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 8)
    so = await _confirmed_so(
        client, admin_token, customer["id"], sample_location["id"], [_so_line(item["id"], 3)]
    )
    inv = await _issued_invoice(client, admin_token, so)
    do = await _create_do(
        client, admin_token, {"invoice_id": inv["id"], "delivery_date": "2026-10-17"}
    )
    resp = await client.post(
        f"/api/inventory/delivery-orders/{do['id']}/confirm", headers=_h(admin_token)
    )
    assert resp.status_code == 200

    stock = await _stock(client, admin_token, item["id"], sample_location["id"])
    assert stock["quantity"] == 5 and stock["reserved"] == 0

    # no DO-tagged movements exist — the only sale movement is the SI one
    resp = await client.get(
        f"/api/inventory/movements?item_id={item['id']}", headers=_h(admin_token)
    )
    refs = [m["reference"] or "" for m in resp.json()]
    assert any(r.startswith(f"SI:{inv['id']}:") for r in refs)
    assert not any(r.startswith(f"DO:{do['id']}:") for r in refs)

    # void: delivered_qty drops, stock unchanged
    resp = await client.post(
        f"/api/inventory/delivery-orders/{do['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    inv = (await client.get(f"/api/inventory/invoices/{inv['id']}", headers=_h(admin_token))).json()
    assert inv["lines"][0]["delivered_qty"] == 0
    stock = await _stock(client, admin_token, item["id"], sample_location["id"])
    assert stock["quantity"] == 5

    # idempotent re-void
    resp = await client.post(
        f"/api/inventory/delivery-orders/{do['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 200


async def test_do_draft_edit_delete_rules(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], sample_location["id"], [_so_line(item["id"], 5)]
    )
    inv = await _issued_invoice(client, admin_token, so)
    do = await _create_do(
        client, admin_token, {"invoice_id": inv["id"], "delivery_date": "2026-10-17"}
    )
    resp = await client.patch(
        f"/api/inventory/delivery-orders/{do['id']}",
        json={"lines": [{"invoice_line_id": inv["lines"][0]["id"], "qty": 1}]},
        headers=_h(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["lines"][0]["qty"] == 1

    await client.post(
        f"/api/inventory/delivery-orders/{do['id']}/confirm", headers=_h(admin_token)
    )
    resp = await client.patch(
        f"/api/inventory/delivery-orders/{do['id']}", json={"notes": "x"}, headers=_h(admin_token)
    )
    assert resp.status_code == 409
    resp = await client.delete(
        f"/api/inventory/delivery-orders/{do['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 409


async def test_so_draft_only_edit_delete(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], sample_location["id"], [_so_line(item["id"], 2)]
    )
    resp = await client.patch(
        f"/api/inventory/sales-orders/{so['id']}", json={"notes": "x"}, headers=_h(admin_token)
    )
    assert resp.status_code == 409
    resp = await client.delete(
        f"/api/inventory/sales-orders/{so['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 409


async def test_doc_numbering_so_pf_do_per_location(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_location_b: dict
):
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 20)
    await _move(client, admin_token, item["id"], sample_location_b["id"], "in", 20)
    line = [_so_line(item["id"], 1)]

    def seq(no: str) -> int:
        return int(no.rsplit("-", 1)[1])

    so1 = await _create_so(client, admin_token, customer["id"], sample_location["id"], line)
    so2 = await _create_so(client, admin_token, customer["id"], sample_location["id"], line)
    so_b = await _create_so(client, admin_token, customer["id"], sample_location_b["id"], line)
    assert seq(so2["so_no"]) == seq(so1["so_no"]) + 1
    assert seq(so_b["so_no"]) == 1

    await client.post(
        f"/api/inventory/sales-orders/{so1['id']}/proforma", json={}, headers=_h(admin_token)
    )
    so1 = await _get_so(client, admin_token, so1["id"])
    assert so1["pf_no"].startswith("PF-")
    assert seq(so1["pf_no"]) == 1

    await client.post(
        f"/api/inventory/sales-orders/{so2['id']}/confirm", headers=_h(admin_token)
    )
    inv = await _issued_invoice(client, admin_token, so2)
    do = await _create_do(
        client, admin_token, {"invoice_id": inv["id"], "delivery_date": "2026-10-17"}
    )
    assert do["do_no"].startswith("DO-")
    assert seq(do["do_no"]) == 1


# ---- Permissions & audit ----


async def test_sales_non_admin_forbidden(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    uname = f"staff_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", role="staff")
    resp = await client.post(
        "/api/auth/login", json={"username": uname, "password": "admin123"}
    )
    token = resp.json()["access_token"]

    for path in (
        "/api/inventory/customers",
        "/api/inventory/sales-orders",
        "/api/inventory/delivery-orders",
    ):
        resp = await client.get(path, headers=_h(token))
        assert resp.status_code == 403, path


async def test_p4_audit_rows_written(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    customer = await _create_customer(client, admin_token)
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 10)
    so = await _confirmed_so(
        client, admin_token, customer["id"], sample_location["id"], [_so_line(item["id"], 2)]
    )
    inv = await _issued_invoice(client, admin_token, so)
    do = await _create_do(
        client, admin_token, {"invoice_id": inv["id"], "delivery_date": "2026-10-17"}
    )
    await client.post(
        f"/api/inventory/delivery-orders/{do['id']}/confirm", headers=_h(admin_token)
    )

    from app.models.audit_log import AuditLog

    async with TestSessionLocal() as session:
        async def actions(table: str) -> set:
            result = await session.execute(
                select(AuditLog.action).where(AuditLog.table_name == table)
            )
            return {r for (r,) in result.all()}

        assert "CREATE" in await actions("customers")
        assert {"CREATE", "UPDATE"} <= await actions("sales_orders")
        assert {"CREATE", "UPDATE"} <= await actions("delivery_orders")


# ---- review-fix coverage ----


async def test_do_list_search_and_invoice_filter(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _create_customer(client, admin_token, name_zh="獨特客戶甲")
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], loc, "in", 5)
    so = await _confirmed_so(
        client, admin_token, customer["id"], loc, [_so_line(item["id"], 2)]
    )
    inv = await _issued_invoice(client, admin_token, so)
    do = await _create_do(
        client, admin_token, {"invoice_id": inv["id"], "delivery_date": "2026-10-17"}
    )

    # search by do_no fragment
    frag = do["do_no"][-6:]
    resp = await client.get(
        f"/api/inventory/delivery-orders?search={frag}", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert any(d["id"] == do["id"] for d in resp.json())

    # search by customer name
    resp = await client.get(
        "/api/inventory/delivery-orders?search=%E7%8D%A8%E7%89%B9",
        headers=_h(admin_token),
    )
    assert resp.status_code == 200
    assert any(d["id"] == do["id"] for d in resp.json())

    # non-matching search returns nothing
    resp = await client.get(
        "/api/inventory/delivery-orders?search=ZZZ-NO-MATCH", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json() == []

    # invoice_id filter
    resp = await client.get(
        f"/api/inventory/delivery-orders?invoice_id={inv['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert [d["id"] for d in resp.json()] == [do["id"]]
