import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_qr_issue_and_scan(client: AsyncClient, admin_token: str, sample_product: dict):
    """Happy path: admin issues QR for a product, then scans it to record attendance."""
    product_id = sample_product["id"]

    qr_resp = await client.get(
        f"/api/qr/token/{product_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert qr_resp.status_code == 200
    qr_data = qr_resp.json()
    assert "qr_token" in qr_data
    assert qr_data["expires_in"] > 0

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


@pytest.mark.asyncio
async def test_qr_replay_idempotent(client: AsyncClient, admin_token: str, sample_product: dict):
    """Scanning same QR twice returns the same event (idempotent)."""
    product_id = sample_product["id"]

    qr_resp = await client.get(
        f"/api/qr/token/{product_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    qr_token = qr_resp.json()["qr_token"]

    scan1 = await client.post(
        "/api/attendance/scan",
        json={"qr_token": qr_token},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    scan2 = await client.post(
        "/api/attendance/scan",
        json={"qr_token": qr_token},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert scan1.status_code == 200
    assert scan2.status_code == 200
    assert scan1.json()["id"] == scan2.json()["id"]


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
    """Tampered or expired QR token is rejected."""
    resp = await client.post(
        "/api/attendance/scan",
        json={"qr_token": "this.is.not.valid"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_toggle_check_in_out(client: AsyncClient, admin_token: str, sample_product: dict):
    """Second scan of the day should be check_out."""
    product_id = sample_product["id"]

    qr1 = (await client.get(
        f"/api/qr/token/{product_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )).json()["qr_token"]
    e1 = (await client.post(
        "/api/attendance/scan",
        json={"qr_token": qr1},
        headers={"Authorization": f"Bearer {admin_token}"},
    )).json()
    assert e1["event_type"] == "check_in"

    qr2 = (await client.get(
        f"/api/qr/token/{product_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )).json()["qr_token"]
    e2 = (await client.post(
        "/api/attendance/scan",
        json={"qr_token": qr2},
        headers={"Authorization": f"Bearer {admin_token}"},
    )).json()
    assert e2["event_type"] == "check_out"
