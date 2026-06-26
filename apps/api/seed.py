"""Seed script: creates default admin + sample products.  Run with:
    python seed.py
"""
import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models.location import Location
from app.models.product import Product
from app.models.staff_profile import StaffProfile
from app.models.student_profile import StudentProfile
from app.models.user import User
from app.services.auth import hash_password

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
]


async def main(*, users_only: bool = False) -> None:
    async with async_session_factory() as db:
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

        await db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed AQUA Attendance database")
    parser.add_argument("--users-only", action="store_true", help="Only seed users, skip locations and products")
    args = parser.parse_args()
    asyncio.run(main(users_only=args.users_only))
