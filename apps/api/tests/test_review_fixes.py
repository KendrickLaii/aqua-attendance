"""Tests for backend review fixes (2026-05)."""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from tests.conftest import _insert_test_user, scan_body


@pytest.mark.asyncio
async def test_health_includes_database(client: AsyncClient) -> None:
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


@pytest.mark.asyncio
async def test_refresh_token_rotation(client: AsyncClient) -> None:
    uname = f"user_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", password="testpass123")
    login = await client.post("/api/auth/login", json={"username": uname, "password": "testpass123"})
    old_refresh = login.json()["refresh_token"]

    refreshed = await client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 200

    reuse = await client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_scan_rejects_manual_correction_event_type(
    client: AsyncClient, admin_token: str, sample_product: dict
) -> None:
    qr = await client.get(
        f"/api/qr/token/{sample_product['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.post(
        "/api/attendance/scan",
        json={
            "qr_token": qr.json()["qr_token"],
            "event_type": "manual_correction",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_product_with_events_blocked(
    client: AsyncClient, admin_token: str, sample_product: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    product_id = sample_product["id"]
    qr = await client.get(f"/api/qr/token/{product_id}", headers=headers)
    await client.post(
        "/api/attendance/scan",
        json=scan_body(qr.json()["qr_token"], sample_product, event_type="check_in"),
        headers=headers,
    )

    delete = await client.delete(f"/api/products/{product_id}", headers=headers)
    assert delete.status_code == 409
    assert "attendance" in delete.json()["detail"].lower()


@pytest.mark.asyncio
async def test_export_csv_requires_date_range(
    client: AsyncClient, admin_token: str
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    missing = await client.get("/api/attendance/export/csv", headers=headers)
    assert missing.status_code == 422


@pytest.mark.asyncio
async def test_debounce_allows_opposite_action_within_window(
    client: AsyncClient, admin_token: str, sample_product: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    qr_token = (
        await client.get(
            f"/api/qr/token/{sample_product['id']}",
            headers=headers,
        )
    ).json()["qr_token"]

    first = await client.post(
        "/api/attendance/scan",
        json=scan_body(qr_token, sample_product, event_type="check_in"),
        headers=headers,
    )
    assert first.status_code == 200
    assert first.json()["event_type"] == "check_in"

    second = await client.post(
        "/api/attendance/scan",
        json=scan_body(qr_token, sample_product, event_type="check_out"),
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["event_type"] == "check_out"
    assert second.json()["id"] != first.json()["id"]


@pytest.mark.asyncio
async def test_admin_cannot_get_superadmin_user(client: AsyncClient) -> None:
    admin_uname = f"admin_{uuid.uuid4().hex[:8]}"
    super_uname = f"super_{uuid.uuid4().hex[:8]}"

    await _insert_test_user(
        username=super_uname,
        email=f"{super_uname}@test.com",
        password="testpass123",
        role="superadmin",
    )
    await _insert_test_user(
        username=admin_uname,
        email=f"{admin_uname}@test.com",
        password="testpass123",
        role="admin",
    )

    super_login = await client.post(
        "/api/auth/login",
        json={"username": super_uname, "password": "testpass123"},
    )
    super_user = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {super_login.json()['access_token']}"},
    )
    super_id = super_user.json()["id"]

    admin_login = await client.post(
        "/api/auth/login",
        json={"username": admin_uname, "password": "testpass123"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    resp = await client.get(f"/api/users/{super_id}", headers=admin_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    uname = f"user_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", password="testpass123")
    login = await client.post("/api/auth/login", json={"username": uname, "password": "testpass123"})
    refresh = login.json()["refresh_token"]

    logout = await client.post("/api/auth/logout", json={"refresh_token": refresh})
    assert logout.status_code == 204

    reuse = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_logout_idempotent_on_invalid_token(client: AsyncClient) -> None:
    resp = await client.post("/api/auth/logout", json={"refresh_token": "not-a-valid-jwt"})
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_superadmin_cannot_delete_self(client: AsyncClient) -> None:
    uname = f"super_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(
        username=uname,
        email=f"{uname}@test.com",
        password="testpass123",
        role="superadmin",
    )
    login = await client.post("/api/auth/login", json={"username": uname, "password": "testpass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await client.get("/api/auth/me", headers=headers)

    resp = await client.delete(f"/api/users/{me.json()['id']}", headers=headers)
    assert resp.status_code == 409
    assert "own account" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_list_users_superadmin_role_filter_422(client: AsyncClient) -> None:
    uname = f"admin_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", password="admin123", role="admin")
    login = await client.post("/api/auth/login", json={"username": uname, "password": "admin123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/users", params={"role": "superadmin"}, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_product_invalid_product_type_422(
    client: AsyncClient, admin_token: str
) -> None:
    code = f"BAD-{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/api/products",
        json={"code": code, "full_name": "Bad Type", "product_type": "teacher"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_location_create_requires_name_en(client: AsyncClient, admin_token: str) -> None:
    resp = await client.post(
        "/api/locations",
        json={"name_zh": "只有中文", "is_active": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_purges_expired_refresh_tokens(client: AsyncClient) -> None:
    from datetime import timedelta

    from sqlalchemy import func, select

    from app.models.refresh_token import RefreshToken
    from app.models.user import User
    from tests.conftest import TestSessionLocal

    uname = f"user_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", password="testpass123")

    async with TestSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == uname))
        user = result.scalar_one()
        session.add(
            RefreshToken(
                jti=f"expired_{uuid.uuid4().hex}",
                user_id=user.id,
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )
        await session.commit()

    async with TestSessionLocal() as session:
        before = await session.scalar(
            select(func.count()).select_from(RefreshToken).where(
                RefreshToken.expires_at <= datetime.now(timezone.utc)
            )
        )
        assert before == 1

    await client.post("/api/auth/login", json={"username": uname, "password": "testpass123"})

    async with TestSessionLocal() as session:
        after = await session.scalar(
            select(func.count()).select_from(RefreshToken).where(
                RefreshToken.expires_at <= datetime.now(timezone.utc)
            )
        )
        assert after == 0
