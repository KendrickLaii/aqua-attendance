import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

FUTURE = (date.today() + timedelta(days=14)).isoformat()
PAST = "2020-01-06"


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


async def _set_pin(client: AsyncClient, token: str, unit_id: str) -> str:
    resp = await client.post(f"/api/staff-profiles/{unit_id}/shift-pin", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["pin"]) == 6
    assert body["pin"].isdigit()
    assert "shift_pin_hash" not in body
    return body["pin"]


async def _login(client: AsyncClient, code: str, pin: str):
    return await client.post("/api/staff-shifts/login", json={"code": code, "pin": pin})


async def test_admin_sets_pin_once_and_staff_logs_in(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    staff = await _create_staff(client, admin_token, sample_location["id"])
    pin = await _set_pin(client, admin_token, staff["id"])

    listed = await client.get(f"/api/units/{staff['id']}", headers=_auth(admin_token))
    profile = listed.json()["staff_profile"]
    assert profile["shift_pin_set"] is True
    assert "shift_pin_hash" not in profile
    assert pin not in listed.text

    resp = await _login(client, staff["code"], pin)
    assert resp.status_code == 200, resp.text
    assert resp.json()["unit"]["id"] == staff["id"]
    assert resp.cookies.get("staff_shift_access")

    me = await client.get("/api/staff-shifts/me", headers=_auth(resp.json()["access_token"]))
    assert me.status_code == 200
    assert me.json()["code"] == staff["code"]


async def test_staff_login_rejects_bad_pin_inactive_and_students(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_unit: dict
):
    staff = await _create_staff(client, admin_token, sample_location["id"])
    pin = await _set_pin(client, admin_token, staff["id"])

    bad = await _login(client, staff["code"], "000000" if pin != "000000" else "111111")
    assert bad.status_code == 401

    student_pin = await client.post(f"/api/staff-profiles/{sample_unit['id']}/shift-pin", headers=_auth(admin_token))
    assert student_pin.status_code == 422

    inactive = await client.patch(f"/api/units/{staff['id']}", json={"is_active": False}, headers=_auth(admin_token))
    assert inactive.status_code == 200
    blocked = await _login(client, staff["code"], pin)
    assert blocked.status_code == 403


async def test_staff_token_cannot_write_admin_shifts(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    staff = await _create_staff(client, admin_token, sample_location["id"])
    pin = await _set_pin(client, admin_token, staff["id"])
    login = await _login(client, staff["code"], pin)
    token = login.json()["access_token"]

    resp = await client.post(
        "/api/shifts",
        json={
            "unit_id": staff["id"],
            "location_id": sample_location["id"],
            "shift_date": FUTURE,
            "start_time": "09:00",
            "end_time": "13:00",
            "color": "#4CAF50",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 401


async def test_staff_request_rules_and_cancel(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_location_b: dict
):
    staff = await _create_staff(client, admin_token, sample_location["id"])
    pin = await _set_pin(client, admin_token, staff["id"])
    token = (await _login(client, staff["code"], pin)).json()["access_token"]
    headers = _auth(token)

    past = await client.post(
        "/api/staff-shifts/requests",
        json={
            "location_id": sample_location["id"],
            "shift_date": PAST,
            "start_time": "09:00",
            "end_time": "13:00",
            "color": "#4CAF50",
        },
        headers=headers,
    )
    assert past.status_code == 422

    other_branch = await client.post(
        "/api/staff-shifts/requests",
        json={
            "location_id": sample_location_b["id"],
            "shift_date": FUTURE,
            "start_time": "09:00",
            "end_time": "13:00",
            "color": "#4CAF50",
        },
        headers=headers,
    )
    assert other_branch.status_code == 422

    created = await client.post(
        "/api/staff-shifts/requests",
        json={
            "location_id": sample_location["id"],
            "shift_date": FUTURE,
            "start_time": "09:00",
            "end_time": "13:00",
            "title": "Morning",
            "color": "#4CAF50",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    assert created.json()["status"] == "pending"
    assert created.json()["unit_id"] == staff["id"]

    overlap = await client.post(
        "/api/staff-shifts/requests",
        json={
            "location_id": sample_location["id"],
            "shift_date": FUTURE,
            "start_time": "12:00",
            "end_time": "15:00",
            "color": "#2196F3",
        },
        headers=headers,
    )
    assert overlap.status_code == 409

    cancelled = await client.delete(f"/api/staff-shifts/requests/{request_id}", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


async def test_approve_copies_shift_and_reject_is_visible(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    staff = await _create_staff(client, admin_token, sample_location["id"])
    pin = await _set_pin(client, admin_token, staff["id"])
    token = (await _login(client, staff["code"], pin)).json()["access_token"]
    headers = _auth(token)

    first = await client.post(
        "/api/staff-shifts/requests",
        json={
            "location_id": sample_location["id"],
            "shift_date": FUTURE,
            "start_time": "09:00",
            "end_time": "12:00",
            "title": "Morning",
            "color": "#4CAF50",
        },
        headers=headers,
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        "/api/staff-shifts/requests",
        json={
            "location_id": sample_location["id"],
            "shift_date": FUTURE,
            "start_time": "14:00",
            "end_time": "18:00",
            "color": "#FF9800",
        },
        headers=headers,
    )
    assert second.status_code == 201, second.text

    pending = await client.get("/api/shift-requests", params={"status": "pending"}, headers=_auth(admin_token))
    assert pending.status_code == 200
    assert {row["id"] for row in pending.json()} >= {first.json()["id"], second.json()["id"]}

    approved = await client.post(f"/api/shift-requests/{first.json()['id']}/approve", headers=_auth(admin_token))
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    shift_id = approved.json()["shift_id"]
    assert shift_id

    listed = await client.get(
        "/api/shifts", params={"start": FUTURE, "end": FUTURE}, headers=_auth(admin_token)
    )
    match = next(s for s in listed.json() if s["id"] == shift_id)
    assert match["unit_id"] == staff["id"]
    assert match["created_by_id"] is not None
    assert match["title"] == "Morning"

    clash = await client.post(
        "/api/shifts",
        json={
            "unit_id": staff["id"],
            "location_id": sample_location["id"],
            "shift_date": FUTURE,
            "start_time": "13:00",
            "end_time": "16:00",
            "color": "#9C27B0",
        },
        headers=_auth(admin_token),
    )
    assert clash.status_code == 201, clash.text

    rejected = await client.post(
        f"/api/shift-requests/{second.json()['id']}/approve",
        headers=_auth(admin_token),
    )
    assert rejected.status_code == 409

    again = await client.post(
        "/api/staff-shifts/requests",
        json={
            "location_id": sample_location["id"],
            "shift_date": FUTURE,
            "start_time": "18:00",
            "end_time": "20:00",
            "color": "#607D8B",
        },
        headers=headers,
    )
    assert again.status_code == 201, again.text
    denied = await client.post(
        f"/api/shift-requests/{again.json()['id']}/reject",
        json={"reason": "Already covered"},
        headers=_auth(admin_token),
    )
    assert denied.status_code == 200
    assert denied.json()["status"] == "rejected"
    assert denied.json()["reject_reason"] == "Already covered"

    week = await client.get(
        "/api/staff-shifts/week", params={"start": FUTURE, "end": FUTURE}, headers=headers
    )
    assert week.status_code == 200, week.text
    body = week.json()
    assert shift_id in [s["id"] for s in body["shifts"]]
    assert any(r["status"] == "rejected" and r["reject_reason"] == "Already covered" for r in body["requests"])
    assert all(r["unit_id"] == staff["id"] for r in body["requests"])
