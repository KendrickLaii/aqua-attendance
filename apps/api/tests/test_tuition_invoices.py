import uuid
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.services.tuition_invoice_generator import _line_from_enrollment


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


def test_line_from_enrollment_per_session_uses_purchased_quantity() -> None:
    sku = SimpleNamespace(id=uuid.uuid4(), code="SESS", name_zh="堂費班", price=150, billing_unit="per_session")
    enrollment = SimpleNamespace(id=uuid.uuid4(), sku=sku, purchased_quantity=8)
    line = _line_from_enrollment(enrollment, already_billed_elsewhere=set())
    assert line is not None
    assert line.billing_unit == "per_session"
    assert float(line.quantity) == 8
    assert float(line.amount) == 1200


def test_line_from_enrollment_per_session_skips_without_purchased_quantity() -> None:
    sku = SimpleNamespace(id=uuid.uuid4(), code="SESS", name_zh="堂費班", price=150, billing_unit="per_session")
    enrollment = SimpleNamespace(id=uuid.uuid4(), sku=sku, purchased_quantity=None)
    assert _line_from_enrollment(enrollment, already_billed_elsewhere=set()) is None


def test_line_from_enrollment_per_session_skips_when_already_billed_elsewhere() -> None:
    sku = SimpleNamespace(id=uuid.uuid4(), code="SESS", name_zh="堂費班", price=150, billing_unit="per_session")
    enrollment = SimpleNamespace(id=uuid.uuid4(), sku=sku, purchased_quantity=8)
    assert _line_from_enrollment(enrollment, already_billed_elsewhere={enrollment.id}) is None


def test_line_from_enrollment_monthly_ignores_purchased_quantity() -> None:
    sku = SimpleNamespace(id=uuid.uuid4(), code="MTH", name_zh="月費班", price=800, billing_unit="monthly")
    enrollment = SimpleNamespace(id=uuid.uuid4(), sku=sku, purchased_quantity=None)
    line = _line_from_enrollment(enrollment, already_billed_elsewhere=set())
    assert line is not None
    assert float(line.quantity) == 1
    assert float(line.amount) == 800


@pytest.mark.asyncio
async def test_generate_per_session_bills_purchased_quantity_once(
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
        end_date="2026-08-31",
        purchased_quantity=8,
    )

    first = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert first.json()["created"] == 1
    line = (
        await client.get("/api/tuition-invoices?year=2026&month=6", headers=_auth(admin_token))
    ).json()[0]["lines"][0]
    assert float(line["quantity"]) == 8
    assert float(line["amount"]) == 1200

    # Re-running Generate for the same month recomputes the same line (still draft).
    second = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert second.json()["updated"] == 1
    line_again = (
        await client.get("/api/tuition-invoices?year=2026&month=6", headers=_auth(admin_token))
    ).json()[0]["lines"][0]
    assert float(line_again["quantity"]) == 8

    # A later month does not bill the one-time charge again.
    july = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=7",
        headers=_auth(admin_token),
    )
    assert july.status_code == 200, july.text
    july_listed = await client.get(
        "/api/tuition-invoices?year=2026&month=7",
        headers=_auth(admin_token),
    )
    assert july_listed.json() == []


@pytest.mark.asyncio
async def test_generate_per_session_skips_when_purchased_quantity_missing(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    """Enrolled while the SKU was monthly, then the SKU switched to per_session."""
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="monthly", price=150)
    await _enroll(
        client,
        admin_token,
        sample_unit["id"],
        sku["id"],
        start_date="2026-06-01",
        end_date="2026-06-30",
    )
    switch = await client.patch(
        f"/api/course-skus/{sku['id']}",
        json={"billing_unit": "per_session"},
        headers=_auth(admin_token),
    )
    assert switch.status_code == 200, switch.text

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
async def test_generate_per_session_rebills_after_invoice_voided(
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
        end_date="2026-08-31",
        purchased_quantity=8,
    )

    await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    invoice_id = (
        await client.get("/api/tuition-invoices?year=2026&month=6", headers=_auth(admin_token))
    ).json()[0]["id"]
    voided = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"status": "void"},
        headers=_auth(admin_token),
    )
    assert voided.status_code == 200, voided.text

    july = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=7",
        headers=_auth(admin_token),
    )
    assert july.json()["created"] == 1
    july_line = (
        await client.get("/api/tuition-invoices?year=2026&month=7", headers=_auth(admin_token))
    ).json()[0]["lines"][0]
    assert float(july_line["quantity"]) == 8
    assert float(july_line["amount"]) == 1200


