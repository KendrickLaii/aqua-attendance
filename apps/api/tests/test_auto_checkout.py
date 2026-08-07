"""Tests for auto-checkout, including selective checkout by unit_ids."""

import uuid
from datetime import date
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from app.services.auto_checkout import ATTENDANCE_TZ, day_boundary_at
from tests.conftest import scan_body


@pytest.fixture(autouse=True)
def _enable_auto_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep product default off; enable for this suite so Day-end behaviour is still covered."""
    monkeypatch.setattr(
        "app.services.auto_checkout.settings.AUTO_CHECKOUT_ENABLED",
        True,
    )
    monkeypatch.setattr(
        "app.config.settings.AUTO_CHECKOUT_ENABLED",
        True,
    )


def test_day_boundary_uses_hong_kong_not_utc() -> None:
    """Log 'Today' filters in HKT; day-boundary must sit on that local day."""
    boundary = day_boundary_at(date(2026, 7, 17))
    assert boundary.tzinfo == ATTENDANCE_TZ
    assert boundary.hour == 23 and boundary.minute == 59
    # 23:59 HKT == 15:59 UTC — still on 17 Jul UTC, inside HKT "today" window
    as_utc = boundary.astimezone(ZoneInfo("UTC"))
    assert as_utc.day == 17
    assert as_utc.hour == 15
    assert as_utc.minute == 59


async def _create_unit(client: AsyncClient, headers: dict, location_id: str) -> dict:
    code = f"STU-{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/api/units",
        json={
            "code": code,
            "full_name": f"Student {code}",
            "unit_type": "student",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


async def _check_in(client: AsyncClient, headers: dict, unit: dict) -> None:
    qr = await client.get(f"/api/qr/token/{unit['id']}", headers=headers)
    resp = await client.post(
        "/api/attendance/scan",
        json=scan_body(qr.json()["qr_token"], unit, event_type="check_in"),
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["event_type"] == "check_in"


async def _attendance_status(client: AsyncClient, headers: dict, unit_id: str) -> str:
    resp = await client.get(f"/api/units/{unit_id}", headers=headers)
    assert resp.status_code == 200
    return resp.json()["attendance_status"]


@pytest.mark.asyncio
async def test_auto_checkout_status_counts_checked_in(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    p1 = await _create_unit(client, headers, sample_location["id"])
    p2 = await _create_unit(client, headers, sample_location["id"])
    await _check_in(client, headers, p1)
    await _check_in(client, headers, p2)

    resp = await client.get("/api/auto-checkout/status", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["still_checked_in_count"] == 2


@pytest.mark.asyncio
async def test_auto_checkout_only_selected_units(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    p1 = await _create_unit(client, headers, sample_location["id"])
    p2 = await _create_unit(client, headers, sample_location["id"])
    await _check_in(client, headers, p1)
    await _check_in(client, headers, p2)

    resp = await client.post(
        "/api/auto-checkout/run",
        json={"unit_ids": [p1["id"]]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["created_events"] == 1

    # Selected unit is checked out; unselected stays checked in for follow-up.
    assert await _attendance_status(client, headers, p1["id"]) == "checked_out"
    assert await _attendance_status(client, headers, p2["id"]) == "checked_in"


@pytest.mark.asyncio
async def test_auto_checkout_empty_selection_checks_out_nobody(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    p1 = await _create_unit(client, headers, sample_location["id"])
    await _check_in(client, headers, p1)

    resp = await client.post(
        "/api/auto-checkout/run",
        json={"unit_ids": []},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["created_events"] == 0
    assert await _attendance_status(client, headers, p1["id"]) == "checked_in"


@pytest.mark.asyncio
async def test_auto_checkout_without_ids_checks_out_all(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    p1 = await _create_unit(client, headers, sample_location["id"])
    p2 = await _create_unit(client, headers, sample_location["id"])
    await _check_in(client, headers, p1)
    await _check_in(client, headers, p2)

    resp = await client.post("/api/auto-checkout/run", json={}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["created_events"] == 2

    assert await _attendance_status(client, headers, p1["id"]) == "checked_out"
    assert await _attendance_status(client, headers, p2["id"]) == "checked_out"


@pytest.mark.asyncio
async def test_auto_checkout_requires_admin(
    client: AsyncClient, sample_location: dict
) -> None:
    resp = await client.post("/api/auto-checkout/run", json={})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_auto_checkout_disabled_creates_nothing(
    client: AsyncClient,
    admin_token: str,
    sample_location: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.auto_checkout.settings.AUTO_CHECKOUT_ENABLED", False)
    monkeypatch.setattr("app.config.settings.AUTO_CHECKOUT_ENABLED", False)

    headers = {"Authorization": f"Bearer {admin_token}"}
    unit = await _create_unit(client, headers, sample_location["id"])
    await _check_in(client, headers, unit)

    resp = await client.post("/api/auto-checkout/run", json={}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_events"] == 0
    assert body["disabled"] is True
    assert await _attendance_status(client, headers, unit["id"]) == "checked_in"


@pytest.mark.asyncio
async def test_auto_checkout_skips_voided_check_in(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    """Day-end must not close a unit whose only check-in that day was voided."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    unit = await _create_unit(client, headers, sample_location["id"])
    await _check_in(client, headers, unit)

    events = await client.get(
        f"/api/attendance?unit_id={unit['id']}&include_voided=true",
        headers=headers,
    )
    assert events.status_code == 200
    check_in = next(e for e in events.json() if e["event_type"] == "check_in")

    voided = await client.post(
        f"/api/attendance/{check_in['id']}/void",
        headers=headers,
    )
    assert voided.status_code == 200
    assert await _attendance_status(client, headers, unit["id"]) == "checked_out"

    # Force status stale (old bug path) — still must not create auto-checkout.
    from sqlalchemy import select

    from app.models.unit import AttendanceStatus, Unit
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        row = await session.execute(
            select(Unit).where(Unit.id == uuid.UUID(unit["id"]))
        )
        u = row.scalar_one()
        u.attendance_status = AttendanceStatus.checked_in.value
        await session.commit()

    resp = await client.post(
        "/api/auto-checkout/run",
        json={"unit_ids": [unit["id"]]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["created_events"] == 0


@pytest.mark.asyncio
async def test_void_check_in_voids_orphan_auto_checkout(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    unit = await _create_unit(client, headers, sample_location["id"])
    await _check_in(client, headers, unit)

    run = await client.post(
        "/api/auto-checkout/run",
        json={"unit_ids": [unit["id"]]},
        headers=headers,
    )
    assert run.status_code == 200
    assert run.json()["created_events"] == 1

    events_resp = await client.get(
        f"/api/attendance?unit_id={unit['id']}&include_voided=true",
        headers=headers,
    )
    events = events_resp.json()
    check_in = next(e for e in events if e["event_type"] == "check_in" and not e.get("voided_at"))
    auto_out = next(
        e for e in events
        if e["event_type"] == "check_out" and e.get("source") == "auto_checkout" and not e.get("voided_at")
    )

    voided = await client.post(
        f"/api/attendance/{check_in['id']}/void",
        headers=headers,
    )
    assert voided.status_code == 200

    after = await client.get(
        f"/api/attendance?unit_id={unit['id']}&include_voided=true",
        headers=headers,
    )
    by_id = {e["id"]: e for e in after.json()}
    assert by_id[check_in["id"]]["voided_at"]
    assert by_id[auto_out["id"]]["voided_at"]
