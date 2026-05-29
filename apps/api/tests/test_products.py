import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_products_x_total_count(client: AsyncClient, admin_token: str) -> None:
    for i in range(3):
        code = f"CNT-{uuid.uuid4().hex[:6]}"
        resp = await client.post(
            "/api/products",
            json={"code": code, "full_name": f"Product {i}", "product_type": "student"},
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
) -> None:
    qr = await client.get(
        f"/api/qr/token/{sample_product['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    token = qr.json()["qr_token"]

    scan = await client.post(
        "/api/attendance/scan",
        json={"qr_token": token, "device_id": "test", "event_type": "check_in"},
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
async def test_product_employment_type(client: AsyncClient, admin_token: str) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    code = f"EMP-{uuid.uuid4().hex[:6]}"

    create = await client.post(
        "/api/products",
        json={
            "code": code,
            "full_name": "Part-time Tutor",
            "product_type": "staff",
            "employment_type": "part_time",
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
        },
        headers=headers,
    )
    assert invalid.status_code == 422
