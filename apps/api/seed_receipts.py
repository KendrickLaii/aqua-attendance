"""Seed demo receipts on top of seed_invoices.py.  Run with:
    python seed_invoices.py
    python seed_receipts.py

Leaves 戴卓嵐 (ZA240919) issued so Mark paid / new receipt can be tested.
Creates posted receipts (including 李美欣 one receipt / two invoices), a voided
receipt, and walk-in invoices.
"""
import asyncio
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models.location import Location
from app.models.tuition_invoice import TuitionInvoice, TuitionInvoiceLine, TuitionInvoiceStatus
from app.models.tuition_receipt import TuitionReceipt, TuitionReceiptInvoice, TuitionReceiptStatus
from app.models.unit import Unit
from seed_invoices import LOCATION_CODE

NOW = datetime.now(timezone.utc)
PERIOD_START = date(2026, 9, 1)


async def _period_invoice(db, unit_id, period_start: date) -> TuitionInvoice | None:
    return (
        await db.execute(
            select(TuitionInvoice).where(
                TuitionInvoice.unit_id == unit_id,
                TuitionInvoice.period_start == period_start,
            )
        )
    ).scalar_one_or_none()


async def _sept_invoice(db, unit_id) -> TuitionInvoice | None:
    return await _period_invoice(db, unit_id, PERIOD_START)


async def _posted_receipt(db, invoice_id) -> TuitionReceipt | None:
    return (
        await db.execute(
            select(TuitionReceipt)
            .join(TuitionReceiptInvoice, TuitionReceiptInvoice.receipt_id == TuitionReceipt.id)
            .where(
                TuitionReceiptInvoice.invoice_id == invoice_id,
                TuitionReceiptInvoice.is_posted.is_(True),
                TuitionReceipt.status == TuitionReceiptStatus.posted.value,
            )
        )
    ).scalar_one_or_none()


async def _receipt_by_no(db, location_id, receipt_no: str) -> TuitionReceipt | None:
    return (
        await db.execute(
            select(TuitionReceipt)
            .options(selectinload(TuitionReceipt.invoices))
            .where(
                TuitionReceipt.location_id == location_id,
                TuitionReceipt.receipt_no == receipt_no,
            )
        )
    ).scalar_one_or_none()


async def _unused_invoice_no(db, location_id) -> str:
    existing = set(
        (
            await db.execute(
                select(TuitionInvoice.invoice_no).where(
                    TuitionInvoice.location_id == location_id,
                    TuitionInvoice.invoice_no.is_not(None),
                )
            )
        ).scalars().all()
    )
    n = 9001
    while str(n) in existing:
        n += 1
    return str(n)


async def _ensure_issued(db, invoice: TuitionInvoice) -> bool:
    """Return True if the invoice can be collected. Paid-without-receipt rows
    are rolled back to issued so a receipt can be created."""
    if invoice.status == TuitionInvoiceStatus.void.value:
        return False
    if invoice.status == TuitionInvoiceStatus.paid.value:
        invoice.status = TuitionInvoiceStatus.issued.value
    if invoice.status == TuitionInvoiceStatus.draft.value:
        if not invoice.invoice_no:
            invoice.invoice_no = await _unused_invoice_no(db, invoice.location_id)
        invoice.status = TuitionInvoiceStatus.issued.value
        invoice.issued_at = NOW
    return invoice.status == TuitionInvoiceStatus.issued.value


