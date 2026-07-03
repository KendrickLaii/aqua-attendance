"""Generate payroll records from attendance summaries for a given month.

Admin selects a month → this service aggregates daily attendance summaries
per product and inserts/updates `payroll_records` rows with hours only.
Pay amounts are intentionally left at zero until a rate/salary model is added.
"""

import calendar
from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance_summary import AttendanceSummary
from app.models.payroll_record import PayrollRecord, PayrollStatus
from app.models.product import Product


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

    created_count = 0
    updated_count = 0
    skipped_count = 0
    now = datetime.now(timezone.utc)

    for product_id, product_summaries in grouped.items():
        record = existing_records.get(product_id)
        total_regular_hours = sum(s.regular_hours for s in product_summaries)
        total_overtime_hours = sum(s.overtime_hours for s in product_summaries)
        total_holiday_hours = sum(s.holiday_hours for s in product_summaries)
        total_work_days = len([s for s in product_summaries if s.is_complete])

        if record:
            if record.status in (PayrollStatus.approved.value, PayrollStatus.paid.value):
                skipped_count += 1
                continue

            record.total_regular_hours = total_regular_hours
            record.total_overtime_hours = total_overtime_hours
            record.total_holiday_hours = total_holiday_hours
            record.total_work_days = total_work_days
            record.status = PayrollStatus.calculated.value
            record.calculation_date = now
            record.calculation_method = "from_summaries"
            updated_count += 1
        else:
            record = PayrollRecord(
                product_id=product_id,
                payroll_period_start=first_day,
                payroll_period_end=last_day,
                total_regular_hours=total_regular_hours,
                total_overtime_hours=total_overtime_hours,
                total_holiday_hours=total_holiday_hours,
                total_work_days=total_work_days,
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
