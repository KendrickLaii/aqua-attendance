import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import DB, AdminOnly
from app.models.unit import Unit
from app.models.student_profile import StudentProfile
from app.schemas.student_profile import StudentProfileCreate, StudentProfileOut, StudentProfileUpdate

router = APIRouter(prefix="/student-profiles", tags=["student-profiles"])


@router.get("/{unit_id}", response_model=StudentProfileOut)
async def get_student_profile(unit_id: uuid.UUID, _admin: AdminOnly, db: DB) -> StudentProfileOut:
    result = await db.execute(
        select(StudentProfile)
        .options(selectinload(StudentProfile.unit))
        .where(StudentProfile.id == unit_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    return StudentProfileOut.model_validate(profile)


@router.post("/{unit_id}", response_model=StudentProfileOut, status_code=status.HTTP_201_CREATED)
async def create_student_profile(
    unit_id: uuid.UUID, body: StudentProfileCreate, _admin: AdminOnly, db: DB
) -> StudentProfileOut:
    result = await db.execute(select(Unit).where(Unit.id == unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    if unit.unit_type != "student":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unit must be of type 'student'",
        )

    existing = await db.execute(select(StudentProfile).where(StudentProfile.id == unit_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Student profile already exists")

    profile = StudentProfile(id=unit_id, **body.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return StudentProfileOut.model_validate(profile)


@router.patch("/{unit_id}", response_model=StudentProfileOut)
async def update_student_profile(
    unit_id: uuid.UUID, body: StudentProfileUpdate, _admin: AdminOnly, db: DB
) -> StudentProfileOut:
    result = await db.execute(select(StudentProfile).where(StudentProfile.id == unit_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return StudentProfileOut.model_validate(profile)


@router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student_profile(unit_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    result = await db.execute(select(StudentProfile).where(StudentProfile.id == unit_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    await db.delete(profile)
    await db.commit()
