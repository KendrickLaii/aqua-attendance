import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.user import Role


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
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
    email: EmailStr | None = None
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
