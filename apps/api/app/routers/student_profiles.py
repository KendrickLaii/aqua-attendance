import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import DB, AdminOnly
from app.models.product import Product
from app.models.student_profile import StudentProfile
from app.schemas.student_profile import StudentProfileCreate, StudentProfileOut, StudentProfileUpdate

router = APIRouter(prefix="/student-profiles", tags=["student-profiles"])


@router.get("/{product_id}", response_model=StudentProfileOut)
async def get_student_profile(product_id: uuid.UUID, _admin: AdminOnly, db: DB) -> StudentProfileOut:
    result = await db.execute(
        select(StudentProfile)
        .options(selectinload(StudentProfile.product))
        .where(StudentProfile.id == product_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    return StudentProfileOut.model_validate(profile)


@router.post("/{product_id}", response_model=StudentProfileOut, status_code=status.HTTP_201_CREATED)
async def create_student_profile(
    product_id: uuid.UUID, body: StudentProfileCreate, _admin: AdminOnly, db: DB
) -> StudentProfileOut:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if product.product_type != "student":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Product must be of type 'student'",
        )

    existing = await db.execute(select(StudentProfile).where(StudentProfile.id == product_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Student profile already exists")

    profile = StudentProfile(id=product_id, **body.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return StudentProfileOut.model_validate(profile)


@router.patch("/{product_id}", response_model=StudentProfileOut)
async def update_student_profile(
    product_id: uuid.UUID, body: StudentProfileUpdate, _admin: AdminOnly, db: DB
) -> StudentProfileOut:
    result = await db.execute(select(StudentProfile).where(StudentProfile.id == product_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return StudentProfileOut.model_validate(profile)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student_profile(product_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    result = await db.execute(select(StudentProfile).where(StudentProfile.id == product_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    await db.delete(profile)
    await db.commit()