async def _pay(
    db,
    location: Location,
    invoices: TuitionInvoice | list[TuitionInvoice],
    *,
    receipt_no: str,
    receipt_date: date,
    paid_by: str,
    description: str | None = None,
    adjustments: list[dict] | None = None,
    void: bool = False,
) -> TuitionReceipt | None:
    rows_in = [invoices] if isinstance(invoices, TuitionInvoice) else list(invoices)
    to_link = [invoice for invoice in rows_in if invoice is not None]
    if not to_link:
        return None
    existing = await _receipt_by_no(db, location.id, receipt_no)
    if existing:
        if existing.status == TuitionReceiptStatus.void.value:
            return existing
        linked = {row.invoice_id for row in existing.invoices}
        extra = 0.0
        for invoice in to_link:
            if invoice.id in linked or await _posted_receipt(db, invoice.id):
                continue
            if not await _ensure_issued(db, invoice):
                continue
            link = TuitionReceiptInvoice(
                invoice_id=invoice.id,
                amount=invoice.total,
                is_posted=True,
            )
            existing.invoices.append(link)
            invoice.status = TuitionInvoiceStatus.paid.value
            extra += float(invoice.total)
        if extra:
            existing.amount = float(existing.amount) + extra
            if description:
                existing.description = description
        return existing
    rows = adjustments or []
    adj_total = sum(float(row["amount"]) for row in rows)
    receipt_amount = sum(float(invoice.total) for invoice in to_link) + adj_total
    first = to_link[0]
    receipt = TuitionReceipt(
        location_id=location.id,
        unit_id=first.unit_id,
        payer_name=first.manual_student_name if first.unit_id is None else None,
        paid_by=paid_by,
        receipt_no=receipt_no,
        receipt_date=receipt_date,
        amount=receipt_amount,
        status=TuitionReceiptStatus.posted.value,
        description=description,
        adjustments=rows,
    )
    db.add(receipt)
    await db.flush()
    links: list[TuitionReceiptInvoice] = []
    for invoice in to_link:
        link = TuitionReceiptInvoice(
            receipt_id=receipt.id,
            invoice_id=invoice.id,
            amount=invoice.total,
            is_posted=True,
        )
        db.add(link)
        links.append(link)
        invoice.status = TuitionInvoiceStatus.paid.value
    if void:
        receipt.status = TuitionReceiptStatus.void.value
        for link in links:
            link.is_posted = False
        for invoice in to_link:
            invoice.status = TuitionInvoiceStatus.issued.value
    return receipt


async def _walk_in(
    db,
    location: Location,
    *,
    name: str,
    invoice_no: str,
    fee: float,
    day: date,
) -> TuitionInvoice:
    existing = (
        await db.execute(
            select(TuitionInvoice).where(
                TuitionInvoice.location_id == location.id,
                TuitionInvoice.manual_student_name == name,
                TuitionInvoice.kind == "manual",
            )
        )
    ).scalars().first()
    if existing:
        return existing
    invoice = TuitionInvoice(
        location_id=location.id,
        period_start=day,
        period_end=day,
        status=TuitionInvoiceStatus.issued.value,
        kind="manual",
        manual_student_name=name,
        total=fee,
        invoice_no=invoice_no,
        issued_at=NOW,
    )
    invoice.lines = [
        TuitionInvoiceLine(
            sku_code="manual",
            name_zh="私補",
            billing_unit="per_session",
            unit_price=fee,
            quantity=1,
            amount=fee,
            month_label="Sept-26",
        )
    ]
    db.add(invoice)
    await db.flush()
    return invoice


