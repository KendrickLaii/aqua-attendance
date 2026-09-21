"""API hygiene from the remaining review: lock fake writes, recompute payroll totals."""

import uuid

import pytest
from httpx import AsyncClient


async def _staff_unit(client: AsyncClient, token: str, location_id: str) -> dict:
    resp = await client.post(
        "/api/units",
        json={
            "code": f"LCK-{uuid.uuid4().hex[:6]}",
            "full_name": "Lock Staff",
            "unit_type": "staff",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_post_attendance_summary_is_disabled(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    unit = await _staff_unit(client, admin_token, sample_location["id"])
    resp = await client.post(
        "/api/attendance-summaries",
        json={
            "unit_id": unit["id"],
            "summary_date": "2026-08-01",
            "location_id": sample_location["id"],
            "regular_slots": 80,
            "regular_hours": 20,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 405


@pytest.mark.asyncio
async def test_create_payroll_rejects_non_draft_status(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    unit = await _staff_unit(client, admin_token, sample_location["id"])
    resp = await client.post(
        "/api/payroll-records",
        json={
            "unit_id": unit["id"],
            "payroll_period_start": "2026-08-01",
            "payroll_period_end": "2026-08-31",
            "status": "approved",
            "net_pay": 1000,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422, resp.text
    assert "draft" in str(resp.json()["detail"]).lower()


@pytest.mark.asyncio
async def test_patch_payroll_recomputes_gross_and_net(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    unit = await _staff_unit(client, admin_token, sample_location["id"])
    created = await client.post(
        "/api/payroll-records",
        json={
            "unit_id": unit["id"],
            "payroll_period_start": "2026-08-01",
            "payroll_period_end": "2026-08-31",
            "base_salary": 1000,
            "overtime_pay": 100,
            "holiday_pay": 50,
            "adjustment_1": 10,
            "adjustment_2": -20,
            "gross_pay": 9999,
            "net_pay": 1,
            "status": "draft",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]

    patched = await client.patch(
        f"/api/payroll-records/{record_id}",
        json={"adjustment_1": 200, "gross_pay": 0, "net_pay": 0},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["gross_pay"] == pytest.approx(1350.0)
    assert body["net_pay"] == pytest.approx(1330.0)
    assert body["adjustment_1"] == pytest.approx(200.0)
