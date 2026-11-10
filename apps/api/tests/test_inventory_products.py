import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import _insert_test_user

pytestmark = pytest.mark.asyncio

SIZES = ["S", "M", "L", "XL"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _code(prefix: str = "SPU") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


async def _create_category(client: AsyncClient, token: str) -> dict:
    resp = await client.post(
        "/api/inventory/categories", json={"name_zh": f"校服-{uuid.uuid4().hex[:6]}", "name_en": "Uniform"}, headers=_h(token)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_product(client: AsyncClient, token: str, **overrides) -> dict:
    body = {"code": _code(), "name_zh": "校服 T-shirt", "options": {"尺寸": SIZES}, **overrides}
    resp = await client.post("/api/inventory/products", json=body, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _generate(client: AsyncClient, token: str, product_id: str, **body) -> dict:
    resp = await client.post(
        f"/api/inventory/products/{product_id}/generate-skus", json=body, headers=_h(token)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _create_item(client: AsyncClient, token: str, **overrides):
    body = {"sku_code": f"ITM-{uuid.uuid4().hex[:6]}", "name_zh": "T恤", **overrides}
    return await client.post("/api/inventory/items", json=body, headers=_h(token))


async def test_product_crud_list_and_search(client: AsyncClient, admin_token: str):
    cat = await _create_category(client, admin_token)
    code = _code("TSHIRT")
    product = await _create_product(
        client,
        admin_token,
        code=code,
        name_en="Uniform Tee",
        category_id=cat["id"],
        unit_of_measure="pcs",
        options={" 尺寸 ": [" S ", "M"]},
    )
    assert product["code"] == code
    assert product["options"] == {"尺寸": ["S", "M"]}
    assert product["skus"] == []
    assert product["sku_count"] == 0
    assert product["is_active"] is True

    dup = await client.post(
        "/api/inventory/products", json={"code": code, "name_zh": "other"}, headers=_h(admin_token)
    )
    assert dup.status_code == 409

    bad_cat = await client.post(
        "/api/inventory/products",
        json={"code": _code(), "name_zh": "x", "category_id": str(uuid.uuid4())},
        headers=_h(admin_token),
    )
    assert bad_cat.status_code == 422

    listed = await client.get("/api/inventory/products?search=Uniform Tee", headers=_h(admin_token))
    assert listed.status_code == 200
    assert [p["id"] for p in listed.json()] == [product["id"]]
    assert listed.headers["X-Total-Count"] == "1"

    by_cat = await client.get(f"/api/inventory/products?category_id={cat['id']}", headers=_h(admin_token))
    assert [p["id"] for p in by_cat.json()] == [product["id"]]

    paged = await client.get("/api/inventory/products?page_size=1", headers=_h(admin_token))
    assert len(paged.json()) == 1
    assert int(paged.headers["X-Total-Count"]) >= 1

    patched = await client.patch(
        f"/api/inventory/products/{product['id']}",
        json={"name_zh": "新校服", "is_active": False},
        headers=_h(admin_token),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name_zh"] == "新校服"
    assert patched.json()["is_active"] is False

    inactive = await client.get("/api/inventory/products?is_active=false", headers=_h(admin_token))
    assert any(p["id"] == product["id"] for p in inactive.json())

    other = await _create_product(client, admin_token)
    clash = await client.patch(
        f"/api/inventory/products/{other['id']}", json={"code": code}, headers=_h(admin_token)
    )
    assert clash.status_code == 409

    fetched = await client.get(f"/api/inventory/products/{product['id']}", headers=_h(admin_token))
    assert fetched.status_code == 200
    assert fetched.json()["name_zh"] == "新校服"

    missing = await client.get(f"/api/inventory/products/{uuid.uuid4()}", headers=_h(admin_token))
    assert missing.status_code == 404


@pytest.mark.parametrize(
    "options",
    [
        {"尺寸": [""]},
        {"尺寸": ["  "]},
        {"尺寸": []},
        {"尺寸": ["S", "S"]},
        {"": ["S"]},
        {"尺寸": ["S"], " 尺寸": ["M"]},
        {"k" * 51: ["S"]},
        {f"k{i}": ["a"] for i in range(6)},
        {"尺寸": [str(i) for i in range(51)]},
    ],
)
async def test_product_options_validation(client: AsyncClient, admin_token: str, options: dict):
    resp = await client.post(
        "/api/inventory/products",
        json={"code": _code(), "name_zh": "x", "options": options},
        headers=_h(admin_token),
    )
    assert resp.status_code == 422, resp.text


async def test_empty_options_become_null(client: AsyncClient, admin_token: str):
    product = await _create_product(client, admin_token, options={})
    assert product["options"] is None


async def test_generate_skus(client: AsyncClient, admin_token: str):
    cat = await _create_category(client, admin_token)
    code = _code("TSHIRT")
    product = await _create_product(
        client,
        admin_token,
        code=code,
        name_en="Tee",
        category_id=cat["id"],
        unit_of_measure="pcs",
        image_url="/uploads/tee.png",
    )

    result = await _generate(client, admin_token, product["id"], sale_price=80, cost_price=30, reorder_level=3)
    assert result["sku_count"] == 4
    skus = result["skus"]
    assert [s["sku_code"] for s in skus] == sorted(f"{code}-{size}" for size in SIZES)
    by_size = {s["variant_attrs"]["尺寸"]: s for s in skus}
    assert set(by_size) == set(SIZES)
    xl = by_size["XL"]
    assert xl["sku_code"] == f"{code}-XL"
    assert xl["name_zh"] == "校服 T-shirt XL"
    assert xl["name_en"] == "Tee XL"
    assert xl["category_id"] == cat["id"]
    assert xl["unit_of_measure"] == "pcs"
    assert xl["image_url"] == "/uploads/tee.png"
    assert xl["product_id"] == product["id"]
    assert xl["sale_price"] == 80
    assert xl["cost_price"] == 30
    assert xl["reorder_level"] == 3

    again = await _generate(client, admin_token, product["id"])
    assert again["sku_count"] == 4
    assert {s["id"] for s in again["skus"]} == {s["id"] for s in skus}

    await client.patch(
        f"/api/inventory/products/{product['id']}",
        json={"options": {"尺寸": [*SIZES, "XXL"]}},
        headers=_h(admin_token),
    )
    grown = await _generate(client, admin_token, product["id"])
    assert grown["sku_count"] == 5
    assert {s["id"] for s in skus} <= {s["id"] for s in grown["skus"]}
    assert f"{code}-XXL" in {s["sku_code"] for s in grown["skus"]}

    by_product = await client.get(
        f"/api/inventory/items?product_id={product['id']}", headers=_h(admin_token)
    )
    assert len(by_product.json()) == 5
    assert all(i["product_id"] == product["id"] for i in by_product.json())


async def test_generate_skus_multiple_options(client: AsyncClient, admin_token: str):
    code = _code("MO")
    product = await _create_product(
        client, admin_token, code=code, options={"尺寸": ["S", "M"], "顏色": ["紅", "藍"]}
    )
    result = await _generate(client, admin_token, product["id"])
    assert result["sku_count"] == 4
    assert {s["sku_code"] for s in result["skus"]} == {f"{code}-{a}-{b}" for a in ("S", "M") for b in ("紅", "藍")}
    assert all(s["name_en"] is None for s in result["skus"])
    sample = next(s for s in result["skus"] if s["sku_code"] == f"{code}-S-紅")
    assert sample["variant_attrs"] == {"尺寸": "S", "顏色": "紅"}
    assert sample["name_zh"] == "校服 T-shirt S / 紅"


async def test_generate_skus_conflict_creates_nothing(client: AsyncClient, admin_token: str):
    code = _code("CF")
    product = await _create_product(client, admin_token, code=code)
    unrelated = await _create_item(client, admin_token, sku_code=f"{code}-M")
    assert unrelated.status_code == 201

    resp = await client.post(
        f"/api/inventory/products/{product['id']}/generate-skus", json={}, headers=_h(admin_token)
    )
    assert resp.status_code == 409
    assert f"{code}-M" in resp.json()["detail"]

    fetched = await client.get(f"/api/inventory/products/{product['id']}", headers=_h(admin_token))
    assert fetched.json()["sku_count"] == 0


async def test_generate_skus_without_options_422(client: AsyncClient, admin_token: str):
    product = await _create_product(client, admin_token, options=None)
    resp = await client.post(
        f"/api/inventory/products/{product['id']}/generate-skus", json={}, headers=_h(admin_token)
    )
    assert resp.status_code == 422

    missing = await client.post(
        f"/api/inventory/products/{uuid.uuid4()}/generate-skus", json={}, headers=_h(admin_token)
    )
    assert missing.status_code == 404


async def test_patch_options_cannot_remove_used_values(client: AsyncClient, admin_token: str):
    product = await _create_product(client, admin_token)
    await _generate(client, admin_token, product["id"])
    created = await _create_item(
        client, admin_token, product_id=product["id"], variant_attrs={"尺寸": "XL"}, sku_code=_code("DUP")
    )
    assert created.status_code == 409  # XL already generated

    removed_used = await client.patch(
        f"/api/inventory/products/{product['id']}",
        json={"options": {"尺寸": ["S", "M", "L"]}},
        headers=_h(admin_token),
    )
    assert removed_used.status_code == 409

    removed_key = await client.patch(
        f"/api/inventory/products/{product['id']}", json={"options": None}, headers=_h(admin_token)
    )
    assert removed_key.status_code == 409

    added_key = await client.patch(
        f"/api/inventory/products/{product['id']}",
        json={"options": {"尺寸": SIZES, "顏色": ["紅"]}},
        headers=_h(admin_token),
    )
    assert added_key.status_code == 200, added_key.text

    unused = await _create_product(client, admin_token, options={"尺寸": ["S", "M", "L"]})
    ok = await client.patch(
        f"/api/inventory/products/{unused['id']}",
        json={"options": {"尺寸": ["S", "M"]}},
        headers=_h(admin_token),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["options"] == {"尺寸": ["S", "M"]}


async def test_item_variant_validation(client: AsyncClient, admin_token: str):
    product = await _create_product(client, admin_token)
    pid = product["id"]

    ok = await _create_item(client, admin_token, product_id=pid, variant_attrs={"尺寸": " S "})
    assert ok.status_code == 201, ok.text
    assert ok.json()["variant_attrs"] == {"尺寸": "S"}
    assert ok.json()["product_id"] == pid

    bad_value = await _create_item(client, admin_token, product_id=pid, variant_attrs={"尺寸": "XXXL"})
    assert bad_value.status_code == 422

    bad_key = await _create_item(client, admin_token, product_id=pid, variant_attrs={"顏色": "紅"})
    assert bad_key.status_code == 422

    dup = await _create_item(client, admin_token, product_id=pid, variant_attrs={"尺寸": "S"})
    assert dup.status_code == 409

    no_product = await _create_item(client, admin_token, variant_attrs={"尺寸": "S"})
    assert no_product.status_code == 422

    unknown_product = await _create_item(client, admin_token, product_id=str(uuid.uuid4()))
    assert unknown_product.status_code == 422

    plain = await _create_item(client, admin_token, product_id=pid)
    assert plain.status_code == 201
    assert plain.json()["variant_attrs"] is None

    patch_dup = await client.patch(
        f"/api/inventory/items/{plain.json()['id']}",
        json={"variant_attrs": {"尺寸": "S"}},
        headers=_h(admin_token),
    )
    assert patch_dup.status_code == 409

    patch_ok = await client.patch(
        f"/api/inventory/items/{plain.json()['id']}",
        json={"variant_attrs": {"尺寸": "M"}},
        headers=_h(admin_token),
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["variant_attrs"] == {"尺寸": "M"}

    same = await client.patch(
        f"/api/inventory/items/{plain.json()['id']}",
        json={"variant_attrs": {"尺寸": "M"}, "name_zh": "改名"},
        headers=_h(admin_token),
    )
    assert same.status_code == 200, same.text

    standalone = await _create_item(client, admin_token)
    attrs_without_product = await client.patch(
        f"/api/inventory/items/{standalone.json()['id']}",
        json={"variant_attrs": {"尺寸": "S"}},
        headers=_h(admin_token),
    )
    assert attrs_without_product.status_code == 422


async def test_detaching_product_clears_variant_attrs(client: AsyncClient, admin_token: str):
    product = await _create_product(client, admin_token)
    item = (
        await _create_item(client, admin_token, product_id=product["id"], variant_attrs={"尺寸": "L"})
    ).json()

    detached = await client.patch(
        f"/api/inventory/items/{item['id']}", json={"product_id": None}, headers=_h(admin_token)
    )
    assert detached.status_code == 200, detached.text
    assert detached.json()["product_id"] is None
    assert detached.json()["variant_attrs"] is None

    fetched = await client.get(f"/api/inventory/products/{product['id']}", headers=_h(admin_token))
    assert fetched.json()["sku_count"] == 0

    attached = await client.patch(
        f"/api/inventory/items/{item['id']}",
        json={"product_id": product["id"], "variant_attrs": {"尺寸": "L"}},
        headers=_h(admin_token),
    )
    assert attached.status_code == 200, attached.text
    assert attached.json()["variant_attrs"] == {"尺寸": "L"}


async def test_items_product_filter(client: AsyncClient, admin_token: str):
    product = await _create_product(client, admin_token)
    other = await _create_product(client, admin_token)
    await _generate(client, admin_token, product["id"])
    await _generate(client, admin_token, other["id"])
    await _create_item(client, admin_token)

    resp = await client.get(f"/api/inventory/items?product_id={product['id']}", headers=_h(admin_token))
    assert resp.status_code == 200
    assert len(resp.json()) == 4
    assert resp.headers["X-Total-Count"] == "4"
    assert all(i["product_id"] == product["id"] for i in resp.json())


async def test_product_endpoints_admin_only(client: AsyncClient, admin_token: str):
    uname = f"staff_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", role="staff")
    login = await client.post("/api/auth/login", json={"username": uname, "password": "admin123"})
    assert login.status_code == 200, login.text
    staff_headers = _h(login.json()["access_token"])

    product = await _create_product(client, admin_token)
    pid = product["id"]
    for method, url, kwargs in (
        ("GET", "/api/inventory/products", {}),
        ("POST", "/api/inventory/products", {"json": {"code": _code(), "name_zh": "x"}}),
        ("GET", f"/api/inventory/products/{pid}", {}),
        ("PATCH", f"/api/inventory/products/{pid}", {"json": {"name_zh": "y"}}),
        ("POST", f"/api/inventory/products/{pid}/generate-skus", {"json": {}}),
    ):
        resp = await client.request(method, url, headers=staff_headers, **kwargs)
        assert resp.status_code == 403, (method, url, resp.status_code)


def _options_with_combinations(*counts: int) -> dict[str, list[str]]:
    return {f"opt{i}": [f"v{j}" for j in range(count)] for i, count in enumerate(counts)}


async def test_options_combination_cap(client: AsyncClient, admin_token: str):
    too_many = await client.post(
        "/api/inventory/products",
        json={"code": _code(), "name_zh": "x", "options": _options_with_combinations(6, 6, 6)},
        headers=_h(admin_token),
    )
    assert too_many.status_code == 422, too_many.text
    assert "216 combinations" in too_many.text

    product = await _create_product(client, admin_token, options=_options_with_combinations(10, 20))
    assert product["sku_count"] == 0

    patched = await client.patch(
        f"/api/inventory/products/{product['id']}",
        json={"options": _options_with_combinations(6, 6, 6)},
        headers=_h(admin_token),
    )
    assert patched.status_code == 422

    at_cap = await client.patch(
        f"/api/inventory/products/{product['id']}",
        json={"options": _options_with_combinations(4, 50)},
        headers=_h(admin_token),
    )
    assert at_cap.status_code == 200, at_cap.text


async def test_generate_requires_backfill_after_adding_option(client: AsyncClient, admin_token: str):
    code = _code("BF")
    product = await _create_product(client, admin_token, code=code, options={"尺寸": ["S", "M"]})
    pid = product["id"]
    generated = await _generate(client, admin_token, pid)
    skus = {s["variant_attrs"]["尺寸"]: s for s in generated["skus"]}
    assert len(skus) == 2

    added = await client.patch(
        f"/api/inventory/products/{pid}",
        json={"options": {"尺寸": ["S", "M"], "顏色": ["紅", "藍"]}},
        headers=_h(admin_token),
    )
    assert added.status_code == 200, added.text

    async def generate():
        return await client.post(
            f"/api/inventory/products/{pid}/generate-skus", json={}, headers=_h(admin_token)
        )

    blocked = await generate()
    assert blocked.status_code == 409
    assert f"{code}-S" in blocked.json()["detail"] and f"{code}-M" in blocked.json()["detail"]
    assert "顏色" in blocked.json()["detail"]
    after_block = await client.get(f"/api/inventory/products/{pid}", headers=_h(admin_token))
    assert after_block.json()["sku_count"] == 2

    patch_s = await client.patch(
        f"/api/inventory/items/{skus['S']['id']}",
        json={"variant_attrs": {"尺寸": "S", "顏色": "紅"}},
        headers=_h(admin_token),
    )
    assert patch_s.status_code == 200, patch_s.text
    still_blocked = await generate()
    assert still_blocked.status_code == 409
    assert f"{code}-M" in still_blocked.json()["detail"]
    assert f"{code}-S," not in still_blocked.json()["detail"]

    patch_m = await client.patch(
        f"/api/inventory/items/{skus['M']['id']}",
        json={"variant_attrs": {"尺寸": "M", "顏色": "紅"}},
        headers=_h(admin_token),
    )
    assert patch_m.status_code == 200, patch_m.text

    ok = await generate()
    assert ok.status_code == 200, ok.text
    assert ok.json()["sku_count"] == 4
    assert {s["id"] for s in ok.json()["skus"]} >= {skus["S"]["id"], skus["M"]["id"]}
    assert {tuple(s["variant_attrs"].values()) for s in ok.json()["skus"]} == {
        ("S", "紅"), ("M", "紅"), ("S", "藍"), ("M", "藍")
    }


def _sku(code: str, size: str, **extra) -> dict:
    return {"sku_code": code, "variant_attrs": {"尺寸": size}, **extra}


async def _post_product(client: AsyncClient, token: str, body: dict, expected: int = 201):
    resp = await client.post("/api/inventory/products", json=body, headers=_h(token))
    assert resp.status_code == expected, resp.text
    return resp.json()


async def _patch_product(client: AsyncClient, token: str, product_id: str, body: dict, expected: int = 200):
    resp = await client.patch(f"/api/inventory/products/{product_id}", json=body, headers=_h(token))
    assert resp.status_code == expected, resp.text
    return resp.json()


async def _create_brand(client: AsyncClient, token: str) -> dict:
    resp = await client.post("/api/inventory/brands", json={"name_zh": _code("B")}, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_product_with_skus_is_atomic(client: AsyncClient, admin_token: str):
    cat = await _create_category(client, admin_token)
    code = _code("UP")
    body = {
        "code": code,
        "name_zh": "校服",
        "name_en": "Uniform",
        "category_id": cat["id"],
        "unit_of_measure": "pcs",
        "options": {"尺寸": ["S", "M"]},
        "skus": [
            _sku(f"{code}-S", "S", sale_price=80, cost_price=30, barcode=" 111 ", reorder_level=2),
            _sku(f"{code}-M", "M", sale_price=85, is_active=False),
        ],
    }
    product = await _post_product(client, admin_token, body)
    assert product["sku_count"] == 2
    by_size = {s["variant_attrs"]["尺寸"]: s for s in product["skus"]}
    assert by_size["S"]["name_zh"] == "校服 S"
    assert by_size["S"]["name_en"] == "Uniform S"
    assert by_size["S"]["barcode"] == "111"
    assert by_size["S"]["sale_price"] == 80
    assert by_size["S"]["category_id"] == cat["id"]
    assert by_size["S"]["unit_of_measure"] == "pcs"
    assert by_size["S"]["product_id"] == product["id"]
    assert by_size["M"]["is_active"] is False
    assert by_size["S"]["on_hand"] == 0

    failing = {
        "bad_attrs": (dict(body, code=_code("UP"), skus=[_sku("ATOMIC-1", "S"), _sku("ATOMIC-2", "XL")]), 422),
        "dup_attrs": (dict(body, code=_code("UP"), skus=[_sku("ATOMIC-3", "S"), _sku("ATOMIC-4", "S")]), 409),
        "dup_codes": (dict(body, code=_code("UP"), skus=[_sku("ATOMIC-5", "S"), _sku("ATOMIC-5", "M")]), 409),
        "taken": (dict(body, code=_code("UP"), skus=[_sku(f"{code}-S", "S")]), 409),
        "with_id": (
            dict(body, code=_code("UP"), skus=[{**_sku("ATOMIC-6", "S"), "id": str(uuid.uuid4())}]),
            422,
        ),
        "no_options": ({"code": _code("UP"), "name_zh": "x", "skus": [_sku("ATOMIC-7", "S")]}, 422),
    }
    for name, (payload, expected) in failing.items():
        await _post_product(client, admin_token, payload, expected=expected)

    leftovers = await client.get("/api/inventory/items?search=ATOMIC-", headers=_h(admin_token))
    assert leftovers.json() == []
    for name, (payload, _expected) in failing.items():
        found = await client.get(f"/api/inventory/products?search={payload['code']}", headers=_h(admin_token))
        assert found.json() == [], name


async def test_patch_product_updates_and_adds_skus(client: AsyncClient, admin_token: str):
    code = _code("PA")
    product = await _post_product(
        client,
        admin_token,
        {
            "code": code,
            "name_zh": "T恤",
            "options": {"尺寸": ["S", "M"]},
            "skus": [_sku(f"{code}-S", "S", sale_price=10), _sku(f"{code}-M", "M", sale_price=10)],
        },
    )
    by_size = {s["variant_attrs"]["尺寸"]: s for s in product["skus"]}

    patched = await _patch_product(
        client,
        admin_token,
        product["id"],
        {
            "options": {"尺寸": ["S", "M", "L"]},
            "skus": [
                {**_sku(f"{code}-S", "S", sale_price=12, cost_price=5), "id": by_size["S"]["id"]},
                _sku(f"{code}-L", "L", sale_price=20),
            ],
        },
    )
    assert patched["sku_count"] == 3
    after = {s["variant_attrs"]["尺寸"]: s for s in patched["skus"]}
    assert after["S"]["id"] == by_size["S"]["id"]
    assert after["S"]["sale_price"] == 12
    assert after["S"]["cost_price"] == 5
    assert after["M"]["id"] == by_size["M"]["id"]
    assert after["M"]["sale_price"] == 10
    assert after["L"]["name_zh"] == "T恤 L"

    foreign = (await _create_item(client, admin_token, sku_code=_code("FOREIGN"))).json()
    resp = await client.patch(
        f"/api/inventory/products/{product['id']}",
        json={"skus": [{**_sku("FOREIGN-X", "S"), "id": foreign["id"]}]},
        headers=_h(admin_token),
    )
    assert resp.status_code == 422

    dup_attrs = await client.patch(
        f"/api/inventory/products/{product['id']}",
        json={"skus": [_sku(f"{code}-S2", "S")]},
        headers=_h(admin_token),
    )
    assert dup_attrs.status_code == 409
    four_sizes = {"尺寸": ["S", "M", "L", "XL"]}
    dup_code = await client.patch(
        f"/api/inventory/products/{product['id']}",
        json={"options": four_sizes, "skus": [_sku(f"{code}-S", "XL")]},
        headers=_h(admin_token),
    )
    assert dup_code.status_code == 409
    other_code = await client.patch(
        f"/api/inventory/products/{product['id']}",
        json={"options": four_sizes, "skus": [_sku(foreign["sku_code"], "XL")]},
        headers=_h(admin_token),
    )
    assert other_code.status_code == 409
    assert foreign["sku_code"] in other_code.json()["detail"]

    unchanged = await client.get(f"/api/inventory/products/{product['id']}", headers=_h(admin_token))
    assert unchanged.json()["sku_count"] == 3
    assert unchanged.json()["options"] == {"尺寸": ["S", "M", "L"]}


async def test_patch_adding_option_key_requires_backfill_in_same_request(client: AsyncClient, admin_token: str):
    code = _code("KEY")
    product = await _post_product(
        client,
        admin_token,
        {
            "code": code,
            "name_zh": "T恤",
            "options": {"尺寸": ["S", "M"]},
            "skus": [_sku(f"{code}-S", "S"), _sku(f"{code}-M", "M")],
        },
    )
    by_size = {s["variant_attrs"]["尺寸"]: s for s in product["skus"]}
    new_options = {"尺寸": ["S", "M"], "顏色": ["紅"]}

    only_one = await client.patch(
        f"/api/inventory/products/{product['id']}",
        json={
            "options": new_options,
            "skus": [
                {"id": by_size["S"]["id"], "sku_code": f"{code}-S", "variant_attrs": {"尺寸": "S", "顏色": "紅"}}
            ],
        },
        headers=_h(admin_token),
    )
    assert only_one.status_code == 422
    assert f"{code}-M" in only_one.json()["detail"]

    unchanged = await client.get(f"/api/inventory/products/{product['id']}", headers=_h(admin_token))
    assert unchanged.json()["options"] == {"尺寸": ["S", "M"]}
    assert {s["name_zh"] for s in unchanged.json()["skus"]} == {"T恤 S", "T恤 M"}
    assert all(list(s["variant_attrs"]) == ["尺寸"] for s in unchanged.json()["skus"])

    entries = [
        {"id": by_size[size]["id"], "sku_code": f"{code}-{size}-紅", "variant_attrs": {"尺寸": size, "顏色": "紅"}}
        for size in ("S", "M")
    ]
    ok = await _patch_product(client, admin_token, product["id"], {"options": new_options, "skus": entries})
    assert {s["sku_code"] for s in ok["skus"]} == {f"{code}-S-紅", f"{code}-M-紅"}
    assert {s["name_zh"] for s in ok["skus"]} == {"T恤 S / 紅", "T恤 M / 紅"}

    removed_used = await client.patch(
        f"/api/inventory/products/{product['id']}",
        json={"options": {"尺寸": ["S"], "顏色": ["紅"]}, "skus": []},
        headers=_h(admin_token),
    )
    assert removed_used.status_code == 422


async def test_patch_product_cascades_to_skus(client: AsyncClient, admin_token: str):
    code = _code("CS")
    cat_a = await _create_category(client, admin_token)
    cat_b = await _create_category(client, admin_token)
    brand_a = await _create_brand(client, admin_token)
    brand_b = await _create_brand(client, admin_token)
    product = await _post_product(
        client,
        admin_token,
        {
            "code": code,
            "name_zh": "舊名",
            "name_en": "Old",
            "category_id": cat_a["id"],
            "brand_id": brand_a["id"],
            "unit_of_measure": "pcs",
            "image_url": "/uploads/a.png",
            "options": {"尺寸": ["S", "M"]},
            "skus": [_sku(f"{code}-S", "S"), _sku(f"{code}-M", "M")],
        },
    )
    linked = await _create_item(client, admin_token, sku_code=_code("LINK"), product_id=product["id"])
    assert linked.status_code == 201

    patched = await _patch_product(
        client,
        admin_token,
        product["id"],
        {
            "name_zh": "新名",
            "name_en": None,
            "category_id": cat_b["id"],
            "brand_id": brand_b["id"],
            "unit_of_measure": "box",
            "image_url": "/uploads/b.png",
        },
    )
    assert patched["sku_count"] == 3
    for sku in patched["skus"]:
        assert sku["category_id"] == cat_b["id"]
        assert sku["brand_id"] == brand_b["id"]
        assert sku["unit_of_measure"] == "box"
        if sku["sku_code"] != linked.json()["sku_code"]:
            assert sku["image_url"] == "/uploads/a.png"
        assert sku["name_en"] is None
    names = {s["sku_code"]: s["name_zh"] for s in patched["skus"]}
    assert names[f"{code}-S"] == "新名 S"
    assert names[f"{code}-M"] == "新名 M"
    assert names[linked.json()["sku_code"]] == "新名"


async def test_on_hand_sums_across_warehouses(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_location_b: dict
):
    code = _code("OH")
    product = await _post_product(
        client,
        admin_token,
        {
            "code": code,
            "name_zh": "庫存",
            "options": {"尺寸": ["S", "M"]},
            "skus": [_sku(f"{code}-S", "S"), _sku(f"{code}-M", "M")],
        },
    )
    by_size = {s["variant_attrs"]["尺寸"]: s for s in product["skus"]}
    standalone = (await _create_item(client, admin_token)).json()

    async def move(item_id: str, warehouse_id: str, qty: int):
        resp = await client.post(
            "/api/inventory/movements",
            json={
                "item_id": item_id,
                "warehouse_id": warehouse_id,
                "type": "in",
                "quantity": qty,
                "reason_code": "opening",
            },
            headers=_h(admin_token),
        )
        assert resp.status_code == 201, resp.text

    await move(by_size["S"]["id"], sample_location["id"], 5)
    await move(by_size["S"]["id"], sample_location_b["id"], 7)
    await move(standalone["id"], sample_location["id"], 3)

    fetched = (await client.get(f"/api/inventory/products/{product['id']}", headers=_h(admin_token))).json()
    assert {s["variant_attrs"]["尺寸"]: s["on_hand"] for s in fetched["skus"]} == {"S": 12, "M": 0}

    listed = await client.get(f"/api/inventory/products?search={code}", headers=_h(admin_token))
    assert {s["on_hand"] for s in listed.json()[0]["skus"]} == {12, 0}

    items = await client.get(f"/api/inventory/items?product_id={product['id']}", headers=_h(admin_token))
    assert {i["variant_attrs"]["尺寸"]: i["on_hand"] for i in items.json()} == {"S": 12, "M": 0}
    single = await client.get(f"/api/inventory/items/{standalone['id']}", headers=_h(admin_token))
    assert single.json()["on_hand"] == 3


async def test_inactive_product_forces_skus_inactive(client: AsyncClient, admin_token: str):
    code = _code("ACT")
    options = {"尺寸": ["S", "M"]}
    product = await _post_product(
        client,
        admin_token,
        {"code": code, "name_zh": "停用", "options": options, "skus": [_sku(f"{code}-S", "S"), _sku(f"{code}-M", "M")]},
    )
    assert all(s["is_active"] for s in product["skus"])
    ids = {s["variant_attrs"]["尺寸"]: s["id"] for s in product["skus"]}

    off = await _patch_product(client, admin_token, product["id"], {"is_active": False})
    assert off["is_active"] is False
    assert all(s["is_active"] is False for s in off["skus"])

    still_off = await _patch_product(
        client,
        admin_token,
        product["id"],
        {"skus": [{**_sku(f"{code}-S", "S", is_active=True), "id": ids["S"]}]},
    )
    assert all(s["is_active"] is False for s in still_off["skus"])

    blocked = await client.patch(
        f"/api/inventory/items/{ids['M']}", json={"is_active": True}, headers=_h(admin_token)
    )
    assert blocked.status_code == 409
    assert "Product is inactive" in blocked.json()["detail"]
    blocked_create = await _create_item(
        client, admin_token, product_id=product["id"], variant_attrs=None, is_active=True
    )
    assert blocked_create.status_code == 409

    on = await _patch_product(
        client,
        admin_token,
        product["id"],
        {
            "is_active": True,
            "skus": [
                {**_sku(f"{code}-S", "S", is_active=True), "id": ids["S"]},
                {**_sku(f"{code}-M", "M", is_active=False), "id": ids["M"]},
            ],
        },
    )
    assert {s["variant_attrs"]["尺寸"]: s["is_active"] for s in on["skus"]} == {"S": True, "M": False}

    reactivate_only = await _patch_product(client, admin_token, product["id"], {"is_active": False})
    assert all(s["is_active"] is False for s in reactivate_only["skus"])
    back_on = await _patch_product(client, admin_token, product["id"], {"is_active": True})
    assert all(s["is_active"] is False for s in back_on["skus"])
    allowed = await client.patch(
        f"/api/inventory/items/{ids['S']}", json={"is_active": True}, headers=_h(admin_token)
    )
    assert allowed.status_code == 200, allowed.text


async def test_create_inactive_product_with_skus(client: AsyncClient, admin_token: str):
    code = _code("ACT")
    product = await _post_product(
        client,
        admin_token,
        {
            "code": code,
            "name_zh": "停用",
            "is_active": False,
            "options": {"尺寸": ["S"]},
            "skus": [_sku(f"{code}-S", "S", is_active=True)],
        },
    )
    assert [s["is_active"] for s in product["skus"]] == [False]
