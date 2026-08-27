"""Generate monthly tuition invoices from course enrollments."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.course_enrollment import CourseEnrollment
from app.models.tuition_invoice import TuitionInvoice, TuitionInvoiceLine, TuitionInvoiceStatus

_LOCKED = frozenset({TuitionInvoiceStatus.issued.value, TuitionInvoiceStatus.paid.value})


def enrollment_overlaps_month(enrollment: CourseEnrollment, first_day: date, last_day: date) -> bool:
    if enrollment.status != "active":
        return False
    if enrollment.start_date is not None and enrollment.start_date > last_day:
        return False
    if enrollment.end_date is not None and enrollment.end_date < first_day:
        return False
    return True


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _line_from_enrollment(enrollment: CourseEnrollment) -> TuitionInvoiceLine:
    sku = enrollment.sku
    unit_price = _money(sku.price)
    quantity = _money(1)
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


async def generate_monthly_tuition_invoices(
    db: AsyncSession,
    *,
    year: int,
    month: int,
) -> dict[str, int]:
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    result = await db.execute(
        select(CourseEnrollment).options(
            selectinload(CourseEnrollment.sku),
        )
    )
    enrollments = result.scalars().all()

    by_unit: dict = defaultdict(list)
    for enrollment in enrollments:
        if not enrollment_overlaps_month(enrollment, first_day, last_day):
            continue
        sku = enrollment.sku
        if sku is None or sku.price is None:
            continue
        by_unit[enrollment.unit_id].append(enrollment)

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

        lines = [_line_from_enrollment(enrollment) for enrollment in unit_enrollments]
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

    await db.commit()
    return {"created": created, "updated": updated, "skipped": skipped}
