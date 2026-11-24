"""Which teams a web login may read or change.

Superadmin (GM) is unrestricted. Admin (store manager) and user (staff web
account) only see teams linked in user_locations. An empty link list returns
no rows; it does not fall back to every team.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import false, select
from sqlalchemy.sql import ColumnElement

from app.models.user import Role, User
from app.models.user_location import UserLocation


async def assigned_team_ids(db, user: User) -> set[uuid.UUID] | None:
    """None means every team. An empty set means the account is not assigned."""
    if user.role == Role.superadmin.value:
        return None
    rows = await db.scalars(select(UserLocation.location_id).where(UserLocation.user_id == user.id))
    return set(rows.all())


def team_filter(column, team_ids: set[uuid.UUID] | None) -> ColumnElement | None:
    if team_ids is None:
        return None
    if not team_ids:
        return false()
    return column.in_(team_ids)


async def require_team(db, user: User, location_id: uuid.UUID | None) -> None:
    team_ids = await assigned_team_ids(db, user)
    if team_ids is None:
        return
    if location_id is None or location_id not in team_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this team")