async def main() -> None:
    async with async_session_factory() as db:
        location = (
            await db.execute(select(Location).where(Location.code == LOCATION_CODE))
        ).scalar_one_or_none()
        if not location:
            raise SystemExit("Run seed_invoices.py first (location YT-WF is missing).")

        locations = {
            row.code: row
            for row in (
                await db.execute(select(Location).where(Location.code.in_(["YT-WF", "YT-AB", "YT-TW"])))
            ).scalars().all()
        }

        units = {
            unit.code: unit
            for unit in (
                await db.execute(select(Unit).where(Unit.code.in_([
                    "ZA240919", "ZA240920", "ZA240921", "ZA240922", "ZA240925",
                    "ZA250101", "ZA250201", "ZA250203",
                ])))
            ).scalars().all()
        }
        if "ZA240919" not in units:
            raise SystemExit("Run seed_invoices.py first (demo students are missing).")

        unpaid = await _sept_invoice(db, units["ZA240919"].id)
        if unpaid and unpaid.status == TuitionInvoiceStatus.paid.value and not await _posted_receipt(db, unpaid.id):
            unpaid.status = TuitionInvoiceStatus.issued.value
        print("left issued for Mark paid:", unpaid.invoice_no if unpaid else "missing")

        chen = await _sept_invoice(db, units["ZA240920"].id)
        if chen and not await _posted_receipt(db, chen.id) and await _ensure_issued(db, chen):
            await _pay(
                db, location, chen,
                receipt_no="R260918",
                receipt_date=date(2026, 9, 18),
                paid_by="Cash",
                description="Sept tuition",
            )
            print("posted", "R260918", units["ZA240920"].full_name)

        li_aug = await _period_invoice(db, units["ZA240921"].id, date(2026, 8, 1))
        li_sept = await _sept_invoice(db, units["ZA240921"].id)
        li_invoices = []
        for invoice in (li_aug, li_sept):
            if invoice is None or await _posted_receipt(db, invoice.id):
                continue
            if await _ensure_issued(db, invoice):
                li_invoices.append(invoice)
        if li_invoices:
            await _pay(
                db, location, li_invoices,
                receipt_no="R260918-2",
                receipt_date=date(2026, 9, 18),
                paid_by="FPS",
                description="Aug + Sept tuition",
            )
            print(
                "posted",
                "R260918-2",
                units["ZA240921"].full_name,
                f"{len(li_invoices)} invoices",
            )

        wong = await _sept_invoice(db, units["ZA240922"].id)
        if wong and not await _receipt_by_no(db, location.id, "R260917") and await _ensure_issued(db, wong):
            await _pay(
                db, location, wong,
                receipt_no="R260917",
                receipt_date=date(2026, 9, 17),
                paid_by="HSBC",
                description="Created then voided",
                void=True,
            )
            print("voided", "R260917", units["ZA240922"].full_name)

        walk_unpaid = await _walk_in(
            db, location,
            name="張訪客",
            invoice_no=await _unused_invoice_no(db, location.id),
            fee=400,
            day=date(2026, 9, 18),
        )
        print("walk-in issued:", walk_unpaid.invoice_no, walk_unpaid.manual_student_name)

        walk_paid = await _walk_in(
            db, location,
            name="林訪客",
            invoice_no=await _unused_invoice_no(db, location.id),
            fee=350,
            day=date(2026, 9, 16),
        )
        if not await _posted_receipt(db, walk_paid.id) and walk_paid.status == TuitionInvoiceStatus.issued.value:
            await _pay(
                db, location, walk_paid,
                receipt_no="R260916",
                receipt_date=date(2026, 9, 16),
                paid_by="Cheque",
                description="Walk-in makeup class",
            )
            print("posted", "R260916", walk_paid.manual_student_name)

        ye = await _sept_invoice(db, units["ZA240925"].id) if "ZA240925" in units else None
        if ye and not await _posted_receipt(db, ye.id) and await _ensure_issued(db, ye):
            await _pay(
                db, location, ye,
                receipt_no="R260915",
                receipt_date=date(2026, 9, 15),
                paid_by="Bank Transfer",
                description="English September",
            )
            print("posted", "R260915", units["ZA240925"].full_name)

        aberdeen = locations.get("YT-AB")
        lam = await _sept_invoice(db, units["ZA250101"].id) if aberdeen and "ZA250101" in units else None
        if aberdeen and lam and not await _posted_receipt(db, lam.id) and await _ensure_issued(db, lam):
            await _pay(
                db, aberdeen, lam,
                receipt_no="R260918",
                receipt_date=date(2026, 9, 18),
                paid_by="FPS",
                description="Aberdeen monthly",
            )
            print("posted", "R260918", units["ZA250101"].full_name, "Aberdeen")

        tsuen_wan = locations.get("YT-TW")
        ma = await _sept_invoice(db, units["ZA250201"].id) if tsuen_wan and "ZA250201" in units else None
        if tsuen_wan and ma and not await _posted_receipt(db, ma.id) and await _ensure_issued(db, ma):
            await _pay(
                db, tsuen_wan, ma,
                receipt_no="R260918",
                receipt_date=date(2026, 9, 18),
                paid_by="Cash",
                description="Discounted English",
                adjustments=[{"month": "Sept-26", "course": "Early-bird discount", "amount": -50}],
            )
            print("posted", "R260918", units["ZA250201"].full_name, "Tsuen Wan + adjustment")

        lau = await _sept_invoice(db, units["ZA250203"].id) if tsuen_wan and "ZA250203" in units else None
        if tsuen_wan and lau and not await _posted_receipt(db, lau.id) and await _ensure_issued(db, lau):
            await _pay(
                db, tsuen_wan, lau,
                receipt_no="R260918-2",
                receipt_date=date(2026, 9, 18),
                paid_by="HSBC 1234",
                description="Two classes",
            )
            print("posted", "R260918-2", units["ZA250203"].full_name, "Tsuen Wan")

        if aberdeen:
            ab_walk = await _walk_in(
                db, aberdeen,
                name="周訪客",
                invoice_no=await _unused_invoice_no(db, aberdeen.id),
                fee=280,
                day=date(2026, 9, 17),
            )
            if not await _posted_receipt(db, ab_walk.id):
                await _pay(
                    db, aberdeen, ab_walk,
                    receipt_no="R260917",
                    receipt_date=date(2026, 9, 17),
                    paid_by="Cash",
                    description="Walk-in Aberdeen",
                )
                print("posted", "R260917", ab_walk.manual_student_name)

        await db.commit()
        print("seed_receipts done")


if __name__ == "__main__":
    asyncio.run(main())
