"""Seed script: creates default admin + sample products.  Run with:
    python seed.py
    python seed.py --users-only
    python seed.py --summaries
"""
import argparse
import asyncio
import calendar
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

SEED_USERS = [
    {"username": "admin", "email": "admin@aqua.local", "password": "admin123", "full_name": "Admin User", "role": "admin"},
    {"username": "superadmin", "email": "superadmin@aqua.local", "password": "super123", "full_name": "Super Admin", "role": "superadmin"},
]

SEED_LOCATIONS = [
    {"code": "HK-CWB", "name_en": "Causeway Bay", "name_zh": "銅鑼灣", "region": "Hong Kong Island"},
    {"code": "HK-MK", "name_en": "Mong Kok", "name_zh": "旺角", "region": "Kowloon"},
]

SEED_PRODUCTS = [
    {
        "code": "STAFF-001",
        "full_name": "Tanaka Sensei",
        "product_type": "staff",
        "status": "active",
        "allowed_codes": ["HK-CWB", "HK-MK"],
        "home_code": "HK-CWB",
        "staff_profile": {"employment_type": "full_time", "department": "Math"},
    },
    {
        "code": "STAFF-002",
        "full_name": "Yamamoto Sensei",
        "product_type": "staff",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
        "staff_profile": {"employment_type": "part_time", "department": "English"},
    },
    {
        "code": "STU-001",
        "full_name": "Suzuki Taro",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-CWB"],
        "home_code": "HK-CWB",
        "student_profile": {"school_name": "Tokyo High", "grade_class": "3-A"},
    },
    {
        "code": "STU-002",
        "full_name": "Yamada Hanako",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
        "student_profile": {"school_name": "Osaka Middle", "grade_class": "2-B"},
    },
    {
        "code": "STAFF-003",
        "full_name": "Nakamura Sensei",
        "product_type": "staff",
        "status": "active",
        "allowed_codes": ["HK-CWB"],
        "home_code": "HK-CWB",
        "staff_profile": {"employment_type": "full_time", "department": "Science"},
    },
    {
        "code": "STAFF-004",
        "full_name": "Sato Sensei",
        "product_type": "staff",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
        "staff_profile": {"employment_type": "full_time", "department": "Chinese"},
    },
    {
        "code": "STAFF-005",
        "full_name": "Kobayashi Sensei",
        "product_type": "staff",
        "status": "active",
        "allowed_codes": ["HK-CWB", "HK-MK"],
        "home_code": "HK-CWB",
        "staff_profile": {"employment_type": "part_time", "department": "Art"},
    },
    {
        "code": "STAFF-006",
        "full_name": "Ito Sensei",
        "product_type": "staff",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
        "staff_profile": {"employment_type": "part_time", "department": "Music"},
    },
    {
        "code": "STU-003",
        "full_name": "Watanabe Ken",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-CWB"],
        "home_code": "HK-CWB",
        "student_profile": {"school_name": "Tokyo High", "grade_class": "1-C"},
    },
    {
        "code": "STU-004",
        "full_name": "Takahashi Yui",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-CWB"],
        "home_code": "HK-CWB",
        "student_profile": {"school_name": "Tokyo High", "grade_class": "2-A"},
    },
    {
        "code": "STU-005",
        "full_name": "Saito Ryo",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
        "student_profile": {"school_name": "Osaka Middle", "grade_class": "3-A"},
    },
    {
        "code": "STU-006",
        "full_name": "Kato Mei",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
        "student_profile": {"school_name": "Osaka Middle", "grade_class": "1-B"},
    },
    {
        "code": "STU-007",
        "full_name": "Yoshida Hiro",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-CWB"],
        "home_code": "HK-CWB",
        "student_profile": {"school_name": "Kobe Prep", "grade_class": "4-A"},
    },
    {
        "code": "STU-008",
        "full_name": "Mori Aki",
        "product_type": "student",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
        "student_profile": {"school_name": "Kobe Prep", "grade_class": "2-C"},
    },
]


