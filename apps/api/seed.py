"""Seed script: creates default admin + sample products.  Run with:
    python seed.py
"""
import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models.location import Location
from app.models.product import Product
from app.models.user import User
from app.services.auth import hash_password

SEED_USERS = [
    {"username": "admin", "email": "admin@juku.local", "password": "admin123", "full_name": "Admin User", "role": "admin"},
    {"username": "superadmin", "email": "superadmin@juku.local", "password": "super123", "full_name": "Super Admin", "role": "superadmin"},
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
        "employment_type": "full_time",
        "status": "active",
        "allowed_codes": ["HK-CWB", "HK-MK"],
        "home_code": "HK-CWB",
    },
    {
        "code": "STAFF-002",
        "full_name": "Yamamoto Sensei",
        "product_type": "staff",
        "employment_type": "part_time",
        "status": "active",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
    },
    {
        "code": "STU-001",
        "full_name": "Suzuki Taro",
        "product_type": "student",
        "status": "active",
        "school_name": "Tokyo High",
        "grade_class": "3-A",
        "allowed_codes": ["HK-CWB"],
        "home_code": "HK-CWB",
    },
    {
        "code": "STU-002",
        "full_name": "Yamada Hanako",
        "product_type": "student",
        "status": "active",
        "school_name": "Osaka Middle",
        "grade_class": "2-B",
        "allowed_codes": ["HK-MK"],
        "home_code": "HK-MK",
    },
]


async def main() -> None:
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
            home_location = location_by_code[home_code]
            allowed_locations = [location_by_code[code] for code in allowed_codes]

            existing = await db.execute(select(Product).where(Product.code == p["code"]))
            product = existing.scalar_one_or_none()
            if product:
                for field, value in p.items():
                    setattr(product, field, value)
                product.home_location_id = home_location.id
                product.allowed_locations = allowed_locations
                print(f"  updated {p['code']} ({p['product_type']})")
                continue

            product = Product(**p, home_location_id=home_location.id)
            product.allowed_locations = allowed_locations
            db.add(product)
            print(f"  created {p['code']} - {p['full_name']} ({p['product_type']})")

        await db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
