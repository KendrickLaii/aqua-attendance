"""Admin image upload → stored file → public GET by relative /api/uploads URL."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import settings

# 1×1 PNG (valid signature + IHDR)
MIN_PNG = bytes(
    [
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53, 0xDE,
        0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41, 0x54,
        0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00, 0x00,
        0x00, 0x02, 0x00, 0x01, 0xE2, 0x21, 0xBC, 0x33,
        0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
        0xAE, 0x42, 0x60, 0x82,
    ]
)

MIN_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16 + b"\xff\xd9"


@pytest.fixture(autouse=True)
def _isolated_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


async def _upload(
    client: AsyncClient,
    token: str | None,
    content: bytes,
    filename: str,
    content_type: str,
):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return await client.post(
        "/api/uploads",
        files={"file": (filename, content, content_type)},
        headers=headers,
    )


@pytest.mark.asyncio
async def test_admin_upload_png_returns_relative_url(client: AsyncClient, admin_token: str) -> None:
    resp = await _upload(client, admin_token, MIN_PNG, "logo.png", "image/png")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["url"].startswith("/api/uploads/")
    assert body["url"].endswith(".png")
    assert not body["url"].startswith("http")
    assert body["content_type"] == "image/png"
    assert body["size"] == len(MIN_PNG)
    assert body["key"] in body["url"]


@pytest.mark.asyncio
async def test_get_uploaded_file_is_public(client: AsyncClient, admin_token: str) -> None:
    uploaded = await _upload(client, admin_token, MIN_PNG, "icon.png", "image/png")
    url = uploaded.json()["url"]

    client.cookies.clear()
    anonymous = await client.get(url)
    assert anonymous.status_code == 200
    assert anonymous.headers["content-type"].startswith("image/png")
    assert anonymous.content == MIN_PNG


@pytest.mark.asyncio
async def test_upload_requires_auth(client: AsyncClient) -> None:
    resp = await _upload(client, None, MIN_PNG, "logo.png", "image/png")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_rejects_non_image(client: AsyncClient, admin_token: str) -> None:
    resp = await _upload(client, admin_token, b"not-an-image", "notes.txt", "text/plain")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rejects_spoofed_png_content_type(client: AsyncClient, admin_token: str) -> None:
    resp = await _upload(client, admin_token, b"hello world", "fake.png", "image/png")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rejects_file_over_max_bytes(
    client: AsyncClient, admin_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "UPLOAD_MAX_BYTES", 32)
    resp = await _upload(client, admin_token, MIN_PNG, "big.png", "image/png")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_jpeg(client: AsyncClient, admin_token: str) -> None:
    resp = await _upload(client, admin_token, MIN_JPEG, "photo.jpg", "image/jpeg")
    assert resp.status_code == 200, resp.text
    assert resp.json()["url"].endswith(".jpg")
    got = await client.get(
        resp.json()["url"],
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert got.status_code == 200
    assert got.content == MIN_JPEG


@pytest.mark.asyncio
async def test_get_missing_upload_is_404(client: AsyncClient, admin_token: str) -> None:
    resp = await client.get(
        "/api/uploads/2099/01/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_rejects_path_traversal(client: AsyncClient) -> None:
    resp = await client.get("/api/uploads/../test_uploads.py")
    assert resp.status_code in (400, 404)
