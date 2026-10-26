import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import _insert_test_user

pytestmark = pytest.mark.asyncio


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_category(client: AsyncClient, token: str, **overrides) -> dict:
    body = {"name_zh": "教材", "name_en": "Books", **overrides}
    resp = await client.post("/api/inventory/categories", json=body, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


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


async def test_category_crud(client: AsyncClient, admin_token: str):
    cat = await _create_category(client, admin_token)
    assert cat["name_zh"] == "教材"
    assert cat["is_active"] is True

    listed = await client.get("/api/inventory/categories", headers=_h(admin_token))
    assert listed.status_code == 200
    assert any(c["id"] == cat["id"] for c in listed.json())

    patched = await client.patch(
        f"/api/inventory/categories/{cat['id']}",
        json={"name_en": "Materials", "is_active": False},
        headers=_h(admin_token),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name_en"] == "Materials"
    assert patched.json()["is_active"] is False

    active_only = await client.get("/api/inventory/categories?is_active=true", headers=_h(admin_token))
    assert all(c["is_active"] for c in active_only.json())


async def test_item_crud_and_search(client: AsyncClient, admin_token: str):
    cat = await _create_category(client, admin_token)
    item = await _create_item(
        client,
        admin_token,
        name_en="Workbook",
        category_id=cat["id"],
        unit_of_measure="pcs",
        cost_price=10,
        sale_price=30,
        reorder_level=5,
    )
    assert item["category_id"] == cat["id"]
    assert item["reorder_level"] == 5

    by_search = await client.get("/api/inventory/items?search=Workbook", headers=_h(admin_token))
    assert any(i["id"] == item["id"] for i in by_search.json())

    by_category = await client.get(f"/api/inventory/items?category_id={cat['id']}", headers=_h(admin_token))
    assert any(i["id"] == item["id"] for i in by_category.json())

    patched = await client.patch(
        f"/api/inventory/items/{item['id']}", json={"sale_price": 35.5}, headers=_h(admin_token)
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["sale_price"] == 35.5

    fetched = await client.get(f"/api/inventory/items/{item['id']}", headers=_h(admin_token))
    assert fetched.status_code == 200

    missing = await client.get(f"/api/inventory/items/{uuid.uuid4()}", headers=_h(admin_token))
    assert missing.status_code == 404


async def test_item_image_url(client: AsyncClient, admin_token: str):
    item = await _create_item(client, admin_token)
    assert item["image_url"] is None

    item = await _create_item(
        client, admin_token, image_url="/api/uploads/abc123.jpg"
    )
    assert item["image_url"] == "/api/uploads/abc123.jpg"

    patched = await client.patch(
        f"/api/inventory/items/{item['id']}",
        json={"image_url": "/api/uploads/def456.png"},
        headers=_h(admin_token),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["image_url"] == "/api/uploads/def456.png"

    cleared = await client.patch(
        f"/api/inventory/items/{item['id']}",
        json={"image_url": None},
        headers=_h(admin_token),
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["image_url"] is None

    fetched = await client.get(f"/api/inventory/items/{item['id']}", headers=_h(admin_token))
    assert fetched.json()["image_url"] is None


async def test_item_duplicate_sku_rejected(client: AsyncClient, admin_token: str):
    item = await _create_item(client, admin_token)
    dup = await client.post(
        "/api/inventory/items",
        json={"sku_code": item["sku_code"], "name_zh": "重複"},
        headers=_h(admin_token),
    )
    assert dup.status_code == 409


async def test_movement_in_out_and_balance_after(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    item = await _create_item(client, admin_token)
    loc = sample_location["id"]

    m1 = await _move(client, admin_token, item["id"], loc, "in", 10)
    assert m1["quantity_delta"] == 10
    assert m1["balance_after"] == 10

    m2 = await _move(client, admin_token, item["id"], loc, "out", 3)
    assert m2["quantity_delta"] == -3
    assert m2["balance_after"] == 7

    stocks = await client.get(f"/api/inventory/stocks?location_id={loc}", headers=_h(admin_token))
    assert stocks.status_code == 200
    stock = next(s for s in stocks.json() if s["item_id"] == item["id"])
    assert stock["quantity"] == 7


async def test_movement_negative_stock_blocked(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    item = await _create_item(client, admin_token)
    loc = sample_location["id"]
    await _move(client, admin_token, item["id"], loc, "in", 4)

    resp = await client.post(
        "/api/inventory/movements",
        json={"item_id": item["id"], "location_id": loc, "type": "out", "quantity": 5},
        headers=_h(admin_token),
    )
    assert resp.status_code == 422

    stocks = await client.get(f"/api/inventory/stocks?location_id={loc}", headers=_h(admin_token))
    stock = next(s for s in stocks.json() if s["item_id"] == item["id"])
    assert stock["quantity"] == 4


async def test_adjust_sets_absolute_count(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    item = await _create_item(client, admin_token)
    loc = sample_location["id"]
    await _move(client, admin_token, item["id"], loc, "in", 10)

    m = await _move(client, admin_token, item["id"], loc, "adjust", 6)
    assert m["quantity_delta"] == -4
    assert m["balance_after"] == 6

    stocks = await client.get(f"/api/inventory/stocks?location_id={loc}", headers=_h(admin_token))
    stock = next(s for s in stocks.json() if s["item_id"] == item["id"])
    assert stock["quantity"] == 6


async def test_movement_reference_idempotent(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    item = await _create_item(client, admin_token)
    loc = sample_location["id"]
    body = {
        "item_id": item["id"],
        "location_id": loc,
        "type": "in",
        "quantity": 5,
        "reference": f"TEST-{uuid.uuid4().hex[:8]}",
    }
    first = await client.post("/api/inventory/movements", json=body, headers=_h(admin_token))
    assert first.status_code == 201, first.text
    second = await client.post("/api/inventory/movements", json=body, headers=_h(admin_token))
    assert second.status_code == 200, second.text  # idempotent repeat → 200
    assert second.json()["id"] == first.json()["id"]

    stocks = await client.get(f"/api/inventory/stocks?location_id={loc}", headers=_h(admin_token))
    stock = next(s for s in stocks.json() if s["item_id"] == item["id"])
    assert stock["quantity"] == 5

    conflict = await client.post(
        "/api/inventory/movements",
        json={**body, "type": "out"},
        headers=_h(admin_token),
    )
    assert conflict.status_code == 409


async def test_movements_list_filters(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_location_b: dict
):
    item = await _create_item(client, admin_token)
    other_item = await _create_item(client, admin_token)
    await _move(client, admin_token, item["id"], sample_location["id"], "in", 10)
    await _move(client, admin_token, other_item["id"], sample_location_b["id"], "in", 2)

    by_item = await client.get(
        f"/api/inventory/movements?item_id={item['id']}", headers=_h(admin_token)
    )
    assert by_item.status_code == 200
    assert all(m["item_id"] == item["id"] for m in by_item.json())
    assert by_item.headers.get("x-total-count") == "1"

    by_location = await client.get(
        f"/api/inventory/movements?location_id={sample_location_b['id']}", headers=_h(admin_token)
    )
    assert all(m["location_id"] == sample_location_b["id"] for m in by_location.json())


async def test_low_stock_endpoint(client: AsyncClient, admin_token: str, sample_location: dict):
    item = await _create_item(client, admin_token, reorder_level=5)
    other = await _create_item(client, admin_token, reorder_level=0)
    loc = sample_location["id"]
    await _move(client, admin_token, item["id"], loc, "in", 3)
    await _move(client, admin_token, other["id"], loc, "in", 10)

    low = await client.get("/api/inventory/low-stock", headers=_h(admin_token))
    assert low.status_code == 200
    low_ids = {s["item_id"] for s in low.json()}
    assert item["id"] in low_ids
    assert other["id"] not in low_ids

    low_items = await client.get("/api/inventory/items?low_stock=true", headers=_h(admin_token))
    assert any(i["id"] == item["id"] for i in low_items.json())
    assert all(i["id"] != other["id"] for i in low_items.json())


async def test_non_admin_forbidden(client: AsyncClient, admin_token: str, sample_location: dict):
    uname = f"staff_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", role="staff")
    login = await client.post("/api/auth/login", json={"username": uname, "password": "admin123"})
    assert login.status_code == 200, login.text
    staff_headers = _h(login.json()["access_token"])

    for method, url, kwargs in (
        ("GET", "/api/inventory/items", {}),
        ("GET", "/api/inventory/categories", {}),
        ("GET", "/api/inventory/stocks", {}),
        ("GET", "/api/inventory/movements", {}),
        ("GET", "/api/inventory/low-stock", {}),
        ("POST", "/api/inventory/categories", {"json": {"name_zh": "x"}}),
        ("POST", "/api/inventory/items", {"json": {"sku_code": "X-1", "name_zh": "x"}}),
        (
            "POST",
            "/api/inventory/movements",
            {"json": {"item_id": str(uuid.uuid4()), "location_id": sample_location["id"], "type": "in", "quantity": 1}},
        ),
    ):
        resp = await client.request(method, url, headers=staff_headers, **kwargs)
        assert resp.status_code == 403, (method, url, resp.status_code)


async def test_movement_unknown_item_404(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    resp = await client.post(
        "/api/inventory/movements",
        json={
            "item_id": str(uuid.uuid4()),
            "location_id": sample_location["id"],
            "type": "in",
            "quantity": 1,
        },
        headers=_h(admin_token),
    )
    assert resp.status_code == 404


async def test_writes_are_audited(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    uname = f"sa_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", role="superadmin")
    sa_login = await client.post("/api/auth/login", json={"username": uname, "password": "admin123"})
    sa = sa_login.json()["access_token"]

    cat = await _create_category(client, admin_token)
    item = await _create_item(client, admin_token, category_id=cat["id"])
    movement = await _move(client, admin_token, item["id"], sample_location["id"], "in", 5)
    await client.patch(
        f"/api/inventory/items/{item['id']}", json={"sale_price": 12}, headers=_h(admin_token)
    )

    async def logs(table: str) -> list[dict]:
        resp = await client.get(
            "/api/audit-logs", params={"table_name": table, "page_size": 200}, headers=_h(sa)
        )
        assert resp.status_code == 200
        return resp.json()

    cat_actions = {r["action"] for r in await logs("inventory_categories") if r["record_id"] == cat["id"]}
    assert "CREATE" in cat_actions
    item_rows = [r for r in await logs("inventory_items") if r["record_id"] == item["id"]]
    assert {r["action"] for r in item_rows} == {"CREATE", "UPDATE"}
    movement_rows = [r for r in await logs("inventory_movements") if r["record_id"] == movement["id"]]
    assert any(r["action"] == "CREATE" for r in movement_rows)
