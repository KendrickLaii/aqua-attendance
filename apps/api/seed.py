"""Seed script: creates default admin + sample products.  Run with:
    python seed.py
    python seed.py --users-only
    python seed.py --summaries
"""
import argparse
import asyncio
import calendar
import copy
from datetime import date, datetime, time, timezone

from sqlalchemy import select

from app.database import async_session_factory
from app.models.attendance_summary import AttendanceSummary
from app.models.location import Location
from app.models.product import Product
from app.models.staff_profile import StaffProfile
from app.models.student_profile import StudentProfile
from app.models.user import User
from app.services.auth import hash_password

# Months filled with bulk generated rows (year, month)
BULK_SUMMARY_MONTHS = [(2026, 6), (2026, 7)]

# Weekday business hours used by OT calculation (location.business_hours.close)
DEFAULT_BUSINESS_HOURS = {
    "monday": {"open": "09:00", "close": "18:00"},
    "tuesday": {"open": "09:00", "close": "18:00"},
    "wednesday": {"open": "09:00", "close": "18:00"},
    "thursday": {"open": "09:00", "close": "18:00"},
    "friday": {"open": "09:00", "close": "18:00"},
    "saturday": None,
    "sunday": None,
}

SEED_USERS = [
    {"username": "admin", "email": "admin@aqua.local", "password": "admin123", "full_name": "Admin User", "role": "admin"},
    {"username": "superadmin", "email": "superadmin@aqua.local", "password": "super123", "full_name": "Super Admin", "role": "superadmin"},
]

SEED_LOCATIONS = [
    {
        "code": "HK-CWB",
        "name_en": "Causeway Bay",
        "name_zh": "銅鑼灣",
        "region": "Hong Kong Island",
        "location_type": "branch",
        "business_hours": DEFAULT_BUSINESS_HOURS,
        "address": "Causeway Bay, Hong Kong",
        "is_active": True,
    },
    {
        "code": "HK-MK",
        "name_en": "Mong Kok",
        "name_zh": "旺角",
        "region": "Kowloon",
        "location_type": "branch",
        "business_hours": DEFAULT_BUSINESS_HOURS,
        "address": "Mong Kok, Kowloon",
        "is_active": True,
    },
]

