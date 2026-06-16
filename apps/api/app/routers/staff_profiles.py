import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import DB, AdminOnly
from app.models.product import Product
from app.models.staff_profile import StaffProfile
from app.schemas.staff_profile import StaffProfileCreate, StaffProfileOut, StaffProfileUpdate

router = APIRouter(prefix="/staff-profiles", tags=["staff-profiles"])


@router.get("/{product_id}", response_model=StaffProfileOut)
async def get_staff_profile(product_id: uuid.UUID, _admin: AdminOnly, db: DB) -> StaffProfileOut:
    result = await db.execute(
        select(StaffProfile)
        .options(selectinload(StaffProfile.product))
        .where(StaffProfile.id == product_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff profile not found")
    return StaffProfileOut.model_validate(profile)


@router.post("/{product_id}", response_model=StaffProfileOut, status_code=status.HTTP_201_CREATED)
async def create_staff_profile(
    product_id: uuid.UUID, body: StaffProfileCreate, _admin: AdminOnly, db: DB
) -> StaffProfileOut:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if product.product_type != "staff":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Product must be of type 'staff'",
        )

    existing = await db.execute(select(StaffProfile).where(StaffProfile.id == product_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Staff profile already exists")

    profile = StaffProfile(id=product_id, **body.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return StaffProfileOut.model_validate(profile)


@router.patch("/{product_id}", response_model=StaffProfileOut)
async def update_staff_profile(
    product_id: uuid.UUID, body: StaffProfileUpdate, _admin: AdminOnly, db: DB
) -> StaffProfileOut:
    result = await db.execute(select(StaffProfile).where(StaffProfile.id == product_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff profile not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return StaffProfileOut.model_validate(profile)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff_profile(product_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    result = await db.execute(select(StaffProfile).where(StaffProfile.id == product_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff profile not found")
    await db.delete(profile)
    await db.commit()
