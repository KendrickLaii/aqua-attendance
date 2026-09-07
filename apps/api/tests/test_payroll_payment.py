"""Payroll payment split (cheque / cash) is stored when a slip is marked paid."""

import uuid

import pytest
from httpx import AsyncClient


async def _create_staff_unit(client: AsyncClient, token: str, location_id: str) -> dict:
    code = f"STF-{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/api/units",
        json={
            "code": code,
            "full_name": "Ko Long Yin",
            "unit_type": "staff",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_pay_persists_cheque_and_cash_split(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    unit = await _create_staff_unit(client, admin_token, sample_location["id"])

    created = await client.post(
        "/api/payroll-records",
        json={
            "unit_id": unit["id"],
            "payroll_period_start": "2026-08-01",
            "payroll_period_end": "2026-08-31",
            "net_pay": 1897880.0,
            "status": "approved",
        },
        headers=headers,
    )
    assert created.status_code == 201
    record_id = created.json()["id"]
    assert created.json()["cheque_number"] is None
    assert created.json()["cheque_amount"] == 0
    assert created.json()["cash_amount"] == 0

    paid = await client.patch(
        f"/api/payroll-records/{record_id}",
        json={
            "status": "paid",
            "cheque_number": "  518862  ",
            "cheque_amount": 1897880.0,
            "cash_amount": 0,
        },
        headers=headers,
    )
    assert paid.status_code == 200
    body = paid.json()
    assert body["status"] == "paid"
    assert body["cheque_number"] == "518862"
    assert body["cheque_amount"] == pytest.approx(1897880.0)
    assert body["cash_amount"] == pytest.approx(0.0)
    assert body["payment_date"] is not None

    fetched = await client.get(f"/api/payroll-records/{record_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["cheque_number"] == "518862"
    assert fetched.json()["cheque_amount"] == pytest.approx(1897880.0)


@pytest.mark.asyncio
async def test_pay_split_cash_only(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    unit = await _create_staff_unit(client, admin_token, sample_location["id"])

    created = await client.post(
        "/api/payroll-records",
        json={
            "unit_id": unit["id"],
            "payroll_period_start": "2026-08-01",
            "payroll_period_end": "2026-08-31",
            "net_pay": 9000.0,
            "status": "approved",
        },
        headers=headers,
    )
    record_id = created.json()["id"]

    paid = await client.patch(
        f"/api/payroll-records/{record_id}",
        json={
            "status": "paid",
            "cheque_number": "",
            "cheque_amount": 0,
            "cash_amount": 9000.0,
        },
        headers=headers,
    )
    assert paid.status_code == 200
    body = paid.json()
    assert body["cheque_number"] is None
    assert body["cash_amount"] == pytest.approx(9000.0)
