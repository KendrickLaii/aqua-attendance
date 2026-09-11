"""Seed demo data for the tuition invoices page.  Run with:
    python seed_invoices.py

Creates a Wah Fu location (with invoice header details), one SPU, three SKUs
(堂費 + 月費), five student units and their September 2026 enrollments, then
runs the invoice generator for Sept 2026 and marks a few bills issued / paid /
void so every status chip has rows.
"""
import asyncio
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.database import async_session_factory
from app.models.course_enrollment import CourseEnrollment
from app.models.course_sku import CourseSku
from app.models.course_spu import CourseSpu
from app.models.location import Location
from app.models.tuition_invoice import TuitionInvoice, TuitionInvoiceStatus
from app.models.unit import Unit
from app.services.tuition_invoice_generator import generate_monthly_tuition_invoices

LOCATION_CODE = "YT-WF"

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
    {"code": "ZA240919", "full_name": "戴卓嵐"},
    {"code": "ZA240920", "full_name": "陳小明"},
    {"code": "ZA240921", "full_name": "李美欣"},
    {"code": "ZA240922", "full_name": "黃志強"},
    {"code": "ZA240923", "full_name": "周雅婷"},
]

# unit_code -> [(sku_code, purchased_quantity)]
ENROLLMENTS = {
    "ZA240919": [("TUTOR-SESS", 18)],                    # 87 × 18 = 1,566 like the Excel bill
    "ZA240920": [("TUTOR-MON", None)],
    "ZA240921": [("TUTOR-SESS", 10), ("ENG-A1", None)],
    "ZA240922": [("ENG-A1", None)],
    "ZA240923": [("TUTOR-SESS", 8)],
}

# unit_code -> (status, invoice_no)
DEMO_STATUSES = {
    "ZA240919": ("issued", "2704"),
    "ZA240920": ("paid", "2698"),
    "ZA240923": ("void", None),
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
        location = await upsert_by_code(db, Location, LOCATION_CODE, {
            "name_en": "Wah Fu",
            "name_zh": "華富",
            "location_type": "branch",
            "region": "Hong Kong Island",
            "address": "華富(二)邨商場5樓1-2號舖",
            "phone": "2237-1299",
            "details": {"school_reg_no": "613118"},
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
                "registered_location_id": location.id,
            })

        for unit_code, entries in ENROLLMENTS.items():
            for sku_code, purchased_qty in entries:
                existing = (await db.execute(
                    select(CourseEnrollment).where(
                        CourseEnrollment.unit_id == unit_by_code[unit_code].id,
                        CourseEnrollment.sku_id == sku_by_code[sku_code].id,
                    )
                )).scalar_one_or_none()
                if existing is None:
                    db.add(CourseEnrollment(
                        unit_id=unit_by_code[unit_code].id,
                        sku_id=sku_by_code[sku_code].id,
                        status="active",
                        start_date=date(2026, 9, 1),
                        purchased_quantity=purchased_qty,
                    ))
                else:
                    existing.status = "active"
                    existing.start_date = date(2026, 9, 1)
                    existing.purchased_quantity = purchased_qty

        await db.commit()

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
            invoice.status = status
            if status in (TuitionInvoiceStatus.issued.value, TuitionInvoiceStatus.paid.value):
                invoice.invoice_no = invoice_no
                invoice.issued_at = now
        await db.commit()
        print("demo statuses applied:", ", ".join(DEMO_STATUSES))


if __name__ == "__main__":
    asyncio.run(main())
