import uuid

from fastapi import APIRouter, HTTPException, Request, Response, status
import jwt
from sqlalchemy import func, select

from app.auth_cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.config import settings
from app.deps import DB, CurrentUser
from app.limiter import limiter
from app.models.user import User
from app.schemas.auth import TokenPair, TokenRefresh
from app.schemas.user import UserLogin, UserOut
from app.services.auth import (
    consume_refresh_token,
    decode_token,
    issue_token_pair,
    purge_expired_refresh_tokens,
    revoke_all_refresh_tokens_for_user,
    revoke_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register() -> None:
    """Public self-registration is disabled. Create users via POST /api/users (admin)."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Public registration is disabled. Ask an administrator to create your account.",
    )


@router.post("/login", response_model=TokenPair)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(request: Request, response: Response, body: UserLogin, db: DB) -> dict:
    result = await db.execute(
        select(User).where(func.lower(User.username) == body.username.lower())
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    await revoke_all_refresh_tokens_for_user(db, user_id=user.id)
    tokens = await issue_token_pair(db, user_id=user.id, role=user.role)
    set_auth_cookies(response, tokens)
    return tokens


@router.post("/refresh", response_model=TokenPair)
@limiter.limit("10/minute")
async def refresh(request: Request, response: Response, db: DB, body: TokenRefresh | None = None) -> dict:
    raw = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    try:
        payload = decode_token(raw, expected_type="refresh")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    jti = payload.get("jti")
    if not jti or not await consume_refresh_token(db, jti=jti, user_id=user_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked refresh token")

    tokens = await issue_token_pair(db, user_id=user_id, role=user.role)
    set_auth_cookies(response, tokens)
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, db: DB, body: TokenRefresh | None = None) -> None:
    """Revoke the supplied refresh token so it cannot be reused.

    Clients should call this on sign-out and discard both tokens locally.
    If the token is already expired or unknown, the call still returns 204
    (idempotent — safe to call on every logout regardless of token state).
    """
    await purge_expired_refresh_tokens(db)
    raw = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE)
    if raw:
        try:
            payload = decode_token(raw, expected_type="refresh")
            jti = payload.get("jti")
            if jti:
                await revoke_refresh_token(db, jti=jti)
        except jwt.PyJWTError:
            pass  # expired / invalid token — nothing to revoke
    clear_auth_cookies(response)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user
