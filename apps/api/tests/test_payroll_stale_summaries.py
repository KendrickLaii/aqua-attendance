"""Regression: payroll generate flags summaries that are stale vs their events.

Covers KNOWN-GAPS #M15 — detect_stale_summary_products compares the latest
attendance-event mutation (insert/void) against the summary's updated_at.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient

from app.models.attendance import AttendanceEvent
from app.models.attendance_summary import AttendanceSummary
from app.services.payroll_generator import detect_stale_summary_products
from tests.conftest import TestSessionLocal

YEAR, MONTH = 2026, 3
SUMMARY_DAY = date(YEAR, MONTH, 15)


async def _staff_product(client: AsyncClient, token: str, location_id: str) -> dict:
    code = f"STF-{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/api/products",
        json={
            "code": code,
            "full_name": "Test Staff",
            "product_type": "staff",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()


def _dt(day: int, hour: int = 9) -> datetime:
    return datetime(YEAR, MONTH, day, hour, tzinfo=timezone.utc)


async def _add_summary(session, product_id: str, location_id: str, updated_at: datetime) -> None:
    session.add(
        AttendanceSummary(
            product_id=uuid.UUID(product_id),
            summary_date=SUMMARY_DAY,
            location_id=uuid.UUID(location_id),
            created_at=updated_at,
            updated_at=updated_at,
        )
    )


async def _add_event(
    session,
    product_id: str,
    location_id: str,
    *,
    created_at: datetime,
    voided_at: datetime | None = None,
) -> None:
    session.add(
        AttendanceEvent(
            product_id=uuid.UUID(product_id),
            event_type="check_in",
            source="scan",
            recorded_at=_dt(15),
            created_at=created_at,
            location_id=uuid.UUID(location_id),
            voided_at=voided_at,
        )
    )


@pytest.mark.asyncio
async def test_detects_outdated_missing_and_voided(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    fresh = await _staff_product(client, admin_token, loc)
    outdated = await _staff_product(client, admin_token, loc)
    missing = await _staff_product(client, admin_token, loc)
    voided = await _staff_product(client, admin_token, loc)

    async with TestSessionLocal() as session:
        # fresh: summary generated AFTER its event → up to date
        await _add_event(session, fresh["id"], loc, created_at=_dt(15))
        await _add_summary(session, fresh["id"], loc, updated_at=_dt(16))

        # outdated: a new event inserted AFTER the summary was built
        await _add_summary(session, outdated["id"], loc, updated_at=_dt(16))
        await _add_event(session, outdated["id"], loc, created_at=_dt(17))

        # missing: has events but no summary at all
        await _add_event(session, missing["id"], loc, created_at=_dt(15))

        # voided: event voided AFTER the summary was built
        await _add_summary(session, voided["id"], loc, updated_at=_dt(16))
        await _add_event(session, voided["id"], loc, created_at=_dt(15), voided_at=_dt(18))

        await session.commit()

        stale = await detect_stale_summary_products(
            session, year=YEAR, month=MONTH, product_type="staff"
        )

    by_id = {s["product_id"]: s["reason"] for s in stale}
    assert fresh["id"] not in by_id
    assert by_id.get(outdated["id"]) == "outdated"
    assert by_id.get(missing["id"]) == "no_summary"
    assert by_id.get(voided["id"]) == "outdated"


@pytest.mark.asyncio
async def test_generate_payroll_returns_stale_warning(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    loc = sample_location["id"]
    product = await _staff_product(client, admin_token, loc)

    async with TestSessionLocal() as session:
        await _add_summary(session, product["id"], loc, updated_at=_dt(16))
        await _add_event(session, product["id"], loc, created_at=_dt(17))
        await session.commit()

    resp = await client.post(
        "/api/payroll-records/generate",
        params={"year": YEAR, "month": MONTH, "product_type": "staff"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    stale = body.get("stale_summaries") or []
    assert any(s["product_id"] == product["id"] and s["reason"] == "outdated" for s in stale)
