import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.product import EmploymentType

_VALID_EMPLOYMENT_TYPES = {e.value for e in EmploymentType}


class ProductLocationRef(BaseModel):
    id: uuid.UUID
    code: str | None = None
    name_zh: str
    name_en: str

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    full_name: str = Field(min_length=1, max_length=255)
    english_name: str | None = Field(default=None, max_length=255)
    product_type: Literal["staff", "student"]
    employment_type: str | None = Field(default=None, max_length=20)
    status: str = Field(default="active", max_length=20)
    home_location_id: uuid.UUID
    allowed_location_ids: list[uuid.UUID] = Field(min_length=1)
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

    @field_validator("employment_type")
    @classmethod
    def validate_employment_type(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if value not in _VALID_EMPLOYMENT_TYPES:
            raise ValueError("employment_type must be part_time or full_time")
        return value

    @field_validator("allowed_location_ids")
    @classmethod
    def validate_allowed_location_ids(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        unique = list(dict.fromkeys(value))
        if not unique:
            raise ValueError("allowed_location_ids must contain at least one location")
        return unique


class ProductUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    english_name: str | None = Field(default=None, max_length=255)
    product_type: Literal["staff", "student"] | None = None
    employment_type: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None
    status: str | None = Field(default=None, max_length=20)
    home_location_id: uuid.UUID | None = None
    allowed_location_ids: list[uuid.UUID] | None = Field(default=None, min_length=1)
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

    @field_validator("employment_type")
    @classmethod
    def validate_employment_type(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if value not in _VALID_EMPLOYMENT_TYPES:
            raise ValueError("employment_type must be part_time or full_time")
        return value

    @field_validator("allowed_location_ids")
    @classmethod
    def validate_allowed_location_ids(cls, value: list[uuid.UUID] | None) -> list[uuid.UUID] | None:
        if value is None:
            return None
        unique = list(dict.fromkeys(value))
        if not unique:
            raise ValueError("allowed_location_ids must contain at least one location")
        return unique


class ProductOut(BaseModel):
    id: uuid.UUID
    code: str
    full_name: str
    english_name: str | None = None
    product_type: str
    employment_type: str | None = None
    is_active: bool
    status: str
    attendance_status: str = "checked_out"
    qr_token_version: int = 1
    home_location_id: uuid.UUID
    home_location: ProductLocationRef | None = None
    allowed_location_ids: list[uuid.UUID] = Field(default_factory=list)
    allowed_locations: list[ProductLocationRef] = Field(default_factory=list)
    last_event_at: datetime | None = None
    last_event_location_id: uuid.UUID | None = None
    last_event_location: str | None = None
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

    @classmethod
    def from_product(cls, product) -> "ProductOut":
        allowed = list(product.allowed_locations or [])
        data = ProductOut.model_validate(product, from_attributes=True)
        data.allowed_location_ids = [loc.id for loc in allowed]
        data.allowed_locations = [ProductLocationRef.model_validate(loc) for loc in allowed]
        if product.home_location is not None:
            data.home_location = ProductLocationRef.model_validate(product.home_location)
        return data
