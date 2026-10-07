"""Generate payroll records from attendance summaries for a given month.

Admin selects a month → this service aggregates daily attendance summaries
per unit and inserts/updates `payroll_records` rows.
Compensation is calculated from slot totals × the staff profile pay rate
snapshot at generation time.
"""

import calendar
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.attendance_tz import ATTENDANCE_TZ
from app.models.attendance import AttendanceEvent
from app.models.attendance_summary import AttendanceSummary
from app.models.payroll_record import PayrollRecord, PayrollStatus
from app.models.tuition_invoice import TuitionInvoice, TuitionInvoiceStatus
from app.models.unit import Unit
from app.models.staff_profile import StaffProfile


SLOT_MINUTES = 15
SLOTS_PER_HOUR = 4  # 60 / 15


async def detect_stale_summary_units(
    db: AsyncSession,
    year: int,
    month: int,
    unit_type: str | None = None,
    unit_ids: list | None = None,
) -> list[dict]:
    """Flag units whose attendance events changed after their summaries were built.

    Payroll reads only `attendance_summaries`. If an event was added or voided
    after the daily summary was last generated, the summary — and therefore any
    payroll computed from it — is stale. Returns one entry per affected unit:

        {"unit_id", "unit_code", "unit_name", "reason"}

    where reason is ``"no_summary"`` (has events but no summary at all) or
    ``"outdated"`` (has a summary older than its latest event mutation).
    """
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    start_dt = datetime.combine(first_day, time.min, tzinfo=ATTENDANCE_TZ).astimezone(timezone.utc)
    end_dt = datetime.combine(last_day, time.max, tzinfo=ATTENDANCE_TZ).astimezone(timezone.utc)

    ev_q = (
        select(
            AttendanceEvent.unit_id.label("pid"),
            func.max(AttendanceEvent.created_at).label("max_created"),
            func.max(AttendanceEvent.voided_at).label("max_voided"),
        )
        .where(
            AttendanceEvent.recorded_at >= start_dt,
            AttendanceEvent.recorded_at <= end_dt,
        )
        .group_by(AttendanceEvent.unit_id)
    )
    sm_q = (
        select(
            AttendanceSummary.unit_id.label("pid"),
            func.max(AttendanceSummary.updated_at).label("max_updated"),
        )
        .where(
            AttendanceSummary.summary_date >= first_day,
            AttendanceSummary.summary_date <= last_day,
        )
        .group_by(AttendanceSummary.unit_id)
    )
    if unit_ids:
        ev_q = ev_q.where(AttendanceEvent.unit_id.in_(unit_ids))
        sm_q = sm_q.where(AttendanceSummary.unit_id.in_(unit_ids))
    if unit_type:
        ev_q = ev_q.join(AttendanceEvent.unit).where(
            Unit.unit_type == unit_type
        )
        sm_q = sm_q.join(AttendanceSummary.unit).where(
            Unit.unit_type == unit_type
        )

    ev_rows = (await db.execute(ev_q)).all()
    sm_map = {row.pid: row.max_updated for row in (await db.execute(sm_q)).all()}

    stale: dict = {}  # unit_id -> reason
    for row in ev_rows:
        max_event = row.max_created
        if row.max_voided is not None and (
            max_event is None or row.max_voided > max_event
        ):
            max_event = row.max_voided

        summary_updated = sm_map.get(row.pid)
        if summary_updated is None:
            stale[row.pid] = "no_summary"
        elif max_event is not None and max_event > summary_updated:
            stale[row.pid] = "outdated"

    if not stale:
        return []

    info_rows = (
        await db.execute(
            select(Unit.id, Unit.code, Unit.full_name).where(
                Unit.id.in_(list(stale.keys()))
            )
        )
    ).all()
    info = {row.id: row for row in info_rows}

    return [
        {
            "unit_id": str(pid),
            "unit_code": info[pid].code if pid in info else None,
            "unit_name": info[pid].full_name if pid in info else None,
            "reason": reason,
        }
        for pid, reason in stale.items()
    ]


