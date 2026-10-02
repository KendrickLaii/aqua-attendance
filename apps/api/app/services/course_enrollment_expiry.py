"""Expire active enrollments whose last billed day has passed."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course_enrollment import CourseEnrollment, EnrollmentStatus

_HK = ZoneInfo("Asia/Hong_Kong")


def hong_kong_today() -> date:
    return datetime.now(_HK).date()


async def expire_past_end_date_enrollments(
    db: AsyncSession,
    *,
    sku_id: UUID | None = None,
    unit_id: UUID | None = None,
    enrollment_id: UUID | None = None,
    as_of: date | None = None,
) -> int:
    """Mark active enrollments with end_date before as_of as completed.

    completed means the term finished (still bill months that overlap the dates).
    Staff Leave stays cancelled and is excluded from Generate.

    end_date is the last billed day, so the student stays In class on that day
    and leaves starting the next Hong Kong calendar day.
    """
    today = as_of or hong_kong_today()
    clauses = [
        CourseEnrollment.status == EnrollmentStatus.active.value,
        CourseEnrollment.end_date.is_not(None),
        CourseEnrollment.end_date < today,
    ]
    if sku_id is not None:
        clauses.append(CourseEnrollment.sku_id == sku_id)
    if unit_id is not None:
        clauses.append(CourseEnrollment.unit_id == unit_id)
    if enrollment_id is not None:
        clauses.append(CourseEnrollment.id == enrollment_id)

    result = await db.execute(
        update(CourseEnrollment)
        .where(*clauses)
        .values(status=EnrollmentStatus.completed.value)
        .returning(CourseEnrollment.id)
    )
    expired_ids = list(result.scalars().all())
    return len(expired_ids)


def should_auto_leave(*, end_date: date | None, status: str, as_of: date | None = None) -> bool:
    if status != EnrollmentStatus.active.value or end_date is None:
        return False
    return end_date < (as_of or hong_kong_today())
