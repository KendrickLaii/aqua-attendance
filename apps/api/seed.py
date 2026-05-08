"""Seed script: creates default admin + sample users.  Run with:
    python seed.py
"""
import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import User
from app.services.auth import hash_password

SEED_USERS = [
    {"username": "admin", "email": "admin@juku.local", "password": "admin123", "full_name": "Admin User", "role": "admin"},
    {"username": "staff1", "email": "staff1@juku.local", "password": "staff123", "full_name": "Tanaka Sensei", "role": "staff"},
    {"username": "student1", "email": "student1@juku.local", "password": "student123", "full_name": "Suzuki Taro", "role": "student"},
    {"username": "student2", "email": "student2@juku.local", "password": "student123", "full_name": "Yamada Hanako", "role": "student"},
]


async def main() -> None:
    async with async_session_factory() as db:
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
        await db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
