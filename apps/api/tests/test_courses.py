import uuid

import pytest
from httpx import AsyncClient


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def spu_payload() -> dict:
    return {
        "code": f"MATH-{uuid.uuid4().hex[:6]}",
        "name_zh": "小學數學",
        "name_en": "Primary Math",
        "subject": "math",
    }


async def _create_spu(client: AsyncClient, admin_token: str, payload: dict) -> dict:
    resp = await client.post("/api/course-spus", json=payload, headers=_auth(admin_token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_sku(client: AsyncClient, admin_token: str, spu_id: str, **overrides) -> dict:
    payload = {
        "spu_id": spu_id,
        "code": f"MATH-P3-{uuid.uuid4().hex[:6]}",
        "name_zh": "小學數學 P3 週二班",
        "level": "P3",
        "schedule_note": "週二 18:00-19:30",
        "price": 800,
        "capacity": 12,
        **overrides,
    }
    resp = await client.post("/api/course-skus", json=payload, headers=_auth(admin_token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_student(client: AsyncClient, admin_token: str, location_id: str) -> dict:
    resp = await client.post(
        "/api/units",
        json={
            "code": f"STU-{uuid.uuid4().hex[:6]}",
            "full_name": "Second Student",
            "unit_type": "student",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_create_course_spu(client: AsyncClient, admin_token: str, spu_payload: dict) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    assert spu["code"] == spu_payload["code"]
    assert spu["is_active"] is True


@pytest.mark.asyncio
async def test_duplicate_spu_code_rejected(client: AsyncClient, admin_token: str, spu_payload: dict) -> None:
    await _create_spu(client, admin_token, spu_payload)
    resp = await client.post("/api/course-spus", json=spu_payload, headers=_auth(admin_token))
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_sku_under_spu_with_location(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_location: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"], location_id=sample_location["id"])
    assert sku["spu_id"] == spu["id"]
    assert sku["location_id"] == sample_location["id"]

    listed = await client.get(f"/api/course-skus?spu_id={spu['id']}", headers=_auth(admin_token))
    assert listed.status_code == 200
    assert any(row["id"] == sku["id"] for row in listed.json())


@pytest.mark.asyncio
async def test_create_sku_defaults_billing_unit_to_monthly(
    client: AsyncClient, admin_token: str, spu_payload: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"])
    assert sku["billing_unit"] == "monthly"
    assert sku["meeting_weekdays"] == []


@pytest.mark.asyncio
async def test_create_sku_with_per_session_billing_unit(
    client: AsyncClient, admin_token: str, spu_payload: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", meeting_weekdays=["tuesday"])
    assert sku["billing_unit"] == "per_session"
    assert sku["meeting_weekdays"] == ["tuesday"]


@pytest.mark.asyncio
async def test_create_sku_rejects_invalid_billing_unit(
    client: AsyncClient, admin_token: str, spu_payload: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    resp = await client.post(
        "/api/course-skus",
        json={
            "spu_id": spu["id"],
            "code": f"MATH-P3-{uuid.uuid4().hex[:6]}",
            "name_zh": "小學數學 P3 週二班",
            "billing_unit": "term",
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_sku_billing_unit(
    client: AsyncClient, admin_token: str, spu_payload: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"])
    assert sku["billing_unit"] == "monthly"

    resp = await client.patch(
        f"/api/course-skus/{sku['id']}",
        json={"billing_unit": "per_session", "meeting_weekdays": ["wednesday"]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["billing_unit"] == "per_session"
    assert resp.json()["meeting_weekdays"] == ["wednesday"]


@pytest.mark.asyncio
async def test_create_sku_with_meeting_weekdays(
    client: AsyncClient, admin_token: str, spu_payload: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(
        client,
        admin_token,
        spu["id"],
        meeting_weekdays=["monday", "wednesday"],
    )
    assert sku["meeting_weekdays"] == ["monday", "wednesday"]


@pytest.mark.asyncio
async def test_create_per_session_sku_without_meeting_weekdays(
    client: AsyncClient, admin_token: str, spu_payload: dict
) -> None:
    """meeting_weekdays is display-only now; per_session billing no longer needs it."""
    spu = await _create_spu(client, admin_token, spu_payload)
    resp = await client.post(
        "/api/course-skus",
        json={
            "spu_id": spu["id"],
            "code": f"SESS-{uuid.uuid4().hex[:6]}",
            "name_zh": "堂費班",
            "billing_unit": "per_session",
            "meeting_weekdays": [],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["billing_unit"] == "per_session"


@pytest.mark.asyncio
async def test_update_to_per_session_without_meeting_weekdays(
    client: AsyncClient, admin_token: str, spu_payload: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"])
    resp = await client.patch(
        f"/api/course-skus/{sku['id']}",
        json={"billing_unit": "per_session"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["billing_unit"] == "per_session"


@pytest.mark.asyncio
async def test_clear_per_session_weekdays_allowed(
    client: AsyncClient, admin_token: str, spu_payload: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(
        client,
        admin_token,
        spu["id"],
        billing_unit="per_session",
        meeting_weekdays=["tuesday"],
    )
    resp = await client.patch(
        f"/api/course-skus/{sku['id']}",
        json={"meeting_weekdays": []},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["meeting_weekdays"] == []


@pytest.mark.asyncio
async def test_enroll_inactive_sku_rejected(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"], is_active=False)
    resp = await client.post(
        "/api/course-enrollments",
        json={"unit_id": sample_unit["id"], "sku_id": sku["id"]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_enroll_inactive_student_rejected(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    deactivate = await client.patch(
        f"/api/units/{sample_unit['id']}",
        json={"is_active": False},
        headers=_auth(admin_token),
    )
    assert deactivate.status_code == 200
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"])
    resp = await client.post(
        "/api/course-enrollments",
        json={"unit_id": sample_unit["id"], "sku_id": sku["id"]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_enroll_suspended_student_rejected(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    suspend = await client.patch(
        f"/api/units/{sample_unit['id']}",
        json={"status": "suspended"},
        headers=_auth(admin_token),
    )
    assert suspend.status_code == 200
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"])
    resp = await client.post(
        "/api/course-enrollments",
        json={"unit_id": sample_unit["id"], "sku_id": sku["id"]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_enroll_rejected_when_sku_at_capacity(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"], capacity=1)
    first = await client.post(
        "/api/course-enrollments",
        json={"unit_id": sample_unit["id"], "sku_id": sku["id"]},
        headers=_auth(admin_token),
    )
    assert first.status_code == 201, first.text
    other = await _create_student(client, admin_token, sample_unit["registered_location_id"])
    second = await client.post(
        "/api/course-enrollments",
        json={"unit_id": other["id"], "sku_id": sku["id"]},
        headers=_auth(admin_token),
    )
    assert second.status_code == 422


@pytest.mark.asyncio
async def test_reactivate_enrollment_on_inactive_sku_rejected(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"])
    enrolled = await client.post(
        "/api/course-enrollments",
        json={"unit_id": sample_unit["id"], "sku_id": sku["id"]},
        headers=_auth(admin_token),
    )
    assert enrolled.status_code == 201, enrolled.text
    cancel = await client.patch(
        f"/api/course-enrollments/{enrolled.json()['id']}",
        json={"status": "cancelled"},
        headers=_auth(admin_token),
    )
    assert cancel.status_code == 200
    deactivate = await client.patch(
        f"/api/course-skus/{sku['id']}",
        json={"is_active": False},
        headers=_auth(admin_token),
    )
    assert deactivate.status_code == 200
    reactivate = await client.patch(
        f"/api/course-enrollments/{enrolled.json()['id']}",
        json={"status": "active"},
        headers=_auth(admin_token),
    )
    assert reactivate.status_code == 422


@pytest.mark.asyncio
async def test_create_sku_rejects_invalid_meeting_weekday(
    client: AsyncClient, admin_token: str, spu_payload: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    resp = await client.post(
        "/api/course-skus",
        json={
            "spu_id": spu["id"],
            "code": f"BAD-{uuid.uuid4().hex[:6]}",
            "name_zh": "bad",
            "meeting_weekdays": ["funday"],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_sku_with_unknown_spu_rejected(client: AsyncClient, admin_token: str) -> None:
    resp = await client.post(
        "/api/course-skus",
        json={"spu_id": str(uuid.uuid4()), "code": "X", "name_zh": "X"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_enroll_student_in_sku(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"])

    resp = await client.post(
        "/api/course-enrollments",
        json={"unit_id": sample_unit["id"], "sku_id": sku["id"]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["unit_id"] == sample_unit["id"]
    assert body["sku_id"] == sku["id"]
    assert body["status"] == "active"

    listed = await client.get(f"/api/course-enrollments?unit_id={sample_unit['id']}", headers=_auth(admin_token))
    assert listed.status_code == 200
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_enroll_with_term_dates_and_list_by_sku(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"])

    resp = await client.post(
        "/api/course-enrollments",
        json={
            "unit_id": sample_unit["id"],
            "sku_id": sku["id"],
            "start_date": "2026-06-01",
            "end_date": "2026-08-31",
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["start_date"] == "2026-06-01"
    assert body["end_date"] == "2026-08-31"

    listed = await client.get(f"/api/course-enrollments?sku_id={sku['id']}", headers=_auth(admin_token))
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["unit_id"] == sample_unit["id"]


@pytest.mark.asyncio
async def test_enrollment_rejects_end_before_start(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"])

    resp = await client.post(
        "/api/course-enrollments",
        json={
            "unit_id": sample_unit["id"],
            "sku_id": sku["id"],
            "start_date": "2026-06-30",
            "end_date": "2026-06-01",
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_per_session_enrollment_requires_purchased_quantity(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=150)

    resp = await client.post(
        "/api/course-enrollments",
        json={"unit_id": sample_unit["id"], "sku_id": sku["id"]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_per_session_enrollment_with_purchased_quantity(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=150)

    resp = await client.post(
        "/api/course-enrollments",
        json={"unit_id": sample_unit["id"], "sku_id": sku["id"], "purchased_quantity": 8},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["purchased_quantity"] == 8


@pytest.mark.asyncio
async def test_purchased_quantity_must_be_positive(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"], billing_unit="per_session", price=150)

    resp = await client.post(
        "/api/course-enrollments",
        json={"unit_id": sample_unit["id"], "sku_id": sku["id"], "purchased_quantity": 0},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_enrollment_rejected(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"])
    body = {"unit_id": sample_unit["id"], "sku_id": sku["id"]}

    first = await client.post("/api/course-enrollments", json=body, headers=_auth(admin_token))
    assert first.status_code == 201
    second = await client.post("/api/course-enrollments", json=body, headers=_auth(admin_token))
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_only_student_units_can_enroll(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_location: dict
) -> None:
    staff_resp = await client.post(
        "/api/units",
        json={
            "code": f"STAFF-{uuid.uuid4().hex[:6]}",
            "full_name": "Test Staff",
            "unit_type": "staff",
            "registered_location_id": sample_location["id"],
            "scan_location_ids": [sample_location["id"]],
        },
        headers=_auth(admin_token),
    )
    assert staff_resp.status_code == 201
    staff_unit = staff_resp.json()

    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"])

    resp = await client.post(
        "/api/course-enrollments",
        json={"unit_id": staff_unit["id"], "sku_id": sku["id"]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cannot_delete_spu_with_skus(client: AsyncClient, admin_token: str, spu_payload: dict) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    await _create_sku(client, admin_token, spu["id"])

    resp = await client.delete(f"/api/course-spus/{spu['id']}", headers=_auth(admin_token))
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_cannot_delete_sku_with_enrollments(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"])
    await client.post(
        "/api/course-enrollments",
        json={"unit_id": sample_unit["id"], "sku_id": sku["id"]},
        headers=_auth(admin_token),
    )

    resp = await client.delete(f"/api/course-skus/{sku['id']}", headers=_auth(admin_token))
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_patch_enrollment_dates(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"])
    created = await client.post(
        "/api/course-enrollments",
        json={
            "unit_id": sample_unit["id"],
            "sku_id": sku["id"],
            "start_date": "2026-06-01",
            "end_date": "2026-08-31",
        },
        headers=_auth(admin_token),
    )
    enrollment_id = created.json()["id"]
    patched = await client.patch(
        f"/api/course-enrollments/{enrollment_id}",
        json={"start_date": "2026-07-01", "end_date": "2026-07-31"},
        headers=_auth(admin_token),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["start_date"] == "2026-07-01"
    assert patched.json()["end_date"] == "2026-07-31"


@pytest.mark.asyncio
async def test_patch_enrollment_start_after_existing_end_rejected(
    client: AsyncClient, admin_token: str, spu_payload: dict, sample_unit: dict
) -> None:
    spu = await _create_spu(client, admin_token, spu_payload)
    sku = await _create_sku(client, admin_token, spu["id"])
    created = await client.post(
        "/api/course-enrollments",
        json={
            "unit_id": sample_unit["id"],
            "sku_id": sku["id"],
            "start_date": "2026-06-01",
            "end_date": "2026-06-30",
        },
        headers=_auth(admin_token),
    )
    resp = await client.patch(
        f"/api/course-enrollments/{created.json()['id']}",
        json={"start_date": "2026-07-01"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422
