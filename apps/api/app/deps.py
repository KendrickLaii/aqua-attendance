import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_cookies import ACCESS_COOKIE
from app.database import get_db
from app.models.user import Role, User
from app.services.auth import decode_token

bearer_scheme = HTTPBearer(auto_error=False)

DB = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DB,
) -> User:
    token = credentials.credentials if credentials else None
    if not token:
        token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    try:
        payload = decode_token(token, expected_type="access")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
    user = user.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role):
    """Dependency factory that restricts access to specific roles."""
    role_values = {r.value for r in roles}

    async def _check(user: CurrentUser) -> User:
        if user.role not in role_values:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return _check


AdminOnly = Annotated[User, Depends(require_roles(Role.admin, Role.superadmin))]
SuperAdminOnly = Annotated[User, Depends(require_roles(Role.superadmin))]
