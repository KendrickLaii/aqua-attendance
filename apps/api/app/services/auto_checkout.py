"""Auto-checkout service.

Runs at 23:59 daily to create check-out events for any product still checked in.
This is the "day boundary" safety net for users who forget to scan out.

Rules (from DATABASE_CHANGES.md):
- Trigger time = 23:59 (day boundary), NOT closing time
- All double check_in / check_out are allowed; calculation only uses first & last
"""

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attendance import AttendanceEvent, EventType
from app.models.product import AttendanceStatus, Product


async def auto_checkout_for_date(
    db: AsyncSession,
    target_date: date | None = None,
) -> list[AttendanceEvent]:
    """Create auto-checkout events for all products still checked-in at 23:59.

    Args:
        db: database session
        target_date: the date to process (defaults to today)

    Returns:
        list of created auto-checkout events
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    # Find all products with attendance_status = checked_in
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.registered_location))
        .where(Product.attendance_status == AttendanceStatus.checked_in.value)
        .where(Product.is_active.is_(True))
    )
    products = result.scalars().all()

    # Auto-checkout time = 23:59 of target date
    checkout_time = datetime.combine(target_date, time(23, 59, 0), tzinfo=timezone.utc)

    created_events: list[AttendanceEvent] = []
    for product in products:
        event = AttendanceEvent(
            product_id=product.id,
            event_type=EventType.check_out.value,
            source="auto_checkout",
            recorded_at=checkout_time,
            location_id=product.last_event_location_id,
            location=product.last_event_location or "auto",
            notes=f"Auto checkout at day boundary (product was still checked in)",
        )
        db.add(event)

        # Update product status
        product.attendance_status = AttendanceStatus.checked_out.value
        product.last_event_at = checkout_time

        created_events.append(event)

    if created_events:
        await db.commit()
        for event in created_events:
            await db.refresh(event)

    return created_events


async def get_still_checked_in_count(db: AsyncSession) -> int:
    """Return the number of products currently checked in."""
    from sqlalchemy import func
    result = await db.execute(
        select(func.count())
        .select_from(Product)
        .where(Product.attendance_status == AttendanceStatus.checked_in.value)
        .where(Product.is_active.is_(True))
    )
    return result.scalar_one()
