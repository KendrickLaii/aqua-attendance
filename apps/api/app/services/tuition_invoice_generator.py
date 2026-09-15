"""Generate monthly tuition invoices from course enrollments.

Billing is derived purely from CourseEnrollment + CourseSku, not attendance:

- monthly (月費): flat unit_price, quantity 1, billed every active month.
- price: enrollment.unit_price overrides the SKU price when set — lets
  price-less classes (e.g. 私補) be billed per student.
- per_session (堂費): each EnrollmentPurchase (initial purchase or top-up)
  is billed once, in the first month Generate runs for that covers or
  follows its ``purchased_at`` date. A purchase stays billable while its
  ``billed_invoice_line_id`` is NULL or points at a line on a void or
  rebuilt-draft invoice.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.course_enrollment import CourseEnrollment, EnrollmentPurchase
from app.models.course_sku import CourseSku
from app.models.tuition_invoice import TuitionInvoice, TuitionInvoiceLine, TuitionInvoiceStatus
from app.models.unit import Unit, UnitStatus

_LOCKED = frozenset({TuitionInvoiceStatus.issued.value, TuitionInvoiceStatus.paid.value})


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


@dataclass
class _BillingContext:
    first_day: date
    last_day: date
    unbilled_line_ids: set[UUID] = field(default_factory=set)


def _enrollment_price(enrollment: CourseEnrollment, sku: CourseSku) -> Decimal | None:
    override = getattr(enrollment, "unit_price", None)
    raw_price = override if override is not None else sku.price
    if raw_price is None:
        return None
    return _money(raw_price)


def _new_line(
    enrollment: CourseEnrollment,
    sku: CourseSku,
    unit_price: Decimal,
    quantity: Decimal,
) -> TuitionInvoiceLine:
    staff = getattr(sku, "staff", None)
    return TuitionInvoiceLine(
        enrollment_id=enrollment.id,
        sku_id=sku.id,
        sku_code=sku.code,
        name_zh=sku.name_zh,
        billing_unit=sku.billing_unit,
        unit_price=unit_price,
        quantity=quantity,
        amount=unit_price * quantity,
        staff_name=staff.full_name if staff else None,
    )


def _lines_from_enrollment(
    enrollment: CourseEnrollment,
    ctx: _BillingContext,
) -> tuple[list[TuitionInvoiceLine], list[tuple[TuitionInvoiceLine, EnrollmentPurchase]]]:
    sku = enrollment.sku
    if sku is None:
        return [], []
    lines: list[TuitionInvoiceLine] = []
    purchase_links: list[tuple[TuitionInvoiceLine, EnrollmentPurchase]] = []

    if sku.billing_unit == "per_session":
        # Each purchase bills itself; a purchase counts as unbilled while its
        # link is NULL or points at a line that is being rebuilt/voided this
        # run. Enrollments without purchases have nothing to bill.
        for p in getattr(enrollment, "purchases", []):
            if p.purchased_at > ctx.last_day:
                continue
            if p.billed_invoice_line_id is not None and p.billed_invoice_line_id not in ctx.unbilled_line_ids:
                continue
            quantity = _money(p.purchased_quantity)
            if quantity <= 0:
                continue
            unit_price = _money(p.unit_price)
            line = _new_line(enrollment, sku, unit_price, quantity)
            lines.append(line)
            purchase_links.append((line, p))
        return lines, purchase_links

    unit_price = _enrollment_price(enrollment, sku)
    if unit_price is None:
        return [], []
    lines.append(_new_line(enrollment, sku, unit_price, _money(1)))
    return lines, purchase_links


async def _unbilled_line_ids(
    db: AsyncSession,
    enrollment_ids: set[UUID],
    first_day: date,
    last_day: date,
) -> set[UUID]:
    """Line ids that must not block a purchase from being billed again:
    lines on voided invoices (any period), plus lines on this period's
    draft/void invoices, which get cleared and rebuilt below."""
    if not enrollment_ids:
        return set()
    result = await db.execute(
        select(TuitionInvoiceLine.id)
        .join(TuitionInvoice, TuitionInvoiceLine.invoice_id == TuitionInvoice.id)
        .where(
            TuitionInvoiceLine.enrollment_id.in_(enrollment_ids),
            or_(
                TuitionInvoice.status == TuitionInvoiceStatus.void.value,
                and_(
                    TuitionInvoice.period_start == first_day,
                    TuitionInvoice.period_end == last_day,
                    TuitionInvoice.status.in_(
                        [TuitionInvoiceStatus.draft.value, TuitionInvoiceStatus.void.value]
                    ),
                ),
            ),
        )
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
        .options(
            selectinload(CourseEnrollment.sku).selectinload(CourseSku.staff),
            selectinload(CourseEnrollment.unit),
            selectinload(CourseEnrollment.purchases),
        )
        .join(CourseSku, CourseEnrollment.sku_id == CourseSku.id)
        .join(Unit, CourseEnrollment.unit_id == Unit.id)
        .where(
            CourseEnrollment.status == "active",
            or_(CourseEnrollment.start_date.is_(None), CourseEnrollment.start_date <= last_day),
            or_(CourseEnrollment.end_date.is_(None), CourseEnrollment.end_date >= first_day),
            # per_session prices live on EnrollmentPurchase, not the SKU/enrollment.
            or_(
                CourseSku.billing_unit == "per_session",
                CourseSku.price.is_not(None),
                CourseEnrollment.unit_price.is_not(None),
            ),
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
    ctx = _BillingContext(
        first_day=first_day,
        last_day=last_day,
        unbilled_line_ids=await _unbilled_line_ids(db, per_session_ids, first_day, last_day),
    )

    by_unit: dict = defaultdict(list)
    unit_locations: dict = {}
    line_purchase_links: list[tuple[TuitionInvoiceLine, EnrollmentPurchase]] = []
    for enrollment in enrollments:
        lines, links = _lines_from_enrollment(enrollment, ctx)
        if not lines:
            continue
        by_unit[enrollment.unit_id].extend(lines)
        line_purchase_links.extend(links)
        unit_locations[enrollment.unit_id] = enrollment.unit.registered_location_id

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
                location_id=unit_locations.get(unit_id),
                period_start=first_day,
                period_end=last_day,
                status=TuitionInvoiceStatus.draft.value,
                total=total,
            )
            invoice.lines = lines
            db.add(invoice)
            created += 1
            continue

        was_void = invoice.status == TuitionInvoiceStatus.void.value
        invoice.lines.clear()
        invoice.total = total
        invoice.status = TuitionInvoiceStatus.draft.value
        if invoice.location_id is None:
            invoice.location_id = unit_locations.get(unit_id)
        if was_void:
            # A voided invoice has already been printed with its old number.
            # Re-issuing it must use a fresh number, not reuse the old one.
            invoice.invoice_no = None
            invoice.issued_at = None
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
        await db.flush()
        for line, purchase in line_purchase_links:
            purchase.billed_invoice_line_id = line.id
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise
    return {"created": created, "updated": updated, "skipped": skipped, "deleted": deleted}
