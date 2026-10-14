"""Generate monthly tuition invoices from course enrollments.

Billing is derived purely from CourseEnrollment + CourseSku, not attendance:

- monthly (月費): flat unit_price, quantity 1, billed every active month.
- price: enrollment.unit_price overrides the SKU price when set — lets
  price-less classes (e.g. 私補) be billed per student.
- per_session (堂費): each EnrollmentPurchase (initial purchase or top-up)
  is billed once, in the calendar month of its ``purchased_at`` date. Older
  unbilled purchases are reported as leftovers instead of being rolled into
  a later month. A purchase stays billable while its
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

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.course_enrollment import CourseEnrollment, EnrollmentPurchase
from app.models.course_sku import CourseSku
from app.models.tuition_invoice import TuitionInvoice, TuitionInvoiceLine, TuitionInvoiceStatus
from app.models.unit import Unit, UnitStatus
from app.services import audit_log as audit_log_svc

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
            if p.purchased_at < ctx.first_day or p.purchased_at > ctx.last_day:
                continue
            if p.billed_invoice_line_id is not None and p.billed_invoice_line_id not in ctx.unbilled_line_ids:
                continue
            quantity = _money(p.purchased_quantity)
            if quantity <= 0:
                continue
            # NULL purchase price = "price set at invoice time" (私補).
            # Fall back to the enrollment/SKU price if one exists; otherwise
            # leave the purchase unbilled for the manual invoice flow.
            raw_price = p.unit_price
            if raw_price is None:
                fallback = _enrollment_price(enrollment, sku)
                if fallback is None:
                    continue
                unit_price = fallback
            else:
                unit_price = _money(raw_price)
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
    """Line ids that must not block a purchase from being billed again.

    Only this period's draft/void invoices matter: their lines are cleared and
    rebuilt below, so a purchase linked to one of them is really unbilled.
    Voiding an invoice already clears its purchase links (see the invoice PATCH
    route), so voids from other periods need no special case here.
    """
    if not enrollment_ids:
        return set()
    result = await db.execute(
        select(TuitionInvoiceLine.id)
        .join(TuitionInvoice, TuitionInvoiceLine.invoice_id == TuitionInvoice.id)
        .where(
            TuitionInvoiceLine.enrollment_id.in_(enrollment_ids),
            TuitionInvoice.period_start == first_day,
            TuitionInvoice.period_end == last_day,
            TuitionInvoice.status.in_([TuitionInvoiceStatus.draft.value, TuitionInvoiceStatus.void.value]),
        )
    )
    return {row[0] for row in result.all()}


def _credit_reason(
    enrollment: CourseEnrollment | None,
    first_day: date,
    last_day: date,
) -> str:
    """Why an enrollment billed on a locked invoice is no longer billable."""
    if enrollment is None or enrollment.status not in ("active", "completed"):
        return "enrollment_cancelled"
    if (enrollment.end_date is not None and enrollment.end_date < first_day) or (
        enrollment.start_date is not None and enrollment.start_date > last_day
    ):
        return "enrollment_ended"
    sku = enrollment.sku
    if sku is None or not sku.is_active:
        return "sku_inactive"
    unit = enrollment.unit
    if unit is None or not unit.is_active or unit.status != UnitStatus.active.value:
        return "unit_inactive"
    return "not_billable"


async def generate_monthly_tuition_invoices(
    db: AsyncSession,
    *,
    year: int,
    month: int,
    location_id: UUID | None = None,
    user_id: UUID | None = None,
) -> dict[str, object]:
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    enrollment_clauses = [
        CourseEnrollment.status.in_(["active", "completed"]),
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
    ]
    if location_id is not None:
        enrollment_clauses.append(Unit.registered_location_id == location_id)

    result = await db.execute(
        select(CourseEnrollment)
        .options(
            selectinload(CourseEnrollment.sku).selectinload(CourseSku.staff),
            selectinload(CourseEnrollment.unit),
            selectinload(CourseEnrollment.purchases),
        )
        .join(CourseSku, CourseEnrollment.sku_id == CourseSku.id)
        .join(Unit, CourseEnrollment.unit_id == Unit.id)
        .where(*enrollment_clauses)
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
    by_unit_links: dict = defaultdict(list)
    billable_enrollment_ids: dict = defaultdict(set)
    unit_locations: dict = {}
    unit_infos: dict = {}
    line_purchase_links: list[tuple[TuitionInvoiceLine, EnrollmentPurchase]] = []
    for enrollment in enrollments:
        unit_infos[enrollment.unit_id] = enrollment.unit
        unit_locations[enrollment.unit_id] = enrollment.unit.registered_location_id
        billable_enrollment_ids[enrollment.unit_id].add(enrollment.id)
        lines, links = _lines_from_enrollment(enrollment, ctx)
        if not lines:
            continue
        by_unit[enrollment.unit_id].extend(lines)
        by_unit_links[enrollment.unit_id].extend(links)

    leftover_clauses = [
        CourseSku.billing_unit == "per_session",
        EnrollmentPurchase.purchased_at < first_day,
        EnrollmentPurchase.billed_invoice_line_id.is_(None),
    ]
    if location_id is not None:
        leftover_clauses.append(Unit.registered_location_id == location_id)
    leftover_result = await db.execute(
        select(EnrollmentPurchase, Unit, CourseSku)
        .join(CourseEnrollment, EnrollmentPurchase.enrollment_id == CourseEnrollment.id)
        .join(Unit, CourseEnrollment.unit_id == Unit.id)
        .join(CourseSku, CourseEnrollment.sku_id == CourseSku.id)
        .where(*leftover_clauses)
        .order_by(EnrollmentPurchase.purchased_at)
    )
    leftover_purchases = [
        {
            "unit_code": unit.code,
            "unit_name": unit.full_name,
            "sku_code": sku.code,
            "purchased_at": purchase.purchased_at,
            "purchased_quantity": purchase.purchased_quantity,
        }
        for purchase, unit, sku in leftover_result.all()
    ]

    existing_clauses = [
        TuitionInvoice.period_start == first_day,
        TuitionInvoice.period_end == last_day,
        TuitionInvoice.kind == "tuition",
    ]
    if location_id is not None:
        existing_clauses.append(TuitionInvoice.location_id == location_id)

    existing_result = await db.execute(
        select(TuitionInvoice)
        .options(selectinload(TuitionInvoice.lines))
        .where(*existing_clauses)
    )
    existing_by_unit: dict = defaultdict(list)
    for invoice in existing_result.scalars().all():
        existing_by_unit[invoice.unit_id].append(invoice)

    # Units referenced by locked invoices but missing from unit_infos (no
    # billable enrollment this run) still need code/name for the credit-note
    # report.
    locked_unit_ids = {
        unit_id
        for unit_id, invoices in existing_by_unit.items()
        if unit_id is not None and any(i.status in _LOCKED for i in invoices)
    }
    missing_unit_ids = locked_unit_ids - set(unit_infos)
    if missing_unit_ids:
        unit_result = await db.execute(select(Unit).where(Unit.id.in_(missing_unit_ids)))
        for unit in unit_result.scalars().all():
            unit_infos[unit.id] = unit

    # Negative-delta report: locked lines whose enrollment is no longer
    # billable this run (cancelled, ended, SKU/unit inactive). Reported only
    # — never auto-credited.
    locked_line_enrollment_ids: set[UUID] = set()
    for unit_id, invoices in existing_by_unit.items():
        billable = billable_enrollment_ids.get(unit_id, set())
        for invoice in invoices:
            if invoice.status not in _LOCKED:
                continue
            for line in invoice.lines:
                if (
                    line.billing_unit != "per_session"
                    and line.enrollment_id is not None
                    and line.enrollment_id not in billable
                ):
                    locked_line_enrollment_ids.add(line.enrollment_id)
    locked_enrollments: dict[UUID, CourseEnrollment] = {}
    if locked_line_enrollment_ids:
        enr_result = await db.execute(
            select(CourseEnrollment)
            .options(
                selectinload(CourseEnrollment.sku),
                selectinload(CourseEnrollment.unit),
            )
            .where(CourseEnrollment.id.in_(locked_line_enrollment_ids))
        )
        locked_enrollments = {e.id: e for e in enr_result.scalars().all()}

    needs_credit_note: list[dict[str, object]] = []
    for unit_id, invoices in existing_by_unit.items():
        billable = billable_enrollment_ids.get(unit_id, set())
        unit = unit_infos.get(unit_id)
        for invoice in invoices:
            if invoice.status not in _LOCKED:
                continue
            for line in invoice.lines:
                if (
                    line.billing_unit == "per_session"
                    or line.enrollment_id is None
                    or line.enrollment_id in billable
                ):
                    continue
                needs_credit_note.append(
                    {
                        "unit_id": unit_id,
                        "unit_code": unit.code if unit else None,
                        "unit_name": unit.full_name if unit else None,
                        "invoice_no": invoice.invoice_no,
                        "invoice_status": invoice.status,
                        "sku_code": line.sku_code,
                        "name_zh": line.name_zh,
                        "amount": line.amount,
                        "reason": _credit_reason(
                            locked_enrollments.get(line.enrollment_id), first_day, last_day
                        ),
                    }
                )

    created = 0
    updated = 0
    skipped = 0
    deleted = 0
    deleted_invoices: list[tuple[UUID, str | None]] = []
    supplements: list[dict[str, object]] = []

    for unit_id in set(by_unit) | set(existing_by_unit):
        invoices = existing_by_unit.get(unit_id, [])
        locked = [i for i in invoices if i.status in _LOCKED]
        draft = next((i for i in invoices if i.status == TuitionInvoiceStatus.draft.value), None)
        voids = [i for i in invoices if i.status == TuitionInvoiceStatus.void.value]

        # Enrollments already billed on a locked invoice are covered; only
        # the uncovered delta may be written. Per-session lines are already
        # filtered by their purchase link, so they always pass through.
        covered_enrollment_ids = {
            line.enrollment_id
            for invoice in locked
            for line in invoice.lines
            if line.enrollment_id is not None and line.billing_unit != "per_session"
        }
        delta_lines = [
            line
            for line in by_unit.get(unit_id, [])
            if line.enrollment_id not in covered_enrollment_ids
        ]
        delta_ids = {id(line) for line in delta_lines}
        delta_links = [
            (line, purchase)
            for line, purchase in by_unit_links.get(unit_id, [])
            if id(line) in delta_ids
        ]
        line_purchase_links.extend(delta_links)

        if not delta_lines:
            if draft is not None:
                deleted_invoices.append((draft.id, draft.invoice_no))
                await db.delete(draft)
                deleted += 1
            if locked:
                # Everything for this student+month is on locked invoices.
                skipped += 1
            continue

        total = sum((line.amount for line in delta_lines), Decimal("0.00"))
        invoice = draft
        if invoice is None and voids:
            # Revive the most recently cancelled invoice rather than
            # creating a new row.
            invoice = max(voids, key=lambda i: i.created_at)

        is_new = invoice is None
        if is_new:
            invoice = TuitionInvoice(
                unit_id=unit_id,
                location_id=unit_locations.get(unit_id),
                period_start=first_day,
                period_end=last_day,
                status=TuitionInvoiceStatus.draft.value,
                total=total,
            )
            invoice.lines = delta_lines
            db.add(invoice)
            created += 1
        else:
            was_void = invoice.status == TuitionInvoiceStatus.void.value
            invoice.lines.clear()
            invoice.total = total
            invoice.status = TuitionInvoiceStatus.draft.value
            if invoice.location_id is None:
                invoice.location_id = unit_locations.get(unit_id)
            if was_void:
                # A voided invoice has already been printed with its old
                # number. Re-issuing it must use a fresh number, not reuse
                # the old one.
                invoice.invoice_no = None
                invoice.issued_at = None
            for line in delta_lines:
                invoice.lines.append(line)
            updated += 1

        if locked:
            unit = unit_infos.get(unit_id)
            supplements.append(
                {
                    "unit_id": unit_id,
                    "unit_code": unit.code if unit else None,
                    "unit_name": unit.full_name if unit else None,
                    "prior_invoice_nos": [i.invoice_no for i in locked if i.invoice_no],
                    "lines": [
                        {
                            "sku_code": line.sku_code,
                            "name_zh": line.name_zh,
                            "billing_unit": line.billing_unit,
                            "quantity": line.quantity,
                            "unit_price": line.unit_price,
                            "amount": line.amount,
                        }
                        for line in delta_lines
                    ],
                    "total": total,
                    "is_new": is_new,
                }
            )

    try:
        await db.flush()
        for line, purchase in line_purchase_links:
            purchase.billed_invoice_line_id = line.id
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise

    if deleted_invoices and user_id is not None:
        await audit_log_svc.log_audit_many(
            db,
            [
                {
                    "user_id": user_id,
                    "action": "DELETE",
                    "table_name": "tuition_invoices",
                    "record_id": invoice_id,
                    "description": f"Generator deleted stale tuition invoice {invoice_no or invoice_id} for {year}-{month:02d}",
                }
                for invoice_id, invoice_no in deleted_invoices
            ],
        )
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "deleted": deleted,
        "leftover_unbilled": len(leftover_purchases),
        "leftover_purchases": leftover_purchases,
        "supplements": supplements,
        "needs_credit_note": needs_credit_note,
    }
