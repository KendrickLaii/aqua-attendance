import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import _insert_test_user


@pytest.mark.asyncio
async def test_qr_issue_and_scan(client: AsyncClient, admin_token: str, sample_product: dict):
    """Happy path: admin issues QR for a product, then scans it to check in."""
    product_id = sample_product["id"]

    qr_resp = await client.get(
        f"/api/qr/token/{product_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert qr_resp.status_code == 200
    qr_data = qr_resp.json()
    assert "qr_token" in qr_data
    assert qr_data["token_version"] == 1

    scan_resp = await client.post(
        "/api/attendance/scan",
        json={"qr_token": qr_data["qr_token"], "device_id": "kiosk-1"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert scan_resp.status_code == 200
    event = scan_resp.json()
    assert event["event_type"] == "check_in"
    assert event["client_device_id"] == "kiosk-1"
    assert event["product_id"] == product_id
    assert event["attendance_status"] == "checked_in"


@pytest.mark.asyncio
async def test_same_token_toggles_in_then_out(
    client: AsyncClient, admin_token: str, sample_product: dict
):
    """The same QR scanned again should produce a check_out, no refresh needed."""
    product_id = sample_product["id"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    qr_token = (
        await client.get(f"/api/qr/token/{product_id}", headers=headers)
    ).json()["qr_token"]

    e1 = (
        await client.post(
            "/api/attendance/scan", json={"qr_token": qr_token}, headers=headers
        )
    ).json()
    assert e1["event_type"] == "check_in"
    assert e1["attendance_status"] == "checked_in"

    # Wait past the debounce window before the second scan.
    import asyncio
    await asyncio.sleep(3.2)

    e2 = (
        await client.post(
            "/api/attendance/scan", json={"qr_token": qr_token}, headers=headers
        )
    ).json()
    assert e2["event_type"] == "check_out"
    assert e2["attendance_status"] == "checked_out"
    assert e2["id"] != e1["id"]


@pytest.mark.asyncio
async def test_debounce_returns_existing_event(
    client: AsyncClient, admin_token: str, sample_product: dict
):
    """Rapid duplicate scans return the same event (kiosk double-tap protection)."""
    product_id = sample_product["id"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    qr_token = (
        await client.get(f"/api/qr/token/{product_id}", headers=headers)
    ).json()["qr_token"]

    scan1 = await client.post(
        "/api/attendance/scan", json={"qr_token": qr_token}, headers=headers
    )
    scan2 = await client.post(
        "/api/attendance/scan", json={"qr_token": qr_token}, headers=headers
    )
    assert scan1.status_code == 200
    assert scan2.status_code == 200
    assert scan1.json()["id"] == scan2.json()["id"]
    assert scan1.json()["event_type"] == "check_in"
    assert scan2.json()["event_type"] == "check_in"


@pytest.mark.asyncio
async def test_refresh_invalidates_old_token(
    client: AsyncClient, admin_token: str, sample_product: dict
):
    """After refresh, the previous QR token is rejected with 400."""
    product_id = sample_product["id"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    old_token = (
        await client.get(f"/api/qr/token/{product_id}", headers=headers)
    ).json()["qr_token"]

    refresh = await client.post(
        f"/api/qr/token/{product_id}/refresh", headers=headers
    )
    assert refresh.status_code == 200
    new_data = refresh.json()
    assert new_data["token_version"] == 2
    assert new_data["qr_token"] != old_token

    rejected = await client.post(
        "/api/attendance/scan", json={"qr_token": old_token}, headers=headers
    )
    assert rejected.status_code == 400

    accepted = await client.post(
        "/api/attendance/scan",
        json={"qr_token": new_data["qr_token"]},
        headers=headers,
    )
    assert accepted.status_code == 200
    assert accepted.json()["event_type"] == "check_in"


@pytest.mark.asyncio
async def test_unauthenticated_cannot_scan(client: AsyncClient):
    """Unauthenticated requests cannot use the scan endpoint."""
    resp = await client.post(
        "/api/attendance/scan",
        json={"qr_token": "fake"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_invalid_qr_rejected(client: AsyncClient, admin_token: str):
    """Tampered token is rejected."""
    resp = await client.post(
        "/api/attendance/scan",
        json={"qr_token": "this.is.not.valid"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_manual_check_in_updates_status(
    client: AsyncClient, admin_token: str, sample_product: dict
):
    """A manual check_in correction should set the product's attendance_status."""
    product_id = sample_product["id"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.post(
        "/api/attendance/manual",
        json={"product_id": product_id, "event_type": "check_in"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["attendance_status"] == "checked_in"

    product = (
        await client.get(f"/api/products/{product_id}", headers=headers)
    ).json()
    assert product["attendance_status"] == "checked_in"


@pytest.mark.asyncio
async def test_inactive_product_scan_rejected(
    client: AsyncClient, admin_token: str, sample_product: dict
):
    """Scanning an inactive product should be rejected."""
    product_id = sample_product["id"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    qr_token = (
        await client.get(f"/api/qr/token/{product_id}", headers=headers)
    ).json()["qr_token"]

    await client.patch(
        f"/api/products/{product_id}",
        json={"is_active": False},
        headers=headers,
    )

    resp = await client.post(
        "/api/attendance/scan", json={"qr_token": qr_token}, headers=headers
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_unauthenticated_cannot_list_attendance(client: AsyncClient):
    resp = await client.get("/api/attendance")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_scan_or_list(client: AsyncClient, admin_token: str, sample_product: dict):
    """Users without admin/superadmin role cannot scan or list attendance."""
    uname = f"staff_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(
        username=uname,
        email=f"{uname}@test.com",
        password="staff123",
        role="staff",
    )
    login = await client.post("/api/auth/login", json={"username": uname, "password": "staff123"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    qr_resp = await client.get(
        f"/api/qr/token/{sample_product['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    qr_token = qr_resp.json()["qr_token"]

    scan_resp = await client.post(
        "/api/attendance/scan",
        json={"qr_token": qr_token},
        headers=headers,
    )
    assert scan_resp.status_code == 403

    list_resp = await client.get("/api/attendance", headers=headers)
    assert list_resp.status_code == 403
