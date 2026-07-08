"""Generate payroll records from attendance summaries for a given month.

Admin selects a month → this service aggregates daily attendance summaries
per product and inserts/updates `payroll_records` rows.
Compensation is calculated from slot totals × the staff profile pay rate
snapshot at generation time.
"""

import calendar
from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance_summary import AttendanceSummary
from app.models.payroll_record import PayrollRecord, PayrollStatus
from app.models.product import Product
from app.models.staff_profile import StaffProfile


SLOT_MINUTES = 15
SLOTS_PER_HOUR = 4  # 60 / 15


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
    product_type: str | None = None,
) -> dict:
    """Generate payroll records for every product with attendance summaries.

    Returns:
        dict with counts: {"created": int, "updated": int, "skipped": int}
    """
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    q = select(AttendanceSummary).where(
        AttendanceSummary.summary_date >= first_day,
        AttendanceSummary.summary_date <= last_day,
    )
    if product_type:
        q = q.join(AttendanceSummary.product).where(Product.product_type == product_type)

    result = await db.execute(q)
    summaries = result.scalars().all()

    grouped: defaultdict = defaultdict(list)
    for summary in summaries:
        grouped[summary.product_id].append(summary)

    existing_result = await db.execute(
        select(PayrollRecord).where(
            PayrollRecord.payroll_period_start == first_day,
            PayrollRecord.payroll_period_end == last_day,
        )
    )
    existing_records = {r.product_id: r for r in existing_result.scalars().all()}

    # Load staff profiles for all grouped products in one query
    product_ids = list(grouped.keys())
    staff_by_product: dict = {}
    if product_ids:
        staff_result = await db.execute(
            select(StaffProfile).where(StaffProfile.id.in_(product_ids))
        )
        staff_by_product = {s.id: s for s in staff_result.scalars().all()}

    created_count = 0
    updated_count = 0
    skipped_count = 0
    now = datetime.now(timezone.utc)

    for product_id, product_summaries in grouped.items():
        record = existing_records.get(product_id)

        regular_slots = sum(s.regular_slots for s in product_summaries)
        ot_slots = sum(s.ot_slots for s in product_summaries)
        total_holiday_hours = sum(s.holiday_hours for s in product_summaries)
        total_work_days = len([s for s in product_summaries if s.is_complete])

        staff = staff_by_product.get(product_id)
        regular_hours, ot_hours, base_salary, overtime_pay, hourly_rate_snapshot, ot_multiplier_snapshot = _pay_from_profile(
            staff, regular_slots, ot_slots
        )

        gross_pay = round(base_salary + overtime_pay, 2)
        net_pay = gross_pay  # allowances/deductions/bonus are manually edited later

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
            record.gross_pay = gross_pay
            record.net_pay = net_pay
            record.status = PayrollStatus.calculated.value
            record.calculation_date = now
            record.calculation_method = "from_summaries"
            updated_count += 1
        else:
            record = PayrollRecord(
                product_id=product_id,
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
    }