# Staff pay rates drive payroll_generator (slot × rate).
# full_time → monthly + optional hourly for OT; part_time → hourly.
SEED_PRODUCTS = [
    {
        "code": "STAFF-001",
        "full_name": "Tanaka Sensei",
        "english_name": "Tanaka",
        "product_type": "staff",
        "status": "active",
        "allowed_codes": ["HK-CWB", "HK-MK"],
        "home_code": "HK-CWB",
        "staff_profile": {
            "employment_type": "full_time",
            "department": "Math",
            "position": "Senior Tutor",
            "employee_id": "E-001",
            "hire_date": date(2024, 4, 1),
            "pay_type": "monthly",
            "monthly_salary": 28000.00,
            "hourly_rate": 180.00,
            "ot_multiplier": 1.5,
            "work_schedule": "Mon–Fri 09:00–18:00",
        },
    },
    {
        "code": "STAFF-002",
        "full_name": "Yamamoto Sensei",
        "english_name": "Yamamoto",
        "product_type": "staff",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
        "staff_profile": {
            "employment_type": "part_time",
            "department": "English",
            "position": "Tutor",
            "employee_id": "E-002",
            "hire_date": date(2025, 1, 15),
            "pay_type": "hourly",
            "hourly_rate": 220.00,
            "ot_multiplier": 1.5,
            "work_schedule": "Mon/Wed/Fri afternoons",
        },
    },
    {
        "code": "STU-001",
        "full_name": "Suzuki Taro",
        "english_name": "Taro Suzuki",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-CWB"],
        "home_code": "HK-CWB",
        "student_profile": {
            "school_name": "Tokyo High",
            "grade_class": "3-A",
            "student_id": "S-001",
            "enrollment_date": date(2025, 4, 1),
        },
    },
    {
        "code": "STU-002",
        "full_name": "Yamada Hanako",
        "english_name": "Hanako Yamada",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
        "student_profile": {
            "school_name": "Osaka Middle",
            "grade_class": "2-B",
            "student_id": "S-002",
            "enrollment_date": date(2025, 4, 1),
        },
    },
    {
        "code": "STAFF-003",
        "full_name": "Nakamura Sensei",
        "english_name": "Nakamura",
        "product_type": "staff",
        "status": "active",
        "allowed_codes": ["HK-CWB"],
        "home_code": "HK-CWB",
        "staff_profile": {
            "employment_type": "full_time",
            "department": "Science",
            "position": "Tutor",
            "employee_id": "E-003",
            "hire_date": date(2024, 9, 1),
            "pay_type": "monthly",
            "monthly_salary": 25000.00,
            "hourly_rate": 160.00,
            "ot_multiplier": 1.5,
        },
    },
    {
        "code": "STAFF-004",
        "full_name": "Sato Sensei",
        "english_name": "Sato",
        "product_type": "staff",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
        "staff_profile": {
            "employment_type": "full_time",
            "department": "Chinese",
            "position": "Tutor",
            "employee_id": "E-004",
            "hire_date": date(2023, 4, 1),
            "pay_type": "monthly",
            "monthly_salary": 26000.00,
            "hourly_rate": 170.00,
            "ot_multiplier": 1.5,
        },
    },
    {
        "code": "STAFF-005",
        "full_name": "Kobayashi Sensei",
        "english_name": "Kobayashi",
        "product_type": "staff",
        "status": "active",
        "allowed_codes": ["HK-CWB", "HK-MK"],
        "home_code": "HK-CWB",
        "staff_profile": {
            "employment_type": "part_time",
            "department": "Art",
            "position": "Tutor",
            "employee_id": "E-005",
            "hire_date": date(2025, 6, 1),
            "pay_type": "hourly",
            "hourly_rate": 200.00,
            "ot_multiplier": 1.5,
            "work_schedule": "Mon/Wed/Fri afternoons",
        },
    },
    {
        "code": "STAFF-006",
        "full_name": "Ito Sensei",
        "english_name": "Ito",
        "product_type": "staff",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
        "staff_profile": {
            "employment_type": "part_time",
            "department": "Music",
            "position": "Tutor",
            "employee_id": "E-006",
            "hire_date": date(2025, 3, 1),
            "pay_type": "hourly",
            "hourly_rate": 210.00,
            "ot_multiplier": 1.5,
            "work_schedule": "Mon/Wed/Fri afternoons",
        },
    },
    {
        "code": "STU-003",
        "full_name": "Watanabe Ken",
        "english_name": "Ken Watanabe",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-CWB"],
        "home_code": "HK-CWB",
        "student_profile": {
            "school_name": "Tokyo High",
            "grade_class": "1-C",
            "student_id": "S-003",
            "enrollment_date": date(2026, 4, 1),
        },
    },
    {
        "code": "STU-004",
        "full_name": "Takahashi Yui",
        "english_name": "Yui Takahashi",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-CWB"],
        "home_code": "HK-CWB",
        "student_profile": {
            "school_name": "Tokyo High",
            "grade_class": "2-A",
            "student_id": "S-004",
            "enrollment_date": date(2025, 4, 1),
        },
    },
    {
        "code": "STU-005",
        "full_name": "Saito Ryo",
        "english_name": "Ryo Saito",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
        "student_profile": {
            "school_name": "Osaka Middle",
            "grade_class": "3-A",
            "student_id": "S-005",
            "enrollment_date": date(2024, 4, 1),
        },
    },
    {
        "code": "STU-006",
        "full_name": "Kato Mei",
        "english_name": "Mei Kato",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
        "student_profile": {
            "school_name": "Osaka Middle",
            "grade_class": "1-B",
            "student_id": "S-006",
            "enrollment_date": date(2026, 4, 1),
        },
    },
    {
        "code": "STU-007",
        "full_name": "Yoshida Hiro",
        "english_name": "Hiro Yoshida",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-CWB"],
        "home_code": "HK-CWB",
        "student_profile": {
            "school_name": "Kobe Prep",
            "grade_class": "4-A",
            "student_id": "S-007",
            "enrollment_date": date(2023, 4, 1),
        },
    },
    {
        "code": "STU-008",
        "full_name": "Mori Aki",
        "english_name": "Aki Mori",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
        "student_profile": {
            "school_name": "Kobe Prep",
            "grade_class": "2-C",
            "student_id": "S-008",
            "enrollment_date": date(2025, 4, 1),
        },
    },
]


