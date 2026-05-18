import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.user import Role


def _flex_email(value: object) -> str:
    """
    Allows internal domains (e.g. *.local used in seeds) — stricter EmailStr rejects those.
    """
    if not isinstance(value, str):
        raise ValueError('email must be a string')

    normalized = value.strip()
    if not (3 <= len(normalized) <= 255):
        raise ValueError('email must be 3–255 characters')

    if normalized.count('@') != 1:
        raise ValueError('email must contain exactly one @')

    local_part, _, domain_part = normalized.partition('@')
    if not local_part or not domain_part:
        raise ValueError('email must have non-empty parts before and after @')

    if any(c.isspace() for c in local_part) or any(c.isspace() for c in domain_part):
        raise ValueError('email must not contain whitespace in the local or domain part')

    return normalized


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=100)

    @field_validator('username', mode='before')
    @classmethod
    def strip_username(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError('username must be a string')
        stripped = v.strip()
        return stripped

    email: str = Field(min_length=3, max_length=255)

    @field_validator('email', mode='before')
    @classmethod
    def normalize_create_email(cls, v: object) -> str:
        return _flex_email(v)

    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(default="", max_length=255)
    role: Role = Role.admin


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)

    @field_validator('email', mode='before')
    @classmethod
    def normalize_update_email(cls, v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return _flex_email(v)

    password: str | None = Field(default=None, min_length=6, max_length=128)
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserLogin(BaseModel):
    username: str
    password: str
