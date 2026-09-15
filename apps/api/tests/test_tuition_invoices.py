import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.course_enrollment import EnrollmentPurchase
from app.services.tuition_invoice_generator import _BillingContext, _lines_from_enrollment
from tests.conftest import TestSessionLocal


def _ctx(**overrides) -> _BillingContext:
    kwargs = {
        "first_day": date.min,
        "last_day": date.max,
        "unbilled_line_ids": set(),
    }
    kwargs.update(overrides)
    return _BillingContext(**kwargs)


def _one_line(enrollment, ctx: _BillingContext | None = None):
    lines, _ = _lines_from_enrollment(enrollment, ctx or _ctx())
    return lines[0] if lines else None


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


def _purchase(quantity=8, price=150, billed_line_id=None, purchased_at=date(2026, 6, 1)):
    return SimpleNamespace(
        id=uuid.uuid4(),
        purchased_quantity=quantity,
        unit_price=price,
        purchased_at=purchased_at,
        billed_invoice_line_id=billed_line_id,
    )


def test_line_from_enrollment_per_session_bills_unbilled_purchase() -> None:
    sku = SimpleNamespace(id=uuid.uuid4(), code="SESS", name_zh="堂費班", price=150, billing_unit="per_session")
    enrollment = SimpleNamespace(id=uuid.uuid4(), sku=sku, unit_price=None, purchases=[_purchase()])
    line = _one_line(enrollment)
    assert line is not None
    assert line.billing_unit == "per_session"
    assert float(line.quantity) == 8
    assert float(line.amount) == 1200


def test_line_from_enrollment_per_session_skips_without_purchases() -> None:
    sku = SimpleNamespace(id=uuid.uuid4(), code="SESS", name_zh="堂費班", price=150, billing_unit="per_session")
    enrollment = SimpleNamespace(id=uuid.uuid4(), sku=sku, unit_price=None, purchases=[])
    assert _one_line(enrollment) is None


def test_line_from_enrollment_per_session_skips_billed_purchase() -> None:
    sku = SimpleNamespace(id=uuid.uuid4(), code="SESS", name_zh="堂費班", price=150, billing_unit="per_session")
    purchase = _purchase(billed_line_id=uuid.uuid4())
    enrollment = SimpleNamespace(id=uuid.uuid4(), sku=sku, unit_price=None, purchases=[purchase])
    assert _one_line(enrollment) is None

    # A line being rebuilt/voided this run does not block re-billing.
    line = _one_line(enrollment, _ctx(unbilled_line_ids={purchase.billed_invoice_line_id}))
    assert line is not None
    assert float(line.amount) == 1200


def test_line_from_enrollment_per_session_skips_future_purchase() -> None:
    sku = SimpleNamespace(id=uuid.uuid4(), code="SESS", name_zh="堂費班", price=150, billing_unit="per_session")
    purchase = _purchase(purchased_at=date(2026, 7, 1))
    enrollment = SimpleNamespace(id=uuid.uuid4(), sku=sku, unit_price=None, purchases=[purchase])
    assert _one_line(enrollment, _ctx(last_day=date(2026, 6, 30))) is None


def test_line_from_enrollment_monthly_ignores_purchased_quantity() -> None:
    sku = SimpleNamespace(id=uuid.uuid4(), code="MTH", name_zh="月費班", price=800, billing_unit="monthly")
    enrollment = SimpleNamespace(id=uuid.uuid4(), sku=sku, purchased_quantity=None, unit_price=None, purchases=[])
    line = _one_line(enrollment)
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