# (product_code, summary_date, check_in, check_out, regular_h, ot_h, is_complete, is_weekend, is_holiday)
SEED_SUMMARIES: list[tuple] = [
    # May 2026 — staff with mixed complete / OT days (all complete; day-boundary closes forgotten outs)
    ("STAFF-001", date(2026, 5, 6), (9, 0), (18, 30), 8.00, 0.50, True, False, False),
    ("STAFF-001", date(2026, 5, 7), (8, 45), (17, 15), 7.50, 0.00, True, False, False),
    ("STAFF-001", date(2026, 5, 8), (9, 15), (19, 0), 8.00, 1.25, True, False, False),
    ("STAFF-001", date(2026, 5, 10), (9, 0), (23, 59), 8.00, 0.00, True, True, False),
    ("STAFF-001", date(2026, 5, 12), (9, 0), (18, 0), 8.00, 0.00, True, False, False),
    ("STAFF-001", date(2026, 5, 15), (9, 0), (18, 45), 8.00, 0.75, True, False, False),
    ("STAFF-001", date(2026, 5, 20), (9, 0), (18, 0), 8.00, 0.00, True, False, False),
    ("STAFF-002", date(2026, 5, 6), (14, 0), (18, 0), 3.50, 0.00, True, False, False),
    ("STAFF-002", date(2026, 5, 13), (13, 30), (17, 30), 3.50, 0.00, True, False, False),
    ("STAFF-002", date(2026, 5, 20), (14, 0), (23, 59), 3.50, 0.00, True, False, False),
    ("STAFF-002", date(2026, 5, 22), (14, 0), (19, 30), 4.00, 1.00, True, False, False),
    ("STAFF-002", date(2026, 5, 27), (14, 0), (18, 0), 3.50, 0.00, True, False, False),
    # May 2026 — students
    ("STU-001", date(2026, 5, 5), (15, 30), (18, 30), 2.50, 0.00, True, False, False),
    ("STU-001", date(2026, 5, 12), (15, 30), (18, 0), 2.00, 0.00, True, False, False),
    ("STU-001", date(2026, 5, 19), (16, 0), (18, 30), 2.00, 0.00, True, False, False),
    ("STU-001", date(2026, 5, 26), (15, 30), (23, 59), 2.00, 0.00, True, False, False),
    ("STU-002", date(2026, 5, 7), (16, 0), (18, 30), 2.00, 0.00, True, False, False),
    ("STU-002", date(2026, 5, 14), (15, 30), (18, 0), 2.00, 0.00, True, False, False),
    ("STU-002", date(2026, 5, 18), (16, 0), (19, 0), 2.50, 0.00, True, False, False),
    ("STU-002", date(2026, 5, 20), (15, 30), (18, 0), 2.00, 0.00, True, False, False),
    ("STU-002", date(2026, 5, 22), (16, 0), (18, 30), 2.00, 0.00, True, False, False),
    ("STU-002", date(2026, 5, 27), (15, 30), (23, 59), 2.00, 0.00, True, False, False),
    ("STU-002", date(2026, 5, 29), (16, 0), (18, 30), 2.00, 0.00, True, False, False),
]


def _hours_to_slots(hours: float) -> int:
    """1 hour = 4 × 15-min slots."""
    return int(round(float(hours or 0) * 4))


