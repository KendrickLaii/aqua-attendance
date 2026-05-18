import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    full_name: str = Field(min_length=1, max_length=255)
    english_name: str | None = Field(default=None, max_length=255)
    product_type: str = Field(min_length=1, max_length=50)
    status: str = Field(default="active", max_length=20)
    gender: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    email: str | None = Field(default=None, max_length=255)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=50)
    school_name: str | None = Field(default=None, max_length=255)
    grade_class: str | None = Field(default=None, max_length=100)
    guardian1_name: str | None = Field(default=None, max_length=255)
    guardian1_relationship: str | None = Field(default=None, max_length=100)
    guardian1_phone: str | None = Field(default=None, max_length=50)
    guardian2_name: str | None = Field(default=None, max_length=255)
    guardian2_relationship: str | None = Field(default=None, max_length=100)
    guardian2_phone: str | None = Field(default=None, max_length=50)
    whatsapp_enabled: bool = False
    remarks: str | None = None


class ProductUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    english_name: str | None = Field(default=None, max_length=255)
    product_type: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None
    status: str | None = Field(default=None, max_length=20)
    gender: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    email: str | None = Field(default=None, max_length=255)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=50)
    school_name: str | None = Field(default=None, max_length=255)
    grade_class: str | None = Field(default=None, max_length=100)
    guardian1_name: str | None = Field(default=None, max_length=255)
    guardian1_relationship: str | None = Field(default=None, max_length=100)
    guardian1_phone: str | None = Field(default=None, max_length=50)
    guardian2_name: str | None = Field(default=None, max_length=255)
    guardian2_relationship: str | None = Field(default=None, max_length=100)
    guardian2_phone: str | None = Field(default=None, max_length=50)
    whatsapp_enabled: bool | None = None
    remarks: str | None = None


class ProductOut(BaseModel):
    id: uuid.UUID
    code: str
    full_name: str
    english_name: str | None = None
    product_type: str
    is_active: bool
    status: str
    gender: str | None = None
    date_of_birth: date | None = None
    phone: str | None = None
    address: str | None = None
    email: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    school_name: str | None = None
    grade_class: str | None = None
    guardian1_name: str | None = None
    guardian1_relationship: str | None = None
    guardian1_phone: str | None = None
    guardian2_name: str | None = None
    guardian2_relationship: str | None = None
    guardian2_phone: str | None = None
    whatsapp_enabled: bool
    remarks: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
