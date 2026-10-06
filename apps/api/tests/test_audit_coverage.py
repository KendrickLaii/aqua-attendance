"""Every mutating endpoint must write an audit row without breaking the request."""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import _insert_test_user

pytestmark = pytest.mark.asyncio

FUTURE = (date.today() + timedelta(days=14)).isoformat()


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _superadmin_token(client: AsyncClient) -> str:
    uname = f"sa_{uuid.uuid4().hex[:8]}"
    await _insert_test_user(username=uname, email=f"{uname}@test.com", role="superadmin")
    resp = await client.post("/api/auth/login", json={"username": uname, "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _logs(client: AsyncClient, token: str, table: str, action: str | None = None) -> list[dict]:
    params = {"table_name": table, "page_size": 200}
    if action:
        params["action"] = action
    resp = await client.get("/api/audit-logs", params=params, headers=_h(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _staff_unit(client: AsyncClient, token: str, location_id: str) -> dict:
    resp = await client.post(
        "/api/units",
        json={
            "code": f"STF-{uuid.uuid4().hex[:6]}",
            "full_name": "Audit Staff",
            "unit_type": "staff",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
        },
        headers=_h(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_audit_rows_capture_ip_and_user_agent_from_request(
    client: AsyncClient, admin_token: str
):
    sa = await _superadmin_token(client)
    headers = {**_h(admin_token), "X-Forwarded-For": "203.0.113.7", "User-Agent": "audit-test/1.0"}
    loc = await client.post("/api/locations", json={"name_en": "IP Branch"}, headers=headers)
    assert loc.status_code == 201, loc.text

    row = next(r for r in await _logs(client, sa, "locations", "CREATE") if r["record_id"] == loc.json()["id"])
    assert row["ip_address"] == "203.0.113.7"
    assert row["user_agent"] == "audit-test/1.0"


async def test_failed_audit_write_does_not_break_the_request(
    client: AsyncClient, admin_token: str, monkeypatch: pytest.MonkeyPatch
):
    from app.services import audit_log as audit_svc

    class _Boom(Exception):
        pass

    real_json_safe = audit_svc._json_safe

    def _explode(data):
        if data and data.get("name_en") == "Boom Branch":
            raise _Boom("audit serialization failed")
        return real_json_safe(data)

    monkeypatch.setattr(audit_svc, "_json_safe", _explode)

    resp = await client.post("/api/locations", json={"name_en": "Boom Branch"}, headers=_h(admin_token))
    assert resp.status_code == 201, resp.text
    listed = await client.get("/api/locations", headers=_h(admin_token))
    assert any(loc["name_en"] == "Boom Branch" for loc in listed.json())


async def test_database_error_in_audit_write_leaves_caller_session_usable():
    from app.models.location import Location
    from app.services import audit_log as audit_svc
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        location = Location(name_en="Savepoint Branch", name_zh="Savepoint Branch")
        session.add(location)
        await session.commit()

        result = await audit_svc.log_audit(
            session,
            user_id=uuid.uuid4(),  # no such user -> FK violation
            action="CREATE",
            table_name="locations",
            record_id=location.id,
        )
        assert result is None
        assert location.name_en == "Savepoint Branch"
        assert (await session.get(Location, location.id)) is not None

        ok = await audit_svc.log_audit(
            session, user_id=None, action="CREATE", table_name="locations", record_id=location.id
        )
        assert ok is not None


async def test_generator_deleting_stale_invoices_is_logged(
    client: AsyncClient, admin_token: str, sample_unit: dict
):
    sa = await _superadmin_token(client)
    spu = (
        await client.post(
            "/api/course-spus",
            json={"code": f"SPU-{uuid.uuid4().hex[:5]}", "name_zh": "課"},
            headers=_h(admin_token),
        )
    ).json()
    sku = (
        await client.post(
            "/api/course-skus",
            json={"spu_id": spu["id"], "code": f"SKU-{uuid.uuid4().hex[:5]}", "name_zh": "班", "price": 100},
            headers=_h(admin_token),
        )
    ).json()
    enrollment = await client.post(
        "/api/course-enrollments",
        json={"unit_id": sample_unit["id"], "sku_id": sku["id"], "start_date": "2026-06-01", "end_date": "2026-08-31"},
        headers=_h(admin_token),
    )
    assert enrollment.status_code == 201, enrollment.text
    enrollment_id = enrollment.json()["id"]

    await client.post("/api/tuition-invoices/generate?year=2026&month=6", headers=_h(admin_token))
    listed = await client.get("/api/tuition-invoices?year=2026&month=6", headers=_h(admin_token))
    invoice_id = listed.json()[0]["id"]

    await client.patch(
        f"/api/course-enrollments/{enrollment_id}", json={"status": "cancelled"}, headers=_h(admin_token)
    )
    result = await client.post("/api/tuition-invoices/generate?year=2026&month=6", headers=_h(admin_token))
    assert result.json()["deleted"] == 1

    rows = [r for r in await _logs(client, sa, "tuition_invoices") if r["record_id"] == invoice_id]
    assert any(r["action"] == "DELETE" and "Generator deleted" in (r["description"] or "") for r in rows)


async def test_manual_invoice_void_issue_and_delete_are_logged(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_unit: dict
):
    sa = await _superadmin_token(client)
    created = await client.post(
        "/api/tuition-invoices/manual",
        json={
            "date": "2026-06-10",
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "lines": [{"month": "2026-06", "course": "Audit", "fee": 100, "qty": 2}],
        },
        headers=_h(admin_token),
    )
    assert created.status_code == 201, created.text
    invoice_id = created.json()["id"]

    edited = await client.patch(
        f"/api/tuition-invoices/{invoice_id}", json={"notes": "typo fixed"}, headers=_h(admin_token)
    )
    assert edited.status_code == 200, edited.text

    voided = await client.patch(
        f"/api/tuition-invoices/{invoice_id}", json={"status": "void"}, headers=_h(admin_token)
    )
    assert voided.status_code == 200, voided.text

    deleted = await client.delete(f"/api/tuition-invoices/{invoice_id}", headers=_h(admin_token))
    assert deleted.status_code == 204, deleted.text

    rows = [r for r in await _logs(client, sa, "tuition_invoices") if r["record_id"] == invoice_id]
    descriptions = " | ".join(r["description"] or "" for r in rows)
    assert {r["action"] for r in rows} == {"CREATE", "UPDATE", "DELETE"}
    assert "from issued to void" in descriptions
    assert "Edited invoice" in descriptions

    void_row = next(r for r in rows if "to void" in (r["description"] or ""))
    assert void_row["old_values"]["status"] == "issued"
    assert void_row["new_values"]["status"] == "void"
    assert void_row["username"]


async def test_shift_template_and_shift_with_time_values_are_logged(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    sa = await _superadmin_token(client)
    staff = await _staff_unit(client, admin_token, sample_location["id"])

    template = await client.post(
        "/api/shift-templates",
        json={"name": "AM", "start_time": "09:00", "end_time": "13:00", "color": "#4CAF50"},
        headers=_h(admin_token),
    )
    assert template.status_code == 201, template.text
    patched = await client.patch(
        f"/api/shift-templates/{template.json()['id']}",
        json={"end_time": "14:00"},
        headers=_h(admin_token),
    )
    assert patched.status_code == 200, patched.text

    shift = await client.post(
        "/api/shifts",
        json={
            "unit_id": staff["id"],
            "location_id": sample_location["id"],
            "shift_date": FUTURE,
            "start_time": "09:00",
            "end_time": "13:00",
            "color": "#4CAF50",
        },
        headers=_h(admin_token),
    )
    assert shift.status_code == 201, shift.text
    shift_id = shift.json()["id"]
    moved = await client.patch(
        f"/api/shifts/{shift_id}", json={"end_time": "15:00"}, headers=_h(admin_token)
    )
    assert moved.status_code == 200, moved.text
    gone = await client.delete(f"/api/shifts/{shift_id}", headers=_h(admin_token))
    assert gone.status_code == 204, gone.text

    shift_rows = [r for r in await _logs(client, sa, "shifts") if r["record_id"] == shift_id]
    assert {r["action"] for r in shift_rows} == {"CREATE", "UPDATE", "DELETE"}
    created_row = next(r for r in shift_rows if r["action"] == "CREATE")
    assert created_row["new_values"]["start_time"] == "09:00:00"
    assert len(await _logs(client, sa, "shift_templates")) == 2


async def test_staff_portal_requests_are_logged_without_user_fk_error(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    sa = await _superadmin_token(client)
    staff = await _staff_unit(client, admin_token, sample_location["id"])
    pin = (await client.post(f"/api/staff-profiles/{staff['id']}/shift-pin", headers=_h(admin_token))).json()["pin"]
    login = await client.post("/api/staff-shifts/login", json={"code": staff["code"], "pin": pin})
    assert login.status_code == 200, login.text
    staff_headers = _h(login.json()["access_token"])

    created = await client.post(
        "/api/staff-shifts/requests",
        json={
            "location_id": sample_location["id"],
            "shift_date": FUTURE,
            "start_time": "09:00",
            "end_time": "13:00",
            "color": "#4CAF50",
        },
        headers=staff_headers,
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    cancelled = await client.delete(f"/api/staff-shifts/requests/{request_id}", headers=staff_headers)
    assert cancelled.status_code == 200, cancelled.text

    rows = [r for r in await _logs(client, sa, "shift_requests") if r["record_id"] == request_id]
    assert {r["action"] for r in rows} == {"CREATE", "UPDATE"}
    assert all(r["user_id"] is None for r in rows)
    assert all(staff["code"] in r["description"] for r in rows)

    pin_rows = [r for r in await _logs(client, sa, "staff_profiles") if "PIN" in (r["description"] or "")]
    assert len(pin_rows) == 1
    assert pin not in (pin_rows[0]["description"] or "")


async def test_admin_shift_request_review_is_logged(
    client: AsyncClient, admin_token: str, sample_location: dict
):
    sa = await _superadmin_token(client)
    staff = await _staff_unit(client, admin_token, sample_location["id"])
    pin = (await client.post(f"/api/staff-profiles/{staff['id']}/shift-pin", headers=_h(admin_token))).json()["pin"]
    token = (await client.post("/api/staff-shifts/login", json={"code": staff["code"], "pin": pin})).json()[
        "access_token"
    ]
    body = {
        "location_id": sample_location["id"],
        "shift_date": FUTURE,
        "start_time": "09:00",
        "end_time": "13:00",
        "color": "#4CAF50",
    }
    first = (await client.post("/api/staff-shifts/requests", json=body, headers=_h(token))).json()
    approved = await client.post(f"/api/shift-requests/{first['id']}/approve", headers=_h(admin_token))
    assert approved.status_code == 200, approved.text

    body["shift_date"] = (date.today() + timedelta(days=15)).isoformat()
    second = (await client.post("/api/staff-shifts/requests", json=body, headers=_h(token))).json()
    rejected = await client.post(
        f"/api/shift-requests/{second['id']}/reject", json={"reason": "full"}, headers=_h(admin_token)
    )
    assert rejected.status_code == 200, rejected.text

    updates = await _logs(client, sa, "shift_requests", "UPDATE")
    descriptions = " | ".join(r["description"] for r in updates)
    assert "Approved shift request" in descriptions
    assert "Rejected shift request" in descriptions


async def test_location_course_and_unit_crud_are_logged(
    client: AsyncClient, admin_token: str
):
    sa = await _superadmin_token(client)
    loc = await client.post("/api/locations", json={"name_en": "Audit Branch"}, headers=_h(admin_token))
    assert loc.status_code == 201, loc.text
    loc_id = loc.json()["id"]
    assert (await client.patch(f"/api/locations/{loc_id}", json={"name_en": "Renamed"}, headers=_h(admin_token))).status_code == 200

    spu = await client.post(
        "/api/course-spus", json={"code": f"SPU-{uuid.uuid4().hex[:5]}", "name_zh": "課", "name_en": "Course"},
        headers=_h(admin_token),
    )
    assert spu.status_code == 201, spu.text
    spu_id = spu.json()["id"]
    sku = await client.post(
        "/api/course-skus",
        json={"spu_id": spu_id, "code": f"SKU-{uuid.uuid4().hex[:5]}", "name_zh": "班", "price": 120.5},
        headers=_h(admin_token),
    )
    assert sku.status_code == 201, sku.text
    sku_id = sku.json()["id"]
    assert (await client.patch(f"/api/course-skus/{sku_id}", json={"price": 99.5}, headers=_h(admin_token))).status_code == 200

    unit = await client.post(
        "/api/units",
        json={
            "code": f"STU-{uuid.uuid4().hex[:6]}",
            "full_name": "Audit Student",
            "unit_type": "student",
            "registered_location_id": loc_id,
            "scan_location_ids": [loc_id],
        },
        headers=_h(admin_token),
    )
    assert unit.status_code == 201, unit.text
    unit_id = unit.json()["id"]
    assert (await client.patch(f"/api/units/{unit_id}", json={"full_name": "Audit Student 2"}, headers=_h(admin_token))).status_code == 200
    assert (await client.delete(f"/api/units/{unit_id}", headers=_h(admin_token))).status_code == 204
    assert (await client.delete(f"/api/course-skus/{sku_id}", headers=_h(admin_token))).status_code == 204
    assert (await client.delete(f"/api/course-spus/{spu_id}", headers=_h(admin_token))).status_code == 204
    assert (await client.delete(f"/api/locations/{loc_id}", headers=_h(admin_token))).status_code == 204

    for table, record_id in (
        ("locations", loc_id),
        ("course_spus", spu_id),
        ("course_skus", sku_id),
        ("units", unit_id),
    ):
        actions = {r["action"] for r in await _logs(client, sa, table) if r["record_id"] == record_id}
        assert {"CREATE", "DELETE"} <= actions, (table, actions)

    sku_update = next(
        r for r in await _logs(client, sa, "course_skus", "UPDATE") if r["record_id"] == sku_id
    )
    assert sku_update["old_values"]["price"] == 120.5
    assert sku_update["new_values"]["price"] == 99.5


async def test_enrollment_notification_and_profile_changes_are_logged(
    client: AsyncClient, admin_token: str, sample_location: dict, sample_unit: dict
):
    sa = await _superadmin_token(client)
    spu = (
        await client.post(
            "/api/course-spus",
            json={"code": f"SPU-{uuid.uuid4().hex[:5]}", "name_zh": "課"},
            headers=_h(admin_token),
        )
    ).json()
    sku = (
        await client.post(
            "/api/course-skus",
            json={"spu_id": spu["id"], "code": f"SKU-{uuid.uuid4().hex[:5]}", "name_zh": "班", "price": 100},
            headers=_h(admin_token),
        )
    ).json()
    enrollment = await client.post(
        "/api/course-enrollments",
        json={"unit_id": sample_unit["id"], "sku_id": sku["id"], "start_date": "2026-06-01"},
        headers=_h(admin_token),
    )
    assert enrollment.status_code == 201, enrollment.text
    enrollment_id = enrollment.json()["id"]
    edited = await client.patch(
        f"/api/course-enrollments/{enrollment_id}", json={"notes": "x"}, headers=_h(admin_token)
    )
    assert edited.status_code == 200, edited.text
    left = await client.patch(
        f"/api/course-enrollments/{enrollment_id}", json={"status": "cancelled"}, headers=_h(admin_token)
    )
    assert left.status_code == 200, left.text

    rows = [r for r in await _logs(client, sa, "course_enrollments") if r["record_id"] == enrollment_id]
    descriptions = " | ".join(r["description"] for r in rows)
    assert {r["action"] for r in rows} == {"CREATE", "UPDATE"}
    assert "Edited enrollment" in descriptions
    assert "status from active to cancelled" in descriptions

    note = await client.post(
        "/api/notifications",
        json={"title": "Hi", "message": "Hello"},
        headers=_h(admin_token),
    )
    assert note.status_code == 201, note.text
    note_id = note.json()["id"]
    read = await client.patch(
        f"/api/notifications/{note_id}", json={"is_read": True}, headers=_h(admin_token)
    )
    assert read.status_code == 200, read.text
    assert (await client.delete(f"/api/notifications/{note_id}", headers=_h(admin_token))).status_code == 204
    note_actions = {r["action"] for r in await _logs(client, sa, "notifications") if r["record_id"] == note_id}
    assert note_actions == {"CREATE", "DELETE"}

    staff = await _staff_unit(client, admin_token, sample_location["id"])
    made = await client.post(
        f"/api/staff-profiles/{staff['id']}", json={"hourly_rate": 50}, headers=_h(admin_token)
    )
    assert made.status_code == 201, made.text
    profile = await client.patch(
        f"/api/staff-profiles/{staff['id']}",
        json={"hourly_rate": 55.5, "date_of_birth": "1990-01-02"},
        headers=_h(admin_token),
    )
    assert profile.status_code == 200, profile.text
    gone = await client.delete(f"/api/staff-profiles/{staff['id']}", headers=_h(admin_token))
    assert gone.status_code == 204, gone.text
    profile_rows = [r for r in await _logs(client, sa, "staff_profiles") if r["record_id"] == staff["id"]]
    assert {r["action"] for r in profile_rows} == {"CREATE", "UPDATE", "DELETE"}
    assert any(r["action"] == "UPDATE" and r["new_values"]["date_of_birth"] == "1990-01-02" for r in profile_rows)

    made_student = await client.post(
        f"/api/student-profiles/{sample_unit['id']}", json={}, headers=_h(admin_token)
    )
    assert made_student.status_code == 201, made_student.text
    student = await client.patch(
        f"/api/student-profiles/{sample_unit['id']}", json={"school": "ABC"}, headers=_h(admin_token)
    )
    assert student.status_code == 200, student.text
    student_gone = await client.delete(f"/api/student-profiles/{sample_unit['id']}", headers=_h(admin_token))
    assert student_gone.status_code == 204, student_gone.text
    student_rows = [r for r in await _logs(client, sa, "student_profiles") if r["record_id"] == sample_unit["id"]]
    assert {r["action"] for r in student_rows} == {"CREATE", "UPDATE", "DELETE"}
