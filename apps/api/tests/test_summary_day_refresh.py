"""Void / manual correction must refresh that unit's daily summary immediately."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.attendance_tz import attendance_today
from app.models.attendance_summary import AttendanceSummary
from tests.conftest import TestSessionLocal, scan_body

YEAR, MONTH, DAY = 2026, 3, 15
SUMMARY_DAY = date(YEAR, MONTH, DAY)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _staff_unit(client: AsyncClient, token: str, location_id: str) -> dict:
    resp = await client.post(
        "/api/units",
        json={
            "code": f"STF-{uuid.uuid4().hex[:6]}",
            "full_name": "Summary Refresh Staff",
            "unit_type": "staff",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def _summary_row(unit_id: str, day: date = SUMMARY_DAY) -> AttendanceSummary | None:
    async with TestSessionLocal() as session:
        return (
            await session.execute(
                select(AttendanceSummary).where(
                    AttendanceSummary.unit_id == uuid.UUID(unit_id),
                    AttendanceSummary.summary_date == day,
                )
            )
        ).scalar_one_or_none()


@pytest.mark.asyncio
async def test_void_check_out_refreshes_that_day_summary(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    unit = await _staff_unit(client, admin_token, sample_location["id"])
    headers = _auth(admin_token)
    loc = sample_location["id"]

    check_in = await client.post(
        "/api/attendance/manual",
        json={
            "unit_id": unit["id"],
            "event_type": "check_in",
            "location_id": loc,
            "recorded_at": datetime(YEAR, MONTH, DAY, 1, 0, tzinfo=timezone.utc).isoformat(),
        },
        headers=headers,
    )
    assert check_in.status_code == 201, check_in.text
    check_out = await client.post(
        "/api/attendance/manual",
        json={
            "unit_id": unit["id"],
            "event_type": "check_out",
            "location_id": loc,
            "recorded_at": datetime(YEAR, MONTH, DAY, 10, 0, tzinfo=timezone.utc).isoformat(),
        },
        headers=headers,
    )
    assert check_out.status_code == 201, check_out.text

    complete = await _summary_row(unit["id"])
    assert complete is not None
    assert complete.is_complete is True
    assert complete.last_check_out is not None

    voided = await client.post(
        f"/api/attendance/{check_out.json()['id']}/void",
        headers=headers,
    )
    assert voided.status_code == 200, voided.text

    after = await _summary_row(unit["id"])
    assert after is not None
    assert after.is_complete is False
    assert after.last_check_out is None


@pytest.mark.asyncio
async def test_manual_check_out_completes_existing_summary(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    unit = await _staff_unit(client, admin_token, sample_location["id"])
    headers = _auth(admin_token)
    loc = sample_location["id"]

    check_in = await client.post(
        "/api/attendance/manual",
        json={
            "unit_id": unit["id"],
            "event_type": "check_in",
            "location_id": loc,
            "recorded_at": datetime(YEAR, MONTH, DAY, 1, 0, tzinfo=timezone.utc).isoformat(),
        },
        headers=headers,
    )
    assert check_in.status_code == 201, check_in.text

    incomplete = await _summary_row(unit["id"])
    assert incomplete is not None
    assert incomplete.is_complete is False

    check_out = await client.post(
        "/api/attendance/manual",
        json={
            "unit_id": unit["id"],
            "event_type": "check_out",
            "location_id": loc,
            "recorded_at": datetime(YEAR, MONTH, DAY, 10, 0, tzinfo=timezone.utc).isoformat(),
        },
        headers=headers,
    )
    assert check_out.status_code == 201, check_out.text

    complete = await _summary_row(unit["id"])
    assert complete is not None
    assert complete.is_complete is True
    assert complete.last_check_out is not None


async def _unit_status(client: AsyncClient, token: str, unit_id: str) -> str:
    resp = await client.get(f"/api/units/{unit_id}", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["attendance_status"]


@pytest.mark.asyncio
async def test_historical_manual_check_out_does_not_overwrite_live_status(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    """补昨天的签退不得把今天已在场的人改成已离场（否则夜间 auto-checkout 会漏掉）。"""
    unit = await _staff_unit(client, admin_token, sample_location["id"])
    headers = _auth(admin_token)
    loc = sample_location["id"]
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    today_in = await client.post(
        "/api/attendance/manual",
        json={
            "unit_id": unit["id"],
            "event_type": "check_in",
            "location_id": loc,
            "recorded_at": now.isoformat(),
        },
        headers=headers,
    )
    assert today_in.status_code == 201, today_in.text
    assert await _unit_status(client, admin_token, unit["id"]) == "checked_in"

    yesterday_out = await client.post(
        "/api/attendance/manual",
        json={
            "unit_id": unit["id"],
            "event_type": "check_out",
            "location_id": loc,
            "recorded_at": yesterday.isoformat(),
        },
        headers=headers,
    )
    assert yesterday_out.status_code == 201, yesterday_out.text
    assert await _unit_status(client, admin_token, unit["id"]) == "checked_in"


@pytest.mark.asyncio
async def test_latest_manual_check_out_does_update_live_status(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    """补登如果是最新一笔 in/out，现场状态仍要跟着改，下次扫码才能对上。"""
    unit = await _staff_unit(client, admin_token, sample_location["id"])
    headers = _auth(admin_token)
    loc = sample_location["id"]
    now = datetime.now(timezone.utc)

    check_in = await client.post(
        "/api/attendance/manual",
        json={
            "unit_id": unit["id"],
            "event_type": "check_in",
            "location_id": loc,
            "recorded_at": (now - timedelta(hours=2)).isoformat(),
        },
        headers=headers,
    )
    assert check_in.status_code == 201, check_in.text
    assert await _unit_status(client, admin_token, unit["id"]) == "checked_in"

    check_out = await client.post(
        "/api/attendance/manual",
        json={
            "unit_id": unit["id"],
            "event_type": "check_out",
            "location_id": loc,
            "recorded_at": now.isoformat(),
        },
        headers=headers,
    )
    assert check_out.status_code == 201, check_out.text
    assert await _unit_status(client, admin_token, unit["id"]) == "checked_out"


@pytest.mark.asyncio
async def test_scan_refreshes_that_day_summary(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    unit = await _staff_unit(client, admin_token, sample_location["id"])
    headers = _auth(admin_token)
    today = attendance_today()

    qr = await client.get(f"/api/qr/token/{unit['id']}", headers=headers)
    assert qr.status_code == 200, qr.text
    token = qr.json()["qr_token"]

    check_in = await client.post(
        "/api/attendance/scan",
        json=scan_body(token, unit, event_type="check_in", location_id=sample_location["id"]),
        headers=headers,
    )
    assert check_in.status_code == 200, check_in.text

    incomplete = await _summary_row(unit["id"], today)
    assert incomplete is not None
    assert incomplete.is_complete is False
    assert incomplete.first_check_in is not None

    check_out = await client.post(
        "/api/attendance/scan",
        json=scan_body(token, unit, event_type="check_out", location_id=sample_location["id"]),
        headers=headers,
    )
    assert check_out.status_code == 200, check_out.text

    complete = await _summary_row(unit["id"], today)
    assert complete is not None
    assert complete.is_complete is True
    assert complete.last_check_out is not None
