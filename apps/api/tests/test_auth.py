import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import _insert_test_user


@pytest.mark.asyncio
async def test_public_register_disabled(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "username": "hacker",
        "email": "hacker@test.com",
        "password": "testpass123",
        "full_name": "Hacker",
        "role": "superadmin",
    })
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_and_me(client: AsyncClient):
    uname = f"user_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(
        username=uname,
        email=f"{uname}@test.com",
        password="testpass123",
        full_name="Test User",
    )

    resp = await client.post("/api/auth/login", json={"username": uname, "password": "testpass123"})
    assert resp.status_code == 200
    tokens = resp.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == uname


@pytest.mark.asyncio
async def test_login_username_case_insensitive(client: AsyncClient):
    uname = f"user_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", password="testpass123")

    resp = await client.post(
        "/api/auth/login",
        json={"username": uname.upper(), "password": "testpass123"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    uname = f"user_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", password="testpass123")
    resp = await client.post("/api/auth/login", json={"username": uname, "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    uname = f"user_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", password="testpass123")
    login_resp = await client.post("/api/auth/login", json={"username": uname, "password": "testpass123"})
    tokens = login_resp.json()
    resp = await client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
