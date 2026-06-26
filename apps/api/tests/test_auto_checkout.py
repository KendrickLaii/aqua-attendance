"""Tests for auto-checkout, including selective checkout by product_ids."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import scan_body


async def _create_product(client: AsyncClient, headers: dict, location_id: str) -> dict:
    code = f"STU-{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/api/products",
        json={
            "code": code,
            "full_name": f"Student {code}",
            "product_type": "student",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


async def _check_in(client: AsyncClient, headers: dict, product: dict) -> None:
    qr = await client.get(f"/api/qr/token/{product['id']}", headers=headers)
    resp = await client.post(
        "/api/attendance/scan",
        json=scan_body(qr.json()["qr_token"], product, event_type="check_in"),
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["event_type"] == "check_in"


async def _attendance_status(client: AsyncClient, headers: dict, product_id: str) -> str:
    resp = await client.get(f"/api/products/{product_id}", headers=headers)
    assert resp.status_code == 200
    return resp.json()["attendance_status"]


@pytest.mark.asyncio
async def test_auto_checkout_status_counts_checked_in(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    p1 = await _create_product(client, headers, sample_location["id"])
    p2 = await _create_product(client, headers, sample_location["id"])
    await _check_in(client, headers, p1)
    await _check_in(client, headers, p2)

    resp = await client.get("/api/auto-checkout/status", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["still_checked_in_count"] == 2


@pytest.mark.asyncio
async def test_auto_checkout_only_selected_products(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    p1 = await _create_product(client, headers, sample_location["id"])
    p2 = await _create_product(client, headers, sample_location["id"])
    await _check_in(client, headers, p1)
    await _check_in(client, headers, p2)

    resp = await client.post(
        "/api/auto-checkout/run",
        json={"product_ids": [p1["id"]]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["created_events"] == 1

    # Selected product is checked out; unselected stays checked in for follow-up.
    assert await _attendance_status(client, headers, p1["id"]) == "checked_out"
    assert await _attendance_status(client, headers, p2["id"]) == "checked_in"


@pytest.mark.asyncio
async def test_auto_checkout_empty_selection_checks_out_nobody(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    p1 = await _create_product(client, headers, sample_location["id"])
    await _check_in(client, headers, p1)

    resp = await client.post(
        "/api/auto-checkout/run",
        json={"product_ids": []},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["created_events"] == 0
    assert await _attendance_status(client, headers, p1["id"]) == "checked_in"


@pytest.mark.asyncio
async def test_auto_checkout_without_ids_checks_out_all(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    p1 = await _create_product(client, headers, sample_location["id"])
    p2 = await _create_product(client, headers, sample_location["id"])
    await _check_in(client, headers, p1)
    await _check_in(client, headers, p2)

    resp = await client.post("/api/auto-checkout/run", json={}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["created_events"] == 2

    assert await _attendance_status(client, headers, p1["id"]) == "checked_out"
    assert await _attendance_status(client, headers, p2["id"]) == "checked_out"


@pytest.mark.asyncio
async def test_auto_checkout_requires_admin(
    client: AsyncClient, sample_location: dict
) -> None:
    resp = await client.post("/api/auto-checkout/run", json={})
    assert resp.status_code in (401, 403)
