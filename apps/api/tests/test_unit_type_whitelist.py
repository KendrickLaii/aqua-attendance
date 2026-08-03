"""#M19: attendance / QR endpoints reject non-eligible unit types."""

import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy import insert

from app.models.unit import Unit, unit_scan_locations
from app.services.qr import issue_qr_token
from tests.conftest import TestSessionLocal, scan_body


async def _insert_device_unit(location_id: str) -> dict:
    """Bypass API schema Literal so we can create a device unit for defense-in-depth tests."""
    loc_uuid = uuid.UUID(location_id)
    unit = Unit(
        code=f"DEV-{uuid.uuid4().hex[:6]}",
        full_name="Test Device",
        unit_type="device",
        registered_location_id=loc_uuid,
        is_active=True,
    )
    async with TestSessionLocal() as session:
        session.add(unit)
        await session.flush()
        unit_id = unit.id
        qr_token_version = unit.qr_token_version
        await session.execute(
            insert(unit_scan_locations).values(unit_id=unit_id, location_id=loc_uuid)
        )
        await session.commit()
    return {
        "id": str(unit_id),
        "qr_token_version": qr_token_version,
        "scan_location_ids": [location_id],
    }


@pytest.mark.asyncio
async def test_qr_token_rejects_device_unit(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    unit = await _insert_device_unit(sample_location["id"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.get(f"/api/qr/token/{unit['id']}", headers=headers)
    assert resp.status_code == 400
    assert "does not support attendance" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_qr_refresh_rejects_device_unit(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    unit = await _insert_device_unit(sample_location["id"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.post(f"/api/qr/token/{unit['id']}/refresh", headers=headers)
    assert resp.status_code == 400
    assert "does not support attendance" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_scan_rejects_device_unit(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    unit = await _insert_device_unit(sample_location["id"])
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Issue token via service (API endpoint itself rejects device units)
    qr_token = issue_qr_token(unit["id"], unit["qr_token_version"])

    resp = await client.post(
        "/api/attendance/scan",
        json=scan_body(qr_token, unit),
        headers=headers,
    )
    assert resp.status_code == 400
    assert "does not support attendance" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_scan_preview_rejects_device_unit(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    unit = await _insert_device_unit(sample_location["id"])
    headers = {"Authorization": f"Bearer {admin_token}"}
    qr_token = issue_qr_token(unit["id"], unit["qr_token_version"])

    resp = await client.post(
        "/api/attendance/scan/preview",
        json=scan_body(qr_token, unit),
        headers=headers,
    )
    assert resp.status_code == 400
    assert "does not support attendance" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_manual_correction_rejects_device_unit(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    unit = await _insert_device_unit(sample_location["id"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.post(
        "/api/attendance/manual",
        json={
            "unit_id": unit["id"],
            "event_type": "check_in",
            "location_id": sample_location["id"],
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert "does not support attendance" in resp.json()["detail"]
