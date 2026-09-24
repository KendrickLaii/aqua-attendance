import calendar
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.deps import AdminOnly, DB
from app.models.course_enrollment import CourseEnrollment, EnrollmentPurchase
from app.models.course_sku import CourseSku
from app.models.credit_note_counter import CreditNoteCounter
from app.models.invoice_counter import InvoiceCounter
from app.models.location import Location
from app.models.tuition_invoice import TuitionInvoice, TuitionInvoiceLine, TuitionInvoiceStatus
from app.models.tuition_receipt import TuitionReceipt, TuitionReceiptInvoice, TuitionReceiptStatus
from app.models.unit import Unit
from app.schemas.tuition_invoice import (
    TuitionInvoiceGenerateResult,
    TuitionInvoiceManualCreate,
    TuitionInvoiceManualLine,
    TuitionInvoiceNextNo,
    TuitionInvoiceOut,
    TuitionInvoiceUpdate,
)
from app.services import audit_log as audit_log_svc
from app.services.tuition_invoice_generator import generate_monthly_tuition_invoices

router = APIRouter(prefix="/tuition-invoices", tags=["tuition-invoices"])

_ALLOWED_STATUS = {
    TuitionInvoiceStatus.draft.value: {TuitionInvoiceStatus.issued.value, TuitionInvoiceStatus.void.value},
    TuitionInvoiceStatus.issued.value: {TuitionInvoiceStatus.void.value},
    TuitionInvoiceStatus.paid.value: set(),
    TuitionInvoiceStatus.void.value: set(),
}
_EDITABLE_STATUS = frozenset({TuitionInvoiceStatus.draft.value, TuitionInvoiceStatus.issued.value})


def _invoice_to_out(
    invoice: TuitionInvoice,
    receipt_no: str | None = None,
    purchase_ids: dict[uuid.UUID, uuid.UUID] | None = None,
) -> TuitionInvoiceOut:
    out = TuitionInvoiceOut.model_validate(invoice)
    out.receipt_no = receipt_no
    if invoice.unit:
        out.unit_name = invoice.unit.full_name
        out.unit_code = invoice.unit.code
    elif invoice.kind == "manual":
        out.unit_name = invoice.manual_student_name
    linked = purchase_ids or {}
    for line_out, line in zip(out.lines, invoice.lines):
        line_out.purchase_id = linked.get(line.id)
        if line_out.staff_name:
            continue
        staff = line.sku.staff if line.sku else None
        line_out.staff_name = staff.full_name if staff else None
    return out


