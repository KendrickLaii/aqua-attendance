"""Generate attendance summaries from raw events for a given month.

Admin selects a month → this service calculates daily summaries for every
product and inserts / updates `attendance_summaries` rows.
"""

import calendar
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attendance import AttendanceEvent
from app.models.attendance_summary import AttendanceSummary
from app.models.location import Location
from app.models.product import Product
from app.services.overtime import calculate_workday


async def generate_monthly_summaries(
    db: AsyncSession,
    year: int,
    month: int,
    lunch_minutes: int = 60,
) -> dict:
    """Generate attendance summaries for every product for the given month.

    Returns:
        dict with counts: {"created": int, "updated": int, "total_days": int}
    """
    # Date range
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    start_dt = datetime.combine(first_day, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(last_day, datetime.max.time(), tzinfo=timezone.utc)

    # Fetch all non-voided events in range with product & location
    result = await db.execute(
        select(AttendanceEvent)
        .options(
            selectinload(AttendanceEvent.product).selectinload(Product.registered_location),
            selectinload(AttendanceEvent.location_ref),
        )
        .where(AttendanceEvent.recorded_at >= start_dt)
        .where(AttendanceEvent.recorded_at <= end_dt)
        .where(AttendanceEvent.voided_at.is_(None))
        .order_by(AttendanceEvent.recorded_at)
    )
    events = result.scalars().all()

    # Group by (product_id, date)
    grouped: dict[tuple[uuid.UUID, date], list[AttendanceEvent]] = defaultdict(list)
    for event in events:
        event_date = event.recorded_at.date()
        grouped[(event.product_id, event_date)].append(event)

    created_count = 0
    updated_count = 0

    for (product_id, event_date), day_events in grouped.items():
        # Separate check_ins and check_outs
        check_ins = [e for e in day_events if e.event_type == "check_in"]
        check_outs = [e for e in day_events if e.event_type == "check_out"]

        if not check_ins:
            continue  # No check-in → cannot calculate workday

        first_check_in = min(e.recorded_at for e in check_ins)
        last_check_out = max(e.recorded_at for e in check_outs) if check_outs else None

        # Determine location (prefer first event's location, fallback to product's registered)
        first_event = day_events[0]
        location = first_event.location_ref or (
            first_event.product.registered_location if first_event.product else None
        )
        location_id = location.id if location else None

        # Calculate work hours
        if last_check_out:
            work_result = calculate_workday(
                first_check_in=first_check_in,
                last_check_out=last_check_out,
                location=location,
                target_date=event_date,
                lunch_minutes=lunch_minutes,
            )
            is_complete = True
        else:
            # No check-out → incomplete day
            work_result = None
            is_complete = False

        # Build values
        total_minutes = int(work_result.total_hours * 60) if work_result else 0
        ot_minutes = int(work_result.ot_hours * 60) if work_result else 0
        regular_hours = float(work_result.standard_hours) if work_result else 0.0
        ot_hours = float(work_result.ot_hours) if work_result else 0.0

        # Upsert
        existing_result = await db.execute(
            select(AttendanceSummary).where(
                AttendanceSummary.product_id == product_id,
                AttendanceSummary.summary_date == event_date,
            )
        )
        summary = existing_result.scalar_one_or_none()

        if summary:
            summary.first_check_in = first_check_in
            summary.last_check_out = last_check_out
            summary.total_work_minutes = total_minutes
            summary.total_overtime_minutes = ot_minutes
            summary.total_break_minutes = lunch_minutes
            summary.is_complete = is_complete
            summary.is_weekend = event_date.weekday() >= 5
            summary.regular_hours = regular_hours
            summary.overtime_hours = ot_hours
            summary.location_id = location_id
            summary.updated_at = datetime.now(timezone.utc)
            updated_count += 1
        else:
            summary = AttendanceSummary(
                product_id=product_id,
                summary_date=event_date,
                location_id=location_id,
                first_check_in=first_check_in,
                last_check_out=last_check_out,
                total_work_minutes=total_minutes,
                total_overtime_minutes=ot_minutes,
                total_break_minutes=lunch_minutes,
                is_complete=is_complete,
                is_weekend=event_date.weekday() >= 5,
                regular_hours=regular_hours,
                overtime_hours=ot_hours,
            )
            db.add(summary)
            created_count += 1

    await db.commit()

    return {
        "created": created_count,
        "updated": updated_count,
        "total_days": len(grouped),
        "year": year,
        "month": month,
    }
