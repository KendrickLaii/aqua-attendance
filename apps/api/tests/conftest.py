import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
import app.models  # noqa: F401 — register all tables on Base.metadata
from app.main import app as fastapi_app
from app.models.user import User
from app.services.auth import hash_password

TEST_DB_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    """Enable FK enforcement in SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


fastapi_app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _insert_test_user(
    *,
    username: str,
    email: str,
    password: str = "admin123",
    role: str = "admin",
    full_name: str = "Test Admin",
) -> None:
    async with TestSessionLocal() as session:
        session.add(
            User(
                username=username,
                email=email,
                hashed_password=hash_password(password),
                full_name=full_name,
                role=role,
            )
        )
        await session.commit()


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient) -> str:
    uname = f"admin_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com")
    resp = await client.post("/api/auth/login", json={"username": uname, "password": "admin123"})
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def sample_location(client: AsyncClient, admin_token: str) -> dict:
    resp = await client.post(
        "/api/locations",
        json={"name_en": "Test Branch A", "name_zh": "測試分店 A"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def sample_location_b(client: AsyncClient, admin_token: str) -> dict:
    resp = await client.post(
        "/api/locations",
        json={"name_en": "Test Branch B", "name_zh": "測試分店 B"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def sample_product(client: AsyncClient, admin_token: str, sample_location: dict) -> dict:
    """Create a sample product and return its data."""
    code = f"STU-{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/api/products",
        json={
            "code": code,
            "full_name": "Test Student",
            "product_type": "student",
            "registered_location_id": sample_location["id"],
            "scan_location_ids": [sample_location["id"]],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    return resp.json()


def scan_body(qr_token: str, product: dict, **extra) -> dict:
    """Build scan JSON with a whitelisted location_id."""
    location_id = extra.pop("location_id", product["scan_location_ids"][0])
    return {"qr_token": qr_token, "location_id": location_id, **extra}