async def _receipt_no_map(db: AsyncSession, invoice_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not invoice_ids:
        return {}
    result = await db.execute(
        select(TuitionReceiptInvoice.invoice_id, TuitionReceipt.receipt_no)
        .join(TuitionReceipt, TuitionReceiptInvoice.receipt_id == TuitionReceipt.id)
        .where(
            TuitionReceiptInvoice.invoice_id.in_(invoice_ids),
            TuitionReceiptInvoice.is_posted.is_(True),
            TuitionReceipt.status == TuitionReceiptStatus.posted.value,
        )
    )
    return {row[0]: row[1] for row in result.all()}


async def _line_purchase_ids(
    db: AsyncSession, invoices: list[TuitionInvoice]
) -> dict[uuid.UUID, uuid.UUID]:
    line_ids = [line.id for invoice in invoices for line in invoice.lines]
    if not line_ids:
        return {}
    result = await db.execute(
        select(EnrollmentPurchase.billed_invoice_line_id, EnrollmentPurchase.id).where(
            EnrollmentPurchase.billed_invoice_line_id.in_(line_ids)
        )
    )
    return {row[0]: row[1] for row in result.all() if row[0] is not None}


async def _invoices_to_out(db: AsyncSession, invoices: list[TuitionInvoice]) -> list[TuitionInvoiceOut]:
    nos = await _receipt_no_map(db, [invoice.id for invoice in invoices])
    purchase_ids = await _line_purchase_ids(db, invoices)
    return [_invoice_to_out(invoice, nos.get(invoice.id), purchase_ids) for invoice in invoices]


_INVOICE_LOAD = (
    selectinload(TuitionInvoice.unit),
    selectinload(TuitionInvoice.lines)
    .selectinload(TuitionInvoiceLine.sku)
    .selectinload(CourseSku.staff),
)


@router.get("", response_model=list[TuitionInvoiceOut])
async def list_tuition_invoices(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    year: int | None = None,
    month: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    location_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[TuitionInvoiceOut]:
    clauses = []
    if year is not None and month is not None:
        if not (1 <= month <= 12):
            raise HTTPException(status_code=422, detail="month must be 1-12")
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        # Includes tuition invoices for the full month and manual invoices
        # for any day in the month (manual period_start == period_end == date).
        clauses.append(TuitionInvoice.period_start >= first_day)
        clauses.append(TuitionInvoice.period_end <= last_day)
    if status_filter is not None:
        clauses.append(TuitionInvoice.status == status_filter)

    count_q = select(func.count()).select_from(TuitionInvoice)
    q = select(TuitionInvoice).options(*_INVOICE_LOAD)
    if location_id is not None:
        clauses.append(TuitionInvoice.location_id == location_id)
    if clauses:
        count_q = count_q.where(*clauses)
        q = q.where(*clauses)

    total = await db.scalar(count_q) or 0
    q = q.order_by(TuitionInvoice.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return await _invoices_to_out(db, list(result.scalars().all()))


@router.post("/generate", response_model=TuitionInvoiceGenerateResult)
async def generate_tuition_invoices(
    admin: AdminOnly,
    db: DB,
    year: int,
    month: int,
    location_id: uuid.UUID | None = None,
) -> TuitionInvoiceGenerateResult:
    if not (1 <= month <= 12):
        raise HTTPException(status_code=422, detail="month must be 1-12")

    try:
        result = await generate_monthly_tuition_invoices(
            db, year=year, month=month, location_id=location_id
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invoice already exists for this student and period",
        )
    leftover = int(result.get("leftover_unbilled") or 0)
    await audit_log_svc.log_audit(
        db,
        user_id=admin.id,
        action="DATA_EXPORT",
        table_name="tuition_invoices",
        description=(
            f"Generated tuition invoices for {year}-{month:02d}"
            f"{f' location {location_id}' if location_id else ''}: "
            f"{result['created']} created, {result['updated']} updated, "
            f"{result['skipped']} skipped, {result['deleted']} deleted"
            + (f", {leftover} leftover unbilled" if leftover else "")
        ),
    )
    return TuitionInvoiceGenerateResult(**result)


_INVOICE_NO_MAX = 999999
_COUNTER_ID = 1


async def _max_numeric_invoice_no(db: AsyncSession, location_id: uuid.UUID | None) -> int:
    result = await db.execute(
        select(TuitionInvoice.invoice_no).where(
            TuitionInvoice.invoice_no.is_not(None),
            TuitionInvoice.location_id == location_id,
        )
    )
    max_no = 0
    for value in result.scalars().all():
        try:
            max_no = max(max_no, int(value))
        except (TypeError, ValueError):
            continue
    return max_no


async def _peek_next_invoice_no(db: AsyncSession, location_id: uuid.UUID | None = None) -> int:
    counter = await db.execute(
        select(InvoiceCounter).where(InvoiceCounter.location_id == location_id)
    )
    row = counter.scalar_one_or_none()
    if row is not None:
        return row.next_no
    return await _max_numeric_invoice_no(db, location_id) + 1


def _parse_numeric_invoice_no(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return None


async def _counter_session(db: AsyncSession):
    """Return a new, independent AsyncSession on the same database engine.

    The invoice counter must be committed independently of the caller's
    transaction so that a uniqueness conflict on an invoice number does not
    roll the counter back and cause number reuse / 409 loops.
    """
    factory = async_sessionmaker(db.bind, class_=AsyncSession, expire_on_commit=False)
    return factory()


async def _bump_invoice_counter(db: AsyncSession, n: int, location_id: uuid.UUID | None = None) -> None:
    """Advance the per-location counter to at least n + 1 in a committed, separate session."""
    if n < 1:
        return
    if n > _INVOICE_NO_MAX:
        raise HTTPException(status_code=422, detail="Invoice number exceeds maximum 999999.")
    session = await _counter_session(db)
    async with session, session.begin():
        counter = await session.execute(
            select(InvoiceCounter).where(InvoiceCounter.location_id == location_id).with_for_update()
        )
        counter = counter.scalar_one_or_none()
        target = n + 1
        if counter is None:
            seed = await _max_numeric_invoice_no(session, location_id)
            target = max(target, seed + 1)
            try:
                async with session.begin_nested():
                    session.add(InvoiceCounter(location_id=location_id, next_no=target))
                    await session.flush()
            except IntegrityError:
                # Another request created the counter row first — update it.
                await session.execute(
                    update(InvoiceCounter)
                    .where(
                        InvoiceCounter.location_id == location_id,
                        InvoiceCounter.next_no < target,
                    )
                    .values(next_no=target)
                )
        elif counter.next_no < target:
            counter.next_no = target


async def _allocate_invoice_no(db: AsyncSession, location_id: uuid.UUID | None = None) -> int:
    """Atomically take the next sequential invoice number for a given location.

    The counter is updated and committed in a separate session so that a
    later failure of the caller's invoice transaction does not roll the
    counter back. If a manual number has already been used, the counter is
    advanced until a free number is returned.
    """
    session = await _counter_session(db)
    async with session, session.begin():
        for _ in range(1000):
            result = await session.execute(
                update(InvoiceCounter)
                .where(InvoiceCounter.location_id == location_id)
                .values(next_no=InvoiceCounter.next_no + 1)
                .returning(InvoiceCounter.next_no)
            )
            next_after = result.scalar_one_or_none()
            if next_after is None:
                allocated = await _max_numeric_invoice_no(session, location_id) + 1
                if allocated > _INVOICE_NO_MAX:
                    raise HTTPException(status_code=422, detail="Invoice numbers exhausted (max 999999).")
                try:
                    async with session.begin_nested():
                        session.add(InvoiceCounter(location_id=location_id, next_no=allocated + 1))
                        await session.flush()
                except IntegrityError:
                    # Another request created the counter row first — fall
                    # through to the normal UPDATE path once.
                    continue
                return allocated

            allocated = next_after - 1
            if allocated > _INVOICE_NO_MAX:
                raise HTTPException(status_code=422, detail="Invoice numbers exhausted (max 999999).")

            # A manually entered number may have been used without updating
            # the counter. Skip any already-allocated numbers in this location.
            exists = await session.scalar(
                select(TuitionInvoice.id).where(
                    TuitionInvoice.location_id == location_id,
                    TuitionInvoice.invoice_no == str(allocated),
                )
            )
            if not exists:
                return allocated
            # already in use — the next loop will bump the counter again

    raise HTTPException(status_code=422, detail="Could not allocate a free invoice number.")


_CREDIT_PREFIX = "RF"
_CREDIT_NO_WIDTH = 4
_CREDIT_NO_MAX = 9999


def _format_credit_no(n: int) -> str:
    return f"{_CREDIT_PREFIX}{n:0{_CREDIT_NO_WIDTH}d}"


def _parse_credit_no(value: str | None) -> int | None:
    if not value:
        return None
    text = value.strip().upper()
    if text.startswith(_CREDIT_PREFIX):
        text = text[len(_CREDIT_PREFIX) :]
    if not text.isdigit():
        return None
    return int(text)


async def _max_credit_no(db: AsyncSession, location_id: uuid.UUID | None) -> int:
    result = await db.execute(
        select(TuitionInvoice.invoice_no).where(
            TuitionInvoice.invoice_no.is_not(None),
            TuitionInvoice.location_id == location_id,
        )
    )
    max_no = 0
    for value in result.scalars().all():
        parsed = _parse_credit_no(value)
        if parsed is not None and str(value).upper().startswith(_CREDIT_PREFIX):
            max_no = max(max_no, parsed)
    return max_no


async def _peek_next_credit_no(db: AsyncSession, location_id: uuid.UUID | None = None) -> int:
    counter = await db.execute(
        select(CreditNoteCounter).where(CreditNoteCounter.location_id == location_id)
    )
    row = counter.scalar_one_or_none()
    if row is not None:
        return row.next_no
    return await _max_credit_no(db, location_id) + 1


async def _bump_credit_counter(db: AsyncSession, n: int, location_id: uuid.UUID | None = None) -> None:
    if n < 1:
        return
    if n > _CREDIT_NO_MAX:
        raise HTTPException(status_code=422, detail="Credit note number exceeds maximum RF9999.")
    session = await _counter_session(db)
    async with session, session.begin():
        counter = await session.execute(
            select(CreditNoteCounter).where(CreditNoteCounter.location_id == location_id).with_for_update()
        )
        counter = counter.scalar_one_or_none()
        target = n + 1
        if counter is None:
            seed = await _max_credit_no(session, location_id)
            target = max(target, seed + 1)
            try:
                async with session.begin_nested():
                    session.add(CreditNoteCounter(location_id=location_id, next_no=target))
                    await session.flush()
            except IntegrityError:
                await session.execute(
                    update(CreditNoteCounter)
                    .where(
                        CreditNoteCounter.location_id == location_id,
                        CreditNoteCounter.next_no < target,
                    )
                    .values(next_no=target)
                )
        elif counter.next_no < target:
            counter.next_no = target


async def _allocate_credit_no(db: AsyncSession, location_id: uuid.UUID | None = None) -> str:
    session = await _counter_session(db)
    async with session, session.begin():
        for _ in range(1000):
            result = await session.execute(
                update(CreditNoteCounter)
                .where(CreditNoteCounter.location_id == location_id)
                .values(next_no=CreditNoteCounter.next_no + 1)
                .returning(CreditNoteCounter.next_no)
            )
            next_after = result.scalar_one_or_none()
            if next_after is None:
                allocated = await _max_credit_no(session, location_id) + 1
                if allocated > _CREDIT_NO_MAX:
                    raise HTTPException(status_code=422, detail="Credit note numbers exhausted (max RF9999).")
                try:
                    async with session.begin_nested():
                        session.add(CreditNoteCounter(location_id=location_id, next_no=allocated + 1))
                        await session.flush()
                except IntegrityError:
                    continue
                formatted = _format_credit_no(allocated)
                exists = await session.scalar(
                    select(TuitionInvoice.id).where(
                        TuitionInvoice.location_id == location_id,
                        TuitionInvoice.invoice_no == formatted,
                    )
                )
                if not exists:
                    return formatted
                continue

            allocated = next_after - 1
            if allocated > _CREDIT_NO_MAX:
                raise HTTPException(status_code=422, detail="Credit note numbers exhausted (max RF9999).")
            formatted = _format_credit_no(allocated)
            exists = await session.scalar(
                select(TuitionInvoice.id).where(
                    TuitionInvoice.location_id == location_id,
                    TuitionInvoice.invoice_no == formatted,
                )
            )
            if not exists:
                return formatted

    raise HTTPException(status_code=422, detail="Could not allocate a free credit note number.")


def _normalize_credit_no(value: str) -> str:
    parsed = _parse_credit_no(value)
    if parsed is None:
        return value.strip()
    return _format_credit_no(parsed)


@router.get("/next-no", response_model=TuitionInvoiceNextNo)
async def next_invoice_no(
    _admin: AdminOnly,
    db: DB,
    location_id: uuid.UUID | None = Query(default=None),
    series: str = Query(default="invoice"),
) -> TuitionInvoiceNextNo:
    if series == "credit":
        next_no = await _peek_next_credit_no(db, location_id)
        return TuitionInvoiceNextNo(next_no=next_no, invoice_no=_format_credit_no(next_no))
    next_no = await _peek_next_invoice_no(db, location_id)
    return TuitionInvoiceNextNo(next_no=next_no, invoice_no=str(next_no))


@router.post("/allocate-no", response_model=TuitionInvoiceNextNo)
async def allocate_invoice_no(
    _admin: AdminOnly,
    db: DB,
    location_id: uuid.UUID | None = Query(default=None),
) -> TuitionInvoiceNextNo:
    """Consume the next invoice number for a given location."""
    allocated = await _allocate_invoice_no(db, location_id)
    await db.commit()
    return TuitionInvoiceNextNo(next_no=allocated)


async def _build_manual_lines(
    db: AsyncSession,
    lines_in: list[TuitionInvoiceManualLine],
    unit_id: uuid.UUID | None,
    *,
    ignore_line_ids: set[uuid.UUID] | None = None,
    existing_lines: list[TuitionInvoiceLine] | None = None,
) -> tuple[list[TuitionInvoiceLine], list[tuple[TuitionInvoiceLine, EnrollmentPurchase]]]:
    purchase_ids = [line.purchase_id for line in lines_in if line.purchase_id]
    if len(purchase_ids) != len(set(purchase_ids)):
        raise HTTPException(
            status_code=422,
            detail="The same session package cannot be billed twice on one invoice.",
        )
    purchases: dict[uuid.UUID, EnrollmentPurchase] = {}
    if purchase_ids:
        result = await db.execute(
            select(EnrollmentPurchase)
            .options(
                selectinload(EnrollmentPurchase.enrollment)
                .selectinload(CourseEnrollment.sku)
                .selectinload(CourseSku.staff)
            )
            .where(EnrollmentPurchase.id.in_(purchase_ids))
        )
        purchases = {p.id: p for p in result.scalars().all()}
        if len(purchases) != len(set(purchase_ids)):
            raise HTTPException(status_code=422, detail="Unknown purchase id")
        linked_line_ids = [
            p.billed_invoice_line_id for p in purchases.values() if p.billed_invoice_line_id is not None
        ]
        blocking_line_ids: set[uuid.UUID] = set()
        if linked_line_ids:
            blocking = await db.execute(
                select(TuitionInvoiceLine.id)
                .join(TuitionInvoice, TuitionInvoiceLine.invoice_id == TuitionInvoice.id)
                .where(
                    TuitionInvoiceLine.id.in_(linked_line_ids),
                    TuitionInvoice.status != TuitionInvoiceStatus.void.value,
                )
            )
            blocking_line_ids = {row[0] for row in blocking.all()}
            if ignore_line_ids:
                blocking_line_ids -= ignore_line_ids
        for purchase in purchases.values():
            if purchase.billed_invoice_line_id in blocking_line_ids:
                raise HTTPException(
                    status_code=409,
                    detail="This session package has already been billed on another invoice.",
                )
            if unit_id is None or purchase.enrollment.unit_id != unit_id:
                raise HTTPException(
                    status_code=422,
                    detail="This session package belongs to a different student.",
                )

    existing_by_id = {line.id: line for line in existing_lines or []}
    unused_existing = set(existing_by_id)

    def take_existing(line_in: TuitionInvoiceManualLine) -> TuitionInvoiceLine | None:
        if line_in.id is not None:
            if not existing_by_id:
                return None
            existing = existing_by_id.get(line_in.id)
            if existing is None or existing.id not in unused_existing:
                raise HTTPException(
                    status_code=422,
                    detail="Line id does not belong to this invoice",
                )
            unused_existing.discard(existing.id)
            return existing
        matches = [
            existing_by_id[line_id]
            for line_id in unused_existing
            if existing_by_id[line_id].enrollment_id is not None
            and existing_by_id[line_id].name_zh == line_in.course
            and (
                not existing_by_id[line_id].month_label
                or existing_by_id[line_id].month_label == (line_in.month or "")
            )
        ]
        if not matches:
            leftover = [
                existing_by_id[line_id]
                for line_id in unused_existing
                if existing_by_id[line_id].enrollment_id is not None
            ]
            if len(leftover) == 1:
                matches = leftover
        if len(matches) == 1:
            unused_existing.discard(matches[0].id)
            return matches[0]
        return None

    lines: list[TuitionInvoiceLine] = []
    purchase_links: list[tuple[TuitionInvoiceLine, EnrollmentPurchase]] = []
    for line_in in lines_in:
        purchase = purchases.get(line_in.purchase_id) if line_in.purchase_id else None
        if purchase is None:
            existing = take_existing(line_in)
            if existing is not None:
                lines.append(
                    TuitionInvoiceLine(
                        enrollment_id=existing.enrollment_id,
                        sku_id=existing.sku_id,
                        sku_code=existing.sku_code,
                        name_zh=line_in.course,
                        billing_unit=existing.billing_unit,
                        unit_price=line_in.fee,
                        quantity=line_in.qty,
                        amount=line_in.fee * line_in.qty,
                        month_label=line_in.month,
                        staff_name=(
                            line_in.staff_name.strip()
                            if line_in.staff_name
                            else existing.staff_name
                        ),
                    )
                )
                continue
            lines.append(
                TuitionInvoiceLine(
                    name_zh=line_in.course,
                    sku_code="manual",
                    billing_unit="manual",
                    unit_price=line_in.fee,
                    quantity=line_in.qty,
                    amount=line_in.fee * line_in.qty,
                    month_label=line_in.month,
                    staff_name=line_in.staff_name.strip() if line_in.staff_name else None,
                )
            )
            continue
        sku: CourseSku | None = purchase.enrollment.sku
        quantity = float(purchase.purchased_quantity)
        line = TuitionInvoiceLine(
            enrollment_id=purchase.enrollment_id,
            sku_id=sku.id if sku else None,
            sku_code=sku.code if sku else "manual",
            name_zh=line_in.course,
            billing_unit="per_session",
            unit_price=line_in.fee,
            quantity=quantity,
            amount=line_in.fee * quantity,
            month_label=line_in.month or purchase.purchased_at.strftime("%Y-%m"),
            staff_name=(
                (line_in.staff_name.strip() if line_in.staff_name else None)
                or (sku.staff.full_name if sku and sku.staff else None)
            ),
        )
        lines.append(line)
        purchase_links.append((line, purchase))
    return lines, purchase_links


@router.post("/manual", response_model=TuitionInvoiceOut, status_code=status.HTTP_201_CREATED)
async def create_manual_tuition_invoice(
    body: TuitionInvoiceManualCreate,
    _admin: AdminOnly,
    db: DB,
) -> TuitionInvoiceOut:
    """Create and issue a manual (ad-hoc) invoice, storing it for reprint/payment tracking."""
    location = await db.get(Location, body.location_id)
    if not location:
        raise HTTPException(status_code=422, detail="location_id does not reference an existing location")

    if body.unit_id is not None:
        unit = await db.get(Unit, body.unit_id)
        if not unit:
            raise HTTPException(status_code=422, detail="unit_id does not reference an existing unit")

    # Validate purchase-linked lines before allocating an invoice number —
    # a failed create must not consume a number.
    lines, purchase_links = await _build_manual_lines(db, body.lines, body.unit_id)

    total = sum(line.amount for line in lines)
    invoice_no = body.invoice_no.strip() if body.invoice_no and body.invoice_no.strip() else None
    is_credit = total < 0
    if invoice_no:
        if is_credit:
            invoice_no = _normalize_credit_no(invoice_no)
            credit_no = _parse_credit_no(invoice_no)
            if credit_no is not None:
                await _bump_credit_counter(db, credit_no, body.location_id)
        else:
            manual_no = _parse_numeric_invoice_no(invoice_no)
            if manual_no is not None:
                await _bump_invoice_counter(db, manual_no, body.location_id)
    elif is_credit:
        invoice_no = await _allocate_credit_no(db, body.location_id)
    else:
        invoice_no = str(await _allocate_invoice_no(db, body.location_id))

    invoice = TuitionInvoice(
        unit_id=body.unit_id,
        location_id=body.location_id,
        manual_student_name=body.manual_student_name.strip() if body.manual_student_name else None,
        staff_name=body.staff_name.strip() if body.staff_name else None,
        payable_to_name=body.payable_to_name.strip() if body.payable_to_name else None,
        payee_name=body.payee_name.strip() if body.payee_name else None,
        period_start=body.date,
        period_end=body.date,
        status=TuitionInvoiceStatus.issued.value,
        kind="manual",
        total=total,
        notes=body.notes,
        invoice_no=invoice_no,
        issued_at=datetime.now(timezone.utc),
    )
    invoice.lines = lines
    db.add(invoice)
    try:
        await db.flush()
        for line, purchase in purchase_links:
            purchase.billed_invoice_line_id = line.id
            if purchase.unit_price is None:
                purchase.unit_price = line.unit_price
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Invoice no. already in use — pick another.")
    await db.refresh(invoice)
    result = await db.execute(
        select(TuitionInvoice).options(*_INVOICE_LOAD).where(TuitionInvoice.id == invoice.id)
    )
    return (await _invoices_to_out(db, [result.scalar_one()]))[0]


@router.get("/{invoice_id}", response_model=TuitionInvoiceOut)
async def get_tuition_invoice(invoice_id: uuid.UUID, _admin: AdminOnly, db: DB) -> TuitionInvoiceOut:
    result = await db.execute(
        select(TuitionInvoice).options(*_INVOICE_LOAD).where(TuitionInvoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return (await _invoices_to_out(db, [invoice]))[0]


@router.patch("/{invoice_id}", response_model=TuitionInvoiceOut)
async def update_tuition_invoice(
    invoice_id: uuid.UUID, body: TuitionInvoiceUpdate, _admin: AdminOnly, db: DB
) -> TuitionInvoiceOut:
    result = await db.execute(
        select(TuitionInvoice)
        .options(*_INVOICE_LOAD)
        .where(TuitionInvoice.id == invoice_id)
        .with_for_update()
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    update_data = body.model_dump(exclude_unset=True)
    line_payload = update_data.pop("lines", None)
    if invoice.status not in _EDITABLE_STATUS:
        extra_fields = set(update_data) - {"status", "payable_to_name", "payee_name"}
        if extra_fields or line_payload is not None:
            raise HTTPException(
                status_code=422,
                detail="Cannot edit a paid or cancelled invoice",
            )
    if line_payload is not None:
        if not body.lines:
            raise HTTPException(status_code=422, detail="At least one line is required")
    new_status = update_data.get("status")
    if new_status is not None:
        allowed = _ALLOWED_STATUS.get(invoice.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot change invoice status from '{invoice.status}' to '{new_status}'",
            )
        if new_status == TuitionInvoiceStatus.void.value:
            posted = await db.scalar(
                select(TuitionReceiptInvoice.id)
                .join(TuitionReceipt, TuitionReceiptInvoice.receipt_id == TuitionReceipt.id)
                .where(
                    TuitionReceiptInvoice.invoice_id == invoice.id,
                    TuitionReceiptInvoice.is_posted.is_(True),
                    TuitionReceipt.status == TuitionReceiptStatus.posted.value,
                )
                .limit(1)
            )
            if posted:
                raise HTTPException(
                    status_code=422,
                    detail="Void the receipt before voiding this invoice",
                )

    if "invoice_no" in update_data and isinstance(update_data["invoice_no"], str):
        update_data["invoice_no"] = update_data["invoice_no"].strip() or None
    if "staff_name" in update_data and isinstance(update_data["staff_name"], str):
        update_data["staff_name"] = update_data["staff_name"].strip() or None
    if "payable_to_name" in update_data and isinstance(update_data["payable_to_name"], str):
        update_data["payable_to_name"] = update_data["payable_to_name"].strip() or None
    if "payee_name" in update_data and isinstance(update_data["payee_name"], str):
        update_data["payee_name"] = update_data["payee_name"].strip() or None

    for field, value in update_data.items():
        setattr(invoice, field, value)
    if line_payload is not None:
        ignore_ids = {line.id for line in invoice.lines}
        lines, purchase_links = await _build_manual_lines(
            db,
            body.lines or [],
            invoice.unit_id,
            ignore_line_ids=ignore_ids,
            existing_lines=list(invoice.lines),
        )
        invoice.lines.clear()
        invoice.total = sum(line.amount for line in lines)
        for line in lines:
            invoice.lines.append(line)
        await db.flush()
        for line, purchase in purchase_links:
            purchase.billed_invoice_line_id = line.id
            if purchase.unit_price is None:
                purchase.unit_price = line.unit_price
    if new_status == TuitionInvoiceStatus.issued.value:
        location_id = invoice.location_id or (invoice.unit.registered_location_id if invoice.unit else None)
        invoice.location_id = location_id
        if not invoice.invoice_no:
            invoice.invoice_no = (
                await _allocate_credit_no(db, location_id)
                if invoice.total < 0
                else str(await _allocate_invoice_no(db, location_id))
            )
        elif invoice.total < 0:
            invoice.invoice_no = _normalize_credit_no(invoice.invoice_no)
            credit_no = _parse_credit_no(invoice.invoice_no)
            if credit_no is not None:
                await _bump_credit_counter(db, credit_no, location_id)
        else:
            # Reserve this manual number so the counter never collides with it.
            manual_no = _parse_numeric_invoice_no(invoice.invoice_no)
            if manual_no is not None:
                await _bump_invoice_counter(db, manual_no, location_id)
        invoice.issued_at = datetime.now(timezone.utc)
    if new_status == TuitionInvoiceStatus.void.value:
        # Free every session package billed on this invoice so it can be
        # billed again on a new one. NULL = unbilled is the single rule.
        await db.execute(
            update(EnrollmentPurchase)
            .where(
                EnrollmentPurchase.billed_invoice_line_id.in_(
                    select(TuitionInvoiceLine.id).where(TuitionInvoiceLine.invoice_id == invoice.id)
                )
            )
            .values(billed_invoice_line_id=None)
        )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Invoice no. already in use — pick another.")
    await db.refresh(invoice)
    result = await db.execute(
        select(TuitionInvoice).options(*_INVOICE_LOAD).where(TuitionInvoice.id == invoice.id)
    )
    return (await _invoices_to_out(db, [result.scalar_one()]))[0]


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tuition_invoice(invoice_id: uuid.UUID, admin: AdminOnly, db: DB) -> None:
    result = await db.execute(
        select(TuitionInvoice).where(TuitionInvoice.id == invoice_id).with_for_update()
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status != TuitionInvoiceStatus.void.value:
        raise HTTPException(status_code=422, detail="Only cancelled invoices can be deleted")

    posted = await db.scalar(
        select(TuitionReceiptInvoice.id).where(
            TuitionReceiptInvoice.invoice_id == invoice.id,
            TuitionReceiptInvoice.is_posted.is_(True),
        ).limit(1)
    )
    if posted:
        raise HTTPException(status_code=409, detail="Void the receipt before deleting this invoice")

    await db.execute(
        delete(TuitionReceiptInvoice).where(
            TuitionReceiptInvoice.invoice_id == invoice.id,
            TuitionReceiptInvoice.is_posted.is_(False),
        )
    )
    invoice_no = invoice.invoice_no
    await db.delete(invoice)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=admin.id,
        action="DELETE",
        table_name="tuition_invoices",
        record_id=invoice_id,
        description=f"Deleted cancelled invoice {invoice_no or invoice_id}",
    )
