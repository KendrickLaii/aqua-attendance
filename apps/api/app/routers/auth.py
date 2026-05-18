import uuid

from fastapi import APIRouter, HTTPException, status
from jose import JWTError
from sqlalchemy import select

from app.deps import DB, CurrentUser
from app.models.user import User
from app.schemas.auth import TokenPair, TokenRefresh
from app.schemas.user import UserCreate, UserLogin, UserOut
from app.services.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: DB) -> User:
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
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
async def login(body: UserLogin, db: DB) -> dict:
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    return {
        "access_token": create_access_token(str(user.id), user.role),
        "refresh_token": create_refresh_token(str(user.id)),
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: TokenRefresh, db: DB) -> dict:
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return {
        "access_token": create_access_token(str(user.id), user.role),
        "refresh_token": create_refresh_token(str(user.id)),
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user
