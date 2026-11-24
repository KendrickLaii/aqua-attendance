import uuid

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, func, or_, select

from app.deps import AdminOnly, DB, SuperAdminOnly
from app.models.location import Location
from app.models.user import Role, User
from app.models.user_location import UserLocation
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services.auth import hash_password
from app.services import audit_log as audit_svc
from app.services.team_access import assigned_team_ids
from app.utils.search import ilike_contains

router = APIRouter(prefix="/users", tags=["users"])


async def _to_out(db: DB, user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.sees_all_teams = user.role == Role.superadmin.value
    rows = await db.scalars(select(UserLocation.location_id).where(UserLocation.user_id == user.id))
    out.location_ids = list(rows.all())
    return out


def _role_name(role: object) -> str:
    return role.value if isinstance(role, Role) else str(role)


async def _location_ids_for(db: DB, user_id: uuid.UUID) -> list[uuid.UUID]:
    rows = await db.scalars(select(UserLocation.location_id).where(UserLocation.user_id == user_id))
    return list(rows.all())


async def _admin_team_ids(db: DB, actor: User) -> set[uuid.UUID] | None:
    """None means superadmin. An empty set means this admin has no teams."""
    if actor.role == Role.superadmin.value:
        return None
    return await assigned_team_ids(db, actor) or set()


def _reject_outside_teams(requested: list[uuid.UUID], allowed: set[uuid.UUID]) -> None:
    if any(location_id not in allowed for location_id in requested):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only assign your own teams")


async def _assert_manageable_user(db: DB, actor: User, user: User) -> set[uuid.UUID] | None:
    allowed = await _admin_team_ids(db, actor)
    if allowed is None:
        return None
    if user.role != Role.user.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only manage user accounts")
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not assigned to a team")
    if not set(await _location_ids_for(db, user.id)) & allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage user accounts in your teams",
        )
    return allowed


async def _replace_locations(db: DB, user: User, location_ids: list[uuid.UUID]) -> None:
    await db.execute(delete(UserLocation).where(UserLocation.user_id == user.id))
    if user.role == Role.superadmin.value:
        return
    for location_id in dict.fromkeys(location_ids):
        if await db.get(Location, location_id) is None:
            raise HTTPException(status_code=422, detail="One of the teams does not exist")
        db.add(UserLocation(user_id=user.id, location_id=location_id))


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
) -> list[UserOut]:
    clauses = []
    allowed = await _admin_team_ids(db, actor)
    if allowed is not None:
        if role and role != Role.user.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only manage user accounts")
        if not allowed:
            response.headers["X-Total-Count"] = "0"
            return []
        clauses.append(User.role == Role.user.value)
        clauses.append(
            User.id.in_(select(UserLocation.user_id).where(UserLocation.location_id.in_(allowed)))
        )
    elif role:
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
    return [await _to_out(db, user) for user in result.scalars().all()]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, actor: AdminOnly, db: DB, request: Request) -> UserOut:
    existing = await db.execute(
        select(User).where(
            (func.lower(User.username) == body.username.lower())
            | (func.lower(User.email) == body.email.lower())
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username or email already exists")

    allowed = await _admin_team_ids(db, actor)
    role_name = _role_name(body.role)
    if allowed is not None:
        if role_name != Role.user.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only create user accounts")
        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not assigned to a team")
        if not body.location_ids:
            raise HTTPException(status_code=422, detail="Choose one of your teams")
        _reject_outside_teams(body.location_ids, allowed)

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=role_name,
    )
    db.add(user)
    await db.flush()
    await _replace_locations(db, user, body.location_ids)
    await db.commit()
    await db.refresh(user)

    await audit_svc.log_audit(
        db,
        user_id=actor.id,
        action="CREATE",
        table_name="users",
        record_id=user.id,
        new_values=body.model_dump(exclude={"password"}, mode="json"),
        description=f"Created user {user.username} with role {user.role}",
        request=request,
    )
    return await _to_out(db, user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: uuid.UUID, actor: AdminOnly, db: DB) -> UserOut:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await _assert_manageable_user(db, actor, user)
    return await _to_out(db, user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, body: UserUpdate, actor: AdminOnly, db: DB, request: Request) -> UserOut:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    allowed = await _assert_manageable_user(db, actor, user)
    update_data = body.model_dump(exclude_unset=True)
    location_ids = update_data.pop("location_ids", None)
    if allowed is not None:
        if "role" in update_data and _role_name(update_data["role"]) != Role.user.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot change this account to another role",
            )
        if location_ids is not None:
            current = await _location_ids_for(db, user.id)
            current_set = set(current)
            added_outside = [
                location_id
                for location_id in location_ids
                if location_id not in allowed and location_id not in current_set
            ]
            if added_outside:
                _reject_outside_teams(added_outside, allowed)
            kept = [location_id for location_id in current if location_id not in allowed]
            chosen = [location_id for location_id in dict.fromkeys(location_ids) if location_id in allowed]
            location_ids = kept + chosen

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
    if location_ids is not None or user.role == Role.superadmin.value:
        await _replace_locations(db, user, location_ids or [])
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
    return await _to_out(db, user)


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