async def _create_staff(client: AsyncClient, admin_token: str, location_id: str) -> dict:
    resp = await client.post(
        "/api/units",
        json={
            "code": f"STF-{uuid.uuid4().hex[:6]}",
            "full_name": "Test Teacher",
            "unit_type": "staff",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_student(
    client: AsyncClient, admin_token: str, location_id: str, name: str
) -> dict:
    resp = await client.post(
        "/api/units",
        json={
            "code": f"STU-{uuid.uuid4().hex[:6]}",
            "full_name": name,
            "unit_type": "student",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_sku_staff_assignment(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    staff = await _create_staff(client, admin_token, sample_location["id"])
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], staff_id=staff["id"])
    assert sku["staff_id"] == staff["id"]

    cleared = await client.patch(
        f"/api/course-skus/{sku['id']}",
        json={"staff_id": None},
        headers=_auth(admin_token),
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["staff_id"] is None

    bad = await client.patch(
        f"/api/course-skus/{sku['id']}",
        json={"staff_id": sample_unit["id"]},
        headers=_auth(admin_token),
    )
    assert bad.status_code == 422


def test_line_from_enrollment_uses_enrollment_unit_price_override() -> None:
    sku = SimpleNamespace(id=uuid.uuid4(), code="PRIV", name_zh="私補", price=None, billing_unit="monthly")
    enrollment = SimpleNamespace(id=uuid.uuid4(), sku=sku, purchased_quantity=None, unit_price=550, purchases=[])
    line = _one_line(enrollment)
    assert line is not None
    assert float(line.unit_price) == 550
    assert float(line.amount) == 550


def test_line_from_enrollment_skips_when_no_price_anywhere() -> None:
    sku = SimpleNamespace(id=uuid.uuid4(), code="PRIV", name_zh="私補", price=None, billing_unit="monthly")
    enrollment = SimpleNamespace(id=uuid.uuid4(), sku=sku, purchased_quantity=None, unit_price=None, purchases=[])
    assert _one_line(enrollment) is None


@pytest.mark.asyncio
async def test_generate_uses_enrollment_price_for_unpriced_sku(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], price=None)
    await _enroll(
        client,
        admin_token,
        sample_unit["id"],
        sku["id"],
        start_date="2026-06-01",
        end_date="2026-08-31",
        unit_price=550,
    )

    resp = await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 1

    invoice = (
        await client.get("/api/tuition-invoices?year=2026&month=6", headers=_auth(admin_token))
    ).json()[0]
    assert float(invoice["total"]) == 550
    assert float(invoice["lines"][0]["unit_price"]) == 550


@pytest.mark.asyncio
async def test_generate_skips_enrollment_with_no_price_anywhere(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], price=None)
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
    assert resp.json()["created"] == 0


@pytest.mark.asyncio
async def test_issue_invoice_auto_assigns_number(
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

    peek = (
        await client.get(
            f"/api/tuition-invoices/next-no?location_id={sample_unit['registered_location_id']}",
            headers=_auth(admin_token),
        )
    ).json()["next_no"]

    resp = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"status": "issued"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["invoice_no"] == str(peek)
    assert body["issued_at"] is not None

    peek_after = (
        await client.get(
            f"/api/tuition-invoices/next-no?location_id={sample_unit['registered_location_id']}",
            headers=_auth(admin_token),
        )
    ).json()["next_no"]
    assert peek_after == peek + 1


@pytest.mark.asyncio
async def test_allocate_invoice_no_increments(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    first = (
        await client.post(
            f"/api/tuition-invoices/allocate-no?location_id={loc}",
            headers=_auth(admin_token),
        )
    ).json()["next_no"]
    second = (
        await client.post(
            f"/api/tuition-invoices/allocate-no?location_id={loc}",
            headers=_auth(admin_token),
        )
    ).json()["next_no"]
    assert second == first + 1


@pytest.mark.asyncio
async def test_duplicate_invoice_no_rejected(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    student_b = await _create_student(client, admin_token, sample_location["id"], "Student B")
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"])
    for student in (sample_unit, student_b):
        await _enroll(
            client,
            admin_token,
            student["id"],
            sku["id"],
            start_date="2026-06-01",
            end_date="2026-06-30",
        )
    await client.post(
        "/api/tuition-invoices/generate?year=2026&month=6",
        headers=_auth(admin_token),
    )
    invoices = (
        await client.get("/api/tuition-invoices?year=2026&month=6", headers=_auth(admin_token))
    ).json()
    assert len(invoices) == 2

    first = await client.patch(
        f"/api/tuition-invoices/{invoices[0]['id']}",
        json={"status": "issued", "invoice_no": "77"},
        headers=_auth(admin_token),
    )
    assert first.status_code == 200, first.text

    dupe = await client.patch(
        f"/api/tuition-invoices/{invoices[1]['id']}",
        json={"status": "issued", "invoice_no": "77"},
        headers=_auth(admin_token),
    )
    assert dupe.status_code == 409


async def _top_up(
    client: AsyncClient,
    admin_token: str,
    enrollment_id: str,
    quantity: int,
    price: float,
    purchased_at: str,
) -> dict:
    resp = await client.post(
        f"/api/course-enrollments/{enrollment_id}/purchases",
        json={
            "purchased_quantity": quantity,
            "unit_price": price,
            "purchased_at": purchased_at,
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _generate(client: AsyncClient, admin_token: str, year: int, month: int) -> dict:
    resp = await client.post(
        f"/api/tuition-invoices/generate?year={year}&month={month}",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _june_invoices(client: AsyncClient, admin_token: str, month: int = 6) -> list[dict]:
    listed = await client.get(
        f"/api/tuition-invoices?year=2026&month={month}",
        headers=_auth(admin_token),
    )
    assert listed.status_code == 200, listed.text
    return listed.json()


@pytest.mark.asyncio
async def test_invoice_numbers_are_per_location(
    client: AsyncClient,
    admin_token: str,
    sample_unit: dict,
    sample_location: dict,
    sample_location_b: dict,
) -> None:
    student_b = await _create_student(client, admin_token, sample_location_b["id"], "Student B")
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"])
    for student in (sample_unit, student_b):
        await _enroll(
            client, admin_token, student["id"], sku["id"],
            start_date="2026-06-01", end_date="2026-06-30",
        )
    await _generate(client, admin_token, 2026, 6)
    invoices = await _june_invoices(client, admin_token)
    assert len(invoices) == 2
    by_location = {inv["location_id"]: inv for inv in invoices}

    issued_a = await client.patch(
        f"/api/tuition-invoices/{by_location[sample_location['id']]['id']}",
        json={"status": "issued"},
        headers=_auth(admin_token),
    )
    assert issued_a.status_code == 200, issued_a.text
    assert issued_a.json()["invoice_no"] == "1"

    issued_b = await client.patch(
        f"/api/tuition-invoices/{by_location[sample_location_b['id']]['id']}",
        json={"status": "issued"},
        headers=_auth(admin_token),
    )
    assert issued_b.status_code == 200, issued_b.text
    assert issued_b.json()["invoice_no"] == "1"

    student_c = await _create_student(client, admin_token, sample_location["id"], "Student C")
    await _enroll(
        client, admin_token, student_c["id"], sku["id"],
        start_date="2026-06-01", end_date="2026-06-30",
    )
    await _generate(client, admin_token, 2026, 6)
    invoice_c = next(
        inv for inv in await _june_invoices(client, admin_token) if inv["unit_id"] == student_c["id"]
    )
    dupe = await client.patch(
        f"/api/tuition-invoices/{invoice_c['id']}",
        json={"status": "issued", "invoice_no": "1"},
        headers=_auth(admin_token),
    )
    assert dupe.status_code == 409


@pytest.mark.asyncio
async def test_next_no_uses_invoice_location(
    client: AsyncClient,
    admin_token: str,
    sample_unit: dict,
    sample_location: dict,
    sample_location_b: dict,
) -> None:
    student_b = await _create_student(client, admin_token, sample_location_b["id"], "Student B")
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"])
    for student in (sample_unit, student_b):
        await _enroll(
            client, admin_token, student["id"], sku["id"],
            start_date="2026-06-01", end_date="2026-06-30",
        )
    await _generate(client, admin_token, 2026, 6)
    invoices = await _june_invoices(client, admin_token)
    invoice_a = next(inv for inv in invoices if inv["unit_id"] == sample_unit["id"])
    issued = await client.patch(
        f"/api/tuition-invoices/{invoice_a['id']}",
        json={"status": "issued"},
        headers=_auth(admin_token),
    )
    assert issued.status_code == 200, issued.text

    next_b = await client.get(
        f"/api/tuition-invoices/next-no?location_id={sample_location_b['id']}",
        headers=_auth(admin_token),
    )
    assert next_b.status_code == 200
    assert next_b.json()["next_no"] == 1


@pytest.mark.asyncio
async def test_enroll_per_session_creates_initial_purchase(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=150)
    enrollment = await _enroll(
        client, admin_token, sample_unit["id"], sku["id"],
        start_date="2026-06-01", purchased_quantity=8,
    )

    fetched = await client.get(
        f"/api/course-enrollments/{enrollment['id']}",
        headers=_auth(admin_token),
    )
    assert fetched.status_code == 200, fetched.text
    purchases = fetched.json()["purchases"]
    assert len(purchases) == 1
    assert purchases[0]["purchased_quantity"] == 8
    assert float(purchases[0]["unit_price"]) == 150


@pytest.mark.asyncio
async def test_topup_bills_only_unbilled_purchase(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=150)
    enrollment = await _enroll(
        client, admin_token, sample_unit["id"], sku["id"],
        start_date="2026-06-01", purchased_quantity=8,
    )

    await _generate(client, admin_token, 2026, 6)
    invoice_id = (await _june_invoices(client, admin_token))[0]["id"]
    issued = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"status": "issued"},
        headers=_auth(admin_token),
    )
    assert issued.status_code == 200, issued.text

    await _top_up(client, admin_token, enrollment["id"], 4, 150, "2026-07-10")

    july = await _generate(client, admin_token, 2026, 7)
    assert july["created"] == 1
    july_invoices = await _june_invoices(client, admin_token, month=7)
    assert len(july_invoices) == 1
    assert len(july_invoices[0]["lines"]) == 1
    line = july_invoices[0]["lines"][0]
    assert float(line["quantity"]) == 4
    assert float(line["amount"]) == 600

    again = await _generate(client, admin_token, 2026, 7)
    assert again["updated"] == 1
    july_again = await _june_invoices(client, admin_token, month=7)
    assert len(july_again[0]["lines"]) == 1
    assert float(july_again[0]["lines"][0]["quantity"]) == 4

    august = await _generate(client, admin_token, 2026, 8)
    assert august["created"] == 0
    assert (await _june_invoices(client, admin_token, month=8)) == []


@pytest.mark.asyncio
async def test_topup_before_first_generate_bills_both(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=150)
    enrollment = await _enroll(
        client, admin_token, sample_unit["id"], sku["id"],
        start_date="2026-06-01", purchased_quantity=8,
    )
    await _top_up(client, admin_token, enrollment["id"], 4, 150, "2026-06-15")

    await _generate(client, admin_token, 2026, 6)
    invoices = await _june_invoices(client, admin_token)
    assert len(invoices) == 1
    lines = invoices[0]["lines"]
    assert len(lines) == 2
    assert sum(float(line["quantity"]) for line in lines) == 12


@pytest.mark.asyncio
async def test_void_makes_purchase_billable_again(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=150)
    enrollment = await _enroll(
        client, admin_token, sample_unit["id"], sku["id"],
        start_date="2026-06-01", purchased_quantity=8,
    )

    await _generate(client, admin_token, 2026, 6)
    invoice_id = (await _june_invoices(client, admin_token))[0]["id"]
    issued = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"status": "issued"},
        headers=_auth(admin_token),
    )
    assert issued.status_code == 200, issued.text
    voided = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"status": "void"},
        headers=_auth(admin_token),
    )
    assert voided.status_code == 200, voided.text

    regen = await _generate(client, admin_token, 2026, 6)
    assert regen["updated"] == 1
    invoices = await _june_invoices(client, admin_token)
    assert len(invoices) == 1
    invoice = invoices[0]
    assert invoice["status"] == "draft"
    assert invoice["invoice_no"] is None
    assert len(invoice["lines"]) == 1
    assert float(invoice["lines"][0]["quantity"]) == 8

    new_line_id = uuid.UUID(invoice["lines"][0]["id"])
    async with TestSessionLocal() as session:
        purchase = (
            await session.execute(
                select(EnrollmentPurchase).where(EnrollmentPurchase.enrollment_id == uuid.UUID(enrollment["id"]))
            )
        ).scalars().one()
        assert purchase.billed_invoice_line_id == new_line_id


@pytest.mark.asyncio
async def test_draft_regenerate_relinks_purchase(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=150)
    enrollment = await _enroll(
        client, admin_token, sample_unit["id"], sku["id"],
        start_date="2026-06-01", purchased_quantity=8,
    )

    await _generate(client, admin_token, 2026, 6)
    second = await _generate(client, admin_token, 2026, 6)
    assert second["updated"] == 1

    invoices = await _june_invoices(client, admin_token)
    assert len(invoices) == 1
    lines = invoices[0]["lines"]
    assert len(lines) == 1
    current_line_id = uuid.UUID(lines[0]["id"])

    async with TestSessionLocal() as session:
        purchase = (
            await session.execute(
                select(EnrollmentPurchase).where(EnrollmentPurchase.enrollment_id == uuid.UUID(enrollment["id"]))
            )
        ).scalars().one()
        assert purchase.billed_invoice_line_id == current_line_id


@pytest.mark.asyncio
async def test_private_tutoring_topup_without_class_price(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=None)
    enrollment = await _enroll(
        client, admin_token, sample_unit["id"], sku["id"],
        start_date="2026-06-01", purchased_quantity=2, unit_price=300,
    )

    await _generate(client, admin_token, 2026, 6)
    invoice = (await _june_invoices(client, admin_token))[0]
    assert float(invoice["lines"][0]["amount"]) == 600

    await _top_up(client, admin_token, enrollment["id"], 1, 350, "2026-07-05")
    await _generate(client, admin_token, 2026, 7)
    july_invoice = (await _june_invoices(client, admin_token, month=7))[0]
    assert len(july_invoice["lines"]) == 1
    assert float(july_invoice["lines"][0]["amount"]) == 350


@pytest.mark.asyncio
async def test_zero_price_topup_creates_zero_line(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=150)
    enrollment = await _enroll(
        client, admin_token, sample_unit["id"], sku["id"],
        start_date="2026-06-01", purchased_quantity=8,
    )
    await _top_up(client, admin_token, enrollment["id"], 2, 0, "2026-06-20")

    await _generate(client, admin_token, 2026, 6)
    invoice = (await _june_invoices(client, admin_token))[0]
    amounts = sorted(float(line["amount"]) for line in invoice["lines"])
    assert amounts == [0, 1200]


@pytest.mark.asyncio
async def test_patch_purchased_quantity_rejected_when_purchases_exist(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=150)
    enrollment = await _enroll(
        client, admin_token, sample_unit["id"], sku["id"],
        start_date="2026-06-01", purchased_quantity=8,
    )

    resp = await client.patch(
        f"/api/course-enrollments/{enrollment['id']}",
        json={"purchased_quantity": 10},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_enroll_per_session_without_any_price_rejected(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=None)
    resp = await client.post(
        "/api/course-enrollments",
        json={
            "unit_id": sample_unit["id"],
            "sku_id": sku["id"],
            "purchased_quantity": 2,
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_per_session_enrollment_with_purchases(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=150)
    enrollment = await _enroll(
        client, admin_token, sample_unit["id"], sku["id"],
        start_date="2026-06-01", purchased_quantity=8,
    )
    await _top_up(client, admin_token, enrollment["id"], 4, 150, "2026-07-10")

    resp = await client.delete(
        f"/api/course-enrollments/{enrollment['id']}",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 204, resp.text

    async with TestSessionLocal() as session:
        remaining = (
            await session.execute(
                select(EnrollmentPurchase).where(EnrollmentPurchase.enrollment_id == uuid.UUID(enrollment["id"]))
            )
        ).scalars().all()
        assert remaining == []


@pytest.mark.asyncio
async def test_manual_invoice_bills_unbilled_purchase(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=150)
    enrollment = await _enroll(
        client, admin_token, sample_unit["id"], sku["id"],
        start_date="2026-06-01", purchased_quantity=8,
    )
    fetched = await client.get(
        f"/api/course-enrollments/{enrollment['id']}",
        headers=_auth(admin_token),
    )
    purchase_id = fetched.json()["purchases"][0]["id"]

    resp = await client.post(
        "/api/tuition-invoices/manual",
        json={
            "date": "2026-06-10",
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "purchase_ids": [purchase_id],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    invoice = resp.json()
    assert invoice["status"] == "issued"
    assert invoice["invoice_no"] is not None
    assert len(invoice["lines"]) == 1
    line = invoice["lines"][0]
    assert line["billing_unit"] == "per_session"
    assert float(line["amount"]) == 1200

    async with TestSessionLocal() as session:
        purchase = (
            await session.execute(
                select(EnrollmentPurchase).where(EnrollmentPurchase.id == uuid.UUID(purchase_id))
            )
        ).scalars().one()
        assert purchase.billed_invoice_line_id == uuid.UUID(line["id"])

    # A later Generate must not bill the same purchase again.
    result = await _generate(client, admin_token, 2026, 7)
    assert result["created"] == 0
    assert (await _june_invoices(client, admin_token, month=7)) == []


@pytest.mark.asyncio
async def test_manual_invoice_rejects_already_billed_purchase(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=150)
    enrollment = await _enroll(
        client, admin_token, sample_unit["id"], sku["id"],
        start_date="2026-06-01", purchased_quantity=8,
    )
    await _generate(client, admin_token, 2026, 6)
    fetched = await client.get(
        f"/api/course-enrollments/{enrollment['id']}",
        headers=_auth(admin_token),
    )
    purchase_id = fetched.json()["purchases"][0]["id"]

    resp = await client.post(
        "/api/tuition-invoices/manual",
        json={
            "date": "2026-06-10",
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "purchase_ids": [purchase_id],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_invoice_line_includes_staff_name(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    staff = await _create_staff(client, admin_token, sample_location["id"])
    spu = await _create_spu(client, admin_token)
    sku = await _create_sku(client, admin_token, spu["id"], staff_id=staff["id"])
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
    line = listed.json()[0]["lines"][0]
    assert line["staff_name"] == "Test Teacher"


@pytest.mark.asyncio
async def test_manual_invoice_line_stores_staff_name(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    resp = await client.post(
        "/api/tuition-invoices/manual",
        json={
            "date": "2026-06-10",
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "lines": [
                {"month": "Jun-26", "course": "私補", "fee": 500, "qty": 1, "staff_name": "Miss Chan"},
            ],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    line = resp.json()["lines"][0]
    assert line["staff_name"] == "Miss Chan"