def _roll(product_code: str, product_type: str, summary_date: date) -> int:
    """Deterministic 0–99 roll for attendance patterns."""
    return hash((product_code, summary_date.isoformat())) % 100


def _should_attend(product_code: str, product_type: str, summary_date: date) -> bool:
    roll = _roll(product_code, product_type, summary_date)
    weekend = summary_date.weekday() >= 5
    is_part_time_staff = product_type == "staff" and product_code in {"STAFF-002", "STAFF-005", "STAFF-006"}

    if product_type == "staff":
        if is_part_time_staff:
            if summary_date.weekday() not in (0, 2, 4):
                return weekend and roll < 12
            return roll < 88
        if weekend:
            return roll < 28
        return roll < 94

    if weekend:
        return roll < 42
    return roll < 72


def _build_day_row(product_code: str, product_type: str, summary_date: date) -> tuple:
    roll = _roll(product_code, product_type, summary_date)
    weekend = summary_date.weekday() >= 5
    is_part_time_staff = product_type == "staff" and product_code in {"STAFF-002", "STAFF-005", "STAFF-006"}
    # Seed rows are always complete: forgotten outs are closed at 23:59 (auto-checkout rule).
    is_complete = True
    closed_by_boundary = roll <= 6

    if product_type == "staff":
        if is_part_time_staff:
            check_in = (13 + roll % 2, 30 if roll % 2 else 0)
            regular = round(3.0 + (roll % 5) * 0.25, 2)
            ot = round((roll % 4) * 0.25, 2) if roll % 7 == 0 else 0.0
            if closed_by_boundary:
                check_out = (23, 59)
            else:
                out_h = check_in[0] + int(regular) + (1 if check_in[1] else 0)
                check_out = (out_h, check_in[1])
        else:
            check_in = (8 + roll % 2, 45 if roll % 3 == 0 else 0)
            regular = round(7.5 + (roll % 4) * 0.25, 2)
            ot = round((roll % 5) * 0.25, 2) if roll % 5 < 2 else 0.0
            if closed_by_boundary:
                check_out = (23, 59)
            else:
                out_h = 17 + int(ot) + (roll % 3)
                check_out = (out_h, 30 if roll % 2 else 0)
    else:
        check_in = (15 + roll % 2, 30 if roll % 2 else 0)
        regular = round(1.5 + (roll % 6) * 0.25, 2)
        ot = 0.0
        if closed_by_boundary:
            check_out = (23, 59)
        else:
            out_h = check_in[0] + int(regular) + 1
            check_out = (out_h, check_in[1])

    return (
        product_code,
        summary_date,
        check_in,
        check_out,
        regular,
        ot,
        is_complete,
        weekend,
        False,
    )


def build_bulk_summary_rows(product_codes: list[str], product_types: dict[str, str]) -> list[tuple]:
    rows: list[tuple] = []
    for year, month in BULK_SUMMARY_MONTHS:
        last_day = calendar.monthrange(year, month)[1]
        for day in range(1, last_day + 1):
            summary_date = date(year, month, day)
            for code in product_codes:
                ptype = product_types.get(code, "student")
                if _should_attend(code, ptype, summary_date):
                    rows.append(_build_day_row(code, ptype, summary_date))
    return rows


def _dt(summary_date: date, hour: int, minute: int) -> datetime:
    return datetime.combine(summary_date, time(hour, minute), tzinfo=timezone.utc)


async def _upsert_staff_profile(db, product_id, profile_data: dict) -> None:
    existing = await db.execute(select(StaffProfile).where(StaffProfile.id == product_id))
    sp = existing.scalar_one_or_none()
    if sp:
        for field, value in profile_data.items():
            setattr(sp, field, value)
    else:
        db.add(StaffProfile(id=product_id, **profile_data))


