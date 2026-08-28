"""Generate monthly tuition invoices from course enrollments."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.attendance_tz import ATTENDANCE_TZ, attendance_date
from app.models.attendance import AttendanceEvent
from app.models.course_enrollment import CourseEnrollment
from app.models.course_sku import CourseSku
from app.models.tuition_invoice import TuitionInvoice, TuitionInvoiceLine, TuitionInvoiceStatus

_LOCKED = frozenset({TuitionInvoiceStatus.issued.value, TuitionInvoiceStatus.paid.value})
_WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def scheduled_session_dates(
    meeting_weekdays: list[str] | None,
    *,
    period_start: date,
    period_end: date,
    enroll_start: date | None,
    enroll_end: date | None,
) -> list[date] | None:
    """Return class dates in the clipped billing window.

    ``None`` means weekdays are not configured (callers treat as quantity 1).
    An empty list means zero sessions (skip the line).
    Does not subtract holidays or absences.
    """
    start = max(period_start, enroll_start or period_start)
    end = min(period_end, enroll_end or period_end)
    if start > end:
        return []
    wanted = {_WEEKDAY_INDEX[day] for day in (meeting_weekdays or []) if day in _WEEKDAY_INDEX}
    if not wanted:
        return None
    dates: list[date] = []
    cursor = start
    step = timedelta(days=1)
    while cursor <= end:
        if cursor.weekday() in wanted:
            dates.append(cursor)
        cursor += step
    return dates


def count_scheduled_sessions(
    meeting_weekdays: list[str] | None,
    *,
    period_start: date,
    period_end: date,
    enroll_start: date | None,
    enroll_end: date | None,
) -> int:
    """Count calendar days in the billing window that match SKU class days."""
    dates = scheduled_session_dates(
        meeting_weekdays,
        period_start=period_start,
        period_end=period_end,
        enroll_start=enroll_start,
        enroll_end=enroll_end,
    )
    if dates is None:
        return 1
    return len(dates)


def _present_dates_for_sku(events: list[AttendanceEvent], sku_location_id: UUID | None) -> set[date]:
    present: set[date] = set()
    for event in events:
        if sku_location_id is not None and event.location_id != sku_location_id:
            continue
        present.add(attendance_date(event.recorded_at))
    return present


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _line_from_enrollment(
    enrollment: CourseEnrollment,
    first_day: date,
    last_day: date,
    present_dates: set[date],
) -> TuitionInvoiceLine | None:
    sku = enrollment.sku
    if sku is None or sku.price is None:
        return None
    unit_price = _money(sku.price)
    if sku.billing_unit == "per_session":
        dates = scheduled_session_dates(
            sku.meeting_weekdays,
            period_start=first_day,
            period_end=last_day,
            enroll_start=enrollment.start_date,
            enroll_end=enrollment.end_date,
        )
        if dates is None:
            quantity = _money(1)
        else:
            quantity = _money(sum(1 for day in dates if day in present_dates))
    else:
        quantity = _money(1)
    if quantity <= 0:
        return None
    return TuitionInvoiceLine(
        enrollment_id=enrollment.id,
        sku_id=sku.id,
        sku_code=sku.code,
        name_zh=sku.name_zh,
        billing_unit=sku.billing_unit,
        unit_price=unit_price,
        quantity=quantity,
        amount=unit_price * quantity,
    )


async def _attendance_by_unit(
    db: AsyncSession,
    unit_ids: set[UUID],
    first_day: date,
    last_day: date,
) -> dict[UUID, list[AttendanceEvent]]:
    if not unit_ids:
        return {}
    start_utc = datetime.combine(first_day, time.min, tzinfo=ATTENDANCE_TZ).astimezone(timezone.utc)
    end_utc = datetime.combine(last_day, time.max, tzinfo=ATTENDANCE_TZ).astimezone(timezone.utc)
    result = await db.execute(
        select(AttendanceEvent).where(
            AttendanceEvent.unit_id.in_(unit_ids),
            AttendanceEvent.voided_at.is_(None),
            AttendanceEvent.recorded_at >= start_utc,
            AttendanceEvent.recorded_at <= end_utc,
        )
    )
    by_unit: dict[UUID, list[AttendanceEvent]] = defaultdict(list)
    for event in result.scalars():
        by_unit[event.unit_id].append(event)
    return by_unit


async def generate_monthly_tuition_invoices(
    db: AsyncSession,
    *,
    year: int,
    month: int,
) -> dict[str, int]:
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    result = await db.execute(
        select(CourseEnrollment)
        .options(selectinload(CourseEnrollment.sku))
        .join(CourseSku, CourseEnrollment.sku_id == CourseSku.id)
        .where(
            CourseEnrollment.status == "active",
            or_(CourseEnrollment.start_date.is_(None), CourseEnrollment.start_date <= last_day),
            or_(CourseEnrollment.end_date.is_(None), CourseEnrollment.end_date >= first_day),
            CourseSku.price.is_not(None),
            CourseSku.is_active.is_(True),
        )
    )
    enrollments = result.scalars().all()
    attendance_by_unit = await _attendance_by_unit(
        db, {enrollment.unit_id for enrollment in enrollments}, first_day, last_day
    )

    by_unit: dict = defaultdict(list)
    for enrollment in enrollments:
        sku = enrollment.sku
        present = _present_dates_for_sku(
            attendance_by_unit.get(enrollment.unit_id, []),
            sku.location_id if sku is not None else None,
        )
        line = _line_from_enrollment(enrollment, first_day, last_day, present)
        if line is None:
            continue
        by_unit[enrollment.unit_id].append(line)

    existing_result = await db.execute(
        select(TuitionInvoice)
        .options(selectinload(TuitionInvoice.lines))
        .where(
            TuitionInvoice.period_start == first_day,
            TuitionInvoice.period_end == last_day,
        )
    )
    existing_by_unit = {invoice.unit_id: invoice for invoice in existing_result.scalars().all()}

    created = 0
    updated = 0
    skipped = 0

    for unit_id, unit_enrollments in by_unit.items():
        invoice = existing_by_unit.get(unit_id)
        if invoice is not None and invoice.status in _LOCKED:
            skipped += 1
            continue

        lines = unit_enrollments
        total = sum((line.amount for line in lines), Decimal("0.00"))

        if invoice is None:
            invoice = TuitionInvoice(
                unit_id=unit_id,
                period_start=first_day,
                period_end=last_day,
                status=TuitionInvoiceStatus.draft.value,
                total=total,
            )
            invoice.lines = lines
            db.add(invoice)
            created += 1
            continue

        invoice.lines.clear()
        invoice.total = total
        invoice.status = TuitionInvoiceStatus.draft.value
        for line in lines:
            invoice.lines.append(line)
        updated += 1

    deleted = 0
    for unit_id, invoice in existing_by_unit.items():
        if unit_id in by_unit:
            continue
        if invoice.status in _LOCKED or invoice.status == TuitionInvoiceStatus.void.value:
            skipped += 1
            continue
        await db.delete(invoice)
        deleted += 1

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise
    return {"created": created, "updated": updated, "skipped": skipped, "deleted": deleted}
