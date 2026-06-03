import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import scan_body


@pytest.mark.asyncio
async def test_list_products_x_total_count(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    for i in range(3):
        code = f"CNT-{uuid.uuid4().hex[:6]}"
        resp = await client.post(
            "/api/products",
            json={
                "code": code,
                "full_name": f"Product {i}",
                "product_type": "student",
                "registered_location_id": sample_location["id"],
                "scan_location_ids": [sample_location["id"]],
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201

    resp = await client.get(
        "/api/products",
        params={"page": 1, "page_size": 2},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Total-Count") == "3"
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_products_attendance_status_filter(
    client: AsyncClient,
    admin_token: str,
    sample_product: dict,
):
    qr = await client.get(
        f"/api/qr/token/{sample_product['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    token = qr.json()["qr_token"]

    scan = await client.post(
        "/api/attendance/scan",
        json=scan_body(token, sample_product, event_type="check_in"),
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert scan.status_code == 200
    assert scan.json()["attendance_status"] == "checked_in"

    checked_in = await client.get(
        "/api/products",
        params={"attendance_status": "checked_in"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert checked_in.status_code == 200
    assert checked_in.headers.get("X-Total-Count") == "1"
    assert len(checked_in.json()) == 1
    assert checked_in.json()[0]["id"] == sample_product["id"]

    checked_out = await client.get(
        "/api/products",
        params={"attendance_status": "checked_out"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert checked_out.status_code == 200
    assert checked_out.headers.get("X-Total-Count") == "0"
    assert checked_out.json() == []


@pytest.mark.asyncio
async def test_list_products_invalid_attendance_status(client: AsyncClient, admin_token: str) -> None:
    resp = await client.get(
        "/api/products",
        params={"attendance_status": "invalid"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_product_employment_type(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    code = f"EMP-{uuid.uuid4().hex[:6]}"

    create = await client.post(
        "/api/products",
        json={
            "code": code,
            "full_name": "Part-time Tutor",
            "product_type": "staff",
            "employment_type": "part_time",
            "registered_location_id": sample_location["id"],
            "scan_location_ids": [sample_location["id"]],
        },
        headers=headers,
    )
    assert create.status_code == 201
    assert create.json()["employment_type"] == "part_time"

    listed = await client.get(
        "/api/products",
        params={"employment_type": "part_time"},
        headers=headers,
    )
    assert listed.status_code == 200
    assert any(p["code"] == code for p in listed.json())

    invalid = await client.post(
        "/api/products",
        json={
            "code": f"BAD-{uuid.uuid4().hex[:6]}",
            "full_name": "Bad",
            "product_type": "staff",
            "employment_type": "contract",
            "registered_location_id": sample_location["id"],
            "scan_location_ids": [sample_location["id"]],
        },
        headers=headers,
    )
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_product_requires_registered_and_scan_locations(
    client: AsyncClient, admin_token: str
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = await client.post(
        "/api/products",
        json={
            "code": f"NOLOC-{uuid.uuid4().hex[:6]}",
            "full_name": "Missing locations",
            "product_type": "student",
        },
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_product_registered_and_scan_locations(
    client: AsyncClient,
    admin_token: str,
    sample_location: dict,
    sample_location_b: dict,
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    code = f"LOC-{uuid.uuid4().hex[:6]}"

    create = await client.post(
        "/api/products",
        json={
            "code": code,
            "full_name": "Multi-branch staff",
            "product_type": "staff",
            "employment_type": "full_time",
            "registered_location_id": sample_location["id"],
            "scan_location_ids": [sample_location["id"], sample_location_b["id"]],
        },
        headers=headers,
    )
    assert create.status_code == 201
    body = create.json()
    assert body["registered_location_id"] == sample_location["id"]
    assert body["registered_location"]["name_en"] == sample_location["name_en"]
    assert set(body["scan_location_ids"]) == {sample_location["id"], sample_location_b["id"]}
    assert len(body["scan_locations"]) == 2

    patch = await client.patch(
        f"/api/products/{body['id']}",
        json={
            "scan_location_ids": [sample_location_b["id"]],
            "registered_location_id": sample_location_b["id"],
        },
        headers=headers,
    )
    assert patch.status_code == 200
    updated = patch.json()
    assert updated["registered_location_id"] == sample_location_b["id"]
    assert updated["scan_location_ids"] == [sample_location_b["id"]]
