"""Generate attendance summaries from raw events for a given month.

Admin selects a month → this service calculates daily summaries for every
product and inserts / updates `attendance_summaries` rows.

Forgotten check-outs on past days are closed at the day boundary (23:59)
with an ``auto_checkout`` event — same helper as the Auto Checkout job —
so Incomplete is reserved for days that are still open (e.g. today).

Orphan cleanup deletes month rows with no usable check-in events, except
rows with ``calculation_method=seed`` (demo data from ``seed.py --summaries``).
"""

import calendar
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attendance import AttendanceEvent, EventSource, EventType
from app.models.attendance_summary import AttendanceSummary
from app.models.product import Product
from app.services.attendance import recompute_product_attendance_status
from app.attendance_tz import ATTENDANCE_TZ, attendance_date, attendance_today, day_boundary_at
from app.services.auto_checkout import DAY_BOUNDARY_NOTE, make_day_boundary_checkout_event

from app.services.overtime import calculate_workday


async def generate_monthly_summaries(
    db: AsyncSession,
    year: int,
    month: int,
) -> dict:
    """Generate attendance summaries for every product for the given month.

    Returns:
        dict with counts: {"created": int, "updated": int, "total_days": int,
        "auto_checkouts": int, "orphans_deleted": int}
    """
    # Date range
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    # Bound the month in attendance TZ so day-boundary outs at 23:59 HKT are included.
    start_dt = datetime.combine(first_day, datetime.min.time(), tzinfo=ATTENDANCE_TZ)
    end_dt = datetime.combine(last_day, datetime.max.time(), tzinfo=ATTENDANCE_TZ)
    today = attendance_today()

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

    # Group by (product_id, attendance-local date) so HKT day-boundary outs stay on that day
    grouped: dict[tuple[uuid.UUID, date], list[AttendanceEvent]] = defaultdict(list)
    for event in events:
        event_date = attendance_date(event.recorded_at)
        grouped[(event.product_id, event_date)].append(event)

    created_count = 0
    updated_count = 0
    auto_checkout_count = 0
    products_to_recompute: set[uuid.UUID] = set()
    kept_keys: set[tuple[uuid.UUID, date]] = set()

    for (product_id, event_date), day_events in grouped.items():
        # Separate check_ins and check_outs
        check_ins = [e for e in day_events if e.event_type == EventType.check_in.value]
        check_outs = [e for e in day_events if e.event_type == EventType.check_out.value]

        if not check_ins:
            continue  # No check-in → cannot calculate workday

        first_check_in = min(e.recorded_at for e in check_ins)
        last_out_event = (
            max(check_outs, key=lambda e: e.recorded_at) if check_outs else None
        )
        last_check_out = last_out_event.recorded_at if last_out_event else None

        # Determine location (prefer first event's location, fallback to product's registered)
        first_event = day_events[0]
        location = first_event.location_ref or (
            first_event.product.registered_location if first_event.product else None
        )
        location_id = location.id if location else (
            first_event.product.registered_location_id if first_event.product else None
        )
        if location_id is None:
            continue  # summaries require a location_id

        notes: str | None = None

        # Past days with check-in but no check-out → day-boundary auto checkout
        if last_check_out is None and event_date < today:
            last_check_out = day_boundary_at(event_date)
            db.add(
                make_day_boundary_checkout_event(
                    product_id=product_id,
                    checkout_time=last_check_out,
                    location_id=location_id,
                    location=first_event.location
                    or (location.code if location and location.code else "auto"),
                )
            )
            notes = "Closed by day-boundary auto checkout (23:59)"
            auto_checkout_count += 1
            products_to_recompute.add(product_id)
        elif (
            last_out_event is not None
            and last_out_event.source == EventSource.auto_checkout.value
        ):
            # Day-end (or prior Generate) already wrote the event — still mark the day
            notes = (last_out_event.notes or "").strip() or DAY_BOUNDARY_NOTE

        # Calculate work hours
        if last_check_out:
            work_result = calculate_workday(
                first_check_in=first_check_in,
                last_check_out=last_check_out,
                location=location,
                target_date=event_date,
            )
            is_complete = True
        else:
            # Still open (typically today before check-out / auto-checkout)
            work_result = None
            is_complete = False

        # Build values
        total_minutes = int(work_result.total_hours * 60) if work_result else 0
        ot_minutes = int(work_result.ot_hours * 60) if work_result else 0
        regular_hours = float(work_result.standard_hours) if work_result else 0.0
        ot_hours = float(work_result.ot_hours) if work_result else 0.0
        # Slot-based source of truth (1 slot = 15 min = 0.25h)
        ot_slots = work_result.ot_slots if work_result else 0
        regular_slots = max(0, work_result.total_slots - ot_slots) if work_result else 0

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
            summary.is_complete = is_complete
            summary.is_weekend = event_date.weekday() >= 5
            summary.regular_slots = regular_slots
            summary.ot_slots = ot_slots
            summary.regular_hours = regular_hours
            summary.overtime_hours = ot_hours
            summary.location_id = location_id
            summary.attendance_notes = notes
            # Real events replace seed demo rows for this product/day
            summary.calculation_method = "standard"
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
                is_complete=is_complete,
                is_weekend=event_date.weekday() >= 5,
                regular_slots=regular_slots,
                ot_slots=ot_slots,
                regular_hours=regular_hours,
                overtime_hours=ot_hours,
                attendance_notes=notes,
                calculation_method="standard",
            )
            db.add(summary)
            created_count += 1

        kept_keys.add((product_id, event_date))

    # Remove event-less month rows, but keep seed demo data (calculation_method=seed)
    existing_summaries = await db.execute(
        select(AttendanceSummary).where(
            AttendanceSummary.summary_date >= first_day,
            AttendanceSummary.summary_date <= last_day,
        )
    )
    orphan_ids = [
        row.id
        for row in existing_summaries.scalars().all()
        if (row.product_id, row.summary_date) not in kept_keys
        and (row.calculation_method or "").lower() != "seed"
    ]
    orphans_deleted = 0
    if orphan_ids:
        await db.execute(
            delete(AttendanceSummary).where(AttendanceSummary.id.in_(orphan_ids))
        )
        orphans_deleted = len(orphan_ids)

    if products_to_recompute:
        await db.flush()
        product_result = await db.execute(
            select(Product).where(Product.id.in_(products_to_recompute))
        )
        for product in product_result.scalars().all():
            await recompute_product_attendance_status(db, product=product)

    await db.commit()

    return {
        "created": created_count,
        "updated": updated_count,
        "total_days": len(kept_keys),
        "auto_checkouts": auto_checkout_count,
        "orphans_deleted": orphans_deleted,
        "year": year,
        "month": month,
    }
