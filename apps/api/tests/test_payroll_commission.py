"""Payroll commission: invoice-level Tutor × staff commission_rate → adjustment_1."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.attendance_summary import AttendanceSummary
from app.models.payroll_record import PayrollRecord
from app.models.tuition_invoice import TuitionInvoice
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
) -> TuitionInvoice:
    return TuitionInvoice(
        location_id=uuid.UUID(location_id),
        period_start=period_start,
        period_end=LAST_DAY,
        status=status,
        kind="tuition",
        staff_name=staff_name,
        total=total,
        invoice_no=invoice_no,
    )


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
        session.add(
            _invoice(loc, staff_name="  ada WONG ", total=1000, invoice_no="INV-1")
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
            # positive invoice still unpaid → not counted
            _invoice(loc, staff_name="Ada Wong", total=500, status="issued"),
            _invoice(loc, staff_name="Ada Wong", total=200, invoice_no="INV-OK"),
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
            _invoice(loc, staff_name="Ada Wong", total=1000, invoice_no="INV-1"),
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
async def test_invoice_outside_month_not_counted(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    staff = await _staff_unit(
        client, admin_token, loc, full_name="Ada Wong", commission_rate=70
    )

    async with TestSessionLocal() as session:
        session.add(_summary(staff["id"], loc))
        session.add(
            _invoice(
                loc,
                staff_name="Ada Wong",
                total=1000,
                period_start=date(2026, 4, 1),
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
async def test_duplicate_staff_name_warns_and_skips(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    a = await _staff_unit(client, admin_token, loc, full_name="Dup Name", commission_rate=70)
    b = await _staff_unit(client, admin_token, loc, full_name="dup name", commission_rate=70)

    async with TestSessionLocal() as session:
        session.add_all([_summary(a["id"], loc), _summary(b["id"], loc)])
        session.add(_invoice(loc, staff_name="Dup Name", total=1000))
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
        session.add(_invoice(loc, staff_name="Ghost Tutor", total=1000, invoice_no="INV-9"))
        session.add(_invoice(loc, staff_name="Ghost Tutor", total=200, invoice_no="INV-10"))
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
        session.add(_invoice(loc, staff_name="No Commission", total=1000))
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
        session.add(_invoice(loc, staff_name="No Attendance", total=500))
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
        session.add(_invoice(loc, staff_name="Ada Wong", total=1000))
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
        session.add(_invoice(loc, staff_name="Ada Wong", total=1000))
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
        session.add(_invoice(loc, staff_name="Ada Wong", total=1000))
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
        session.add(_invoice(loc, staff_name="Ghost Tutor", total=100, invoice_no="INV-1"))
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
