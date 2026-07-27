import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.staff_profile import StaffProfileCreate, StaffProfileOut
from app.schemas.student_profile import StudentProfileCreate, StudentProfileOut


class UnitLocationRef(BaseModel):
    id: uuid.UUID
    code: str | None = None
    name_zh: str
    name_en: str

    model_config = {"from_attributes": True}


class UnitCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    full_name: str = Field(min_length=1, max_length=255)
    english_name: str | None = Field(default=None, max_length=255)
    unit_type: Literal["staff", "student"]
    is_active: bool = True
    status: str = Field(default="active", max_length=20)
    registered_location_id: uuid.UUID
    scan_location_ids: list[uuid.UUID] = Field(min_length=1)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    email: str | None = Field(default=None, max_length=255)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=50)
    photo_url: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None
    whatsapp_enabled: bool = False
    remarks: str | None = None
    student_profile: StudentProfileCreate | None = None
    staff_profile: StaffProfileCreate | None = None

    @field_validator("scan_location_ids")
    @classmethod
    def validate_scan_location_ids(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        unique = list(dict.fromkeys(value))
        if not unique:
            raise ValueError("scan_location_ids must contain at least one location")
        return unique


class UnitUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    english_name: str | None = Field(default=None, max_length=255)
    unit_type: Literal["staff", "student"] | None = None
    is_active: bool | None = None
    status: str | None = Field(default=None, max_length=20)
    registered_location_id: uuid.UUID | None = None
    scan_location_ids: list[uuid.UUID] | None = Field(default=None, min_length=1)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    email: str | None = Field(default=None, max_length=255)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=50)
    photo_url: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None
    whatsapp_enabled: bool | None = None
    remarks: str | None = None

    @field_validator("scan_location_ids")
    @classmethod
    def validate_scan_location_ids(cls, value: list[uuid.UUID] | None) -> list[uuid.UUID] | None:
        if value is None:
            return None
        unique = list(dict.fromkeys(value))
        if not unique:
            raise ValueError("scan_location_ids must contain at least one location")
        return unique


class UnitOut(BaseModel):
    id: uuid.UUID
    code: str
    full_name: str
    english_name: str | None = None
    unit_type: str
    is_active: bool
    status: str
    attendance_status: str = "checked_out"
    qr_token_version: int = 1
    registered_location_id: uuid.UUID
    registered_location: UnitLocationRef | None = None
    scan_location_ids: list[uuid.UUID] = Field(default_factory=list)
    scan_locations: list[UnitLocationRef] = Field(default_factory=list)
    last_event_at: datetime | None = None
    last_event_location_id: uuid.UUID | None = None
    last_event_location: str | None = None
    phone: str | None = None
    address: str | None = None
    email: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    photo_url: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    whatsapp_enabled: bool
    remarks: str | None = None
    created_at: datetime
    updated_at: datetime
    student_profile: StudentProfileOut | None = None
    staff_profile: StaffProfileOut | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_unit(cls, unit) -> "UnitOut":
        scan_locs = list(unit.scan_locations or [])
        data = UnitOut.model_validate(unit, from_attributes=True)
        data.scan_location_ids = [loc.id for loc in scan_locs]
        data.scan_locations = [UnitLocationRef.model_validate(loc) for loc in scan_locs]
        if unit.registered_location is not None:
            data.registered_location = UnitLocationRef.model_validate(unit.registered_location)
        if unit.student_profile is not None:
            data.student_profile = StudentProfileOut.model_validate(unit.student_profile)
        if unit.staff_profile is not None:
            data.staff_profile = StaffProfileOut.model_validate(unit.staff_profile)
        return data