@pytest.mark.asyncio
async def test_generate_monthly_ignores_meeting_weekdays(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(
        client,
        admin_token,
        spu["id"],
        billing_unit="monthly",
        price=800,
        meeting_weekdays=["monday", "tuesday", "wednesday", "thursday", "friday"],
    )
    await _enroll(
        client,
        admin_token,
        sample_unit["id"],
        sku["id"],
        start_date="2026-06-01",
        end_date="2026-06-30",
    )
    await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    line = (
        await client.get("/api/tuition-invoices?year=2026&month=6", headers=_auth(admin_token))
    ).json()[0]["lines"][0]
    assert line["billing_unit"] == "monthly"
    assert float(line["quantity"]) == 1
    assert float(line["amount"]) == 800


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


@pytest.mark.asyncio
async def test_generate_deletes_stale_draft_after_cancel(
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

    first = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert first.json()["created"] == 1

    cancel = await client.patch(
        f"/api/course-enrollments/{enrollment['id']}",
        json={"status": "cancelled"},
        headers=_auth(admin_token),
    )
    assert cancel.status_code == 200

    second = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert second.status_code == 200, second.text
    assert second.json()["deleted"] == 1

    listed = await client.get(
        "/api/tuition-invoices?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert listed.json() == []


@pytest.mark.asyncio
async def test_issued_line_keeps_snapshot_after_sku_price_change(
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
    await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    listed = await client.get(
        "/api/tuition-invoices?year=2026&month=6",
        headers=_auth(admin_token),
    )
    invoice_id = listed.json()[0]["id"]
    issued = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"status": "issued"},
        headers=_auth(admin_token),
    )
    assert issued.status_code == 200

    price_change = await client.patch(
        f"/api/course-skus/{sku['id']}",
        json={"price": 999},
        headers=_auth(admin_token),
    )
    assert price_change.status_code == 200

    regen = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert regen.json()["skipped"] == 1

    after = await client.get(
        f"/api/tuition-invoices/{invoice_id}",
        headers=_auth(admin_token),
    )
    assert after.status_code == 200
    line = after.json()["lines"][0]
    assert float(line["unit_price"]) == 800
    assert float(after.json()["total"]) == 800


@pytest.mark.asyncio
async def test_paid_invoice_cannot_change_status(
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
    await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    invoice_id = (
        await client.get("/api/tuition-invoices?year=2026&month=6", headers=_auth(admin_token))
    ).json()[0]["id"]
    assert (
        await client.patch(
            f"/api/tuition-invoices/{invoice_id}",
            json={"status": "issued"},
            headers=_auth(admin_token),
        )
    ).status_code == 200
    paid = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"status": "paid"},
        headers=_auth(admin_token),
    )
    assert paid.status_code == 200
    blocked = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"status": "void"},
        headers=_auth(admin_token),
    )
    assert blocked.status_code == 422


