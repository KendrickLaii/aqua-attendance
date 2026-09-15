"""Regression tests: a future-dated event must not break live scanning.

Production incident (2026-09): a manual correction was saved with a typo'd
date (2026-09-21 instead of 2026-08-21).  Because the scan debounce window
had no upper bound on ``recorded_at``, that row satisfied
``recorded_at >= now - SCAN_DEBOUNCE_SECONDS`` on every later scan, so each
check-out scan returned the future event instead of creating a new one —
silently, with a success response.  The unit stayed ``checked_in`` for 12 days
and no check-out ever reached the log.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.models.attendance import AttendanceEvent, EventSource, EventType
from tests.conftest import TestSessionLocal, scan_body


async def _add_event(
    *,
    unit_id: str,
    event_type: str,
    recorded_at: datetime,
    location_id: str,
    source: str = EventSource.manual.value,
) -> uuid.UUID:
    async with TestSessionLocal() as session:
        event = AttendanceEvent(
            unit_id=uuid.UUID(unit_id),
            event_type=event_type,
            source=source,
            recorded_at=recorded_at,
            location_id=uuid.UUID(location_id),
            location="Test Branch A",
        )
        session.add(event)
        await session.commit()
        return event.id


@pytest.mark.asyncio
async def test_future_dated_event_does_not_swallow_scan(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    qr_token = (
        await client.get(f"/api/qr/token/{sample_unit['id']}", headers=headers)
    ).json()["qr_token"]

    check_in = await client.post(
        "/api/attendance/scan",
        json=scan_body(qr_token, sample_unit, event_type="check_in"),
        headers=headers,
    )
    assert check_in.status_code == 200

    poison_id = await _add_event(
        unit_id=sample_unit["id"],
        event_type=EventType.check_out.value,
        recorded_at=datetime.now(timezone.utc) + timedelta(days=7),
        location_id=sample_unit["scan_location_ids"][0],
    )

    check_out = await client.post(
        "/api/attendance/scan",
        json=scan_body(qr_token, sample_unit, event_type="check_out"),
        headers=headers,
    )
    assert check_out.status_code == 200
    body = check_out.json()

    # A real check-out row must be created, not the future-dated one echoed back.
    assert body["id"] != str(poison_id)
    assert body["source"] == "scan"
    assert body["attendance_status"] == "checked_out"
    # SQLite drops tzinfo on read; Postgres keeps it. Normalise before comparing.
    recorded_at = datetime.fromisoformat(body["recorded_at"])
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)
    assert recorded_at < datetime.now(timezone.utc) + timedelta(minutes=1)


@pytest.mark.asyncio
async def test_manual_correction_rejects_future_recorded_at(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    future = datetime.now(timezone.utc) + timedelta(days=7)

    resp = await client.post(
        "/api/attendance/manual",
        json={
            "unit_id": sample_unit["id"],
            "event_type": "check_out",
            "recorded_at": future.isoformat(),
            "location_id": sample_unit["scan_location_ids"][0],
        },
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_manual_correction_accepts_past_recorded_at(
    client: AsyncClient, admin_token: str, sample_unit: dict
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    past = datetime.now(timezone.utc) - timedelta(days=1)

    resp = await client.post(
        "/api/attendance/manual",
        json={
            "unit_id": sample_unit["id"],
            "event_type": "check_out",
            "recorded_at": past.isoformat(),
            "location_id": sample_unit["scan_location_ids"][0],
        },
        headers=headers,
    )
    assert resp.status_code == 201
