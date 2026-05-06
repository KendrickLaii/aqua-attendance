import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import DB, AdminOnly
from app.models.user import Role, User
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services.auth import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(
    _admin: AdminOnly,
    db: DB,
    role: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[User]:
    q = select(User)
    if role:
        q = q.where(User.role == role)
    if is_active is not None:
        q = q.where(User.is_active == is_active)
    if search:
        q = q.where(User.username.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%"))
    q = q.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, _admin: AdminOnly, db: DB) -> User:
    existing = await db.execute(
        select(User).where((User.username == body.username) | (User.email == body.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username or email already exists")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role.value if hasattr(body.role, 'value') else body.role,
        status=body.status,
        gender=body.gender,
        date_of_birth=body.date_of_birth,
        phone=body.phone,
        address=body.address,
        emergency_contact_name=body.emergency_contact_name,
        emergency_contact_phone=body.emergency_contact_phone,
        remarks=body.remarks,
        student_code=body.student_code,
        english_name=body.english_name,
        school_name=body.school_name,
        grade_class=body.grade_class,
        guardian1_name=body.guardian1_name,
        guardian1_relationship=body.guardian1_relationship,
        guardian1_phone=body.guardian1_phone,
        guardian2_name=body.guardian2_name,
        guardian2_relationship=body.guardian2_relationship,
        guardian2_phone=body.guardian2_phone,
        whatsapp_enabled=body.whatsapp_enabled,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: uuid.UUID, _admin: AdminOnly, db: DB) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, body: UserUpdate, _admin: AdminOnly, db: DB) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == 'role' and hasattr(value, 'value'):
            value = value.value
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
