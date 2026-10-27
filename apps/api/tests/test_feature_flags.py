import pytest
from httpx import AsyncClient

from app.config import settings


async def test_features_reports_inventory_enabled(client: AsyncClient):
    resp = await client.get("/api/features")
    assert resp.status_code == 200
    assert resp.json() == {"inventory": True}


async def test_features_reports_inventory_disabled(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "INVENTORY_ENABLED", False)
    resp = await client.get("/api/features")
    assert resp.status_code == 200
    assert resp.json() == {"inventory": False}


async def test_inventory_routes_404_when_disabled(
    client: AsyncClient, admin_token: str, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "INVENTORY_ENABLED", False)
    resp = await client.get(
        "/api/inventory/items",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


async def test_inventory_routes_ok_when_enabled(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/api/inventory/items",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code != 404
