import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import DB, AdminOnly
from app.models.unit import Unit
from app.models.staff_profile import StaffProfile
from app.schemas.staff_profile import StaffProfileCreate, StaffProfileOut, StaffProfileUpdate

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


@router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff_profile(unit_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    result = await db.execute(select(StaffProfile).where(StaffProfile.id == unit_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff profile not found")
    await db.delete(profile)
    await db.commit()
