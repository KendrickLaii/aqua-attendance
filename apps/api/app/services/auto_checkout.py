"""Auto-checkout service.

Day-boundary safety net for users who forget to scan out.

Rules (from DATABASE_CHANGES.md):
- Trigger time = 23:59 (day boundary), NOT closing time
- All double check_in / check_out are allowed; calculation only uses first & last

**Status (not a complete automated system):**
- Shared helper + manual ``POST /api/auto-checkout/run`` + Generate backfill for past days: yes
- Nightly 23:59 cron / worker and 00:00 status reset: **not implemented** (see docs/known-gaps.md #M14)

Both the Dashboard Day-end action and summary generate use
``make_day_boundary_checkout_event`` so event shape and status updates stay aligned.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.attendance_tz import (
    ATTENDANCE_TZ,
    attendance_today,
    day_boundary_at,
)
from app.models.attendance import AttendanceEvent, EventSource, EventType
from app.models.unit import AttendanceStatus, Unit
from app.services.attendance import recompute_unit_attendance_status

# Re-export for callers / tests that import from this module.
__all__ = [
    "ATTENDANCE_TZ",
    "DAY_BOUNDARY_NOTE",
    "attendance_today",
    "auto_checkout_for_date",
    "day_boundary_at",
    "get_still_checked_in_count",
    "make_day_boundary_checkout_event",
]

DAY_BOUNDARY_NOTE = "Auto checkout at day boundary (23:59)"


def make_day_boundary_checkout_event(
    *,
    unit_id: uuid.UUID,
    checkout_time: datetime,
    location_id: uuid.UUID | None = None,
    location: str | None = None,
) -> AttendanceEvent:
    """Build a day-boundary check-out event (caller adds to session)."""
    loc = (location or "").strip() or "auto"
    return AttendanceEvent(
        unit_id=unit_id,
        event_type=EventType.check_out.value,
        source=EventSource.auto_checkout.value,
        recorded_at=checkout_time,
        location_id=location_id,
        location=loc[:255],
        notes=DAY_BOUNDARY_NOTE,
    )


async def auto_checkout_for_date(
    db: AsyncSession,
    target_date: date | None = None,
    unit_ids: list[uuid.UUID] | None = None,
) -> list[AttendanceEvent]:
    """Create auto-checkout events for units still checked-in at 23:59.

    Args:
        db: database session
        target_date: the date to process (defaults to today in HKT)
        unit_ids: when provided, only these units are checked out.
            Unselected units stay checked in so admins can investigate
            why they never scanned out. When ``None`` all still-checked-in
            units are processed (intended scheduled-job behaviour once
            a cron exists; today only the manual API uses this path).

    Returns:
        list of created auto-checkout events
    """
    if target_date is None:
        target_date = attendance_today()

    query = (
        select(Unit)
        .options(selectinload(Unit.registered_location))
        .where(Unit.attendance_status == AttendanceStatus.checked_in.value)
        .where(Unit.is_active.is_(True))
    )
    if unit_ids is not None:
        if not unit_ids:
            return []
        query = query.where(Unit.id.in_(unit_ids))

    result = await db.execute(query)
    units = list(result.scalars().all())

    checkout_time = day_boundary_at(target_date)
    created_events: list[AttendanceEvent] = []

    for unit in units:
        event = make_day_boundary_checkout_event(
            unit_id=unit.id,
            checkout_time=checkout_time,
            location_id=unit.last_event_location_id,
            location=unit.last_event_location or "auto",
        )
        db.add(event)
        created_events.append(event)

    if created_events:
        await db.flush()
        for unit in units:
            await recompute_unit_attendance_status(db, unit=unit)
        await db.commit()
        for event in created_events:
            await db.refresh(event)

    return created_events


async def get_still_checked_in_count(db: AsyncSession) -> int:
    """Return the number of units currently checked in."""
    from sqlalchemy import func

    result = await db.execute(
        select(func.count())
        .select_from(Unit)
        .where(Unit.attendance_status == AttendanceStatus.checked_in.value)
        .where(Unit.is_active.is_(True))
    )
    return result.scalar_one()
