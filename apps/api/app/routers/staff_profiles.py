import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import DB, AdminOnly
from app.models.unit import Unit
from app.models.staff_profile import StaffProfile
from app.schemas.staff_profile import StaffProfileCreate, StaffProfileOut, StaffProfileUpdate, ShiftPinResetOut
from app.services.auth import hash_password

router = APIRouter(prefix="/staff-profiles", tags=["staff-profiles"])


@router.get("/{unit_id}", response_model=StaffProfileOut)
async def get_staff_profile(unit_id: uuid.UUID, _admin: AdminOnly, db: DB) -> StaffProfileOut:
    result = await db.execute(
        select(StaffProfile)
        .options(selectinload(StaffProfile.unit))
        .where(StaffProfile.id == unit_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff profile not found")
    return StaffProfileOut.model_validate(profile)


@router.post("/{unit_id}", response_model=StaffProfileOut, status_code=status.HTTP_201_CREATED)
async def create_staff_profile(
    unit_id: uuid.UUID, body: StaffProfileCreate, _admin: AdminOnly, db: DB
) -> StaffProfileOut:
    result = await db.execute(select(Unit).where(Unit.id == unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    if unit.unit_type != "staff":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unit must be of type 'staff'",
        )

    existing = await db.execute(select(StaffProfile).where(StaffProfile.id == unit_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Staff profile already exists")

    profile = StaffProfile(id=unit_id, **body.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return StaffProfileOut.model_validate(profile)


@router.patch("/{unit_id}", response_model=StaffProfileOut)
async def update_staff_profile(
    unit_id: uuid.UUID, body: StaffProfileUpdate, _admin: AdminOnly, db: DB
) -> StaffProfileOut:
    result = await db.execute(select(StaffProfile).where(StaffProfile.id == unit_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff profile not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return StaffProfileOut.model_validate(profile)


@router.post("/{unit_id}/shift-pin", response_model=ShiftPinResetOut)
async def reset_shift_pin(unit_id: uuid.UUID, _admin: AdminOnly, db: DB) -> ShiftPinResetOut:
    result = await db.execute(select(Unit).where(Unit.id == unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    if unit.unit_type != "staff":
        raise HTTPException(status_code=422, detail="Unit must be of type 'staff'")

    profile = await db.get(StaffProfile, unit_id)
    if not profile:
        profile = StaffProfile(id=unit_id)
        db.add(profile)

    pin = f"{secrets.randbelow(1_000_000):06d}"
    profile.shift_pin_hash = hash_password(pin)
    profile.shift_pin_set_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return ShiftPinResetOut(pin=pin, shift_pin_set_at=profile.shift_pin_set_at)


@router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff_profile(unit_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    result = await db.execute(select(StaffProfile).where(StaffProfile.id == unit_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff profile not found")
    await db.delete(profile)
    await db.commit()
