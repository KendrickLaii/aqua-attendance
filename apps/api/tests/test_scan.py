import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_qr_issue_and_scan(client: AsyncClient, staff_token: str, student_token: str):
    """Happy path: student gets QR, staff scans it, attendance is recorded."""
    qr_resp = await client.get(
        "/api/qr/token",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert qr_resp.status_code == 200
    qr_data = qr_resp.json()
    assert "qr_token" in qr_data
    assert qr_data["expires_in"] > 0

    scan_resp = await client.post(
        "/api/attendance/scan",
        json={"qr_token": qr_data["qr_token"], "device_id": "kiosk-1"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert scan_resp.status_code == 200
    event = scan_resp.json()
    assert event["event_type"] == "check_in"
    assert event["client_device_id"] == "kiosk-1"


@pytest.mark.asyncio
async def test_qr_replay_idempotent(client: AsyncClient, staff_token: str, student_token: str):
    """Scanning same QR twice returns the same event (idempotent)."""
    qr_resp = await client.get(
        "/api/qr/token",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    qr_token = qr_resp.json()["qr_token"]

    scan1 = await client.post(
        "/api/attendance/scan",
        json={"qr_token": qr_token},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    scan2 = await client.post(
        "/api/attendance/scan",
        json={"qr_token": qr_token},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert scan1.status_code == 200
    assert scan2.status_code == 200
    assert scan1.json()["id"] == scan2.json()["id"]


@pytest.mark.asyncio
async def test_student_cannot_scan(client: AsyncClient, student_token: str):
    """Students cannot use the scan endpoint (staff/admin only)."""
    resp = await client.post(
        "/api/attendance/scan",
        json={"qr_token": "fake"},
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_invalid_qr_rejected(client: AsyncClient, staff_token: str):
    """Tampered or expired QR token is rejected."""
    resp = await client.post(
        "/api/attendance/scan",
        json={"qr_token": "this.is.not.valid"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_toggle_check_in_out(client: AsyncClient, staff_token: str, student_token: str):
    """Second scan of the day should be check_out."""
    qr1 = (await client.get("/api/qr/token", headers={"Authorization": f"Bearer {student_token}"})).json()["qr_token"]
    e1 = (await client.post("/api/attendance/scan", json={"qr_token": qr1}, headers={"Authorization": f"Bearer {staff_token}"})).json()
    assert e1["event_type"] == "check_in"

    qr2 = (await client.get("/api/qr/token", headers={"Authorization": f"Bearer {student_token}"})).json()["qr_token"]
    e2 = (await client.post("/api/attendance/scan", json={"qr_token": qr2}, headers={"Authorization": f"Bearer {staff_token}"})).json()
    assert e2["event_type"] == "check_out"