async def _commission_by_unit(
    db: AsyncSession,
    first_day: date,
    last_day: date,
    unit_type: str | None = None,
    unit_ids: list | None = None,
) -> tuple[dict[uuid.UUID, tuple[Decimal, int]], dict[uuid.UUID, StaffProfile], list[str]]:
    """Aggregate invoice commission per staff unit for the month.

    Returns (commissions, commission_staff, warnings):
        commissions: unit_id -> (invoice total Decimal, invoice count)
        commission_staff: unit_id -> StaffProfile (commission_rate IS NOT NULL)
        warnings: one entry per unmatched/ambiguous Tutor name
    """
    if unit_type and unit_type != "staff":
        return {}, {}, []

    # Name map covers ALL staff units so an out-of-scope tutor name still
    # resolves (and stays silent); unit_ids only limits who earns commission.
    staff_q = (
        select(StaffProfile, Unit.full_name)
        .join(Unit, Unit.id == StaffProfile.id)
        .where(Unit.unit_type == "staff")
    )
    staff_rows = (await db.execute(staff_q)).all()

    name_to_units: dict[str, list[uuid.UUID]] = defaultdict(list)
    commission_staff: dict[uuid.UUID, StaffProfile] = {}
    requested = set(unit_ids) if unit_ids else None
    for staff, full_name in staff_rows:
        if staff.commission_rate is not None and (requested is None or staff.id in requested):
            commission_staff[staff.id] = staff
        key = (full_name or "").strip().casefold()
        if key:
            name_to_units[key].append(staff.id)

    if not commission_staff:
        return {}, {}, []

    # Commission counts paid invoices (positive) and issued/paid credit notes
    # (negative) in the payroll month; void/draft and unpaid positives don't.
    inv_q = select(TuitionInvoice).where(
        TuitionInvoice.period_start >= first_day,
        TuitionInvoice.period_start <= last_day,
        TuitionInvoice.staff_name.is_not(None),
        func.trim(TuitionInvoice.staff_name) != "",
        or_(
            and_(
                TuitionInvoice.total > 0,
                TuitionInvoice.status == TuitionInvoiceStatus.paid.value,
            ),
            and_(
                TuitionInvoice.total < 0,
                TuitionInvoice.status.in_(
                    [TuitionInvoiceStatus.issued.value, TuitionInvoiceStatus.paid.value]
                ),
            ),
        ),
    )
    invoices = (await db.execute(inv_q)).scalars().all()

    commissions: dict[uuid.UUID, list] = {}
    unmatched: dict[str, dict] = {}  # name -> {"ref": first invoice ref, "count": n}
    ambiguous: dict[str, int] = {}   # name -> invoice count
    for inv in invoices:
        name = inv.staff_name.strip()
        key = name.casefold()
        matches = name_to_units.get(key) or []
        if len(matches) > 1:
            ambiguous[name] = ambiguous.get(name, 0) + 1
            continue
        if not matches:
            entry = unmatched.setdefault(
                name, {"ref": inv.invoice_no or str(inv.id), "count": 0}
            )
            entry["count"] += 1
            continue
        unit_id = matches[0]
        if unit_id not in commission_staff:
            continue  # matched a non-commission staff — ignore silently
        entry = commissions.setdefault(unit_id, [Decimal("0"), 0])
        entry[0] += Decimal(str(inv.total))
        entry[1] += 1

    warnings: list[str] = []
    for name, entry in unmatched.items():
        if entry["count"] == 1:
            warnings.append(
                f'Tutor "{name}" on invoice {entry["ref"]} matches no staff'
            )
        else:
            warnings.append(
                f'Tutor "{name}" on {entry["count"]} invoices matches no staff'
            )
    for name in ambiguous:
        warnings.append(
            f'Tutor "{name}" matches multiple staff; commission not assigned'
        )

    return (
        {uid: (tot, cnt) for uid, (tot, cnt) in commissions.items()},
        commission_staff,
        warnings,
    )


