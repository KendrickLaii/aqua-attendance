import uuid

import pytest
from httpx import AsyncClient


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_spu(client: AsyncClient, admin_token: str) -> dict:
    resp = await client.post(
        "/api/course-spus",
        json={
            "code": f"ENG-{uuid.uuid4().hex[:6]}",
            "name_zh": "英文進修班",
            "subject": "english",
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_sku(client: AsyncClient, admin_token: str, spu_id: str, **overrides) -> dict:
    payload = {
        "spu_id": spu_id,
        "code": f"A1-{uuid.uuid4().hex[:6]}",
        "name_zh": "A1 英文進修班",
        "schedule_note": "Mon 17:30-19:00",
        "price": 800,
        "billing_unit": "monthly",
        **overrides,
    }
    resp = await client.post("/api/course-skus", json=payload, headers=_auth(admin_token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _enroll(
    client: AsyncClient,
    admin_token: str,
    unit_id: str,
    sku_id: str,
    **overrides,
) -> dict:
    payload = {"unit_id": unit_id, "sku_id": sku_id, **overrides}
    resp = await client.post("/api/course-enrollments", json=payload, headers=_auth(admin_token))
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_generate_monthly_invoice_from_enrollment(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"])
    await _enroll(
        client,
        admin_token,
        sample_unit["id"],
        sku["id"],
        start_date="2026-06-01",
        end_date="2026-08-31",
    )

    resp = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["created"] == 1
    assert result["updated"] == 0
    assert result["skipped"] == 0

    listed = await client.get(
        "/api/tuition-invoices?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert listed.status_code == 200, listed.text
    invoices = listed.json()
    assert len(invoices) == 1
    invoice = invoices[0]
    assert invoice["unit_id"] == sample_unit["id"]
    assert invoice["status"] == "draft"
    assert float(invoice["total"]) == 800
    assert len(invoice["lines"]) == 1
    line = invoice["lines"][0]
    assert line["sku_code"] == sku["code"]
    assert line["billing_unit"] == "monthly"
    assert float(line["unit_price"]) == 800
    assert float(line["quantity"]) == 1
    assert float(line["amount"]) == 800


@pytest.mark.asyncio
async def test_generate_skips_enrollment_outside_month(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"])
    await _enroll(
        client,
        admin_token,
        sample_unit["id"],
        sku["id"],
        start_date="2026-07-01",
        end_date="2026-08-31",
    )

    resp = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 0

    listed = await client.get(
        "/api/tuition-invoices?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert listed.json() == []


@pytest.mark.asyncio
async def test_generate_skips_cancelled_enrollment(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"])
    enrollment = await _enroll(
        client,
        admin_token,
        sample_unit["id"],
        sku["id"],
        start_date="2026-06-01",
        end_date="2026-08-31",
    )
    cancel = await client.patch(
        f"/api/course-enrollments/{enrollment['id']}",
        json={"status": "cancelled"},
        headers=_auth(admin_token),
    )
    assert cancel.status_code == 200

    resp = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["created"] == 0


@pytest.mark.asyncio
async def test_generate_per_session_line_uses_quantity_one(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=150)
    await _enroll(
        client,
        admin_token,
        sample_unit["id"],
        sku["id"],
        start_date="2026-06-01",
        end_date="2026-06-30",
    )

    resp = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    listed = await client.get(
        "/api/tuition-invoices?year=2026&month=6",
        headers=_auth(admin_token),
    )
    line = listed.json()[0]["lines"][0]
    assert line["billing_unit"] == "per_session"
    assert float(line["quantity"]) == 1
    assert float(line["amount"]) == 150


@pytest.mark.asyncio
async def test_regenerate_updates_draft_and_skips_issued(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], price=800)
    await _enroll(
        client,
        admin_token,
        sample_unit["id"],
        sku["id"],
        start_date="2026-06-01",
        end_date="2026-08-31",
    )

    first = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert first.json()["created"] == 1

    listed = await client.get(
        "/api/tuition-invoices?year=2026&month=6",
        headers=_auth(admin_token),
    )
    invoice_id = listed.json()[0]["id"]

    second = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert second.json()["created"] == 0
    assert second.json()["updated"] == 1

    issued = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"status": "issued"},
        headers=_auth(admin_token),
    )
    assert issued.status_code == 200, issued.text
    assert issued.json()["status"] == "issued"

    third = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert third.json()["skipped"] == 1
    assert third.json()["updated"] == 0
