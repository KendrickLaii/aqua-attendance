import csv
import io
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _u(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:6]}"


def _simple(path: str, code_field: str | None, code_len: int = 20):
    def build(**names):
        body = dict(names)
        if code_field:
            body[code_field] = _u("N")[:code_len]
        return body

    return path, build


ENTITIES = {
    "warehouse": _simple("/api/inventory/warehouses", "code"),
    "brand": _simple("/api/inventory/brands", None),
    "category": _simple("/api/inventory/categories", None),
    "item": _simple("/api/inventory/items", "sku_code", 100),
    "product": _simple("/api/inventory/products", "code", 100),
    "supplier": _simple("/api/inventory/suppliers", "code", 100),
    "customer": _simple("/api/inventory/customers", "code", 100),
}


@pytest.mark.parametrize("kind", list(ENTITIES))
async def test_create_with_only_english_name(client: AsyncClient, admin_token: str, kind: str):
    path, build = ENTITIES[kind]
    name_en = _u("Only English ")
    resp = await client.post(path, json=build(name_en=name_en), headers=_h(admin_token))
    assert resp.status_code in (200, 201), resp.text
    assert resp.json()["name_zh"] == name_en
    assert resp.json()["name_en"] == name_en

    blank_zh = _u("Blank zh ")
    resp = await client.post(
        path, json=build(name_zh="   ", name_en=blank_zh), headers=_h(admin_token)
    )
    assert resp.status_code in (200, 201), resp.text
    assert resp.json()["name_zh"] == blank_zh


@pytest.mark.parametrize("kind", list(ENTITIES))
async def test_create_with_both_names_blank_is_422(client: AsyncClient, admin_token: str, kind: str):
    path, build = ENTITIES[kind]
    for names in ({}, {"name_zh": "", "name_en": ""}, {"name_zh": "  ", "name_en": "  "}):
        resp = await client.post(path, json=build(**names), headers=_h(admin_token))
        assert resp.status_code == 422, (names, resp.text)
        assert "Enter a Chinese or English name." in resp.text


@pytest.mark.parametrize("kind", list(ENTITIES))
async def test_update_blank_zh_uses_english(client: AsyncClient, admin_token: str, kind: str):
    path, build = ENTITIES[kind]
    created = await client.post(
        path, json=build(name_zh=_u("中文"), name_en=_u("En ")), headers=_h(admin_token)
    )
    assert created.status_code in (200, 201), created.text
    record_id = created.json()["id"]
    new_en = _u("Renamed ")

    patched = await client.patch(
        f"{path}/{record_id}", json={"name_zh": "", "name_en": new_en}, headers=_h(admin_token)
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name_zh"] == new_en

    rejected = await client.patch(
        f"{path}/{record_id}", json={"name_zh": ""}, headers=_h(admin_token)
    )
    assert rejected.status_code == 422, rejected.text

    untouched = await client.patch(
        f"{path}/{record_id}", json={"is_active": False}, headers=_h(admin_token)
    )
    assert untouched.status_code == 200, untouched.text
    assert untouched.json()["name_zh"] == new_en


async def test_product_with_english_name_only_and_variants(client: AsyncClient, admin_token: str):
    code = _u("P")
    name_en = _u("Tee ")
    resp = await client.post(
        "/api/inventory/products",
        json={
            "code": code,
            "name_en": name_en,
            "options": {"Size": ["S", "M"]},
            "skus": [
                {"sku_code": f"{code}-S", "variant_attrs": {"Size": "S"}},
                {"sku_code": f"{code}-M", "variant_attrs": {"Size": "M"}},
            ],
        },
        headers=_h(admin_token),
    )
    assert resp.status_code == 201, resp.text
    product = resp.json()
    assert product["name_zh"] == name_en
    assert sorted(s["name_zh"] for s in product["skus"]) == [f"{name_en} M", f"{name_en} S"]

    renamed = _u("Shirt ")
    patched = await client.patch(
        f"/api/inventory/products/{product['id']}",
        json={"name_zh": "", "name_en": renamed},
        headers=_h(admin_token),
    )
    assert patched.status_code == 200, patched.text
    assert sorted(s["name_zh"] for s in patched.json()["skus"]) == [f"{renamed} M", f"{renamed} S"]

    generated = await client.post(
        f"/api/inventory/products/{product['id']}/generate-skus", json={}, headers=_h(admin_token)
    )
    assert generated.status_code == 200, generated.text


async def test_brand_and_category_uniqueness_uses_filled_name(client: AsyncClient, admin_token: str):
    name_en = _u("Dup ")
    first = await client.post("/api/inventory/brands", json={"name_en": name_en}, headers=_h(admin_token))
    assert first.status_code == 201, first.text
    second = await client.post("/api/inventory/brands", json={"name_en": name_en.upper()}, headers=_h(admin_token))
    assert second.status_code == 409

    cat_en = _u("Cat ")
    first = await client.post("/api/inventory/categories", json={"name_en": cat_en}, headers=_h(admin_token))
    assert first.status_code == 201, first.text
    second = await client.post("/api/inventory/categories", json={"name_en": cat_en}, headers=_h(admin_token))
    assert second.status_code == 409


async def test_items_csv_import_row_with_only_english_name(client: AsyncClient, admin_token: str):
    sku = _u("CSV")
    name_en = _u("Csv English ")
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["sku_code", "name_zh", "name_en"])
    writer.writerow([sku, "", name_en])
    resp = await client.post(
        "/api/inventory/import/items",
        files={"file": ("items.csv", buffer.getvalue().encode("utf-8"), "text/csv")},
        headers=_h(admin_token),
    )
    assert resp.status_code == 200, resp.text
    found = await client.get(f"/api/inventory/items?search={sku}", headers=_h(admin_token))
    assert found.json()[0]["name_zh"] == name_en

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["sku_code", "name_zh", "name_en"])
    writer.writerow([_u("CSV"), "", ""])
    bad = await client.post(
        "/api/inventory/import/items",
        files={"file": ("items.csv", buffer.getvalue().encode("utf-8"), "text/csv")},
        headers=_h(admin_token),
    )
    assert bad.status_code == 422
