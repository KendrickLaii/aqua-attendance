import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.deps import DB, AdminOnly, SuperAdminOnly
from app.models.user import Role, User
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services.auth import hash_password

router = APIRouter(prefix="/users", tags=["users"])


def _role_value(role: object) -> str:
    return role.value if hasattr(role, "value") else str(role)


def _forbid_admin_managing_superadmin(actor: User, *, target_role: str | None = None, new_role: str | None = None) -> None:
    """Admins may manage admin accounts only; superadmins may manage anyone."""
    if actor.role == Role.superadmin.value:
        return
    if target_role == Role.superadmin.value or new_role == Role.superadmin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


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
async def create_user(body: UserCreate, actor: AdminOnly, db: DB) -> User:
    _forbid_admin_managing_superadmin(actor, new_role=_role_value(body.role))

    existing = await db.execute(
        select(User).where(
            (func.lower(User.username) == body.username.lower()) | (User.email == body.email)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username or email already exists")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role.value if hasattr(body.role, 'value') else body.role,
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
async def update_user(user_id: uuid.UUID, body: UserUpdate, actor: AdminOnly, db: DB) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = body.model_dump(exclude_unset=True)
    new_role = _role_value(update_data["role"]) if "role" in update_data else None
    _forbid_admin_managing_superadmin(actor, target_role=user.role, new_role=new_role)
    if 'password' in update_data:
        pwd = update_data.pop('password')
        if pwd:
            user.hashed_password = hash_password(pwd)
    for field, value in update_data.items():
        if field == 'role' and hasattr(value, 'value'):
            value = value.value
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, _admin: SuperAdminOnly, db: DB) -> None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
