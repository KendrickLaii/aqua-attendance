import csv
import io
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}"


async def _brand(client: AsyncClient, token: str, **overrides) -> dict:
    resp = await client.post(
        "/api/inventory/brands", json={"name_zh": _name("品牌"), **overrides}, headers=_h(token)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _category(client: AsyncClient, token: str, expected: int = 201, **overrides):
    resp = await client.post(
        "/api/inventory/categories", json={"name_zh": _name("分類"), **overrides}, headers=_h(token)
    )
    assert resp.status_code == expected, resp.text
    return resp.json()


async def _item(client: AsyncClient, token: str, **overrides) -> dict:
    resp = await client.post(
        "/api/inventory/items",
        json={"sku_code": _name("ITM"), "name_zh": "貨品", **overrides},
        headers=_h(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_brand_crud_and_duplicates(client: AsyncClient, admin_token: str):
    name = _name("IKEA")
    brand = await _brand(client, admin_token, name_zh=f"  {name}  ", name_en="Ikea")
    assert brand["name_zh"] == name
    assert brand["is_active"] is True

    for dup in (name, name.lower(), f" {name} "):
        resp = await client.post("/api/inventory/brands", json={"name_zh": dup}, headers=_h(admin_token))
        assert resp.status_code == 409, dup

    other = await _brand(client, admin_token)
    clash = await client.patch(
        f"/api/inventory/brands/{other['id']}", json={"name_zh": name.upper()}, headers=_h(admin_token)
    )
    assert clash.status_code == 409

    same = await client.patch(
        f"/api/inventory/brands/{brand['id']}", json={"name_zh": name, "is_active": False}, headers=_h(admin_token)
    )
    assert same.status_code == 200, same.text
    assert same.json()["is_active"] is False

    listed = await client.get("/api/inventory/brands?is_active=false", headers=_h(admin_token))
    assert any(b["id"] == brand["id"] for b in listed.json())
    active = await client.get("/api/inventory/brands?is_active=true", headers=_h(admin_token))
    assert all(b["is_active"] for b in active.json())

    missing = await client.patch(
        f"/api/inventory/brands/{uuid.uuid4()}", json={"name_zh": "x"}, headers=_h(admin_token)
    )
    assert missing.status_code == 404


async def test_item_and_product_brand_validation_and_filters(client: AsyncClient, admin_token: str):
    brand = await _brand(client, admin_token)
    other_brand = await _brand(client, admin_token)

    bad_item = await client.post(
        "/api/inventory/items",
        json={"sku_code": _name("X"), "name_zh": "x", "brand_id": str(uuid.uuid4())},
        headers=_h(admin_token),
    )
    assert bad_item.status_code == 422
    bad_product = await client.post(
        "/api/inventory/products",
        json={"code": _name("P"), "name_zh": "x", "brand_id": str(uuid.uuid4())},
        headers=_h(admin_token),
    )
    assert bad_product.status_code == 422

    item = await _item(client, admin_token, brand_id=brand["id"])
    await _item(client, admin_token, brand_id=other_brand["id"])
    assert item["brand_id"] == brand["id"]
    product = await client.post(
        "/api/inventory/products",
        json={"code": _name("P"), "name_zh": "產品", "brand_id": brand["id"]},
        headers=_h(admin_token),
    )
    assert product.status_code == 201, product.text
    assert product.json()["brand_id"] == brand["id"]

    items = await client.get(f"/api/inventory/items?brand_id={brand['id']}", headers=_h(admin_token))
    assert [i["id"] for i in items.json()] == [item["id"]]
    products = await client.get(f"/api/inventory/products?brand_id={brand['id']}", headers=_h(admin_token))
    assert [p["id"] for p in products.json()] == [product.json()["id"]]

    patched = await client.patch(
        f"/api/inventory/items/{item['id']}", json={"brand_id": str(uuid.uuid4())}, headers=_h(admin_token)
    )
    assert patched.status_code == 422


async def test_category_two_level_rules(client: AsyncClient, admin_token: str):
    parent = await _category(client, admin_token)
    assert parent["parent_id"] is None
    child = await _category(client, admin_token, parent_id=parent["id"])
    assert child["parent_id"] == parent["id"]

    # parent must exist
    await _category(client, admin_token, expected=422, parent_id=str(uuid.uuid4()))
    # only 2 levels
    too_deep = await _category(client, admin_token, expected=422, parent_id=child["id"])
    assert "2 levels" in too_deep["detail"]

    # patch: self parent, missing parent, sub-level parent
    other_top = await _category(client, admin_token)
    for parent_id in (str(uuid.uuid4()), child["id"]):
        resp = await client.patch(
            f"/api/inventory/categories/{other_top['id']}", json={"parent_id": parent_id}, headers=_h(admin_token)
        )
        assert resp.status_code == 422, parent_id
    self_parent = await client.patch(
        f"/api/inventory/categories/{other_top['id']}",
        json={"parent_id": other_top["id"]},
        headers=_h(admin_token),
    )
    assert self_parent.status_code == 422

    # a category with children cannot get a parent
    has_children = await client.patch(
        f"/api/inventory/categories/{parent['id']}",
        json={"parent_id": other_top["id"]},
        headers=_h(admin_token),
    )
    assert has_children.status_code == 422

    # leaf can be re-parented, and moved back to top level
    moved = await client.patch(
        f"/api/inventory/categories/{child['id']}", json={"parent_id": other_top["id"]}, headers=_h(admin_token)
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["parent_id"] == other_top["id"]
    top_again = await client.patch(
        f"/api/inventory/categories/{child['id']}", json={"parent_id": None}, headers=_h(admin_token)
    )
    assert top_again.status_code == 200
    assert top_again.json()["parent_id"] is None


async def test_category_sibling_duplicates(client: AsyncClient, admin_token: str):
    parent_a = await _category(client, admin_token)
    parent_b = await _category(client, admin_token)
    name = _name("手機")
    first = await _category(client, admin_token, name_zh=name, parent_id=parent_a["id"])

    dup = await client.post(
        "/api/inventory/categories",
        json={"name_zh": f" {name.upper()} ", "parent_id": parent_a["id"]},
        headers=_h(admin_token),
    )
    assert dup.status_code == 409

    other_parent = await _category(client, admin_token, name_zh=name, parent_id=parent_b["id"])
    assert other_parent["id"] != first["id"]

    top_dup_name = parent_a["name_zh"]
    top_dup = await client.post(
        "/api/inventory/categories", json={"name_zh": top_dup_name}, headers=_h(admin_token)
    )
    assert top_dup.status_code == 409

    rename_clash = await client.patch(
        f"/api/inventory/categories/{other_parent['id']}",
        json={"parent_id": parent_a["id"]},
        headers=_h(admin_token),
    )
    assert rename_clash.status_code == 409

    ok = await client.patch(
        f"/api/inventory/categories/{first['id']}",
        json={"name_zh": name, "is_active": False},
        headers=_h(admin_token),
    )
    assert ok.status_code == 200, ok.text


async def test_category_filter_includes_children(client: AsyncClient, admin_token: str):
    parent = await _category(client, admin_token)
    child = await _category(client, admin_token, parent_id=parent["id"])
    sibling = await _category(client, admin_token)

    in_parent = await _item(client, admin_token, category_id=parent["id"])
    in_child = await _item(client, admin_token, category_id=child["id"])
    elsewhere = await _item(client, admin_token, category_id=sibling["id"])

    by_parent = await client.get(f"/api/inventory/items?category_id={parent['id']}", headers=_h(admin_token))
    ids = {i["id"] for i in by_parent.json()}
    assert ids == {in_parent["id"], in_child["id"]}
    assert elsewhere["id"] not in ids

    by_child = await client.get(f"/api/inventory/items?category_id={child['id']}", headers=_h(admin_token))
    assert {i["id"] for i in by_child.json()} == {in_child["id"]}

    product = await client.post(
        "/api/inventory/products",
        json={"code": _name("P"), "name_zh": "產品", "category_id": child["id"]},
        headers=_h(admin_token),
    )
    assert product.status_code == 201
    products = await client.get(f"/api/inventory/products?category_id={parent['id']}", headers=_h(admin_token))
    assert [p["id"] for p in products.json()] == [product.json()["id"]]


def _csv_file(header: list[str], rows: list[list[str]]):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return {"file": ("items.csv", buffer.getvalue().encode("utf-8"), "text/csv")}


async def test_csv_brand_and_category_path_round_trip(client: AsyncClient, admin_token: str):
    brand = await _brand(client, admin_token)
    parent = await _category(client, admin_token)
    child = await _category(client, admin_token, parent_id=parent["id"])
    sku = _name("CSV")
    item = await _item(client, admin_token, sku_code=sku, category_id=child["id"], brand_id=brand["id"])

    exported = await client.get("/api/inventory/export/items.csv", headers=_h(admin_token))
    assert exported.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
    row = next(r for r in rows if r["sku_code"] == sku)
    assert row["category"] == f"{parent['name_zh']} > {child['name_zh']}"
    assert row["brand"] == brand["name_zh"]

    # re-import after clearing category/brand by editing the item
    await client.patch(
        f"/api/inventory/items/{item['id']}", json={"category_id": None, "brand_id": None}, headers=_h(admin_token)
    )
    header = list(rows[0].keys())
    resp = await client.post(
        "/api/inventory/import/items",
        files=_csv_file(header, [[row[h] for h in header]]),
        headers=_h(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"] == 1
    fetched = (await client.get(f"/api/inventory/items/{item['id']}", headers=_h(admin_token))).json()
    assert fetched["category_id"] == child["id"]
    assert fetched["brand_id"] == brand["id"]


async def test_csv_import_creates_path_categories_and_rejects_unknown_brand(
    client: AsyncClient, admin_token: str
):
    parent_name, child_name = _name("家電"), _name("手機")
    sku = _name("CSV")
    ok = await client.post(
        "/api/inventory/import/items",
        files=_csv_file(
            ["sku_code", "name_zh", "category"], [[sku, "貨品", f"{parent_name} > {child_name}"]]
        ),
        headers=_h(admin_token),
    )
    assert ok.status_code == 200, ok.text
    cats = (await client.get("/api/inventory/categories", headers=_h(admin_token))).json()
    new_parent = next(c for c in cats if c["name_zh"] == parent_name)
    new_child = next(c for c in cats if c["name_zh"] == child_name)
    assert new_child["parent_id"] == new_parent["id"]

    bad_brand = await client.post(
        "/api/inventory/import/items",
        files=_csv_file(["sku_code", "name_zh", "brand"], [[_name("CSV"), "貨品", _name("不存在")]]),
        headers=_h(admin_token),
    )
    assert bad_brand.status_code == 422
    assert "unknown brand" in bad_brand.text

    old_format = await client.post(
        "/api/inventory/import/items",
        files=_csv_file(["sku_code", "name_zh"], [[_name("CSV"), "舊格式"]]),
        headers=_h(admin_token),
    )
    assert old_format.status_code == 200, old_format.text


async def test_csv_import_ambiguous_category_name(client: AsyncClient, admin_token: str):
    parent_a = await _category(client, admin_token)
    parent_b = await _category(client, admin_token)
    shared = _name("配件")
    await _category(client, admin_token, name_zh=shared, parent_id=parent_a["id"])
    await _category(client, admin_token, name_zh=shared, parent_id=parent_b["id"])

    ambiguous = await client.post(
        "/api/inventory/import/items",
        files=_csv_file(["sku_code", "name_zh", "category"], [[_name("CSV"), "貨品", shared]]),
        headers=_h(admin_token),
    )
    assert ambiguous.status_code == 422
    assert "Parent > Child" in ambiguous.text

    by_path = await client.post(
        "/api/inventory/import/items",
        files=_csv_file(
            ["sku_code", "name_zh", "category"], [[_name("CSV"), "貨品", f"{parent_b['name_zh']} > {shared}"]]
        ),
        headers=_h(admin_token),
    )
    assert by_path.status_code == 200, by_path.text
