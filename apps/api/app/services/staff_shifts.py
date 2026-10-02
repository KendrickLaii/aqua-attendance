"""Staff shift portal: PIN login and self-service shift requests."""

import uuid
from datetime import date, datetime, time, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.attendance_tz import attendance_today
from app.models.location import Location
from app.models.shift import Shift, ShiftTemplate
from app.models.shift_request import ShiftRequest, ShiftRequestStatus
from app.models.unit import Unit, unit_scan_locations


def times_overlap(start_a: time, end_a: time, start_b: time, end_b: time) -> bool:
    return start_a < end_b and start_b < end_a


async def allowed_location_ids(db: AsyncSession, unit: Unit) -> set[uuid.UUID]:
    result = await db.execute(
        select(unit_scan_locations.c.location_id).where(unit_scan_locations.c.unit_id == unit.id)
    )
    ids = set(result.scalars().all())
    ids.add(unit.registered_location_id)
    return ids


async def assert_request_slot(
    db: AsyncSession,
    *,
    unit: Unit,
    location_id: uuid.UUID,
    shift_date: date,
    start_time: time,
    end_time: time,
    template_id: uuid.UUID | None,
    exclude_request_id: uuid.UUID | None = None,
) -> None:
    if shift_date < attendance_today():
        raise HTTPException(status_code=422, detail="shift_date cannot be in the past")
    if location_id not in await allowed_location_ids(db, unit):
        raise HTTPException(status_code=422, detail="location is not assigned to this staff member")
    if not await db.scalar(select(Location.id).where(Location.id == location_id)):
        raise HTTPException(status_code=422, detail="location_id does not reference an existing location")
    if template_id and not await db.scalar(select(ShiftTemplate.id).where(ShiftTemplate.id == template_id)):
        raise HTTPException(status_code=422, detail="template_id does not reference an existing shift template")

    shifts = await db.scalars(select(Shift).where(Shift.unit_id == unit.id, Shift.shift_date == shift_date))
    pending = await db.scalars(
        select(ShiftRequest).where(
            ShiftRequest.unit_id == unit.id,
            ShiftRequest.shift_date == shift_date,
            ShiftRequest.status == ShiftRequestStatus.pending.value,
        )
    )
    for row in (*shifts.all(), *pending.all()):
        if exclude_request_id is not None and getattr(row, "id", None) == exclude_request_id:
            continue
        if times_overlap(start_time, end_time, row.start_time, row.end_time):
            raise HTTPException(
                status_code=409,
                detail="This shift overlaps an existing shift or pending request",
            )


def copy_request_to_shift(request: ShiftRequest, *, admin_id: uuid.UUID) -> Shift:
    return Shift(
        unit_id=request.unit_id,
        location_id=request.location_id,
        shift_date=request.shift_date,
        start_time=request.start_time,
        end_time=request.end_time,
        title=request.title,
        color=request.color,
        notes=request.notes,
        template_id=request.template_id,
        created_by_id=admin_id,
        updated_by_id=admin_id,
    )


def mark_reviewed(request: ShiftRequest, *, admin_id: uuid.UUID, status: str, reason: str | None = None) -> None:
    request.status = status
    request.reviewed_by_id = admin_id
    request.reviewed_at = datetime.now(timezone.utc)
    request.reject_reason = reason
