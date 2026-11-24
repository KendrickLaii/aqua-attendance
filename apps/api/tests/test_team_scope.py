import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import _insert_test_user

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, role: str) -> str:
    uname = f"{role}_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", role=role)
    resp = await client.post("/api/auth/login", json={"username": uname, "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_unassigned_admin_sees_no_teams_until_assigned(client: AsyncClient) -> None:
    gm = await _login(client, "superadmin")
    manager = await _login(client, "admin")

    created = await client.post("/api/locations", json={"name_en": "North"}, headers=_h(gm))
    assert created.status_code == 201, created.text
    location_id = created.json()["id"]

    hidden = await client.get("/api/locations", headers=_h(manager))
    assert hidden.status_code == 200
    assert hidden.json() == []

    me = await client.get("/api/auth/me", headers=_h(gm))
    assigned = await client.patch(
        f"/api/users/{(await client.get('/api/auth/me', headers=_h(manager))).json()['id']}",
        json={"location_ids": [location_id]},
        headers=_h(gm),
    )
    assert assigned.status_code == 200, assigned.text
    assert me.status_code == 200

    visible = await client.get("/api/locations", headers=_h(manager))
    assert [row["id"] for row in visible.json()] == [location_id]


async def test_admin_manages_user_accounts_inside_own_teams(client: AsyncClient) -> None:
    gm = await _login(client, "superadmin")
    manager = await _login(client, "admin")
    mine = (await client.post("/api/locations", json={"name_en": "Mine"}, headers=_h(gm))).json()["id"]
    other = (await client.post("/api/locations", json={"name_en": "Other"}, headers=_h(gm))).json()["id"]
    manager_id = (await client.get("/api/auth/me", headers=_h(manager))).json()["id"]
    assigned = await client.patch(
        f"/api/users/{manager_id}",
        json={"location_ids": [mine]},
        headers=_h(gm),
    )
    assert assigned.status_code == 200, assigned.text

    blocked_role = await client.post(
        "/api/users",
        json={
            "username": f"nope_{uuid.uuid4().hex[:6]}",
            "email": f"nope_{uuid.uuid4().hex[:6]}@test.com",
            "password": "admin123",
            "full_name": "Nope",
            "role": "admin",
            "location_ids": [mine],
        },
        headers=_h(manager),
    )
    assert blocked_role.status_code == 403

    suffix = uuid.uuid4().hex[:6]
    created = await client.post(
        "/api/users",
        json={
            "username": f"desk_{suffix}",
            "email": f"desk_{suffix}@test.com",
            "password": "admin123",
            "full_name": "Desk",
            "role": "user",
            "location_ids": [mine],
        },
        headers=_h(manager),
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]

    shared = await client.patch(
        f"/api/users/{user_id}",
        json={"location_ids": [mine, other]},
        headers=_h(gm),
    )
    assert shared.status_code == 200, shared.text

    kept = await client.patch(
        f"/api/users/{user_id}",
        json={"location_ids": [mine], "full_name": "Desk 2"},
        headers=_h(manager),
    )
    assert kept.status_code == 200, kept.text
    assert set(kept.json()["location_ids"]) == {mine, other}

    foreign = (await client.post("/api/locations", json={"name_en": "Foreign"}, headers=_h(gm))).json()["id"]
    stolen = await client.patch(
        f"/api/users/{user_id}",
        json={"location_ids": [foreign]},
        headers=_h(manager),
    )
    assert stolen.status_code == 403

    promoted = await client.patch(
        f"/api/users/{user_id}",
        json={"role": "admin"},
        headers=_h(manager),
    )
    assert promoted.status_code == 403

    listed = await client.get("/api/users", headers=_h(manager))
    assert listed.status_code == 200
    assert listed.json()
    assert all(row["role"] == "user" for row in listed.json())
    assert user_id in {row["id"] for row in listed.json()}

    removed = await client.delete(f"/api/users/{user_id}", headers=_h(manager))
    assert removed.status_code == 403


async def test_admin_deletes_payroll_only_for_own_team(client: AsyncClient) -> None:
    gm = await _login(client, "superadmin")
    manager = await _login(client, "admin")
    mine = (await client.post("/api/locations", json={"name_en": "Pay Mine"}, headers=_h(gm))).json()["id"]
    other = (await client.post("/api/locations", json={"name_en": "Pay Other"}, headers=_h(gm))).json()["id"]
    manager_id = (await client.get("/api/auth/me", headers=_h(manager))).json()["id"]
    assert (await client.patch(
        f"/api/users/{manager_id}",
        json={"location_ids": [mine]},
        headers=_h(gm),
    )).status_code == 200

    async def payroll_for(location_id: str) -> str:
        code = f"STF-{uuid.uuid4().hex[:6]}"
        unit = await client.post(
            "/api/units",
            json={
                "code": code,
                "full_name": "Pay Staff",
                "unit_type": "staff",
                "registered_location_id": location_id,
                "scan_location_ids": [location_id],
            },
            headers=_h(gm),
        )
        assert unit.status_code == 201, unit.text
        created = await client.post(
            "/api/payroll-records",
            json={
                "unit_id": unit.json()["id"],
                "payroll_period_start": "2026-07-01",
                "payroll_period_end": "2026-07-31",
                "gross_pay": 1000,
                "net_pay": 1000,
                "status": "draft",
            },
            headers=_h(gm),
        )
        assert created.status_code == 201, created.text
        return created.json()["id"]

    own = await payroll_for(mine)
    foreign = await payroll_for(other)
    assert (await client.delete(f"/api/payroll-records/{foreign}", headers=_h(manager))).status_code == 403
    deleted = await client.delete(f"/api/payroll-records/{own}", headers=_h(manager))
    assert deleted.status_code == 204, deleted.text


async def test_staff_web_account_cannot_open_payroll(client: AsyncClient) -> None:
    token = await _login(client, "user")
    resp = await client.get("/api/payroll-records", headers=_h(token))
    assert resp.status_code == 403


async def test_same_service_code_can_exist_on_two_teams(client: AsyncClient, admin_token: str) -> None:
    headers = _h(admin_token)
    first = (await client.post("/api/locations", json={"name_en": "A"}, headers=headers)).json()["id"]
    second = (await client.post("/api/locations", json={"name_en": "B"}, headers=headers)).json()["id"]
    code = f"SVC-{uuid.uuid4().hex[:5]}"
    one = await client.post(
        "/api/course-spus",
        json={"location_id": first, "code": code, "name_zh": "甲"},
        headers=headers,
    )
    two = await client.post(
        "/api/course-spus",
        json={"location_id": second, "code": code, "name_zh": "乙"},
        headers=headers,
    )
    assert one.status_code == 201, one.text
    assert two.status_code == 201, two.text
    assert one.json()["id"] != two.json()["id"]
