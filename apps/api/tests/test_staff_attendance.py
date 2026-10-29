import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_staff(
    client: AsyncClient, token: str, location_id: str, can_take_attendance: bool = True
) -> dict:
    resp = await client.post(
        "/api/units",
        json={
            "code": f"STF-{uuid.uuid4().hex[:6]}",
            "full_name": "Scanner Staff",
            "unit_type": "staff",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
            "staff_profile": {"can_take_attendance": can_take_attendance},
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_student(client: AsyncClient, token: str, location_id: str) -> dict:
    resp = await client.post(
        "/api/units",
        json={
            "code": f"STU-{uuid.uuid4().hex[:6]}",
            "full_name": "Scan Target",
            "unit_type": "student",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _staff_token(client: AsyncClient, admin_token: str, staff: dict) -> str:
    resp = await client.post(
        f"/api/staff-profiles/{staff['id']}/shift-pin", headers=_auth(admin_token)
    )
    assert resp.status_code == 200, resp.text
    pin = resp.json()["pin"]
    login = await client.post(
        "/api/staff-shifts/login", json={"code": staff["code"], "pin": pin}
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


async def _qr_token(client: AsyncClient, admin_token: str, unit_id: str) -> str:
    resp = await client.get(f"/api/qr/token/{unit_id}", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    return resp.json()["qr_token"]


async def test_staff_without_permission_gets_403(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_unit: dict
):
    staff = await _create_staff(
        client, admin_token, sample_location["id"], can_take_attendance=False
    )
    token = await _staff_token(client, admin_token, staff)
    headers = _auth(token)
    qr = await _qr_token(client, admin_token, sample_unit["id"])

    preview = await client.post(
        "/api/staff-shifts/attendance/scan/preview",
        json={"qr_token": qr, "location_id": sample_location["id"]},
        headers=headers,
    )
    assert preview.status_code == 403

    scan = await client.post(
        "/api/staff-shifts/attendance/scan",
        json={"qr_token": qr, "location_id": sample_location["id"]},
        headers=headers,
    )
    assert scan.status_code == 403

    listed = await client.get("/api/staff-shifts/attendance", headers=headers)
    assert listed.status_code == 403


async def test_staff_scan_records_recorded_by_unit(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_unit: dict
):
    staff = await _create_staff(client, admin_token, sample_location["id"])
    token = await _staff_token(client, admin_token, staff)
    headers = _auth(token)
    qr = await _qr_token(client, admin_token, sample_unit["id"])

    preview = await client.post(
        "/api/staff-shifts/attendance/scan/preview",
        json={"qr_token": qr, "location_id": sample_location["id"]},
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["unit_id"] == sample_unit["id"]
    assert preview.json()["unit_type"] == "student"

    scan = await client.post(
        "/api/staff-shifts/attendance/scan",
        json={"qr_token": qr, "location_id": sample_location["id"], "event_type": "check_in"},
        headers=headers,
    )
    assert scan.status_code == 200, scan.text
    event = scan.json()
    assert event["recorded_by_unit_id"] == staff["id"]
    assert event["recorded_by_user_id"] is None
    assert event["unit_id"] == sample_unit["id"]


async def test_staff_scan_rejects_location_not_allowed(
    client: AsyncClient,
    admin_token: str,
    sample_location: dict,
    sample_location_b: dict,
    sample_unit: dict,
):
    staff = await _create_staff(client, admin_token, sample_location["id"])
    token = await _staff_token(client, admin_token, staff)
    qr = await _qr_token(client, admin_token, sample_unit["id"])

    resp = await client.post(
        "/api/staff-shifts/attendance/scan",
        json={"qr_token": qr, "location_id": sample_location_b["id"]},
        headers=_auth(token),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Location not allowed for this staff"

    missing = await client.post(
        "/api/staff-shifts/attendance/scan",
        json={"qr_token": qr},
        headers=_auth(token),
    )
    assert missing.status_code == 400


async def test_staff_list_only_own_scans_today(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_unit: dict
):
    staff_a = await _create_staff(client, admin_token, sample_location["id"])
    staff_b = await _create_staff(client, admin_token, sample_location["id"])
    token_a = await _staff_token(client, admin_token, staff_a)
    token_b = await _staff_token(client, admin_token, staff_b)
    location_id = sample_location["id"]

    # Admin-scanned event — must not appear in either staff list.
    unit_admin = await _create_student(client, admin_token, location_id)
    qr_admin = await _qr_token(client, admin_token, unit_admin["id"])
    admin_scan = await client.post(
        "/api/attendance/scan",
        json={"qr_token": qr_admin, "location_id": location_id, "event_type": "check_in"},
        headers=_auth(admin_token),
    )
    assert admin_scan.status_code == 200

    # Staff B-scanned event — must not appear in staff A's list.
    unit_b = await _create_student(client, admin_token, location_id)
    qr_b = await _qr_token(client, admin_token, unit_b["id"])
    scan_b = await client.post(
        "/api/staff-shifts/attendance/scan",
        json={"qr_token": qr_b, "location_id": location_id, "event_type": "check_in"},
        headers=_auth(token_b),
    )
    assert scan_b.status_code == 200, scan_b.text

    qr_a = await _qr_token(client, admin_token, sample_unit["id"])
    scan_a = await client.post(
        "/api/staff-shifts/attendance/scan",
        json={"qr_token": qr_a, "location_id": location_id, "event_type": "check_in"},
        headers=_auth(token_a),
    )
    assert scan_a.status_code == 200, scan_a.text
    event_a_id = scan_a.json()["id"]

    listed = await client.get("/api/staff-shifts/attendance", headers=_auth(token_a))
    assert listed.status_code == 200, listed.text
    ids = [e["id"] for e in listed.json()]
    assert ids == [event_a_id]
    assert int(listed.headers["X-Total-Count"]) == 1


async def test_token_type_enforcement(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_unit: dict
):
    staff = await _create_staff(client, admin_token, sample_location["id"])
    staff_token = await _staff_token(client, admin_token, staff)
    qr = await _qr_token(client, admin_token, sample_unit["id"])
    body = {"qr_token": qr, "location_id": sample_location["id"]}

    # Admin token cannot use staff endpoints.
    assert (
        await client.post(
            "/api/staff-shifts/attendance/scan", json=body, headers=_auth(admin_token)
        )
    ).status_code == 401
    assert (
        await client.get("/api/staff-shifts/attendance", headers=_auth(admin_token))
    ).status_code == 401

    # Staff token cannot use the admin scan endpoint.
    assert (
        await client.post(
            "/api/attendance/scan", json=body, headers=_auth(staff_token)
        )
    ).status_code == 401


async def test_can_take_attendance_in_login_me_and_profile_default(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    staff = await _create_staff(client, admin_token, sample_location["id"])
    pin_resp = await client.post(
        f"/api/staff-profiles/{staff['id']}/shift-pin", headers=_auth(admin_token)
    )
    pin = pin_resp.json()["pin"]

    login = await client.post(
        "/api/staff-shifts/login", json={"code": staff["code"], "pin": pin}
    )
    assert login.status_code == 200
    assert login.json()["unit"]["can_take_attendance"] is True

    me = await client.get(
        "/api/staff-shifts/me", headers=_auth(login.json()["access_token"])
    )
    assert me.status_code == 200
    assert me.json()["can_take_attendance"] is True

    # A staff profile created without the flag defaults to true.
    plain = await client.post(
        "/api/units",
        json={
            "code": f"STF-{uuid.uuid4().hex[:6]}",
            "full_name": "Default Staff",
            "unit_type": "staff",
            "registered_location_id": sample_location["id"],
            "scan_location_ids": [sample_location["id"]],
        },
        headers=_auth(admin_token),
    )
    assert plain.status_code == 201, plain.text
    profile = await client.post(
        f"/api/staff-profiles/{plain.json()['id']}",
        json={},
        headers=_auth(admin_token),
    )
    assert profile.status_code in (200, 201), profile.text
    assert profile.json()["can_take_attendance"] is True