@pytest.mark.asyncio
async def test_generate_skips_null_price_and_completed_enrollment(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    unpaid = await _create_sku(client, admin_token, spu["id"], price=None, code=f"NP-{uuid.uuid4().hex[:6]}")
    done = await _create_sku(client, admin_token, spu["id"], code=f"DN-{uuid.uuid4().hex[:6]}")
    await _enroll(
        client,
        admin_token,
        sample_unit["id"],
        unpaid["id"],
        start_date="2026-06-01",
        end_date="2026-06-30",
    )
    enrollment = await _enroll(
        client,
        admin_token,
        sample_unit["id"],
        done["id"],
        start_date="2026-06-01",
        end_date="2026-06-30",
    )
    complete = await client.patch(
        f"/api/course-enrollments/{enrollment['id']}",
        json={"status": "completed"},
        headers=_auth(admin_token),
    )
    assert complete.status_code == 200

    resp = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["created"] == 0
    listed = await client.get(
        "/api/tuition-invoices?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert listed.json() == []


@pytest.mark.asyncio
async def test_generate_merges_two_skus_onto_one_invoice(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku_a = await _create_sku(client, admin_token, spu["id"], price=800, code=f"A-{uuid.uuid4().hex[:6]}")
    sku_b = await _create_sku(client, admin_token, spu["id"], price=150, code=f"B-{uuid.uuid4().hex[:6]}")
    await _enroll(
        client,
        admin_token,
        sample_unit["id"],
        sku_a["id"],
        start_date="2026-06-01",
        end_date="2026-06-30",
    )
    await _enroll(
        client,
        admin_token,
        sample_unit["id"],
        sku_b["id"],
        start_date="2026-06-01",
        end_date="2026-06-30",
    )

    resp = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert resp.json()["created"] == 1
    listed = await client.get(
        "/api/tuition-invoices?year=2026&month=6",
        headers=_auth(admin_token),
    )
    invoices = listed.json()
    assert len(invoices) == 1
    assert len(invoices[0]["lines"]) == 2
    assert float(invoices[0]["total"]) == 950


@pytest.mark.asyncio
async def test_generate_revives_void_when_enrollment_still_active(
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
    await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    invoice_id = (
        await client.get("/api/tuition-invoices?year=2026&month=6", headers=_auth(admin_token))
    ).json()[0]["id"]
    voided = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"status": "void"},
        headers=_auth(admin_token),
    )
    assert voided.status_code == 200
    patch_blocked = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"status": "draft"},
        headers=_auth(admin_token),
    )
    assert patch_blocked.status_code == 422

    regen = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert regen.status_code == 200
    assert regen.json()["updated"] == 1

    after = await client.get(
        f"/api/tuition-invoices/{invoice_id}",
        headers=_auth(admin_token),
    )
    assert after.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_generate_returns_409_on_unique_conflict(
    client: AsyncClient, admin_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.exc import IntegrityError

    from app.routers import tuition_invoices as tuition_router

    async def _boom(*_args, **_kwargs):
        raise IntegrityError("INSERT", {}, Exception("uq_tuition_invoices_unit_period"))

    monkeypatch.setattr(tuition_router, "generate_monthly_tuition_invoices", _boom)

    resp = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_invoices_paginates_with_total_header(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    other = await client.post(
        "/api/units",
        json={
            "code": f"STU-{uuid.uuid4().hex[:6]}",
            "full_name": "Second Student",
            "unit_type": "student",
            "registered_location_id": sample_location["id"],
            "scan_location_ids": [sample_location["id"]],
        },
        headers=_auth(admin_token),
    )
    assert other.status_code == 201
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"])
    await _enroll(
        client, admin_token, sample_unit["id"], sku["id"], start_date="2026-06-01", end_date="2026-06-30"
    )
    await _enroll(
        client, admin_token, other.json()["id"], sku["id"], start_date="2026-06-01", end_date="2026-06-30"
    )
    await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )

    page1 = await client.get(
        "/api/tuition-invoices?year=2026&month=6&page=1&page_size=1",
        headers=_auth(admin_token),
    )
    assert page1.status_code == 200
    assert page1.headers.get("X-Total-Count") == "2"
    assert len(page1.json()) == 1

    page2 = await client.get(
        "/api/tuition-invoices?year=2026&month=6&page=2&page_size=1",
        headers=_auth(admin_token),
    )
    assert len(page2.json()) == 1
    assert page1.json()[0]["id"] != page2.json()[0]["id"]


@pytest.mark.asyncio
async def test_generate_skips_inactive_sku(
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
        end_date="2026-06-30",
    )
    deactivate = await client.patch(
        f"/api/course-skus/{sku['id']}",
        json={"is_active": False},
        headers=_auth(admin_token),
    )
    assert deactivate.status_code == 200

    resp = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["created"] == 0
    listed = await client.get(
        "/api/tuition-invoices?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert listed.json() == []


@pytest.mark.asyncio
async def test_generate_skips_inactive_student(
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
        end_date="2026-06-30",
    )
    deactivate = await client.patch(
        f"/api/units/{sample_unit['id']}",
        json={"is_active": False},
        headers=_auth(admin_token),
    )
    assert deactivate.status_code == 200

    resp = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["created"] == 0
    listed = await client.get(
        "/api/tuition-invoices?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert listed.json() == []


@pytest.mark.asyncio
async def test_invoice_rejects_unknown_status(
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
        end_date="2026-06-30",
    )
    await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    invoice_id = (
        await client.get("/api/tuition-invoices?year=2026&month=6", headers=_auth(admin_token))
    ).json()[0]["id"]
    resp = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"status": "nope"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422
