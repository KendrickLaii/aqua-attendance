import uuid
from datetime import date, datetime

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
    role: Role = Role.student
    status: str = Field(default="inactive", max_length=20)
    gender: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=50)
    remarks: str | None = None
    student_code: str | None = Field(default=None, max_length=100)
    english_name: str | None = Field(default=None, max_length=255)
    school_name: str | None = Field(default=None, max_length=255)
    grade_class: str | None = Field(default=None, max_length=100)
    guardian1_name: str | None = Field(default=None, max_length=255)
    guardian1_relationship: str | None = Field(default=None, max_length=100)
    guardian1_phone: str | None = Field(default=None, max_length=50)
    guardian2_name: str | None = Field(default=None, max_length=255)
    guardian2_relationship: str | None = Field(default=None, max_length=100)
    guardian2_phone: str | None = Field(default=None, max_length=50)
    whatsapp_enabled: bool = False


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
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    status: str | None = Field(default=None, max_length=20)
    gender: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=50)
    remarks: str | None = None
    student_code: str | None = Field(default=None, max_length=100)
    english_name: str | None = Field(default=None, max_length=255)
    school_name: str | None = Field(default=None, max_length=255)
    grade_class: str | None = Field(default=None, max_length=100)
    guardian1_name: str | None = Field(default=None, max_length=255)
    guardian1_relationship: str | None = Field(default=None, max_length=100)
    guardian1_phone: str | None = Field(default=None, max_length=50)
    guardian2_name: str | None = Field(default=None, max_length=255)
    guardian2_relationship: str | None = Field(default=None, max_length=100)
    guardian2_phone: str | None = Field(default=None, max_length=50)
    whatsapp_enabled: bool | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    status: str
    gender: str | None = None
    date_of_birth: date | None = None
    phone: str | None = None
    address: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    remarks: str | None = None
    student_code: str | None = None
    english_name: str | None = None
    school_name: str | None = None
    grade_class: str | None = None
    guardian1_name: str | None = None
    guardian1_relationship: str | None = None
    guardian1_phone: str | None = None
    guardian2_name: str | None = None
    guardian2_relationship: str | None = None
    guardian2_phone: str | None = None
    whatsapp_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserLogin(BaseModel):
    username: str
    password: str
