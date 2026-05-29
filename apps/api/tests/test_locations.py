import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_location_english_only(client: AsyncClient, admin_token: str) -> None:
    """Chinese name is optional in the UI; API should default name_zh from name_en."""
    resp = await client.post(
        "/api/locations",
        json={"name_en": "dummy", "is_active": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name_en"] == "dummy"
    assert body["name_zh"] == "dummy"


@pytest.mark.asyncio
async def test_create_location_payload_matches_ui(client: AsyncClient, admin_token: str) -> None:
    """Same shape as locations.vue when Chinese name is left blank."""
    resp = await client.post(
        "/api/locations",
        json={
            "name_zh": None,
            "name_en": "dummy",
            "is_active": True,
            "business_hours": "Mon 09:00-18:00 · Tue 09:00-18:00 · Wed 09:00-18:00 · Thu 09:00-18:00 · Fri 09:00-18:00",
            "details": {
                "hours_schedule": [
                    {"day": "mon", "isOpen": True, "openTime": "09:00", "closeTime": "18:00"},
                ],
            },
            "address": None,
            "code": None,
            "contact_person": None,
            "detail_photos": None,
            "email": None,
            "icon_url": None,
            "location_type": None,
            "main_photo_url": None,
            "notes": None,
            "phone": None,
            "region": None,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["name_zh"] == "dummy"


@pytest.mark.asyncio
async def test_create_location_with_both_names(client: AsyncClient, admin_token: str) -> None:
    resp = await client.post(
        "/api/locations",
        json={"name_en": "Central Branch", "name_zh": "中環分校", "is_active": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name_en"] == "Central Branch"
    assert body["name_zh"] == "中環分校"
