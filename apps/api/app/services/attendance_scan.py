"""Shared QR scan helpers used by both the admin attendance router and the
staff mobile scanner router."""

import uuid

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.attendance import AttendanceEvent
from app.models.location import Location
from app.models.unit import Unit
from app.schemas.attendance import (
    AttendanceOut,
    ScanAllowedLocation,
    ScanLocationNotAllowedDetail,
)
from app.services.qr import verify_qr_token
from app.services.unit import ensure_attendance_eligible


def event_to_out(event: AttendanceEvent) -> AttendanceOut:
    return AttendanceOut(
        id=event.id,
        unit_id=event.unit_id,
        unit_code=event.unit.code if event.unit else None,
        unit_name=event.unit.full_name if event.unit else None,
        unit_type=event.unit.unit_type if event.unit else None,
        event_type=event.event_type,
        source=event.source,
        recorded_at=event.recorded_at,
        created_at=event.created_at,
        attendance_status=event.unit.attendance_status if event.unit else None,
        qr_jti=event.qr_jti,
        recorded_by_user_id=event.recorded_by_user_id,
        recorded_by_unit_id=event.recorded_by_unit_id,
        client_device_id=event.client_device_id,
        location_id=event.location_id,
        location=event.location,
        notes=event.notes,
        voided_at=event.voided_at,
    )


async def resolve_location(db: AsyncSession, location_id: uuid.UUID | None, location_text: str | None) -> tuple[uuid.UUID | None, str | None]:
    if location_id is None:
        return None, location_text
    result = await db.execute(select(Location).where(Location.id == location_id))
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    if not location.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Location is inactive")
    display_name = location.name_en or location.name_zh or ""
    return location.id, display_name


async def reload_with_unit(db: AsyncSession, event_id: uuid.UUID) -> AttendanceEvent:
    result = await db.execute(
        select(AttendanceEvent)
        .options(selectinload(AttendanceEvent.unit))
        .where(AttendanceEvent.id == event_id)
    )
    return result.scalar_one()


def raise_location_not_allowed(unit: Unit) -> None:
    allowed = [
        ScanAllowedLocation(
            id=loc.id,
            code=loc.code,
            name_zh=loc.name_zh,
            name_en=loc.name_en,
        )
        for loc in unit.scan_locations
    ]
    detail = ScanLocationNotAllowedDetail(
        message="Unit is not allowed to scan at this location",
        unit_name=unit.full_name,
        unit_code=unit.code,
        allowed_locations=allowed,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail.model_dump(mode="json"),
    )


async def resolve_unit_for_scan(
    db: AsyncSession,
    *,
    qr_token: str,
    location_id: uuid.UUID | None,
    location_text: str | None = None,
) -> tuple[Unit, uuid.UUID, str | None, dict]:
    """Validate QR and location; return unit, location, and JWT payload. Does not record attendance."""
    try:
        payload = verify_qr_token(qr_token)
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid QR: {e}")

    try:
        target_unit_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR: bad subject")

    unit_query = (
        select(Unit)
        .options(selectinload(Unit.scan_locations))
        .where(Unit.id == target_unit_id)
    )
    # PostgreSQL only: row lock prevents concurrent scans of the same unit
    # from creating duplicate attendance events within the debounce window.
    if settings.DATABASE_URL.startswith("postgresql"):
        unit_query = unit_query.with_for_update()
    result = await db.execute(unit_query)
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    if not unit.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unit is inactive")
    ensure_attendance_eligible(unit)

    if payload.get("ver") != unit.qr_token_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid QR: token has been rotated, please refresh the QR",
        )

    resolved_location_id, location_name = await resolve_location(db, location_id, location_text)
    if resolved_location_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="location_id is required for scan",
        )
    if not any(loc.id == resolved_location_id for loc in unit.scan_locations):
        raise_location_not_allowed(unit)
    return unit, resolved_location_id, location_name, payload
