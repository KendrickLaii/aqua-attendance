import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

MONDAY = "2026-09-28"
NEXT_MONDAY = "2026-10-05"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_staff(client: AsyncClient, token: str, location_id: str, **extra) -> dict:
    resp = await client.post(
        "/api/units",
        json={
            "code": f"STF-{uuid.uuid4().hex[:6]}",
            "full_name": "Test Staff",
            "unit_type": "staff",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
            **extra,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_shift(client: AsyncClient, token: str, unit: dict, location_id: str, **extra) -> dict:
    body = {
        "unit_id": unit["id"],
        "location_id": location_id,
        "shift_date": MONDAY,
        "start_time": "09:00",
        "end_time": "13:00",
        "title": "Morning",
        "color": "#4CAF50",
        **extra,
    }
    resp = await client.post("/api/shifts", json=body, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_shifts_require_auth(client: AsyncClient):
    resp = await client.get("/api/shifts", params={"start": MONDAY, "end": MONDAY})
    assert resp.status_code == 401
    resp = await client.get("/api/shift-templates")
    assert resp.status_code == 401


async def test_template_crud_and_delete_keeps_shift(client: AsyncClient, admin_token: str, sample_location: dict):
    resp = await client.post(
        "/api/shift-templates",
        json={"name": "Morning", "start_time": "09:00", "end_time": "13:00", "color": "#4CAF50"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    template = resp.json()

    resp = await client.patch(
        f"/api/shift-templates/{template['id']}", json={"color": "#9C27B0"}, headers=_auth(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["color"] == "#9C27B0"

    resp = await client.patch(
        f"/api/shift-templates/{template['id']}", json={"end_time": "08:00"}, headers=_auth(admin_token)
    )
    assert resp.status_code == 422

    staff = await _create_staff(client, admin_token, sample_location["id"])
    shift = await _create_shift(client, admin_token, staff, sample_location["id"], template_id=template["id"])

    resp = await client.delete(f"/api/shift-templates/{template['id']}", headers=_auth(admin_token))
    assert resp.status_code == 204

    resp = await client.get("/api/shifts", params={"start": MONDAY, "end": MONDAY}, headers=_auth(admin_token))
    assert [s["id"] for s in resp.json()] == [shift["id"]]
    assert resp.json()[0]["template_id"] is None
    assert resp.json()[0]["title"] == "Morning"


async def test_template_validation(client: AsyncClient, admin_token: str):
    bad = [
        {"name": "X", "start_time": "13:00", "end_time": "09:00", "color": "#4CAF50"},
        {"name": "X", "start_time": "09:00", "end_time": "13:00", "color": "green"},
        {"name": "", "start_time": "09:00", "end_time": "13:00", "color": "#4CAF50"},
    ]
    for body in bad:
        resp = await client.post("/api/shift-templates", json=body, headers=_auth(admin_token))
        assert resp.status_code == 422, body


async def test_shift_crud(client: AsyncClient, admin_token: str, sample_location: dict):
    staff = await _create_staff(client, admin_token, sample_location["id"])
    shift = await _create_shift(client, admin_token, staff, sample_location["id"], notes="cover")
    assert shift["start_time"] == "09:00:00"
    assert shift["created_by_id"] is not None

    resp = await client.patch(
        f"/api/shifts/{shift['id']}", json={"end_time": "14:30", "notes": None}, headers=_auth(admin_token)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["end_time"] == "14:30:00"
    assert resp.json()["notes"] is None

    resp = await client.patch(f"/api/shifts/{shift['id']}", json={"end_time": "08:00"}, headers=_auth(admin_token))
    assert resp.status_code == 422

    resp = await client.delete(f"/api/shifts/{shift['id']}", headers=_auth(admin_token))
    assert resp.status_code == 204
    resp = await client.delete(f"/api/shifts/{shift['id']}", headers=_auth(admin_token))
    assert resp.status_code == 404


async def test_shift_rejects_non_staff_and_bad_times(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_unit: dict
):
    base = {
        "location_id": sample_location["id"],
        "shift_date": MONDAY,
        "start_time": "09:00",
        "end_time": "13:00",
        "color": "#4CAF50",
    }
    resp = await client.post("/api/shifts", json={**base, "unit_id": sample_unit["id"]}, headers=_auth(admin_token))
    assert resp.status_code == 422
    assert "staff" in resp.json()["detail"]

    staff = await _create_staff(client, admin_token, sample_location["id"])
    resp = await client.post(
        "/api/shifts", json={**base, "unit_id": staff["id"], "end_time": "09:00"}, headers=_auth(admin_token)
    )
    assert resp.status_code == 422

    resp = await client.post(
        "/api/shifts",
        json={**base, "unit_id": staff["id"], "location_id": str(uuid.uuid4())},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


async def test_list_filters_and_overlap_allowed(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_location_b: dict
):
    staff = await _create_staff(client, admin_token, sample_location["id"])
    a = await _create_shift(client, admin_token, staff, sample_location["id"])
    overlap = await _create_shift(client, admin_token, staff, sample_location["id"], start_time="12:00", end_time="15:00")
    b = await _create_shift(client, admin_token, staff, sample_location_b["id"], shift_date="2026-10-01")
    await _create_shift(client, admin_token, staff, sample_location["id"], shift_date=NEXT_MONDAY)

    resp = await client.get(
        "/api/shifts", params={"start": MONDAY, "end": "2026-10-04"}, headers=_auth(admin_token)
    )
    assert [s["id"] for s in resp.json()] == [a["id"], overlap["id"], b["id"]]

    resp = await client.get(
        "/api/shifts",
        params={"start": MONDAY, "end": "2026-10-04", "location_id": sample_location_b["id"]},
        headers=_auth(admin_token),
    )
    assert [s["id"] for s in resp.json()] == [b["id"]]

    resp = await client.get("/api/shifts", params={"start": "2026-10-04", "end": MONDAY}, headers=_auth(admin_token))
    assert resp.status_code == 422
    resp = await client.get("/api/shifts", params={"start": "2026-01-01", "end": "2026-12-31"}, headers=_auth(admin_token))
    assert resp.status_code == 422


async def test_copy_week_skips_duplicates_and_inactive(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_location_b: dict
):
    active = await _create_staff(client, admin_token, sample_location["id"])
    inactive = await _create_staff(client, admin_token, sample_location["id"])
    await _create_shift(client, admin_token, active, sample_location["id"])
    await _create_shift(client, admin_token, active, sample_location["id"], shift_date="2026-09-30", start_time="18:00", end_time="22:00")
    await _create_shift(client, admin_token, active, sample_location_b["id"], shift_date="2026-10-02")
    await _create_shift(client, admin_token, inactive, sample_location["id"])
    resp = await client.patch(f"/api/units/{inactive['id']}", json={"is_active": False}, headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text

    # Already exists in the target week -> skipped.
    await _create_shift(client, admin_token, active, sample_location["id"], shift_date=NEXT_MONDAY)

    resp = await client.post(
        "/api/shifts/copy-week",
        json={"source_week_start": MONDAY, "target_week_start": NEXT_MONDAY, "location_id": sample_location["id"]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"created": 1, "skipped": 2}

    resp = await client.get(
        "/api/shifts", params={"start": NEXT_MONDAY, "end": "2026-10-11"}, headers=_auth(admin_token)
    )
    target = resp.json()
    assert sorted((s["shift_date"], s["start_time"]) for s in target) == [
        ("2026-10-05", "09:00:00"),
        ("2026-10-07", "18:00:00"),
    ]

    # Without a location filter the branch-B shift is copied too; a second run is idempotent.
    resp = await client.post(
        "/api/shifts/copy-week",
        json={"source_week_start": MONDAY, "target_week_start": NEXT_MONDAY},
        headers=_auth(admin_token),
    )
    assert resp.json() == {"created": 1, "skipped": 3}
    resp = await client.post(
        "/api/shifts/copy-week",
        json={"source_week_start": MONDAY, "target_week_start": NEXT_MONDAY},
        headers=_auth(admin_token),
    )
    assert resp.json() == {"created": 0, "skipped": 4}


async def test_copy_week_requires_mondays(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/shifts/copy-week",
        json={"source_week_start": "2026-09-29", "target_week_start": NEXT_MONDAY},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422
