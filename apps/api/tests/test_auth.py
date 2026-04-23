import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    uname = f"user_{uuid.uuid4().hex[:8]}"
    resp = await client.post("/api/auth/register", json={
        "username": uname,
        "email": f"{uname}@test.com",
        "password": "testpass123",
        "full_name": "Test User",
        "role": "student",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == uname
    assert data["role"] == "student"

    resp = await client.post("/api/auth/login", json={"username": uname, "password": "testpass123"})
    assert resp.status_code == 200
    tokens = resp.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == uname


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    uname = f"user_{uuid.uuid4().hex[:8]}"
    await client.post("/api/auth/register", json={
        "username": uname,
        "email": f"{uname}@test.com",
        "password": "testpass123",
        "full_name": "T",
        "role": "student",
    })
    resp = await client.post("/api/auth/login", json={"username": uname, "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_register(client: AsyncClient):
    uname = f"user_{uuid.uuid4().hex[:8]}"
    body = {
        "username": uname,
        "email": f"{uname}@test.com",
        "password": "testpass123",
        "full_name": "T",
        "role": "student",
    }
    resp1 = await client.post("/api/auth/register", json=body)
    assert resp1.status_code == 201
    resp2 = await client.post("/api/auth/register", json=body)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    uname = f"user_{uuid.uuid4().hex[:8]}"
    await client.post("/api/auth/register", json={
        "username": uname,
        "email": f"{uname}@test.com",
        "password": "testpass123",
        "full_name": "T",
        "role": "student",
    })
    login_resp = await client.post("/api/auth/login", json={"username": uname, "password": "testpass123"})
    tokens = login_resp.json()
    resp = await client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