def _pay_from_profile(
    staff: StaffProfile | None,
    regular_slots: int,
    ot_slots: int,
) -> tuple[float, float, float, float, float | None, float | None]:
    """Return (regular_hours, ot_hours, base_salary, overtime_pay, hourly_rate_snapshot, ot_multiplier_snapshot)."""
    regular_hours = round(regular_slots / SLOTS_PER_HOUR, 2)
    ot_hours = round(ot_slots / SLOTS_PER_HOUR, 2)

    if staff is None or staff.pay_type is None:
        return regular_hours, ot_hours, 0.0, 0.0, None, None

    hourly_rate_snapshot = float(staff.hourly_rate) if staff.hourly_rate is not None else None
    ot_multiplier_snapshot = float(staff.ot_multiplier) if staff.ot_multiplier is not None else 1.5

    if staff.pay_type == "hourly" and hourly_rate_snapshot is not None:
        base_salary = round(regular_hours * hourly_rate_snapshot, 2)
        overtime_pay = round(ot_hours * hourly_rate_snapshot * ot_multiplier_snapshot, 2)
    elif staff.pay_type == "monthly" and staff.monthly_salary is not None:
        # Monthly staff: base = monthly salary; OT only if an explicit hourly rate is set
        base_salary = round(float(staff.monthly_salary), 2)
        if hourly_rate_snapshot is not None:
            overtime_pay = round(ot_hours * hourly_rate_snapshot * ot_multiplier_snapshot, 2)
        else:
            overtime_pay = 0.0
    else:
        base_salary = 0.0
        overtime_pay = 0.0
        hourly_rate_snapshot = None
        ot_multiplier_snapshot = None

    return regular_hours, ot_hours, base_salary, overtime_pay, hourly_rate_snapshot, ot_multiplier_snapshot