async def _upsert_student_profile(db, product_id, profile_data: dict) -> None:
    existing = await db.execute(select(StudentProfile).where(StudentProfile.id == product_id))
    stp = existing.scalar_one_or_none()
    if stp:
        for field, value in profile_data.items():
            setattr(stp, field, value)
    else:
        db.add(StudentProfile(id=product_id, **profile_data))


async def seed_summaries(db) -> None:
    print("--- Seeding attendance summaries ---")
    result = await db.execute(select(Product))
    products = list(result.scalars().all())
    products_by_code = {p.code: p for p in products}
    if not products_by_code:
        print("  skipped: no products found (run seed without --users-only first)")
        return

    # Only generate bulk rows for known seed product codes so custom products
    # (e.g. "mock data stuff") keep their own summaries; slots are still backfilled below.
    seed_codes = {p["code"] for p in SEED_PRODUCTS}
    product_types = {code: products_by_code[code].product_type for code in seed_codes if code in products_by_code}
    bulk_rows = build_bulk_summary_rows(list(product_types.keys()), product_types)
    all_rows = SEED_SUMMARIES + bulk_rows
    print(f"  preparing {len(SEED_SUMMARIES)} fixed + {len(bulk_rows)} bulk rows (Jun/Jul 2026)")

    created = 0
    updated = 0
    skipped = 0
    for row in all_rows:
        (
            product_code,
            summary_date,
            check_in,
            check_out,
            regular_h,
            ot_h,
            is_complete,
            is_weekend,
            is_holiday,
        ) = row

        product = products_by_code.get(product_code)
        if not product:
            skipped += 1
            continue

        if not product.registered_location_id:
            skipped += 1
            continue

        first_check_in = _dt(summary_date, check_in[0], check_in[1])
        last_check_out = (
            _dt(summary_date, check_out[0], check_out[1]) if check_out else None
        )
        work_minutes = int((regular_h + ot_h) * 60)
        ot_minutes = int(ot_h * 60)

        existing = await db.execute(
            select(AttendanceSummary).where(
                AttendanceSummary.product_id == product.id,
                AttendanceSummary.summary_date == summary_date,
            )
        )
        summary = existing.scalar_one_or_none()
        values = dict(
            location_id=product.registered_location_id,
            first_check_in=first_check_in,
            last_check_out=last_check_out,
            total_work_minutes=work_minutes,
            total_overtime_minutes=ot_minutes,
            is_complete=is_complete,
            is_weekend=is_weekend,
            is_holiday=is_holiday,
            regular_slots=_hours_to_slots(regular_h),
            ot_slots=_hours_to_slots(ot_h),
            regular_hours=regular_h,
            overtime_hours=ot_h,
            holiday_hours=0.0,
            calculation_method="seed",
        )

        if summary:
            for field, value in values.items():
                setattr(summary, field, value)
            updated += 1
        else:
            db.add(
                AttendanceSummary(
                    product_id=product.id,
                    summary_date=summary_date,
                    **values,
                )
            )
            created += 1

    # Backfill any leftover rows (custom products / pre-slot data) that still
    # have hours but zero slots — preserves hours, only fills slots.
    backfill_result = await db.execute(
        select(AttendanceSummary).where(
            AttendanceSummary.regular_slots == 0,
            AttendanceSummary.ot_slots == 0,
        )
    )
    backfilled = 0
    for summary in backfill_result.scalars().all():
        regular_h = float(summary.regular_hours or 0)
        ot_h = float(summary.overtime_hours or 0)
        if regular_h <= 0 and ot_h <= 0:
            continue
        summary.regular_slots = _hours_to_slots(regular_h)
        summary.ot_slots = _hours_to_slots(ot_h)
        backfilled += 1

    print(f"  {created} created, {updated} updated, {skipped} skipped ({len(all_rows)} rows configured)")
    if backfilled:
        print(f"  {backfilled} existing rows backfilled slots from hours")

    # Close legacy incomplete seed rows (pre auto-checkout alignment)
    incomplete_result = await db.execute(
        select(AttendanceSummary).where(AttendanceSummary.is_complete.is_(False))
    )
    closed = 0
    for summary in incomplete_result.scalars().all():
        if summary.first_check_in is None:
            continue
        if summary.last_check_out is None:
            summary.last_check_out = datetime.combine(
                summary.summary_date, time(23, 59), tzinfo=timezone.utc
            )
        summary.is_complete = True
        if not summary.attendance_notes:
            summary.attendance_notes = "Closed by day-boundary auto checkout (23:59)"
        closed += 1
    if closed:
        print(f"  {closed} incomplete rows closed at day boundary (23:59)")