# (product_code, summary_date, check_in, check_out, regular_h, ot_h, break_min, is_complete, is_weekend, is_holiday)
SEED_SUMMARIES: list[tuple] = [
    # May 2026 — staff with mixed complete / OT days
    ("STAFF-001", date(2026, 5, 6), (9, 0), (18, 30), 8.00, 0.50, 60, True, False, False),
    ("STAFF-001", date(2026, 5, 7), (8, 45), (17, 15), 7.50, 0.00, 60, True, False, False),
    ("STAFF-001", date(2026, 5, 8), (9, 15), (19, 0), 8.00, 1.25, 60, True, False, False),
    ("STAFF-001", date(2026, 5, 10), (9, 0), None, 0.00, 0.00, 60, False, True, False),
    ("STAFF-001", date(2026, 5, 12), (9, 0), (18, 0), 8.00, 0.00, 60, True, False, False),
    ("STAFF-001", date(2026, 5, 15), (9, 0), (18, 45), 8.00, 0.75, 60, True, False, False),
    ("STAFF-001", date(2026, 5, 20), (9, 0), (18, 0), 8.00, 0.00, 60, True, False, False),
    ("STAFF-002", date(2026, 5, 6), (14, 0), (18, 0), 3.50, 0.00, 30, True, False, False),
    ("STAFF-002", date(2026, 5, 13), (13, 30), (17, 30), 3.50, 0.00, 30, True, False, False),
    ("STAFF-002", date(2026, 5, 20), (14, 0), None, 0.00, 0.00, 30, False, False, False),
    ("STAFF-002", date(2026, 5, 22), (14, 0), (19, 30), 4.00, 1.00, 30, True, False, False),
    ("STAFF-002", date(2026, 5, 27), (14, 0), (18, 0), 3.50, 0.00, 30, True, False, False),
    # May 2026 — students
    ("STU-001", date(2026, 5, 5), (15, 30), (18, 30), 2.50, 0.00, 30, True, False, False),
    ("STU-001", date(2026, 5, 12), (15, 30), (18, 0), 2.00, 0.00, 30, True, False, False),
    ("STU-001", date(2026, 5, 19), (16, 0), (18, 30), 2.00, 0.00, 30, True, False, False),
    ("STU-001", date(2026, 5, 26), (15, 30), None, 0.00, 0.00, 30, False, False, False),
    ("STU-002", date(2026, 5, 7), (16, 0), (18, 30), 2.00, 0.00, 30, True, False, False),
    ("STU-002", date(2026, 5, 14), (15, 30), (18, 0), 2.00, 0.00, 30, True, False, False),
    ("STU-002", date(2026, 5, 18), (16, 0), (19, 0), 2.50, 0.00, 30, True, False, False),
    ("STU-002", date(2026, 5, 20), (15, 30), (18, 0), 2.00, 0.00, 30, True, False, False),
    ("STU-002", date(2026, 5, 22), (16, 0), (18, 30), 2.00, 0.00, 30, True, False, False),
    ("STU-002", date(2026, 5, 27), (15, 30), None, 0.00, 0.00, 30, False, False, False),
    ("STU-002", date(2026, 5, 29), (16, 0), (18, 30), 2.00, 0.00, 30, True, False, False),
]


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
    is_complete = roll > 6

    if product_type == "staff":
        if is_part_time_staff:
            check_in = (13 + roll % 2, 30 if roll % 2 else 0)
            regular = round(3.0 + (roll % 5) * 0.25, 2)
            ot = round((roll % 4) * 0.25, 2) if roll % 7 == 0 else 0.0
            break_min = 30
            out_h = check_in[0] + int(regular) + (1 if check_in[1] else 0)
            check_out = (out_h, check_in[1]) if is_complete else None
        else:
            check_in = (8 + roll % 2, 45 if roll % 3 == 0 else 0)
            regular = round(7.5 + (roll % 4) * 0.25, 2)
            ot = round((roll % 5) * 0.25, 2) if roll % 5 < 2 else 0.0
            break_min = 60
            out_h = 17 + int(ot) + (roll % 3)
            check_out = (out_h, 30 if roll % 2 else 0) if is_complete else None
    else:
        check_in = (15 + roll % 2, 30 if roll % 2 else 0)
        regular = round(1.5 + (roll % 6) * 0.25, 2)
        ot = 0.0
        break_min = 30
        out_h = check_in[0] + int(regular) + 1
        check_out = (out_h, check_in[1]) if is_complete else None

    return (
        product_code,
        summary_date,
        check_in,
        check_out,
        regular,
        ot,
        break_min,
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


async def seed_summaries(db) -> None:
    print("--- Seeding attendance summaries ---")
    result = await db.execute(select(Product))
    products = list(result.scalars().all())
    products_by_code = {p.code: p for p in products}
    if not products_by_code:
        print("  skipped: no products found (run seed without --users-only first)")
        return

    product_types = {p.code: p.product_type for p in products}
    bulk_rows = build_bulk_summary_rows(list(products_by_code.keys()), product_types)
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
            break_min,
            is_complete,
            is_weekend,
            is_holiday,
        ) = row

        product = products_by_code.get(product_code)
        if not product:
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
            total_break_minutes=break_min,
            is_complete=is_complete,
            is_weekend=is_weekend,
            is_holiday=is_holiday,
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

    print(f"  {created} created, {updated} updated, {skipped} skipped ({len(all_rows)} rows configured)")


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
                existing = await db.execute(select(Location).where(Location.code == loc["code"]))
                location = existing.scalar_one_or_none()
                if location:
                    for field, value in loc.items():
                        setattr(location, field, value)
                    print(f"  updated {loc['code']}")
                else:
                    location = Location(**loc)
                    db.add(location)
                    print(f"  created {loc['code']} - {loc['name_en']}")
                location_by_code[loc["code"]] = location

            await db.flush()

            print("--- Seeding products ---")
            for p in SEED_PRODUCTS:
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

                    # Update or create profile for existing product
                    await db.flush()
                    if p["product_type"] == "staff" and profile_data:
                        existing_sp = await db.execute(select(StaffProfile).where(StaffProfile.id == product.id))
                        sp = existing_sp.scalar_one_or_none()
                        if sp:
                            for field, value in profile_data.items():
                                setattr(sp, field, value)
                        else:
                            db.add(StaffProfile(id=product.id, **profile_data))
                    elif p["product_type"] == "student" and profile_data:
                        existing_stp = await db.execute(select(StudentProfile).where(StudentProfile.id == product.id))
                        stp = existing_stp.scalar_one_or_none()
                        if stp:
                            for field, value in profile_data.items():
                                setattr(stp, field, value)
                        else:
                            db.add(StudentProfile(id=product.id, **profile_data))

                    print(f"  updated {p['code']} ({p['product_type']})")
                    continue

                product = Product(**p, registered_location_id=registered_location.id)
                product.scan_locations = scan_locations
                db.add(product)
                await db.flush()

                # Create corresponding profile
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
