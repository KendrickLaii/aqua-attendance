"""Regression: /payroll-records/stats returns full-month totals, not a single page."""

import uuid

import pytest
from httpx import AsyncClient


async def _create_staff_product(client: AsyncClient, token: str, location_id: str) -> dict:
    code = f"STF-{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/api/products",
        json={
            "code": code,
            "full_name": "Test Staff",
            "product_type": "staff",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_payroll(
    client: AsyncClient,
    token: str,
    product_id: str,
    *,
    status: str,
    gross: float,
    net: float,
) -> None:
    resp = await client.post(
        "/api/payroll-records",
        json={
            "product_id": product_id,
            "payroll_period_start": "2026-07-01",
            "payroll_period_end": "2026-07-31",
            "gross_pay": gross,
            "net_pay": net,
            "status": status,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_stats_aggregates_all_records_regardless_of_page(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Three staff, each with one payroll record in July 2026 with distinct statuses.
    specs = [
        ("draft", 1000.0, 900.0),
        ("approved", 2000.0, 1800.0),
        ("paid", 3000.0, 2700.0),
    ]
    for status, gross, net in specs:
        product = await _create_staff_product(client, admin_token, sample_location["id"])
        await _create_payroll(
            client, admin_token, product["id"], status=status, gross=gross, net=net
        )

    # Page size of 1 would only surface one record in the list, but stats must be full-month.
    resp = await client.get(
        "/api/payroll-records/stats",
        params={"product_type": "staff", "year": 2026, "month": 7},
        headers=headers,
    )
    assert resp.status_code == 200
    stats = resp.json()

    assert stats["records"] == 3
    assert stats["total_gross_pay"] == pytest.approx(6000.0)
    assert stats["total_net_pay"] == pytest.approx(5400.0)
    assert stats["approved"] == 1
    assert stats["paid"] == 1
    assert stats["pending"] == 1  # draft counts as pending


@pytest.mark.asyncio
async def test_stats_status_filter(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    for status, gross, net in [("paid", 3000.0, 2700.0), ("draft", 1000.0, 900.0)]:
        product = await _create_staff_product(client, admin_token, sample_location["id"])
        await _create_payroll(
            client, admin_token, product["id"], status=status, gross=gross, net=net
        )

    resp = await client.get(
        "/api/payroll-records/stats",
        params={"status": "paid", "year": 2026, "month": 7},
        headers=headers,
    )
    assert resp.status_code == 200
    stats = resp.json()

    assert stats["records"] == 1
    assert stats["total_gross_pay"] == pytest.approx(3000.0)
    assert stats["paid"] == 1
    assert stats["pending"] == 0
