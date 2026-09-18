"""Seed demo data for the tuition invoices page.  Run with:
    python seed_invoices.py

Creates three branches (Wah Fu / Aberdeen / Tsuen Wan), course SKUs, student
units and September 2026 enrollments, then generates invoices and marks a mix
of issued / void so every status chip has rows. 李美欣 (ZA240921) starts in
August so seed_receipts can post one receipt against two months. Paid invoices
are created by seed_receipts.py.
"""
import asyncio
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.database import async_session_factory
from app.models.course_enrollment import CourseEnrollment, EnrollmentPurchase
from app.models.course_sku import CourseSku
from app.models.course_spu import CourseSpu
from app.models.location import Location
from app.models.tuition_invoice import TuitionInvoice, TuitionInvoiceStatus
from app.models.unit import Unit
from app.services.tuition_invoice_generator import generate_monthly_tuition_invoices

LOCATION_CODE = "YT-WF"

LOCATIONS = [
    {
        "code": "YT-WF", "name_en": "Wah Fu", "name_zh": "華富",
        "region": "Hong Kong Island", "address": "華富(二)邨商場5樓1-2號舖",
        "phone": "2237-1299", "details": {"school_reg_no": "613118"},
    },
    {
        "code": "YT-AB", "name_en": "Aberdeen", "name_zh": "香港仔",
        "region": "Hong Kong Island", "address": "香港仔大道123號",
        "phone": "2552-3388", "details": {"school_reg_no": "613119"},
    },
    {
        "code": "YT-TW", "name_en": "Tsuen Wan", "name_zh": "荃灣",
        "region": "New Territories", "address": "荃灣青山公路88號",
        "phone": "2411-5566", "details": {"school_reg_no": "613120"},
    },
]

SPUS = [
    {"code": "TUTOR", "name_zh": "功課輔導", "name_en": "Tutorial"},
    {"code": "ENG", "name_zh": "英文", "name_en": "English"},
]

SKUS = [
    {"code": "TUTOR-SESS", "spu_code": "TUTOR", "name_zh": "功課輔導班(堂費)", "billing_unit": "per_session", "price": 87.0},
    {"code": "TUTOR-MON", "spu_code": "TUTOR", "name_zh": "功課輔導班(月費)", "billing_unit": "monthly", "price": 1800.0},
    {"code": "ENG-A1", "spu_code": "ENG", "name_zh": "英文進修班", "billing_unit": "monthly", "price": 1200.0},
]

STUDENTS = [
    {"code": "ZA240919", "full_name": "戴卓嵐", "location": "YT-WF"},
    {"code": "ZA240920", "full_name": "陳小明", "location": "YT-WF"},
    {"code": "ZA240921", "full_name": "李美欣", "location": "YT-WF"},
    {"code": "ZA240922", "full_name": "黃志強", "location": "YT-WF"},
    {"code": "ZA240923", "full_name": "周雅婷", "location": "YT-WF"},
    {"code": "ZA240924", "full_name": "蔡曉彤", "location": "YT-WF"},
    {"code": "ZA240925", "full_name": "葉浩然", "location": "YT-WF"},
    {"code": "ZA250101", "full_name": "林子豪", "location": "YT-AB"},
    {"code": "ZA250102", "full_name": "吳嘉欣", "location": "YT-AB"},
    {"code": "ZA250103", "full_name": "鄭志偉", "location": "YT-AB"},
    {"code": "ZA250104", "full_name": "何詠詩", "location": "YT-AB"},
    {"code": "ZA250201", "full_name": "馬俊傑", "location": "YT-TW"},
    {"code": "ZA250202", "full_name": "陳芷晴", "location": "YT-TW"},
    {"code": "ZA250203", "full_name": "劉家輝", "location": "YT-TW"},
    {"code": "ZA250204", "full_name": "許雅文", "location": "YT-TW"},
]

# Most demo enrollments start in September. 李美欣 starts in August so Generate
# can produce two issued invoices for one receipt.
ENROLLMENT_START = {
    "ZA240921": date(2026, 8, 1),
}

# unit_code -> [(sku_code, purchased_quantity)]
ENROLLMENTS = {
    "ZA240919": [("TUTOR-SESS", 18)],
    "ZA240920": [("TUTOR-MON", None)],
    "ZA240921": [("TUTOR-SESS", 10), ("ENG-A1", None)],
    "ZA240922": [("ENG-A1", None)],
    "ZA240923": [("TUTOR-SESS", 8)],
    "ZA240924": [("TUTOR-MON", None)],
    "ZA240925": [("ENG-A1", None)],
    "ZA250101": [("TUTOR-MON", None)],
    "ZA250102": [("ENG-A1", None)],
    "ZA250103": [("TUTOR-SESS", 12)],
    "ZA250104": [("TUTOR-MON", None)],
    "ZA250201": [("ENG-A1", None)],
    "ZA250202": [("TUTOR-SESS", 6)],
    "ZA250203": [("TUTOR-MON", None), ("ENG-A1", None)],
    "ZA250204": [("TUTOR-SESS", 10)],
}

