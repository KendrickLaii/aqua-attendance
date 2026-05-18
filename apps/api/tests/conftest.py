import asyncio
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    """Enable FK enforcement in SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient) -> str:
    uname = f"admin_{uuid.uuid4().hex[:8]}"
    await client.post("/api/auth/register", json={
        "username": uname,
        "email": f"{uname}@test.com",
        "password": "admin123",
        "full_name": "Test Admin",
        "role": "admin",
    })
    resp = await client.post("/api/auth/login", json={"username": uname, "password": "admin123"})
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def sample_product(client: AsyncClient, admin_token: str) -> dict:
    """Create a sample product and return its data."""
    code = f"STU-{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/api/products",
        json={
            "code": code,
            "full_name": "Test Student",
            "product_type": "student",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp.json()