async def generate_monthly_payroll(
    db: AsyncSession,
    year: int,
    month: int,
    unit_type: str | None = None,
    unit_ids: list | None = None,
) -> dict:
    """Generate payroll records for every unit with attendance summaries.

    If `unit_ids` is provided, only those units are processed
    (still filtered by `unit_type` when given).

    Returns:
        dict with counts: {"created": int, "updated": int, "skipped": int}
    """
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    stale_summaries = await detect_stale_summary_units(
        db, year=year, month=month, unit_type=unit_type, unit_ids=unit_ids
    )

    q = select(AttendanceSummary).where(
        AttendanceSummary.summary_date >= first_day,
        AttendanceSummary.summary_date <= last_day,
    )
    if unit_ids:
        q = q.where(AttendanceSummary.unit_id.in_(unit_ids))
    if unit_type:
        q = q.join(AttendanceSummary.unit).where(Unit.unit_type == unit_type)

    result = await db.execute(q)
    summaries = result.scalars().all()

    grouped: defaultdict = defaultdict(list)
    for summary in summaries:
        grouped[summary.unit_id].append(summary)

    existing_result = await db.execute(
        select(PayrollRecord).where(
            PayrollRecord.payroll_period_start == first_day,
            PayrollRecord.payroll_period_end == last_day,
        )
    )
    existing_records = {r.unit_id: r for r in existing_result.scalars().all()}

    commissions, commission_staff, commission_warnings = await _commission_by_unit(
        db, first_day, last_day, unit_type=unit_type, unit_ids=unit_ids
    )

    # Commission staff with invoices but no attendance still get a record
    all_unit_ids = set(grouped.keys()) | set(commissions.keys())

    # Load staff profiles for all processed units in one query
    profile_unit_ids = list(all_unit_ids)
    staff_by_unit: dict = {}
    if profile_unit_ids:
        staff_result = await db.execute(
            select(StaffProfile).where(StaffProfile.id.in_(profile_unit_ids))
        )
        staff_by_unit = {s.id: s for s in staff_result.scalars().all()}

    created_count = 0
    updated_count = 0
    skipped_count = 0
    now = datetime.now(timezone.utc)

    for unit_id in all_unit_ids:
        unit_summaries = grouped.get(unit_id, [])
        record = existing_records.get(unit_id)

        regular_slots = sum(s.regular_slots for s in unit_summaries)
        ot_slots = sum(s.ot_slots for s in unit_summaries)
        total_holiday_hours = sum(s.holiday_hours for s in unit_summaries)
        total_work_days = len([s for s in unit_summaries if s.is_complete])

        staff = staff_by_unit.get(unit_id)
        regular_hours, ot_hours, base_salary, overtime_pay, hourly_rate_snapshot, ot_multiplier_snapshot = _pay_from_profile(
            staff, regular_slots, ot_slots
        )

        # Commission staff: adjustment_1 = invoice total × rate, always overwritten
        commission_remark: str | None = None
        if staff is not None and staff.commission_rate is not None:
            rate = Decimal(str(staff.commission_rate))
            commission_total, commission_count = commissions.get(
                unit_id, (Decimal("0"), 0)
            )
            adjustment_1 = float(
                (commission_total * rate / 100).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            )
            commission_remark = (
                f"Commission {float(rate):g}% × ${float(commission_total):,.2f} "
                f"({commission_count} invoices)"
            )
        else:
            adjustment_1 = float(record.adjustment_1) if record and record.adjustment_1 is not None else 0.0
        adjustment_2 = float(record.adjustment_2) if record and record.adjustment_2 is not None else 0.0

        gross_pay = round(base_salary + overtime_pay + adjustment_1, 2)
        net_pay = round(gross_pay + adjustment_2, 2)

        if record:
            if record.status in (PayrollStatus.approved.value, PayrollStatus.paid.value):
                skipped_count += 1
                continue

            record.regular_slots = regular_slots
            record.ot_slots = ot_slots
            record.total_regular_hours = regular_hours
            record.total_overtime_hours = ot_hours
            record.total_holiday_hours = total_holiday_hours
            record.total_work_days = total_work_days
            record.hourly_rate_snapshot = hourly_rate_snapshot
            record.ot_multiplier_snapshot = ot_multiplier_snapshot
            record.base_salary = base_salary
            record.overtime_pay = overtime_pay
            record.holiday_pay = 0.0
            if commission_remark is not None:
                record.adjustment_1 = adjustment_1
                record.adjustment_1_remark = commission_remark
            record.gross_pay = gross_pay
            record.net_pay = net_pay
            record.status = PayrollStatus.calculated.value
            record.calculation_date = now
            record.calculation_method = "from_summaries"
            updated_count += 1
        else:
            record = PayrollRecord(
                unit_id=unit_id,
                payroll_period_start=first_day,
                payroll_period_end=last_day,
                regular_slots=regular_slots,
                ot_slots=ot_slots,
                total_regular_hours=regular_hours,
                total_overtime_hours=ot_hours,
                total_holiday_hours=total_holiday_hours,
                total_work_days=total_work_days,
                hourly_rate_snapshot=hourly_rate_snapshot,
                ot_multiplier_snapshot=ot_multiplier_snapshot,
                base_salary=base_salary,
                overtime_pay=overtime_pay,
                holiday_pay=0.0,
                adjustment_1=adjustment_1,
                adjustment_1_remark=commission_remark,
                gross_pay=gross_pay,
                net_pay=net_pay,
                status=PayrollStatus.calculated.value,
                calculation_date=now,
                calculation_method="from_summaries",
            )
            db.add(record)
            created_count += 1

    await db.commit()

    return {
        "created": created_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "year": year,
        "month": month,
        "stale_summaries": stale_summaries,
        "commission_warnings": commission_warnings,
    }