async def main(*, users_only: bool = False, summaries_only: bool = False) -> None:
    async with async_session_factory() as db:
        if summaries_only:
            await seed_summaries(db)
            await db.commit()
            print("Seed complete.")
            return

        print("--- Seeding users ---")
        for u in SEED_USERS:
            existing = await db.execute(select(User).where(User.username == u["username"]))
            user = existing.scalar_one_or_none()
            if user:
                user.email = u["email"]
                user.hashed_password = hash_password(u["password"])
                user.full_name = u["full_name"]
                user.role = u["role"]
                print(f"  updated {u['username']} ({u['role']})")
                continue

            user = User(
                username=u["username"],
                email=u["email"],
                hashed_password=hash_password(u["password"]),
                full_name=u["full_name"],
                role=u["role"],
            )
            db.add(user)
            print(f"  created {u['username']} ({u['role']})")

        if not users_only:
            print("--- Seeding locations ---")
            location_by_code: dict[str, Location] = {}
            for loc in SEED_LOCATIONS:
                loc_data = copy.deepcopy(loc)
                existing = await db.execute(select(Location).where(Location.code == loc_data["code"]))
                location = existing.scalar_one_or_none()
                if location:
                    for field, value in loc_data.items():
                        setattr(location, field, value)
                    print(f"  updated {loc_data['code']}")
                else:
                    location = Location(**loc_data)
                    db.add(location)
                    print(f"  created {loc_data['code']} - {loc_data['name_en']}")
                location_by_code[loc_data["code"]] = location

            await db.flush()

            print("--- Seeding products ---")
            for raw in SEED_PRODUCTS:
                p = copy.deepcopy(raw)
                allowed_codes = p.pop("allowed_codes")
                home_code = p.pop("home_code")
                profile_data = p.pop("staff_profile", None) or p.pop("student_profile", None)
                registered_location = location_by_code[home_code]
                scan_locations = [location_by_code[code] for code in allowed_codes]

                existing = await db.execute(select(Product).where(Product.code == p["code"]))
                product = existing.scalar_one_or_none()
                if product:
                    for field, value in p.items():
                        setattr(product, field, value)
                    product.registered_location_id = registered_location.id
                    product.scan_locations = scan_locations
                    await db.flush()
                    if p["product_type"] == "staff" and profile_data:
                        await _upsert_staff_profile(db, product.id, profile_data)
                    elif p["product_type"] == "student" and profile_data:
                        await _upsert_student_profile(db, product.id, profile_data)
                    print(f"  updated {p['code']} ({p['product_type']})")
                    continue

                product = Product(**p, registered_location_id=registered_location.id)
                product.scan_locations = scan_locations
                db.add(product)
                await db.flush()

                if p["product_type"] == "staff" and profile_data:
                    db.add(StaffProfile(id=product.id, **profile_data))
                elif p["product_type"] == "student" and profile_data:
                    db.add(StudentProfile(id=product.id, **profile_data))

                print(f"  created {p['code']} - {p['full_name']} ({p['product_type']})")

            await seed_summaries(db)

        await db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed AQUA Attendance database")
    parser.add_argument("--users-only", action="store_true", help="Only seed users, skip locations and products")
    parser.add_argument(
        "--summaries",
        action="store_true",
        help="Only seed attendance summary dummy data (requires products)",
    )
    args = parser.parse_args()
    asyncio.run(main(users_only=args.users_only, summaries_only=args.summaries))
