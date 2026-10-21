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


async def _create_supplier(client: AsyncClient, token: str, **overrides) -> dict:
    body = {"code": f"SUP-{uuid.uuid4().hex[:6]}", "name_zh": "供應商", **overrides}
    resp = await client.post("/api/inventory/suppliers", json=body, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_po(
    client: AsyncClient,
    token: str,
    supplier_id: str,
    location_id: str,
    lines: list[dict],
    **overrides,
) -> dict:
    body = {
        "supplier_id": supplier_id,
        "location_id": location_id,
        "order_date": "2026-10-16",
        "lines": lines,
        **overrides,
    }
    resp = await client.post("/api/inventory/purchase-orders", json=body, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _po_line(item_id: str, qty: int, cost: float = 10.0, **extra) -> dict:
    return {"item_id": item_id, "ordered_qty": qty, "unit_cost": cost, **extra}


async def _get_po(client: AsyncClient, token: str, po_id: str) -> dict:
    resp = await client.get(f"/api/inventory/purchase-orders/{po_id}", headers=_h(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _create_grn(
    client: AsyncClient, token: str, body: dict, expected: int = 201
) -> dict | int:
    resp = await client.post("/api/inventory/goods-receipts", json=body, headers=_h(token))
    assert resp.status_code == expected, resp.text
    return resp.json() if expected == 201 else resp.status_code


def _grn_body(supplier_id: str, location_id: str, **extra) -> dict:
    return {
        "supplier_id": supplier_id,
        "location_id": location_id,
        "receipt_date": "2026-10-16",
        **extra,
    }


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


# ---- Suppliers ----


async def test_supplier_crud(client: AsyncClient, admin_token: str):
    supplier = await _create_supplier(
        client, admin_token, name_zh="三民書局", name_en="Sanmin", phone="02-1234567"
    )
    assert supplier["code"].startswith("SUP-")

    resp = await client.get(f"/api/inventory/suppliers/{supplier['id']}", headers=_h(admin_token))
    assert resp.status_code == 200
    assert resp.json()["name_zh"] == "三民書局"

    resp = await client.patch(
        f"/api/inventory/suppliers/{supplier['id']}",
        json={"payment_terms": "NET30", "is_active": False},
        headers=_h(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["payment_terms"] == "NET30"
    assert resp.json()["is_active"] is False

    resp = await client.get(
        "/api/inventory/suppliers?search=三民", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert int(resp.headers["x-total-count"]) >= 1
    assert any(s["id"] == supplier["id"] for s in resp.json())

    resp = await client.get(
        "/api/inventory/suppliers?is_active=true", headers=_h(admin_token)
    )
    assert all(s["is_active"] for s in resp.json())


async def test_supplier_duplicate_code_409(client: AsyncClient, admin_token: str):
    supplier = await _create_supplier(client, admin_token)
    resp = await client.post(
        "/api/inventory/suppliers",
        json={"code": supplier["code"], "name_zh": "另一間"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 409


# ---- Purchase orders ----


async def test_po_amount_math_and_discounts(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    item1 = await _create_item(client, admin_token)
    item2 = await _create_item(client, admin_token)
    po = await _create_po(
        client,
        admin_token,
        supplier["id"],
        sample_location["id"],
        [
            _po_line(item1["id"], 10, 100.0, discount_amount=50.0),   # 950
            _po_line(item2["id"], 5, 40.0, discount_amount=100.0),   # 200 - 100 = 100
        ],
        discount_amount=50.0,
    )
    assert po["status"] == "draft"
    assert po["total"] == pytest.approx(1000.0)
    amounts = sorted(l["amount"] for l in po["lines"])
    assert amounts == [100.0, 950.0]
    assert po["lines"][0]["sku_code"] and po["lines"][0]["name_zh"]
    assert po["supplier_name"] == supplier["name_zh"]


async def test_po_total_floors_at_zero(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    item = await _create_item(client, admin_token)
    po = await _create_po(
        client,
        admin_token,
        supplier["id"],
        sample_location["id"],
        [_po_line(item["id"], 1, 10.0)],
        discount_amount=999.0,
    )
    assert po["total"] == 0

    resp = await client.patch(
        f"/api/inventory/purchase-orders/{po['id']}",
        json={
            "discount_amount": 0,
            "lines": [_po_line(item["id"], 1, 10.0, discount_amount=50.0)],
        },
        headers=_h(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["lines"][0]["amount"] == 0


async def test_po_order_and_cancel_rules(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    item = await _create_item(client, admin_token)

    po = await _create_po(client, admin_token, supplier["id"], sample_location["id"], [])
    resp = await client.post(
        f"/api/inventory/purchase-orders/{po['id']}/order", headers=_h(admin_token)
    )
    assert resp.status_code == 422  # no lines

    po2 = await _create_po(
        client, admin_token, supplier["id"], sample_location["id"],
        [_po_line(item["id"], 3)],
    )
    resp = await client.post(
        f"/api/inventory/purchase-orders/{po2['id']}/order", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ordered"

    # ordered PO cannot be patched/deleted
    resp = await client.patch(
        f"/api/inventory/purchase-orders/{po2['id']}",
        json={"notes": "x"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 409
    resp = await client.delete(
        f"/api/inventory/purchase-orders/{po2['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 409

    # cancel works with no confirmed GRN
    resp = await client.post(
        f"/api/inventory/purchase-orders/{po2['id']}/cancel", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    # draft PO can be deleted
    resp = await client.delete(
        f"/api/inventory/purchase-orders/{po['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 204
    resp = await client.get(
        f"/api/inventory/purchase-orders/{po['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 404


async def test_po_cancel_blocked_by_confirmed_grn(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    item = await _create_item(client, admin_token)
    po = await _create_po(
        client, admin_token, supplier["id"], sample_location["id"], [_po_line(item["id"], 2)]
    )
    await client.post(f"/api/inventory/purchase-orders/{po['id']}/order", headers=_h(admin_token))
    grn = await _create_grn(
        client, admin_token, _grn_body(supplier["id"], sample_location["id"], po_id=po["id"])
    )
    await client.post(f"/api/inventory/goods-receipts/{grn['id']}/confirm", headers=_h(admin_token))

    resp = await client.post(
        f"/api/inventory/purchase-orders/{po['id']}/cancel", headers=_h(admin_token)
    )
    assert resp.status_code == 409


async def test_doc_numbering_sequential_per_location_and_type(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_location_b: dict
):
    supplier = await _create_supplier(client, admin_token)
    item = await _create_item(client, admin_token)
    line = [_po_line(item["id"], 1)]

    po1 = await _create_po(client, admin_token, supplier["id"], sample_location["id"], line)
    po2 = await _create_po(client, admin_token, supplier["id"], sample_location["id"], line)
    po_b = await _create_po(client, admin_token, supplier["id"], sample_location_b["id"], line)

    def seq(no: str) -> int:
        return int(no.rsplit("-", 1)[1])

    assert po1["po_no"].startswith("PO-")
    assert seq(po2["po_no"]) == seq(po1["po_no"]) + 1
    assert seq(po_b["po_no"]) == 1  # separate counter per location

    # GRN uses its own counter
    grn = await _create_grn(
        client,
        admin_token,
        _grn_body(supplier["id"], sample_location["id"],
                  lines=[{"item_id": item["id"], "qty": 1, "unit_cost": 5.0}]),
    )
    assert grn["grn_no"].startswith("GRN-")
    assert seq(grn["grn_no"]) == 1

    nos = {po1["po_no"], po2["po_no"], po_b["po_no"], grn["grn_no"]}
    assert len(nos) == 4


# ---- Goods receipts ----


async def _ordered_po_with_item(
    client, token, supplier_id, location_id, qty: int = 10, cost: float = 10.0
) -> tuple[dict, dict]:
    item = await _create_item(client, token)
    po = await _create_po(
        client, token, supplier_id, location_id, [_po_line(item["id"], qty, cost)]
    )
    resp = await client.post(
        f"/api/inventory/purchase-orders/{po['id']}/order", headers=_h(token)
    )
    assert resp.status_code == 200
    return po, item


async def test_grn_partial_then_full_receipt(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    po, item = await _ordered_po_with_item(
        client, admin_token, supplier["id"], sample_location["id"], qty=10
    )
    po_line_id = po["lines"][0]["id"]

    grn1 = await _create_grn(
        client,
        admin_token,
        _grn_body(
            supplier["id"],
            sample_location["id"],
            po_id=po["id"],
            lines=[{"item_id": item["id"], "qty": 4, "unit_cost": 10.0, "po_line_id": po_line_id}],
        ),
    )
    await client.post(f"/api/inventory/goods-receipts/{grn1['id']}/confirm", headers=_h(admin_token))
    po = await _get_po(client, admin_token, po["id"])
    assert po["status"] == "partial"
    assert po["lines"][0]["received_qty"] == 4

    grn2 = await _create_grn(
        client,
        admin_token,
        _grn_body(supplier["id"], sample_location["id"], po_id=po["id"]),
    )
    assert grn2["lines"][0]["qty"] == 6  # prefilled remaining
    await client.post(f"/api/inventory/goods-receipts/{grn2['id']}/confirm", headers=_h(admin_token))
    po = await _get_po(client, admin_token, po["id"])
    assert po["status"] == "received"
    assert po["lines"][0]["received_qty"] == 10

    stock = await _stock(client, admin_token, item["id"], sample_location["id"])
    assert stock["quantity"] == 10


async def test_grn_over_receipt_blocked_unless_allowed(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    po, item = await _ordered_po_with_item(
        client, admin_token, supplier["id"], sample_location["id"], qty=5
    )
    resp = await client.post(
        "/api/inventory/goods-receipts",
        json=_grn_body(
            supplier["id"],
            sample_location["id"],
            po_id=po["id"],
            lines=[{"item_id": item["id"], "qty": 6, "unit_cost": 10.0}],
        ),
        headers=_h(admin_token),
    )
    assert resp.status_code == 422

    grn = await _create_grn(
        client,
        admin_token,
        _grn_body(
            supplier["id"],
            sample_location["id"],
            po_id=po["id"],
            allow_over_receipt=True,
            lines=[{"item_id": item["id"], "qty": 6, "unit_cost": 10.0}],
        ),
    )
    await client.post(f"/api/inventory/goods-receipts/{grn['id']}/confirm", headers=_h(admin_token))
    po = await _get_po(client, admin_token, po["id"])
    assert po["status"] == "received"
    assert po["lines"][0]["received_qty"] == 6


async def test_grn_confirm_stock_and_ledger_refs(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    item = await _create_item(client, admin_token)
    grn = await _create_grn(
        client,
        admin_token,
        _grn_body(
            supplier["id"],
            sample_location["id"],
            lines=[{"item_id": item["id"], "qty": 3, "unit_cost": 12.5}],
        ),
    )
    resp = await client.post(
        f"/api/inventory/goods-receipts/{grn['id']}/confirm", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"

    stock = await _stock(client, admin_token, item["id"], sample_location["id"])
    assert stock["quantity"] == 3

    resp = await client.get(
        f"/api/inventory/movements?item_id={item['id']}&location_id={sample_location['id']}",
        headers=_h(admin_token),
    )
    moves = resp.json()
    assert len(moves) == 1
    assert moves[0]["reference"].startswith(f"GRN:{grn['id']}:")
    assert moves[0]["type"] == "in"


async def test_grn_confirm_weighted_avg_cost(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_location_b: dict
):
    supplier = await _create_supplier(client, admin_token)
    item = await _create_item(client, admin_token, cost_price=10.0)
    # existing stock in two locations: avg_cost becomes 10 on first receipt
    grn_a = await _create_grn(
        client,
        admin_token,
        _grn_body(
            supplier["id"],
            sample_location["id"],
            lines=[{"item_id": item["id"], "qty": 10, "unit_cost": 10.0}],
        ),
    )
    await client.post(f"/api/inventory/goods-receipts/{grn_a['id']}/confirm", headers=_h(admin_token))
    grn_b = await _create_grn(
        client,
        admin_token,
        _grn_body(
            supplier["id"],
            sample_location_b["id"],
            lines=[{"item_id": item["id"], "qty": 5, "unit_cost": 10.0}],
        ),
    )
    await client.post(f"/api/inventory/goods-receipts/{grn_b['id']}/confirm", headers=_h(admin_token))
    # on-hand total across locations = 15, avg_cost = 10
    # new receipt of 15 units @ 20 -> (15*10 + 15*20) / 30 = 15.0
    grn_c = await _create_grn(
        client,
        admin_token,
        _grn_body(
            supplier["id"],
            sample_location["id"],
            lines=[{"item_id": item["id"], "qty": 15, "unit_cost": 20.0}],
        ),
    )
    await client.post(f"/api/inventory/goods-receipts/{grn_c['id']}/confirm", headers=_h(admin_token))

    resp = await client.get(f"/api/inventory/items/{item['id']}", headers=_h(admin_token))
    assert resp.status_code == 200
    assert resp.json()["avg_cost"] == pytest.approx(15.0)


async def test_grn_reconfirm_idempotent(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    item = await _create_item(client, admin_token)
    grn = await _create_grn(
        client,
        admin_token,
        _grn_body(
            supplier["id"],
            sample_location["id"],
            lines=[{"item_id": item["id"], "qty": 2, "unit_cost": 5.0}],
        ),
    )
    for _ in range(2):
        resp = await client.post(
            f"/api/inventory/goods-receipts/{grn['id']}/confirm", headers=_h(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"
    stock = await _stock(client, admin_token, item["id"], sample_location["id"])
    assert stock["quantity"] == 2  # movement applied only once


async def test_grn_void_restores_stock_and_po(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    po, item = await _ordered_po_with_item(
        client, admin_token, supplier["id"], sample_location["id"], qty=5
    )
    grn = await _create_grn(
        client,
        admin_token,
        _grn_body(supplier["id"], sample_location["id"], po_id=po["id"]),
    )
    await client.post(f"/api/inventory/goods-receipts/{grn['id']}/confirm", headers=_h(admin_token))

    resp = await client.post(
        f"/api/inventory/goods-receipts/{grn['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "void"

    stock = await _stock(client, admin_token, item["id"], sample_location["id"])
    assert stock["quantity"] == 0
    po = await _get_po(client, admin_token, po["id"])
    assert po["status"] == "ordered"
    assert po["lines"][0]["received_qty"] == 0

    resp = await client.get(
        f"/api/inventory/movements?item_id={item['id']}", headers=_h(admin_token)
    )
    refs = [m["reference"] for m in resp.json()]
    assert any(r.startswith(f"GRN-VOID:{grn['id']}:") for r in refs)


async def test_grn_void_blocked_when_stock_insufficient(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    item = await _create_item(client, admin_token)
    grn = await _create_grn(
        client,
        admin_token,
        _grn_body(
            supplier["id"],
            sample_location["id"],
            lines=[{"item_id": item["id"], "qty": 5, "unit_cost": 10.0}],
        ),
    )
    await client.post(f"/api/inventory/goods-receipts/{grn['id']}/confirm", headers=_h(admin_token))
    # drain the stock elsewhere
    await _move(client, admin_token, item["id"], sample_location["id"], "out", 4,
               reason_code="other", reason="used")

    resp = await client.post(
        f"/api/inventory/goods-receipts/{grn['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 422

    # nothing changed
    resp = await client.get(f"/api/inventory/goods-receipts/{grn['id']}", headers=_h(admin_token))
    assert resp.json()["status"] == "confirmed"
    stock = await _stock(client, admin_token, item["id"], sample_location["id"])
    assert stock["quantity"] == 1


async def test_grn_draft_edit_delete_rules(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    item = await _create_item(client, admin_token)
    grn = await _create_grn(
        client,
        admin_token,
        _grn_body(
            supplier["id"],
            sample_location["id"],
            lines=[{"item_id": item["id"], "qty": 2, "unit_cost": 5.0}],
        ),
    )
    resp = await client.patch(
        f"/api/inventory/goods-receipts/{grn['id']}",
        json={"lines": [{"item_id": item["id"], "qty": 7, "unit_cost": 5.0}]},
        headers=_h(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["lines"][0]["qty"] == 7

    await client.post(f"/api/inventory/goods-receipts/{grn['id']}/confirm", headers=_h(admin_token))
    resp = await client.patch(
        f"/api/inventory/goods-receipts/{grn['id']}",
        json={"notes": "x"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 409
    resp = await client.delete(
        f"/api/inventory/goods-receipts/{grn['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 409


# ---- Purchase returns ----


async def _confirmed_grn(
    client, token, supplier_id, location_id, item_id, qty, cost=10.0
) -> dict:
    grn = await _create_grn(
        client,
        token,
        _grn_body(
            supplier_id, location_id,
            lines=[{"item_id": item_id, "qty": qty, "unit_cost": cost}],
        ),
    )
    resp = await client.post(
        f"/api/inventory/goods-receipts/{grn['id']}/confirm", headers=_h(token)
    )
    assert resp.status_code == 200
    return resp.json()


async def test_purchase_return_confirm_and_void(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    item = await _create_item(client, admin_token)
    grn = await _confirmed_grn(
        client, admin_token, supplier["id"], sample_location["id"], item["id"], 10
    )

    resp = await client.post(
        "/api/inventory/purchase-returns",
        json={
            "supplier_id": supplier["id"],
            "location_id": sample_location["id"],
            "grn_id": grn["id"],
            "return_date": "2026-10-17",
            "lines": [{"item_id": item["id"], "qty": 3, "unit_cost": 10.0}],
        },
        headers=_h(admin_token),
    )
    assert resp.status_code == 201, resp.text
    prt = resp.json()
    assert prt["prt_no"].startswith("PRT-")
    assert prt["status"] == "draft"

    resp = await client.post(
        f"/api/inventory/purchase-returns/{prt['id']}/confirm", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    stock = await _stock(client, admin_token, item["id"], sample_location["id"])
    assert stock["quantity"] == 7

    resp = await client.get(
        f"/api/inventory/movements?item_id={item['id']}&reason_code=supplier_return",
        headers=_h(admin_token),
    )
    moves = resp.json()
    assert len(moves) == 1
    assert moves[0]["reference"].startswith(f"PRT:{prt['id']}:")

    resp = await client.post(
        f"/api/inventory/purchase-returns/{prt['id']}/void", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    stock = await _stock(client, admin_token, item["id"], sample_location["id"])
    assert stock["quantity"] == 10


async def test_purchase_return_over_return_blocked(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    item = await _create_item(client, admin_token)
    grn = await _confirmed_grn(
        client, admin_token, supplier["id"], sample_location["id"], item["id"], 4
    )

    resp = await client.post(
        "/api/inventory/purchase-returns",
        json={
            "supplier_id": supplier["id"],
            "location_id": sample_location["id"],
            "grn_id": grn["id"],
            "return_date": "2026-10-17",
            "lines": [{"item_id": item["id"], "qty": 5, "unit_cost": 10.0}],
        },
        headers=_h(admin_token),
    )
    assert resp.status_code == 422


async def test_purchase_return_draft_edit_delete_rules(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    item = await _create_item(client, admin_token)
    await _confirmed_grn(
        client, admin_token, supplier["id"], sample_location["id"], item["id"], 5
    )
    resp = await client.post(
        "/api/inventory/purchase-returns",
        json={
            "supplier_id": supplier["id"],
            "location_id": sample_location["id"],
            "return_date": "2026-10-17",
            "lines": [{"item_id": item["id"], "qty": 2, "unit_cost": 10.0}],
        },
        headers=_h(admin_token),
    )
    prt = resp.json()
    resp = await client.post(
        f"/api/inventory/purchase-returns/{prt['id']}/confirm", headers=_h(admin_token)
    )
    assert resp.status_code == 200
    resp = await client.patch(
        f"/api/inventory/purchase-returns/{prt['id']}", json={"notes": "x"}, headers=_h(admin_token)
    )
    assert resp.status_code == 409
    resp = await client.delete(
        f"/api/inventory/purchase-returns/{prt['id']}", headers=_h(admin_token)
    )
    assert resp.status_code == 409


# ---- Permissions & audit ----


async def test_purchasing_non_admin_forbidden(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    uname = f"staff_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", role="staff")
    resp = await client.post(
        "/api/auth/login", json={"username": uname, "password": "admin123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    resp = await client.get("/api/inventory/suppliers", headers=_h(token))
    assert resp.status_code == 403
    resp = await client.post(
        "/api/inventory/suppliers",
        json={"code": "X1", "name_zh": "x"},
        headers=_h(token),
    )
    assert resp.status_code == 403
    resp = await client.get("/api/inventory/purchase-orders", headers=_h(token))
    assert resp.status_code == 403
    resp = await client.get("/api/inventory/goods-receipts", headers=_h(token))
    assert resp.status_code == 403
    resp = await client.get("/api/inventory/purchase-returns", headers=_h(token))
    assert resp.status_code == 403


async def test_p3_audit_rows_written(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    supplier = await _create_supplier(client, admin_token)
    item = await _create_item(client, admin_token)
    po = await _create_po(
        client, admin_token, supplier["id"], sample_location["id"], [_po_line(item["id"], 2)]
    )
    await client.post(f"/api/inventory/purchase-orders/{po['id']}/order", headers=_h(admin_token))
    grn = await _create_grn(
        client,
        admin_token,
        _grn_body(supplier["id"], sample_location["id"], po_id=po["id"]),
    )
    await client.post(f"/api/inventory/goods-receipts/{grn['id']}/confirm", headers=_h(admin_token))
    prt = await client.post(
        "/api/inventory/purchase-returns",
        json={
            "supplier_id": supplier["id"],
            "location_id": sample_location["id"],
            "return_date": "2026-10-17",
            "lines": [{"item_id": item["id"], "qty": 1, "unit_cost": 10.0}],
        },
        headers=_h(admin_token),
    )
    await client.post(
        f"/api/inventory/purchase-returns/{prt.json()['id']}/confirm", headers=_h(admin_token)
    )

    from app.models.audit_log import AuditLog

    async with TestSessionLocal() as session:
        async def logs(table: str) -> list:
            result = await session.execute(
                select(AuditLog).where(AuditLog.table_name == table)
            )
            return [r.action for r in result.scalars().all()]

        assert "CREATE" in await logs("suppliers")
        assert {"CREATE", "UPDATE"} <= set(await logs("purchase_orders"))
        assert {"CREATE", "UPDATE"} <= set(await logs("goods_receipts"))
        assert {"CREATE", "UPDATE"} <= set(await logs("purchase_returns"))
