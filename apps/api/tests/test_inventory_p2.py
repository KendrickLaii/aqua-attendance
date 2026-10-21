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


async def _move(
    client: AsyncClient, token: str, item_id: str, location_id: str, type: str, quantity: int, **extra
) -> dict:
    resp = await client.post(
        "/api/inventory/movements",
        json={"item_id": item_id, "location_id": location_id, "type": type, "quantity": quantity, **extra},
        headers=_h(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _stock_qty(client: AsyncClient, token: str, item_id: str, location_id: str) -> dict | None:
    resp = await client.get(
        f"/api/inventory/stocks?item_id={item_id}&location_id={location_id}", headers=_h(token)
    )
    assert resp.status_code == 200
    stocks = resp.json()
    return stocks[0] if stocks else None


# ---- Transfers ----


async def test_transfer_moves_stock_between_locations(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_location_b: dict
):
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 10)

    resp = await client.post(
        "/api/inventory/transfers",
        json={
            "item_id": item["id"],
            "from_location_id": sample_location["id"],
            "to_location_id": sample_location_b["id"],
            "quantity": 4,
            "reason": "rebalance",
        },
        headers=_h(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["out_movement"]["type"] == "transfer_out"
    assert body["in_movement"]["type"] == "transfer_in"
    assert body["out_movement"]["balance_after"] == 6
    assert body["in_movement"]["balance_after"] == 4

    src = await _stock_qty(client, admin_token, item["id"], sample_location["id"])
    dst = await _stock_qty(client, admin_token, item["id"], sample_location_b["id"])
    assert src["quantity"] == 6
    assert dst["quantity"] == 4


async def test_transfer_insufficient_is_atomic(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_location_b: dict
):
    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 3)

    resp = await client.post(
        "/api/inventory/transfers",
        json={
            "item_id": item["id"],
            "from_location_id": sample_location["id"],
            "to_location_id": sample_location_b["id"],
            "quantity": 5,
        },
        headers=_h(admin_token),
    )
    assert resp.status_code == 422

    src = await _stock_qty(client, admin_token, item["id"], sample_location["id"])
    dst = await _stock_qty(client, admin_token, item["id"], sample_location_b["id"])
    assert src["quantity"] == 3
    assert dst is None or dst["quantity"] == 0

    movements = await client.get(
        f"/api/inventory/movements?item_id={item['id']}&type=transfer_out",
        headers=_h(admin_token),
    )
    assert movements.json() == []


async def test_transfers_both_directions_both_succeed(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_location_b: dict
):
    """Opposite-direction transfers take the same locks in deterministic order;
    SQLite can't reproduce the deadlock, so this asserts behaviour only."""
    item = await _create_item(client, admin_token)
    loc_a = sample_location["id"]
    loc_b = sample_location_b["id"]
    await _move(client, admin_token, item["id"], loc_a, "in", 10)
    await _move(client, admin_token, item["id"], loc_b, "in", 5)

    for frm, to in ((loc_a, loc_b), (loc_b, loc_a)):
        resp = await client.post(
            "/api/inventory/transfers",
            json={
                "item_id": item["id"],
                "from_location_id": frm,
                "to_location_id": to,
                "quantity": 3,
            },
            headers=_h(admin_token),
        )
        assert resp.status_code == 201, resp.text

    a = await _stock_qty(client, admin_token, item["id"], loc_a)
    b = await _stock_qty(client, admin_token, item["id"], loc_b)
    assert a["quantity"] == 10
    assert b["quantity"] == 5

    movements = await client.get(
        f"/api/inventory/movements?item_id={item['id']}", headers=_h(admin_token)
    )
    transfer_rows = [m for m in movements.json() if m["type"].startswith("transfer_")]
    assert len(transfer_rows) == 4
    assert sum(m["quantity_delta"] for m in transfer_rows) == 0


async def test_transfer_same_location_rejected(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    item = await _create_item(client, admin_token)
    resp = await client.post(
        "/api/inventory/transfers",
        json={
            "item_id": item["id"],
            "from_location_id": sample_location["id"],
            "to_location_id": sample_location["id"],
            "quantity": 1,
        },
        headers=_h(admin_token),
    )
    assert resp.status_code == 422


# ---- Reserved / available ----


async def test_reserve_release_and_out_below_reserved_blocked(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    from app.models.inventory import InventoryStock
    from app.services import inventory as inventory_svc

    item = await _create_item(client, admin_token)
    loc = sample_location["id"]
    await _move(client, admin_token, item["id"], loc, "in", 10)

    item_uuid = uuid.UUID(item["id"])
    loc_uuid = uuid.UUID(loc)

    async with TestSessionLocal() as session:
        stock = await inventory_svc.reserve(
            session, item_id=item_uuid, location_id=loc_uuid, quantity=6
        )
        await session.commit()
        assert stock.reserved == 6

    over_reserve = None
    async with TestSessionLocal() as session:
        try:
            await inventory_svc.reserve(
                session, item_id=item_uuid, location_id=loc_uuid, quantity=5
            )
        except Exception as exc:
            over_reserve = exc
    assert over_reserve is not None and getattr(over_reserve, "status_code", None) == 422

    resp = await client.post(
        "/api/inventory/movements",
        json={"item_id": item["id"], "location_id": loc, "type": "out", "quantity": 5},
        headers=_h(admin_token),
    )
    assert resp.status_code == 422

    ok = await client.post(
        "/api/inventory/movements",
        json={"item_id": item["id"], "location_id": loc, "type": "out", "quantity": 4},
        headers=_h(admin_token),
    )
    assert ok.status_code == 201, ok.text

    async with TestSessionLocal() as session:
        stock = await inventory_svc.release(
            session, item_id=item_uuid, location_id=loc_uuid, quantity=2
        )
        await session.commit()
        assert stock.reserved == 4

    too_much_release = None
    async with TestSessionLocal() as session:
        try:
            await inventory_svc.release(
                session, item_id=item_uuid, location_id=loc_uuid, quantity=99
            )
        except Exception as exc:
            too_much_release = exc
    assert too_much_release is not None and getattr(too_much_release, "status_code", None) == 422

    stock_row = await _stock_qty(client, admin_token, item["id"], loc)
    assert stock_row["quantity"] == 6
    assert stock_row["reserved"] == 4
    assert stock_row["available"] == 2

    async with TestSessionLocal() as session:
        found = (
            await session.execute(
                select(InventoryStock).where(
                    InventoryStock.item_id == item_uuid, InventoryStock.location_id == loc_uuid
                )
            )
        ).scalar_one()
        assert found.reserved == 4


# ---- reason_code / unit_cost ----


async def test_out_reason_code_and_unit_cost_snapshot(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    from app.models.inventory import InventoryItem

    item = await _create_item(client, admin_token, sale_price=50)
    loc = sample_location["id"]
    await _move(client, admin_token, item["id"], loc, "in", 10, reason_code="opening")

    async with TestSessionLocal() as session:
        db_item = await session.get(InventoryItem, uuid.UUID(item["id"]))
        db_item.avg_cost = 12.34
        await session.commit()

    movement = await _move(
        client,
        admin_token,
        item["id"],
        loc,
        "out",
        2,
        reason_code="damage",
        reason="water damaged",
    )
    assert movement["reason_code"] == "damage"
    assert movement["unit_cost"] == 12.34


async def test_reason_code_validation(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    item = await _create_item(client, admin_token)
    loc = sample_location["id"]

    bad_in = await client.post(
        "/api/inventory/movements",
        json={
            "item_id": item["id"],
            "location_id": loc,
            "type": "in",
            "quantity": 1,
            "reason_code": "damage",
        },
        headers=_h(admin_token),
    )
    assert bad_in.status_code == 422

    damage_no_note = await client.post(
        "/api/inventory/movements",
        json={
            "item_id": item["id"],
            "location_id": loc,
            "type": "out",
            "quantity": 1,
            "reason_code": "damage",
        },
        headers=_h(admin_token),
    )
    assert damage_no_note.status_code == 422

    bad_adjust = await client.post(
        "/api/inventory/movements",
        json={
            "item_id": item["id"],
            "location_id": loc,
            "type": "adjust",
            "quantity": 1,
            "reason_code": "other",
        },
        headers=_h(admin_token),
    )
    assert bad_adjust.status_code == 422

    await _move(client, admin_token, item["id"], loc, "in", 5)
    gift_no_note = await client.post(
        "/api/inventory/movements",
        json={
            "item_id": item["id"],
            "location_id": loc,
            "type": "out",
            "quantity": 1,
            "reason_code": "gift",
        },
        headers=_h(admin_token),
    )
    assert gift_no_note.status_code == 422

    filtered = await client.get(
        "/api/inventory/movements?reason_code=opening", headers=_h(admin_token)
    )
    assert filtered.status_code == 200
    assert all(m["reason_code"] == "opening" for m in filtered.json())


# ---- Stocktakes ----


async def _create_stocktake(client: AsyncClient, token: str, location_id: str, **extra) -> dict:
    resp = await client.post(
        "/api/inventory/stocktakes",
        json={"location_id": location_id, **extra},
        headers=_h(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_stocktake_flow(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    item = await _create_item(client, admin_token)
    other = await _create_item(client, admin_token)
    loc = sample_location["id"]
    await _move(client, admin_token, item["id"], loc, "in", 10)
    await _move(client, admin_token, other["id"], loc, "in", 7)

    take = await _create_stocktake(client, admin_token, loc, note="monthly count")
    assert take["status"] == "draft"
    assert len(take["lines"]) == 2
    line_qty = {l["item_id"]: l["system_qty"] for l in take["lines"]}
    assert line_qty[item["id"]] == 10
    assert line_qty[other["id"]] == 7

    await _move(client, admin_token, item["id"], loc, "out", 2)

    patched = await client.patch(
        f"/api/inventory/stocktakes/{take['id']}/lines",
        json={
            "lines": [
                {"item_id": item["id"], "counted_qty": 6},
                {"item_id": other["id"], "counted_qty": 7},
            ]
        },
        headers=_h(admin_token),
    )
    assert patched.status_code == 200, patched.text

    applied = await client.post(
        f"/api/inventory/stocktakes/{take['id']}/apply", headers=_h(admin_token)
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "applied"
    assert applied.json()["applied_at"]

    stock = await _stock_qty(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 6

    adjustments = await client.get(
        f"/api/inventory/movements?item_id={item['id']}&type=adjust", headers=_h(admin_token)
    )
    adjust_rows = [m for m in adjustments.json() if (m["reference"] or "").startswith("STK:")]
    assert len(adjust_rows) == 1
    assert adjust_rows[0]["balance_after"] == 6

    reapplied = await client.post(
        f"/api/inventory/stocktakes/{take['id']}/apply", headers=_h(admin_token)
    )
    assert reapplied.status_code == 200
    adjustments2 = await client.get(
        f"/api/inventory/movements?item_id={item['id']}&type=adjust", headers=_h(admin_token)
    )
    assert len([m for m in adjustments2.json() if (m["reference"] or "").startswith("STK:")]) == 1
    stock = await _stock_qty(client, admin_token, item["id"], loc)
    assert stock["quantity"] == 6

    edit_after = await client.patch(
        f"/api/inventory/stocktakes/{take['id']}/lines",
        json={"lines": [{"item_id": item["id"], "counted_qty": 0}]},
        headers=_h(admin_token),
    )
    assert edit_after.status_code == 409

    cancel_after = await client.post(
        f"/api/inventory/stocktakes/{take['id']}/cancel", headers=_h(admin_token)
    )
    assert cancel_after.status_code == 409


async def test_stocktake_cancel_and_subset(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    item = await _create_item(client, admin_token)
    loc = sample_location["id"]

    take = await _create_stocktake(client, admin_token, loc, item_ids=[item["id"]])
    assert [l["item_id"] for l in take["lines"]] == [item["id"]]

    cancelled = await client.post(
        f"/api/inventory/stocktakes/{take['id']}/cancel", headers=_h(admin_token)
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    apply_cancelled = await client.post(
        f"/api/inventory/stocktakes/{take['id']}/apply", headers=_h(admin_token)
    )
    assert apply_cancelled.status_code == 409

    listed = await client.get("/api/inventory/stocktakes?status=cancelled", headers=_h(admin_token))
    assert any(t["id"] == take["id"] for t in listed.json())


# ---- CSV import / export ----


def _csv_file(content: str, name: str = "import.csv") -> dict:
    return {"file": (name, content.encode("utf-8"), "text/csv")}


async def test_items_csv_import_and_export(client: AsyncClient, admin_token: str):
    existing = await _create_item(client, admin_token, sku_code="BK-OLD-1")

    csv_content = (
        "sku_code,name_zh,name_en,category,unit_of_measure,cost_price,sale_price,reorder_level\n"
        "BK-NEW-1,新書一,New Book 1,教材,pcs,10,30,5\n"
        "BK-NEW-2,新書二,New Book 2,文具,box,20,60,2\n"
        f"{existing['sku_code']},更新書,Updated Book,教材,pcs,15,40,3\n"
    )
    resp = await client.post(
        "/api/inventory/import/items", files=_csv_file(csv_content), headers=_h(admin_token)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"created": 2, "updated": 1, "skipped": 0, "errors": []}

    new_item = (
        await client.get("/api/inventory/items?search=BK-NEW-1", headers=_h(admin_token))
    ).json()[0]
    cat = await client.get("/api/inventory/categories", headers=_h(admin_token))
    cat_names = {c["name_zh"] for c in cat.json()}
    assert {"教材", "文具"} <= cat_names
    cat_by_id = {c["id"]: c for c in cat.json()}
    assert cat_by_id[new_item["category_id"]]["name_zh"] == "教材"

    updated_item = (
        await client.get(f"/api/inventory/items/{existing['id']}", headers=_h(admin_token))
    ).json()
    assert updated_item["name_zh"] == "更新書"
    assert updated_item["reorder_level"] == 3

    exported = await client.get("/api/inventory/export/items.csv", headers=_h(admin_token))
    assert exported.status_code == 200
    assert "BK-NEW-1" in exported.text
    assert existing["sku_code"] in exported.text
    assert exported.headers["content-type"].startswith("text/csv")


async def test_items_csv_import_bad_rows_persist_nothing(
    client: AsyncClient, admin_token: str
):
    csv_content = (
        "sku_code,name_zh,name_en,category,unit_of_measure,cost_price,sale_price,reorder_level\n"
        "BK-BAD-1,壞行,Bad Row,教材,pcs,abc,10,1\n"
        ",缺SKU,Missing SKU,教材,pcs,1,1,1\n"
    )
    resp = await client.post(
        "/api/inventory/import/items", files=_csv_file(csv_content), headers=_h(admin_token)
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert len(detail["errors"]) == 2

    listed = await client.get("/api/inventory/items?search=BK-BAD-1", headers=_h(admin_token))
    assert listed.json() == []
    listed = await client.get("/api/inventory/items?search=Missing", headers=_h(admin_token))
    assert listed.json() == []


async def test_opening_stock_import_idempotent(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    item = await _create_item(client, admin_token)
    loc_id = sample_location["id"]

    csv_content = f"sku_code,location,quantity\n{item['sku_code']},{loc_id},25\n"
    first = await client.post(
        "/api/inventory/import/opening-stock",
        files=_csv_file(csv_content),
        headers=_h(admin_token),
    )
    assert first.status_code == 200, first.text
    assert first.json()["created"] == 1
    assert first.json()["skipped"] == 0

    second = await client.post(
        "/api/inventory/import/opening-stock",
        files=_csv_file(csv_content),
        headers=_h(admin_token),
    )
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert second.json()["skipped"] == 1

    stock = await _stock_qty(client, admin_token, item["id"], loc_id)
    assert stock["quantity"] == 25

    movements = await client.get(
        f"/api/inventory/movements?item_id={item['id']}", headers=_h(admin_token)
    )
    opening = [m for m in movements.json() if m["reason_code"] == "opening"]
    assert len(opening) == 1

    exported = await client.get(
        f"/api/inventory/export/stocks.csv?location_id={loc_id}", headers=_h(admin_token)
    )
    assert exported.status_code == 200
    assert item["sku_code"] in exported.text
    assert ",25," in exported.text or exported.text.rstrip().endswith(",25,0,25")


async def test_opening_stock_import_by_location_code(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    item = await _create_item(client, admin_token)
    patch = await client.patch(
        f"/api/locations/{sample_location['id']}", json={"code": "MK"}, headers=_h(admin_token)
    )
    if patch.status_code != 200:
        pytest.skip("location code cannot be set via API")
    csv_content = f"sku_code,location_code,quantity\n{item['sku_code']},MK,8\n"
    resp = await client.post(
        "/api/inventory/import/opening-stock",
        files=_csv_file(csv_content),
        headers=_h(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 1


async def test_p2_audit_rows_written(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_location_b: dict
):
    uname = f"sa_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", role="superadmin")
    sa_login = await client.post("/api/auth/login", json={"username": uname, "password": "admin123"})
    sa = sa_login.json()["access_token"]

    item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 10)
    transfer = await client.post(
        "/api/inventory/transfers",
        json={
            "item_id": item["id"],
            "from_location_id": sample_location["id"],
            "to_location_id": sample_location_b["id"],
            "quantity": 2,
        },
        headers=_h(admin_token),
    )
    assert transfer.status_code == 201
    take = await _create_stocktake(client, admin_token, sample_location["id"])

    async def logs(table: str) -> list[dict]:
        resp = await client.get(
            "/api/audit-logs", params={"table_name": table, "page_size": 200}, headers=_h(sa)
        )
        assert resp.status_code == 200
        return resp.json()

    transfer_row = next(
        r
        for r in await logs("inventory_movements")
        if r["record_id"] == transfer.json()["out_movement"]["id"]
    )
    assert transfer_row["action"] == "CREATE"
    take_rows = [r for r in await logs("inventory_stocktakes") if r["record_id"] == take["id"]]
    assert any(r["action"] == "CREATE" for r in take_rows)


async def test_p2_non_admin_forbidden(client: AsyncClient, admin_token: str, sample_location: dict):
    uname = f"staff_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", role="staff")
    login = await client.post("/api/auth/login", json={"username": uname, "password": "admin123"})
    staff_headers = _h(login.json()["access_token"])

    item = await _create_item(client, admin_token)
    for method, url, kwargs in (
        ("GET", "/api/inventory/stocktakes", {}),
        ("POST", "/api/inventory/stocktakes", {"json": {"location_id": sample_location["id"]}}),
        (
            "POST",
            "/api/inventory/transfers",
            {
                "json": {
                    "item_id": item["id"],
                    "from_location_id": sample_location["id"],
                    "to_location_id": sample_location["id"],
                    "quantity": 1,
                }
            },
        ),
        ("GET", "/api/inventory/export/items.csv", {}),
        ("POST", "/api/inventory/import/items", {"files": _csv_file("sku_code,name_zh\nX,x\n")}),
    ):
        resp = await client.request(method, url, headers=staff_headers, **kwargs)
        assert resp.status_code == 403, (method, url, resp.status_code)
