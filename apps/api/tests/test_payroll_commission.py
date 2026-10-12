"""Payroll commission: invoice-level Tutor × staff commission_rate → adjustment_1."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.attendance_summary import AttendanceSummary
from app.models.payroll_record import PayrollRecord
from app.models.staff_profile import StaffProfile
from app.models.tuition_invoice import TuitionInvoice
from app.models.tuition_receipt import TuitionReceipt, TuitionReceiptInvoice
from app.models.unit import Unit
from app.services.payroll_generator import generate_monthly_payroll
from tests.conftest import TestSessionLocal

YEAR, MONTH = 2026, 3
FIRST_DAY = date(YEAR, MONTH, 1)
LAST_DAY = date(YEAR, MONTH, 31)
SUMMARY_DAY = date(YEAR, MONTH, 15)


async def _staff_unit(
    client: AsyncClient,
    token: str,
    location_id: str,
    *,
    full_name: str = "Test Staff",
    commission_rate: float | None = None,
    hourly_rate: float | None = None,
) -> dict:
    code = f"STF-{uuid.uuid4().hex[:6]}"
    staff_profile: dict = {"employment_type": "part_time"}
    if commission_rate is not None:
        staff_profile["commission_rate"] = commission_rate
    if hourly_rate is not None:
        staff_profile["pay_type"] = "hourly"
        staff_profile["hourly_rate"] = hourly_rate
    resp = await client.post(
        "/api/units",
        json={
            "code": code,
            "full_name": full_name,
            "unit_type": "staff",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
            "staff_profile": staff_profile,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _invoice(
    location_id: str,
    *,
    staff_name: str | None,
    total: float,
    status: str = "paid",
    period_start: date = FIRST_DAY,
    invoice_no: str | None = None,
    tutor_unit_id: str | None = None,
) -> TuitionInvoice:
    return TuitionInvoice(
        location_id=uuid.UUID(location_id),
        period_start=period_start,
        period_end=LAST_DAY,
        status=status,
        kind="tuition",
        staff_name=staff_name,
        tutor_unit_id=uuid.UUID(tutor_unit_id) if tutor_unit_id else None,
        total=total,
        invoice_no=invoice_no,
    )


def _paid_invoice(
    location_id: str,
    *,
    receipt_date: date = SUMMARY_DAY,
    receipt_status: str = "posted",
    **kwargs,
) -> tuple[TuitionInvoice, TuitionReceipt, TuitionReceiptInvoice]:
    """A paid invoice plus the posted receipt that settles it."""
    invoice = _invoice(location_id, **kwargs)
    receipt = TuitionReceipt(
        location_id=uuid.UUID(location_id),
        paid_by="cash",
        receipt_no=f"R-{uuid.uuid4().hex[:6]}",
        receipt_date=receipt_date,
        amount=float(invoice.total),
        status=receipt_status,
    )
    link = TuitionReceiptInvoice(
        receipt=receipt,
        invoice=invoice,
        amount=float(invoice.total),
        is_posted=True,
    )
    return invoice, receipt, link


def _summary(unit_id: str, location_id: str, regular_slots: int = 8) -> AttendanceSummary:
    return AttendanceSummary(
        unit_id=uuid.UUID(unit_id),
        summary_date=SUMMARY_DAY,
        location_id=uuid.UUID(location_id),
        regular_slots=regular_slots,
        is_complete=True,
    )


async def _record_for(unit_id: str) -> PayrollRecord | None:
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(PayrollRecord).where(
                PayrollRecord.unit_id == uuid.UUID(unit_id),
                PayrollRecord.payroll_period_start == FIRST_DAY,
            )
        )
        return result.scalar_one_or_none()


@pytest.mark.asyncio
async def test_commission_matches_invoice_tutor_case_and_space(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add_all(
            _paid_invoice(loc, staff_name="  ada WONG ", total=1000, invoice_no="INV-1")
        )
        await session.commit()
        result = await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    assert record is not None
    assert float(record.adjustment_1) == 700.0
    assert record.adjustment_1_remark == "Commission 70% × $1,000.00 (1 invoices)"
    assert float(record.gross_pay) == float(record.base_salary) + 700.0
    assert result["commission_warnings"] == []


@pytest.mark.asyncio
async def test_blank_and_ineligible_invoices_not_counted(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add_all([
            _invoice(loc, staff_name="", total=500),            # blank Tutor — skipped silently
            _invoice(loc, staff_name="   ", total=500),         # whitespace Tutor — skipped
            _invoice(loc, staff_name="Ada Wong", total=500, status="void"),
            _invoice(loc, staff_name="Ada Wong", total=500, status="draft"),
            *_paid_invoice(loc, staff_name="Ada Wong", total=200, invoice_no="INV-OK"),
        ])
        await session.commit()
        result = await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    assert float(record.adjustment_1) == 140.0
    assert "(1 invoices)" in record.adjustment_1_remark
    assert result["commission_warnings"] == []


@pytest.mark.asyncio
async def test_credit_note_deducts_commission(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=50
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        credit = _invoice(
            loc, staff_name="Ada Wong", total=-300, status="issued", invoice_no="CN-1"
        )
        credit.kind = "credit_note"
        session.add_all([
            *_paid_invoice(loc, staff_name="Ada Wong", total=1000, invoice_no="INV-1"),
            credit,
        ])
        await session.commit()
        await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    assert float(record.adjustment_1) == 350.0
    assert record.adjustment_1_remark == "Commission 50% × $700.00 (2 invoices)"


@pytest.mark.asyncio
async def test_payment_month_counts_not_bill_month(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    """An Oct bill paid in Nov earns commission in Nov payroll, not Oct."""
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add_all(
            _paid_invoice(
                loc,
                staff_name="Ada Wong",
                total=1000,
                period_start=date(2026, 2, 1),
                receipt_date=date(2026, 3, 20),
            )
        )
        await session.commit()
        await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )
        # Bill-month payroll (Feb) does not count it.
        await generate_monthly_payroll(
            session, year=2026, month=2, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    assert float(record.adjustment_1) == 700.0
    assert record.adjustment_1_remark == "Commission 70% × $1,000.00 (1 invoices)"

    async with TestSessionLocal() as session:
        feb = await session.scalar(
            select(PayrollRecord).where(
                PayrollRecord.unit_id == uuid.UUID(staff["id"]),
                PayrollRecord.payroll_period_start == date(2026, 2, 1),
            )
        )
        assert feb is None or float(feb.adjustment_1) == 0.0


@pytest.mark.asyncio
async def test_receipt_outside_month_not_counted(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add_all(
            _paid_invoice(
                loc,
                staff_name="Ada Wong",
                total=1000,
                receipt_date=date(2026, 4, 2),
            )
        )
        await session.commit()
        await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    assert float(record.adjustment_1) == 0.0
    assert record.adjustment_1_remark == "Commission 70% × $0.00 (0 invoices)"


@pytest.mark.asyncio
async def test_paid_invoice_without_receipt_not_counted(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add(_invoice(loc, staff_name="Ada Wong", total=1000))
        await session.commit()
        await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    assert float(record.adjustment_1) == 0.0
    assert "(0 invoices)" in record.adjustment_1_remark


@pytest.mark.asyncio
async def test_voided_receipt_not_counted(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add_all(
            _paid_invoice(
                loc, staff_name="Ada Wong", total=1000, receipt_status="void"
            )
        )
        await session.commit()
        await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    assert float(record.adjustment_1) == 0.0
    assert "(0 invoices)" in record.adjustment_1_remark


@pytest.mark.asyncio
async def test_tutor_unit_id_matches_after_rename(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    """tutor_unit_id wins over staff_name and survives a staff rename."""
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        # staff_name deliberately mismatches — the id link is authoritative.
        session.add_all(
            _paid_invoice(
                loc,
                staff_name="Unrelated Name",
                total=1000,
                tutor_unit_id=staff["id"],
            )
        )
        unit = await session.get(Unit, uuid.UUID(staff["id"]))
        unit.full_name = "Ada Renamed"
        await session.commit()
        result = await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    assert float(record.adjustment_1) == 700.0
    assert result["commission_warnings"] == []


@pytest.mark.asyncio
async def test_rate_snapshot_survives_regenerate(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    """Regenerating a draft record keeps the frozen commission rate."""
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add_all(_paid_invoice(loc, staff_name="Ada Wong", total=1000))
        await session.commit()
        await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )
        # Owner lowers the rate, then regenerates the still-draft record.
        profile = await session.get(StaffProfile, uuid.UUID(staff["id"]))
        profile.commission_rate = 50
        await session.commit()
        await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    assert float(record.commission_rate_snapshot) == 70.0
    assert float(record.adjustment_1) == 700.0
    assert record.adjustment_1_remark.startswith("Commission 70%")


@pytest.mark.asyncio
async def test_warnings_scoped_to_requested_unit_locations(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_location_b: dict
) -> None:
    loc = sample_location["id"]
    loc_b = sample_location_b["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        # Same-location unknown tutor → warns; other location → filtered out.
        session.add_all(_paid_invoice(loc, staff_name="Ghost A", total=100))
        session.add_all(_paid_invoice(loc_b, staff_name="Ghost B", total=200))
        await session.commit()
        result = await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff",
            unit_ids=[uuid.UUID(staff["id"])],
        )

    assert len(result["commission_warnings"]) == 1
    assert 'Tutor "Ghost A"' in result["commission_warnings"][0]


@pytest.mark.asyncio
async def test_awaiting_payment_remark(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add(
            _invoice(loc, staff_name="Ada Wong", total=500, status="issued")
        )
        await session.commit()
        await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    assert float(record.adjustment_1) == 0.0
    assert (
        record.adjustment_1_remark
        == "Commission 70% × $0.00 (0 invoices; 1 awaiting payment)"
    )


@pytest.mark.asyncio
async def test_duplicate_staff_name_warns_and_skips(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    a = await _staff_unit(client, admin_token, loc, full_name="Dup Name", commission_rate=70)
    b = await _staff_unit(client, admin_token, loc, full_name="dup name", commission_rate=70)

    async with TestSessionLocal() as session:
        session.add_all([_summary(a["id"], loc), _summary(b["id"], loc)])
        session.add_all(_paid_invoice(loc, staff_name="Dup Name", total=1000))
        await session.commit()
        result = await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    for unit in (a, b):
        record = await _record_for(unit["id"])
        assert float(record.adjustment_1) == 0.0
        assert "(0 invoices)" in record.adjustment_1_remark
    assert any(
        'Tutor "Dup Name" matches multiple staff' in w
        for w in result["commission_warnings"]
    )


@pytest.mark.asyncio
async def test_unknown_tutor_warns(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add_all(_paid_invoice(loc, staff_name="Ghost Tutor", total=1000, invoice_no="INV-9"))
        session.add_all(_paid_invoice(loc, staff_name="Ghost Tutor", total=200, invoice_no="INV-10"))
        await session.commit()
        result = await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    assert result["commission_warnings"] == [
        'Tutor "Ghost Tutor" on 2 invoices matches no staff'
    ]


@pytest.mark.asyncio
async def test_invoice_matching_non_commission_staff_is_silent(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    plain = await _staff_unit(client, admin_token, loc, full_name="No Commission")
    earner = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add_all([_summary(plain["id"], loc), _summary(earner["id"], loc)])
        session.add_all(_paid_invoice(loc, staff_name="No Commission", total=1000))
        await session.commit()
        result = await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(plain["id"])
    assert float(record.adjustment_1) == 0.0
    assert record.adjustment_1_remark is None
    assert result["commission_warnings"] == []


@pytest.mark.asyncio
async def test_commission_staff_without_attendance_gets_record(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="No Attendance", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add_all(_paid_invoice(loc, staff_name="No Attendance", total=500))
        await session.commit()
        result = await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    assert record is not None
    assert record.regular_slots == 0
    assert float(record.adjustment_1) == 350.0
    assert result["created"] == 1


@pytest.mark.asyncio
async def test_commission_staff_without_invoices_or_attendance_skipped(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Idle Staff", commission_rate=70
    )

    async with TestSessionLocal() as session:
        result = await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    assert await _record_for(staff["id"]) is None
    assert result["created"] == 0


@pytest.mark.asyncio
async def test_approved_record_not_overwritten(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add(
            PayrollRecord(
                unit_id=uuid.UUID(staff["id"]),
                payroll_period_start=FIRST_DAY,
                payroll_period_end=LAST_DAY,
                adjustment_1=123.0,
                adjustment_1_remark="manual",
                status="approved",
            )
        )
        session.add_all(_paid_invoice(loc, staff_name="Ada Wong", total=1000))
        await session.commit()
        result = await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    assert float(record.adjustment_1) == 123.0
    assert record.adjustment_1_remark == "manual"
    assert result["skipped"] == 1


@pytest.mark.asyncio
async def test_null_commission_rate_leaves_adjustment_untouched(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(client, admin_token, loc, full_name="Ada Wong")

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add(
            PayrollRecord(
                unit_id=uuid.UUID(staff["id"]),
                payroll_period_start=FIRST_DAY,
                payroll_period_end=LAST_DAY,
                adjustment_1=88.0,
                adjustment_1_remark="manual",
                status="draft",
            )
        )
        session.add_all(_paid_invoice(loc, staff_name="Ada Wong", total=1000))
        await session.commit()
        await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    assert float(record.adjustment_1) == 88.0
    assert record.adjustment_1_remark == "manual"
    # gross/net recomputed around the preserved adjustment
    assert float(record.gross_pay) == float(record.base_salary) + 88.0


@pytest.mark.asyncio
async def test_regenerate_overwrites_manual_adjustment_for_commission_staff(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add(
            PayrollRecord(
                unit_id=uuid.UUID(staff["id"]),
                payroll_period_start=FIRST_DAY,
                payroll_period_end=LAST_DAY,
                adjustment_1=999.0,
                adjustment_1_remark="manual override",
                status="calculated",
            )
        )
        session.add_all(_paid_invoice(loc, staff_name="Ada Wong", total=1000))
        await session.commit()
        await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    assert float(record.adjustment_1) == 700.0
    assert record.adjustment_1_remark == "Commission 70% × $1,000.00 (1 invoices)"


@pytest.mark.asyncio
async def test_generate_endpoint_returns_commission_warnings(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add_all(_paid_invoice(loc, staff_name="Ghost Tutor", total=100, invoice_no="INV-1"))
        await session.commit()

    resp = await client.post(
        "/api/payroll-records/generate",
        params={"year": YEAR, "month": MONTH, "unit_type": "staff"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["commission_warnings"] == [
        'Tutor "Ghost Tutor" on invoice INV-1 matches no staff'
    ]


@pytest.mark.asyncio
async def test_commission_detail_endpoint(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add_all(
            _paid_invoice(
                loc,
                staff_name="Ada Wong",
                total=1000,
                invoice_no="INV-1",
                receipt_date=date(2026, 3, 20),
            )
        )
        credit = _invoice(
            loc, staff_name="Ada Wong", total=-200, status="issued", invoice_no="RF0001"
        )
        credit.kind = "credit_note"
        session.add(credit)
        session.add(
            _invoice(loc, staff_name="Ada Wong", total=500, status="issued", invoice_no="INV-2")
        )
        await session.commit()
        await generate_monthly_payroll(
            session, year=YEAR, month=MONTH, unit_type="staff"
        )

    record = await _record_for(staff["id"])
    resp = await client.get(
        f"/api/payroll-records/{record.id}/commission-detail",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["rate"] == 70.0
    assert detail["rate_snapshot"] == 70.0
    assert detail["base_total"] == 800.0
    assert detail["amount"] == 560.0
    assert [row["invoice_no"] for row in detail["paid"]] == ["INV-1"]
    assert detail["paid"][0]["receipt_date"] == "2026-03-20"
    assert detail["paid"][0]["receipt_no"]
    assert [row["invoice_no"] for row in detail["credit_notes"]] == ["RF0001"]
    assert [row["invoice_no"] for row in detail["awaiting_payment"]] == ["INV-2"]
    assert detail["awaiting_payment"][0]["bill_month"] == "2026-03"


@pytest.mark.asyncio
async def test_manual_invoice_tutor_unit_id_sets_staff_name(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(client, admin_token, loc, full_name="Ada Wong")

    resp = await client.post(
        "/api/tuition-invoices/manual",
        json={
            "date": "2026-03-10",
            "location_id": loc,
            "manual_student_name": "Walk In",
            "tutor_unit_id": staff["id"],
            "staff_name": "Ignored Typed Name",
            "lines": [{"month": "Mar-26", "course": "Math", "fee": 800, "qty": 1}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["tutor_unit_id"] == staff["id"]
    assert body["staff_name"] == "Ada Wong"


@pytest.mark.asyncio
async def test_manual_invoice_tutor_unit_id_rejects_non_staff(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_unit: dict
) -> None:
    loc = sample_location["id"]

    resp = await client.post(
        "/api/tuition-invoices/manual",
        json={
            "date": "2026-03-10",
            "location_id": loc,
            "manual_student_name": "Walk In",
            "tutor_unit_id": sample_unit["id"],  # a student unit
            "lines": [{"month": "Mar-26", "course": "Math", "fee": 800, "qty": 1}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422

    resp = await client.post(
        "/api/tuition-invoices/manual",
        json={
            "date": "2026-03-10",
            "location_id": loc,
            "manual_student_name": "Walk In",
            "tutor_unit_id": str(uuid.uuid4()),
            "lines": [{"month": "Mar-26", "course": "Math", "fee": 800, "qty": 1}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invoice_update_tutor_unit_id(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(client, admin_token, loc, full_name="Ada Wong")

    resp = await client.post(
        "/api/tuition-invoices/manual",
        json={
            "date": "2026-03-10",
            "location_id": loc,
            "manual_student_name": "Walk In",
            "lines": [{"month": "Mar-26", "course": "Math", "fee": 800, "qty": 1}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201, resp.text
    invoice_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"tutor_unit_id": staff["id"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["tutor_unit_id"] == staff["id"]
    assert resp.json()["staff_name"] == "Ada Wong"

    # Explicit null clears the link (and leaves the name snapshot alone).
    resp = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"tutor_unit_id": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["tutor_unit_id"] is None
    assert resp.json()["staff_name"] == "Ada Wong"
