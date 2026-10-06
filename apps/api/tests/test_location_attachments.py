"""Private monthly location attachments: superadmin only, 2/month, 24-month rolling window."""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import settings
from app.models.location_attachment import LocationAttachment
from app.services.attachments import current_month, earliest_month
from tests.conftest import TestSessionLocal, _insert_test_user
from tests.test_uploads import MIN_PNG


@pytest.fixture(autouse=True)
def _isolated_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


async def _token(client: AsyncClient, role: str) -> str:
    uname = f"{role}_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", role=role)
    resp = await client.post("/api/auth/login", json={"username": uname, "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _location(client: AsyncClient, token: str) -> str:
    resp = await client.post("/api/locations", json={"name_en": "Branch"}, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _upload(client, token, loc, month, name="a.png"):
    return await client.post(
        f"/api/locations/{loc}/attachments",
        files={"file": (name, MIN_PNG, "image/png")},
        data={"month": month, "caption": "cap"},
        headers=_h(token),
    )


@pytest.mark.asyncio
async def test_admin_forbidden_superadmin_allowed(client: AsyncClient) -> None:
    sa = await _token(client, "superadmin")
    admin = await _token(client, "admin")
    loc = await _location(client, sa)

    assert (await _upload(client, admin, loc, current_month())).status_code == 403
    assert (await client.get(f"/api/locations/{loc}/attachments", headers=_h(admin))).status_code == 403

    resp = await _upload(client, sa, loc, current_month())
    assert resp.status_code == 201, resp.text
    att = resp.json()

    listing = (await client.get(f"/api/locations/{loc}/attachments", headers=_h(sa))).json()
    assert listing["per_month"] == 2
    assert [i["id"] for i in listing["items"]] == [att["id"]]

    dl = await client.get(f"/api/locations/{loc}/attachments/{att['id']}/download", headers=_h(sa))
    assert dl.status_code == 200
    assert dl.content == MIN_PNG
    assert "attachment" in dl.headers["content-disposition"]
    client.cookies.clear()
    assert (await client.get(f"/api/locations/{loc}/attachments/{att['id']}/download")).status_code == 401


@pytest.mark.asyncio
async def test_max_two_per_month_and_delete_frees_slot(client: AsyncClient) -> None:
    sa = await _token(client, "superadmin")
    loc = await _location(client, sa)
    month = current_month()

    first = await _upload(client, sa, loc, month)
    assert (await _upload(client, sa, loc, month)).status_code == 201
    assert (await _upload(client, sa, loc, month)).status_code == 409
    assert (await _upload(client, sa, loc, earliest_month())).status_code == 201

    assert (await client.delete(f"/api/locations/{loc}/attachments/{first.json()['id']}", headers=_h(sa))).status_code == 204
    assert (await _upload(client, sa, loc, month)).status_code == 201


@pytest.mark.asyncio
async def test_month_must_be_within_window(client: AsyncClient) -> None:
    sa = await _token(client, "superadmin")
    loc = await _location(client, sa)
    future = f"{(datetime.now(timezone.utc) + timedelta(days=90)):%Y-%m}"

    for bad in ("2000-01", future, "2026-13", "nope"):
        assert (await _upload(client, sa, loc, bad)).status_code == 400


@pytest.mark.asyncio
async def test_rejects_non_image(client: AsyncClient) -> None:
    sa = await _token(client, "superadmin")
    loc = await _location(client, sa)
    resp = await client.post(
        f"/api/locations/{loc}/attachments",
        files={"file": ("x.txt", b"hello", "text/plain")},
        data={"month": current_month()},
        headers=_h(sa),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_attachments_not_publicly_served(client: AsyncClient, _isolated_upload_dir: Path) -> None:
    sa = await _token(client, "superadmin")
    loc = await _location(client, sa)
    att = (await _upload(client, sa, loc, current_month())).json()
    assert (await client.get(f"/api/locations/{loc}/attachments", headers=_h(sa))).status_code == 200
    anon = await client.get("/api/uploads/_attachments/x.png")
    assert anon.status_code in (400, 404)
    assert any(_isolated_upload_dir.rglob("*.png"))
    assert att["id"]


@pytest.mark.asyncio
async def test_expired_months_are_purged(client: AsyncClient, _isolated_upload_dir: Path) -> None:
    sa = await _token(client, "superadmin")
    loc = await _location(client, sa)
    att = (await _upload(client, sa, loc, current_month())).json()

    async with TestSessionLocal() as session:
        row = await session.get(LocationAttachment, uuid.UUID(att["id"]))
        row.month = "2000-01"
        await session.commit()

    listing = (await client.get(f"/api/locations/{loc}/attachments", headers=_h(sa))).json()
    assert listing["items"] == []
    assert not any(_isolated_upload_dir.rglob("*.png"))


@pytest.mark.asyncio
async def test_detail_photos_limited(client: AsyncClient) -> None:
    sa = await _token(client, "superadmin")
    photos = [{"url": f"https://x/{i}.png"} for i in range(settings.MAX_DETAIL_PHOTOS + 1)]
    resp = await client.post("/api/locations", json={"name_en": "B", "detail_photos": photos}, headers=_h(sa))
    assert resp.status_code == 422
