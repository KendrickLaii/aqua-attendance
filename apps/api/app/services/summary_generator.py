"""Generate attendance summaries from raw events for a given month.

Admin selects a month → this service calculates daily summaries for every
unit and inserts / updates `attendance_summaries` rows.

Forgotten check-outs on past days are closed at the day boundary (23:59)
with an ``auto_checkout`` event — same helper as the Auto Checkout job —
so Incomplete is reserved for days that still lack a usable pair
(e.g. today still open, or check-out without check-in).

Checkout-only days are kept as Incomplete (0 hours) so admins can see them
and add a Manual correction check-in to complete the day.

Orphan cleanup deletes month rows with no attendance events for that day,
except rows with ``calculation_method=seed`` (demo data from ``seed.py --summaries``).
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
from app.models.unit import Unit
from app.services.attendance import recompute_unit_attendance_status
from app.attendance_tz import ATTENDANCE_TZ, attendance_date, attendance_today, day_boundary_at
from app.services.auto_checkout import (
    DAY_BOUNDARY_NOTE,
    is_auto_checkout_enabled,
    make_day_boundary_checkout_event,
)

from app.services.overtime import calculate_workday


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _summarize_one_day(
    db: AsyncSession,
    *,
    unit_id: uuid.UUID,
    event_date: date,
    day_events: list[AttendanceEvent],
    today: date,
) -> tuple[int, int, int, uuid.UUID | None]:
    """Upsert one unit/day summary. Returns (created, updated, auto_checkouts, unit_id_to_recompute)."""
    check_ins = [e for e in day_events if e.event_type == EventType.check_in.value]
    check_outs = [e for e in day_events if e.event_type == EventType.check_out.value]

    if not check_ins and not check_outs:
        return 0, 0, 0, None

    first_event = day_events[0]
    location = first_event.location_ref or (
        first_event.unit.registered_location if first_event.unit else None
    )
    location_id = location.id if location else (
        first_event.unit.registered_location_id if first_event.unit else None
    )
    if location_id is None:
        return 0, 0, 0, None

    notes: str | None = None
    work_result = None
    is_complete = False
    first_check_in = None
    last_out_event = (
        max(check_outs, key=lambda e: _as_utc(e.recorded_at)) if check_outs else None
    )
    last_check_out = last_out_event.recorded_at if last_out_event else None
    auto_checkout_count = 0
    recompute_unit_id: uuid.UUID | None = None

    if not check_ins:
        notes = "Missing check-in — add Manual correction to complete the day"
    else:
        first_check_in = min(_as_utc(e.recorded_at) for e in check_ins)

        if (
            is_auto_checkout_enabled()
            and last_check_out is None
            and event_date < today
        ):
            last_check_out = day_boundary_at(event_date)
            db.add(
                make_day_boundary_checkout_event(
                    unit_id=unit_id,
                    checkout_time=last_check_out,
                    location_id=location_id,
                    location=first_event.location
                    or (location.code if location and location.code else "auto"),
                )
            )
            notes = "Closed by day-boundary auto checkout (23:59)"
            auto_checkout_count = 1
            recompute_unit_id = unit_id
        elif (
            last_out_event is not None
            and last_out_event.source == EventSource.auto_checkout.value
        ):
            notes = (last_out_event.notes or "").strip() or DAY_BOUNDARY_NOTE
        elif last_check_out is None and event_date < today:
            notes = "Missing check-out — add Manual correction to complete the day"

        if last_check_out:
            work_result = calculate_workday(
                first_check_in=first_check_in,
                last_check_out=last_check_out,
                location=location,
                target_date=event_date,
            )
            is_complete = True

    total_minutes = int(work_result.total_hours * 60) if work_result else 0
    ot_minutes = int(work_result.ot_hours * 60) if work_result else 0
    regular_hours = float(work_result.standard_hours) if work_result else 0.0
    ot_hours = float(work_result.ot_hours) if work_result else 0.0
    ot_slots = work_result.ot_slots if work_result else 0
    regular_slots = max(0, work_result.total_slots - ot_slots) if work_result else 0

    existing_result = await db.execute(
        select(AttendanceSummary).where(
            AttendanceSummary.unit_id == unit_id,
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
        summary.calculation_method = "standard"
        summary.updated_at = datetime.now(timezone.utc)
        return 0, 1, auto_checkout_count, recompute_unit_id

    db.add(
        AttendanceSummary(
            unit_id=unit_id,
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
    )
    return 1, 0, auto_checkout_count, recompute_unit_id


async def refresh_unit_day_summary(
    db: AsyncSession,
    *,
    unit_id: uuid.UUID,
    day: date,
) -> None:
    """Rebuild one unit's daily summary from current non-voided events. Does not commit."""
    start_dt = datetime.combine(day, datetime.min.time(), tzinfo=ATTENDANCE_TZ)
    end_dt = datetime.combine(day, datetime.max.time(), tzinfo=ATTENDANCE_TZ)
    result = await db.execute(
        select(AttendanceEvent)
        .options(
            selectinload(AttendanceEvent.unit).selectinload(Unit.registered_location),
            selectinload(AttendanceEvent.location_ref),
        )
        .where(AttendanceEvent.unit_id == unit_id)
        .where(AttendanceEvent.recorded_at >= start_dt)
        .where(AttendanceEvent.recorded_at <= end_dt)
        .where(AttendanceEvent.voided_at.is_(None))
        .order_by(AttendanceEvent.recorded_at)
    )
    events = list(result.scalars().all())
    today = attendance_today()

    if not events:
        existing = await db.execute(
            select(AttendanceSummary).where(
                AttendanceSummary.unit_id == unit_id,
                AttendanceSummary.summary_date == day,
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None and (row.calculation_method or "").lower() != "seed":
            await db.delete(row)
        return

    created, updated, auto, recompute_id = await _summarize_one_day(
        db,
        unit_id=unit_id,
        event_date=day,
        day_events=events,
        today=today,
    )
    if recompute_id is not None:
        await db.flush()
        unit_result = await db.execute(select(Unit).where(Unit.id == recompute_id))
        unit = unit_result.scalar_one_or_none()
        if unit is not None:
            await recompute_unit_attendance_status(db, unit=unit)
    _ = (created, updated, auto)


async def generate_monthly_summaries(
    db: AsyncSession,
    year: int,
    month: int,
) -> dict:
    """Generate attendance summaries for every unit for the given month.

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

    # Fetch all non-voided events in range with unit & location
    result = await db.execute(
        select(AttendanceEvent)
        .options(
            selectinload(AttendanceEvent.unit).selectinload(Unit.registered_location),
            selectinload(AttendanceEvent.location_ref),
        )
        .where(AttendanceEvent.recorded_at >= start_dt)
        .where(AttendanceEvent.recorded_at <= end_dt)
        .where(AttendanceEvent.voided_at.is_(None))
        .order_by(AttendanceEvent.recorded_at)
    )
    events = result.scalars().all()

    # Group by (unit_id, attendance-local date) so HKT day-boundary outs stay on that day
    grouped: dict[tuple[uuid.UUID, date], list[AttendanceEvent]] = defaultdict(list)
    for event in events:
        event_date = attendance_date(event.recorded_at)
        grouped[(event.unit_id, event_date)].append(event)

    created_count = 0
    updated_count = 0
    auto_checkout_count = 0
    units_to_recompute: set[uuid.UUID] = set()
    kept_keys: set[tuple[uuid.UUID, date]] = set()

    for (unit_id, event_date), day_events in grouped.items():
        created, updated, auto, recompute_id = await _summarize_one_day(
            db,
            unit_id=unit_id,
            event_date=event_date,
            day_events=day_events,
            today=today,
        )
        if created == 0 and updated == 0 and auto == 0 and recompute_id is None:
            continue
        created_count += created
        updated_count += updated
        auto_checkout_count += auto
        if recompute_id is not None:
            units_to_recompute.add(recompute_id)
        kept_keys.add((unit_id, event_date))

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
        if (row.unit_id, row.summary_date) not in kept_keys
        and (row.calculation_method or "").lower() != "seed"
    ]
    orphans_deleted = 0
    if orphan_ids:
        await db.execute(
            delete(AttendanceSummary).where(AttendanceSummary.id.in_(orphan_ids))
        )
        orphans_deleted = len(orphan_ids)

    if units_to_recompute:
        await db.flush()
        unit_result = await db.execute(
            select(Unit).where(Unit.id.in_(units_to_recompute))
        )
        for unit in unit_result.scalars().all():
            await recompute_unit_attendance_status(db, unit=unit)

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
