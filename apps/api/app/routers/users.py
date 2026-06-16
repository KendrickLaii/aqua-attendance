import uuid

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select

from app.deps import DB, AdminOnly, SuperAdminOnly
from app.models.user import Role, User
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services.auth import hash_password
from app.services import audit_log as audit_svc
from app.utils.search import ilike_contains

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
    actor: AdminOnly,
    db: DB,
    response: Response,
    role: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[User]:
    if actor.role != Role.superadmin.value and role == Role.superadmin.value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Insufficient permissions to filter by superadmin role.",
        )

    clauses = []
    if actor.role != Role.superadmin.value:
        clauses.append(User.role != Role.superadmin.value)
    if role:
        clauses.append(User.role == role)
    if is_active is not None:
        clauses.append(User.is_active == is_active)
    if search:
        clauses.append(
            or_(
                ilike_contains(User.username, search),
                ilike_contains(User.full_name, search),
            )
        )

    count_q = select(func.count()).select_from(User)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(User)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return list(result.scalars().all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, actor: AdminOnly, db: DB, request: Request) -> User:
    _forbid_admin_managing_superadmin(actor, new_role=_role_value(body.role))

    existing = await db.execute(
        select(User).where(
            (func.lower(User.username) == body.username.lower())
            | (func.lower(User.email) == body.email.lower())
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

    await audit_svc.log_audit(
        db,
        user_id=actor.id,
        action="CREATE",
        table_name="users",
        record_id=user.id,
        new_values=body.model_dump(exclude={"password"}),
        description=f"Created user {user.username} with role {user.role}",
        request=request,
    )
    return user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: uuid.UUID, actor: AdminOnly, db: DB) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _forbid_admin_managing_superadmin(actor, target_role=user.role)
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, body: UserUpdate, actor: AdminOnly, db: DB, request: Request) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = body.model_dump(exclude_unset=True)
    new_role = _role_value(update_data["role"]) if "role" in update_data else None
    _forbid_admin_managing_superadmin(actor, target_role=user.role, new_role=new_role)

    if "email" in update_data:
        dup = await db.execute(
            select(User).where(
                func.lower(User.email) == update_data["email"].lower(),
                User.id != user_id,
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already exists")

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

    await audit_svc.log_audit(
        db,
        user_id=actor.id,
        action="UPDATE",
        table_name="users",
        record_id=user.id,
        new_values=update_data,
        description=f"Updated user {user.username}",
        request=request,
    )
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, actor: SuperAdminOnly, db: DB, request: Request) -> None:
    if user_id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot delete your own account.",
        )
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()

    await audit_svc.log_audit(
        db,
        user_id=actor.id,
        action="DELETE",
        table_name="users",
        record_id=user_id,
        description=f"Deleted user {user.username}",
        request=request,
    )
