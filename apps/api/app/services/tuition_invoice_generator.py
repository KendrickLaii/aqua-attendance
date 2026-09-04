"""Generate monthly tuition invoices from course enrollments.

Billing is derived purely from CourseEnrollment + CourseSku, not attendance:

- monthly (月費): flat unit_price, quantity 1, billed every active month.
- per_session (堂費): a one-time charge for ``purchased_quantity`` sessions,
  set by admin at enrollment time. It is billed exactly once, in the first
  month Generate runs for while the enrollment is active; later months are
  skipped by checking whether a non-void invoice line already exists for
  that enrollment in a different period. If that invoice is later voided,
  the charge is treated as not-yet-billed and can be regenerated.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.course_enrollment import CourseEnrollment
from app.models.course_sku import CourseSku
from app.models.tuition_invoice import TuitionInvoice, TuitionInvoiceLine, TuitionInvoiceStatus
from app.models.unit import Unit, UnitStatus

_LOCKED = frozenset({TuitionInvoiceStatus.issued.value, TuitionInvoiceStatus.paid.value})


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _line_from_enrollment(
    enrollment: CourseEnrollment,
    already_billed_elsewhere: set[UUID],
) -> TuitionInvoiceLine | None:
    sku = enrollment.sku
    if sku is None or sku.price is None:
        return None
    unit_price = _money(sku.price)
    if sku.billing_unit == "per_session":
        if enrollment.id in already_billed_elsewhere or enrollment.purchased_quantity is None:
            return None
        quantity = _money(enrollment.purchased_quantity)
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


async def _already_billed_elsewhere(
    db: AsyncSession,
    enrollment_ids: set[UUID],
    first_day: date,
    last_day: date,
) -> set[UUID]:
    """One-time per_session charges: enrollments already billed in a
    different, non-void period. Void invoices don't count as billed."""
    if not enrollment_ids:
        return set()
    result = await db.execute(
        select(TuitionInvoiceLine.enrollment_id)
        .join(TuitionInvoice, TuitionInvoiceLine.invoice_id == TuitionInvoice.id)
        .where(
            TuitionInvoiceLine.enrollment_id.in_(enrollment_ids),
            TuitionInvoice.status != TuitionInvoiceStatus.void.value,
            or_(
                TuitionInvoice.period_start != first_day,
                TuitionInvoice.period_end != last_day,
            ),
        )
        .distinct()
    )
    return {row[0] for row in result.all()}


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
        .join(Unit, CourseEnrollment.unit_id == Unit.id)
        .where(
            CourseEnrollment.status == "active",
            or_(CourseEnrollment.start_date.is_(None), CourseEnrollment.start_date <= last_day),
            or_(CourseEnrollment.end_date.is_(None), CourseEnrollment.end_date >= first_day),
            CourseSku.price.is_not(None),
            CourseSku.is_active.is_(True),
            Unit.is_active.is_(True),
            Unit.status == UnitStatus.active.value,
        )
    )
    enrollments = result.scalars().all()

    per_session_ids = {
        enrollment.id
        for enrollment in enrollments
        if enrollment.sku is not None and enrollment.sku.billing_unit == "per_session"
    }
    already_billed_elsewhere = await _already_billed_elsewhere(db, per_session_ids, first_day, last_day)

    by_unit: dict = defaultdict(list)
    for enrollment in enrollments:
        line = _line_from_enrollment(enrollment, already_billed_elsewhere)
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
