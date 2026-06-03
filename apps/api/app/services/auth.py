import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.refresh_token import RefreshToken

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, role: str, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": uuid.uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> dict:
    """Decode and validate a JWT. Raises JWTError on any problem."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != expected_type:
        raise JWTError(f"Expected token type '{expected_type}', got '{payload.get('type')}'")
    return payload


def _refresh_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


async def store_refresh_token(db: AsyncSession, *, user_id: uuid.UUID, jti: str) -> None:
    db.add(
        RefreshToken(
            jti=jti,
            user_id=user_id,
            expires_at=_refresh_expires_at(),
        )
    )
    await db.commit()


async def revoke_refresh_token(db: AsyncSession, *, jti: str) -> None:
    await db.execute(delete(RefreshToken).where(RefreshToken.jti == jti))
    await db.commit()


async def revoke_all_refresh_tokens_for_user(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    await db.commit()


async def purge_expired_refresh_tokens(db: AsyncSession) -> None:
    """Remove refresh token rows past ``expires_at`` (called on login/refresh/logout)."""
    now = datetime.now(timezone.utc)
    await db.execute(delete(RefreshToken).where(RefreshToken.expires_at <= now))
    await db.commit()


async def consume_refresh_token(db: AsyncSession, *, jti: str, user_id: uuid.UUID) -> bool:
    """Return True if the refresh token exists, belongs to the user, and is not expired."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.user_id == user_id,
            RefreshToken.expires_at > now,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    return True


async def issue_token_pair(db: AsyncSession, *, user_id: uuid.UUID, role: str) -> dict:
    """Create access + refresh tokens and persist the refresh ``jti`` for rotation."""
    await purge_expired_refresh_tokens(db)
    access = create_access_token(str(user_id), role)
    refresh = create_refresh_token(str(user_id))
    refresh_payload = decode_token(refresh, expected_type="refresh")
    await store_refresh_token(db, user_id=user_id, jti=refresh_payload["jti"])
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
    }