# unit_code -> (status, invoice_no). Paid is only set via seed_receipts.py.
DEMO_STATUSES = {
    "ZA240919": ("issued", "2704"),
    "ZA240920": ("issued", "2698"),
    "ZA240923": ("void", None),
    "ZA240924": ("issued", "9101"),
    "ZA240925": ("issued", "9102"),
    "ZA250101": ("issued", "9103"),
    "ZA250102": ("issued", "9104"),
    "ZA250104": ("void", None),
    "ZA250201": ("issued", "9105"),
    "ZA250202": ("issued", "9106"),
    "ZA250203": ("issued", "9107"),
}


async def upsert_by_code(db, model, code: str, defaults: dict):
    obj = (await db.execute(select(model).where(model.code == code))).scalar_one_or_none()
    if obj is None:
        obj = model(code=code, **defaults)
        db.add(obj)
        await db.flush()
    else:
        for key, value in defaults.items():
            setattr(obj, key, value)
    return obj


async def main() -> None:
    async with async_session_factory() as db:
        location_by_code = {}
        for loc in LOCATIONS:
            location_by_code[loc["code"]] = await upsert_by_code(db, Location, loc["code"], {
                "name_en": loc["name_en"],
                "name_zh": loc["name_zh"],
                "location_type": "branch",
                "region": loc["region"],
                "address": loc["address"],
                "phone": loc["phone"],
                "details": loc["details"],
                "is_active": True,
            })

        spu_by_code = {}
        for spu_data in SPUS:
            spu_by_code[spu_data["code"]] = await upsert_by_code(db, CourseSpu, spu_data["code"], {
                "name_zh": spu_data["name_zh"],
                "name_en": spu_data["name_en"],
            })

        sku_by_code = {}
        for sku_data in SKUS:
            sku_by_code[sku_data["code"]] = await upsert_by_code(db, CourseSku, sku_data["code"], {
                "spu_id": spu_by_code[sku_data["spu_code"]].id,
                "name_zh": sku_data["name_zh"],
                "price": sku_data["price"],
                "billing_unit": sku_data["billing_unit"],
                "is_active": True,
            })

        unit_by_code = {}
        for student in STUDENTS:
            unit_by_code[student["code"]] = await upsert_by_code(db, Unit, student["code"], {
                "full_name": student["full_name"],
                "unit_type": "student",
                "is_active": True,
                "status": "active",
                "registered_location_id": location_by_code[student["location"]].id,
            })

        for unit_code, entries in ENROLLMENTS.items():
            start_date = ENROLLMENT_START.get(unit_code, date(2026, 9, 1))
            for sku_code, purchased_qty in entries:
                sku = sku_by_code[sku_code]
                existing = (await db.execute(
                    select(CourseEnrollment).where(
                        CourseEnrollment.unit_id == unit_by_code[unit_code].id,
                        CourseEnrollment.sku_id == sku.id,
                    )
                )).scalar_one_or_none()
                if existing is None:
                    existing = CourseEnrollment(
                        unit_id=unit_by_code[unit_code].id,
                        sku_id=sku.id,
                        status="active",
                        start_date=start_date,
                    )
                    db.add(existing)
                    await db.flush()
                else:
                    existing.status = "active"
                    existing.start_date = start_date

                if purchased_qty is None:
                    continue
                purchase = (await db.execute(
                    select(EnrollmentPurchase).where(
                        EnrollmentPurchase.enrollment_id == existing.id,
                    )
                )).scalars().first()
                if purchase is None:
                    db.add(EnrollmentPurchase(
                        enrollment_id=existing.id,
                        purchased_quantity=purchased_qty,
                        unit_price=sku.price,
                        purchased_at=date(2026, 9, 1),
                    ))
                else:
                    purchase.purchased_quantity = purchased_qty
                    if purchase.unit_price is None:
                        purchase.unit_price = sku.price

        await db.commit()

        result_aug = await generate_monthly_tuition_invoices(db, year=2026, month=8)
        print(f"generate 2026-08: {result_aug}")
        result = await generate_monthly_tuition_invoices(db, year=2026, month=9)
        print(f"generate 2026-09: {result}")

        now = datetime.now(timezone.utc)
        for unit_code, (status, invoice_no) in DEMO_STATUSES.items():
            invoice = (await db.execute(
                select(TuitionInvoice).where(
                    TuitionInvoice.unit_id == unit_by_code[unit_code].id,
                    TuitionInvoice.period_start == date(2026, 9, 1),
                )
            )).scalar_one_or_none()
            if invoice is None:
                continue
            if invoice.status in (
                TuitionInvoiceStatus.paid.value,
                TuitionInvoiceStatus.void.value,
            ) and status != invoice.status:
                continue
            invoice.status = status
            if status == TuitionInvoiceStatus.issued.value:
                if not invoice.invoice_no:
                    invoice.invoice_no = invoice_no
                invoice.issued_at = now
        await db.commit()
        print("locations:", ", ".join(location_by_code))
        print("students:", len(unit_by_code))
        print("demo statuses applied:", ", ".join(DEMO_STATUSES))


if __name__ == "__main__":
    asyncio.run(main())
