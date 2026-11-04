"""List endpoints must match the per-id detail output and not issue per-row queries."""

import uuid
from contextlib import contextmanager

import pytest
from httpx import AsyncClient
from sqlalchemy import event

from tests.conftest import engine

pytestmark = pytest.mark.asyncio


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@contextmanager
def count_statements():
    counter = {"n": 0}

    def _before(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            counter["n"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _before)
    try:
        yield counter
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _before)


async def _post(client, token, path, body, expected=201):
    resp = await client.post(f"/api/inventory/{path}", json=body, headers=_h(token))
    assert resp.status_code == expected, resp.text
    return resp.json()


async def _item(client, token):
    return await _post(
        client, token, "items", {"sku_code": f"B-{uuid.uuid4().hex[:6]}", "name_zh": "品項", "sale_price": 10}
    )


async def _supplier(client, token):
    return await _post(client, token, "suppliers", {"code": f"S-{uuid.uuid4().hex[:6]}", "name_zh": "供應商"})


async def _customer(client, token):
    return await _post(client, token, "customers", {"code": f"C-{uuid.uuid4().hex[:6]}", "name_zh": "客戶"})


async def _stock_in(client, token, item_id, loc, qty):
    await _post(
        client,
        token,
        "movements",
        {"item_id": item_id, "warehouse_id": loc, "type": "in", "quantity": qty, "reason_code": "opening"},
    )


async def _assert_list_matches_details(client, token, list_path, detail_path, ids, expected_count=None):
    listed = await client.get(f"/api/inventory/{list_path}", headers=_h(token))
    assert listed.status_code == 200, listed.text
    by_id = {row["id"]: row for row in listed.json()}
    for doc_id in ids:
        detail = await client.get(f"/api/inventory/{detail_path}/{doc_id}", headers=_h(token))
        assert detail.status_code == 200, detail.text
        assert by_id[doc_id] == detail.json()


async def _list_query_count(client, token, list_path) -> int:
    with count_statements() as counter:
        resp = await client.get(f"/api/inventory/{list_path}", headers=_h(token))
    assert resp.status_code == 200, resp.text
    return counter["n"]


async def test_purchase_documents_lists_match_details_and_are_constant_query(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    supplier = await _supplier(client, admin_token)

    async def make_po_grn_prt():
        item = await _item(client, admin_token)
        po = await _post(
            client,
            admin_token,
            "purchase-orders",
            {
                "supplier_id": supplier["id"],
                "warehouse_id": loc,
                "order_date": "2026-10-16",
                "lines": [{"item_id": item["id"], "ordered_qty": 5, "unit_cost": 3.5}],
            },
        )
        await _post(client, admin_token, f"purchase-orders/{po['id']}/order", {}, expected=200)
        grn = await _post(
            client,
            admin_token,
            "goods-receipts",
            {"supplier_id": supplier["id"], "warehouse_id": loc, "receipt_date": "2026-10-16", "po_id": po["id"]},
        )
        await _post(client, admin_token, f"goods-receipts/{grn['id']}/confirm", {}, expected=200)
        prt = await _post(
            client,
            admin_token,
            "purchase-returns",
            {
                "supplier_id": supplier["id"],
                "warehouse_id": loc,
                "grn_id": grn["id"],
                "return_date": "2026-10-17",
                "lines": [{"item_id": item["id"], "qty": 1, "unit_cost": 3.5}],
            },
        )

        return po["id"], grn["id"], prt["id"]

    first = await make_po_grn_prt()
    one_doc = {
        "po": await _list_query_count(client, admin_token, "purchase-orders"),
        "grn": await _list_query_count(client, admin_token, "goods-receipts"),
        "prt": await _list_query_count(client, admin_token, "purchase-returns"),
    }
    docs = [first] + [await make_po_grn_prt() for _ in range(4)]

    await _assert_list_matches_details(client, admin_token, "purchase-orders", "purchase-orders", [d[0] for d in docs])
    await _assert_list_matches_details(client, admin_token, "goods-receipts", "goods-receipts", [d[1] for d in docs])
    await _assert_list_matches_details(client, admin_token, "purchase-returns", "purchase-returns", [d[2] for d in docs])

    five_docs = {
        "po": await _list_query_count(client, admin_token, "purchase-orders"),
        "grn": await _list_query_count(client, admin_token, "goods-receipts"),
        "prt": await _list_query_count(client, admin_token, "purchase-returns"),
    }
    assert five_docs == one_doc


async def test_sales_documents_lists_match_details_and_are_constant_query(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    loc = sample_location["id"]
    customer = await _customer(client, admin_token)

    async def make_so_do():
        item = await _item(client, admin_token)
        await _stock_in(client, admin_token, item["id"], loc, 10)
        so = await _post(
            client,
            admin_token,
            "sales-orders",
            {
                "customer_id": customer["id"],
                "warehouse_id": loc,
                "order_date": "2026-10-16",
                "lines": [{"item_id": item["id"], "qty": 2, "unit_price": 10}],
            },
        )
        await _post(client, admin_token, f"sales-orders/{so['id']}/confirm", {}, expected=200)
        inv = await _post(client, admin_token, "invoices", {"so_id": so["id"]})
        await _post(client, admin_token, f"invoices/{inv['id']}/issue", {}, expected=200)
        do = await _post(
            client,
            admin_token,
            "delivery-orders",
            {"invoice_id": inv["id"], "delivery_date": "2026-10-17"},
        )

        return so["id"], do["id"]

    first = await make_so_do()
    one_doc = {
        "so": await _list_query_count(client, admin_token, "sales-orders"),
        "do": await _list_query_count(client, admin_token, "delivery-orders"),
    }
    docs = [first] + [await make_so_do() for _ in range(4)]

    await _assert_list_matches_details(client, admin_token, "sales-orders", "sales-orders", [d[0] for d in docs])
    await _assert_list_matches_details(client, admin_token, "delivery-orders", "delivery-orders", [d[1] for d in docs])

    five_docs = {
        "so": await _list_query_count(client, admin_token, "sales-orders"),
        "do": await _list_query_count(client, admin_token, "delivery-orders"),
    }
    assert five_docs == one_doc
