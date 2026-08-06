"""Checkout-only days must appear in summaries as Incomplete (needs check-in)."""

import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.attendance import AttendanceEvent
from app.models.attendance_summary import AttendanceSummary
from app.services.summary_generator import generate_monthly_summaries
from tests.conftest import TestSessionLocal

YEAR, MONTH = 2026, 7
CHECKOUT_DAY = date(YEAR, MONTH, 31)


async def _staff_unit(client: AsyncClient, token: str, location_id: str) -> dict:
    code = f"STF-{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/api/units",
        json={
            "code": code,
            "full_name": "Checkout Only Staff",
            "unit_type": "staff",
            "registered_location_id": location_id,
            "scan_location_ids": [location_id],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_generate_keeps_checkout_only_day_as_incomplete(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    unit = await _staff_unit(client, admin_token, sample_location["id"])
    unit_id = uuid.UUID(unit["id"])
    location_id = uuid.UUID(sample_location["id"])

    async with TestSessionLocal() as session:
        session.add(
            AttendanceEvent(
                unit_id=unit_id,
                event_type="check_out",
                source="manual",
                recorded_at=datetime(YEAR, MONTH, 31, 5, 9, tzinfo=timezone.utc),  # 13:09 HKT
                location_id=location_id,
            )
        )
        await session.commit()

        result = await generate_monthly_summaries(session, year=YEAR, month=MONTH)
        assert result["created"] >= 1

        row = (
            await session.execute(
                select(AttendanceSummary).where(
                    AttendanceSummary.unit_id == unit_id,
                    AttendanceSummary.summary_date == CHECKOUT_DAY,
                )
            )
        ).scalar_one()

        assert row.is_complete is False
        assert row.first_check_in is None
        assert row.last_check_out is not None
        assert row.regular_hours == 0
        assert row.attendance_notes and "Missing check-in" in row.attendance_notes
