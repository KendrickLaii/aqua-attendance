import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.location_photo import LocationDetailPhoto


def _trim_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


class LocationCreate(BaseModel):
    code: str | None = Field(default=None, max_length=100)
    name_zh: str | None = Field(default=None, max_length=255)
    name_en: str = Field(min_length=1, max_length=255)
    location_type: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    business_hours: str | None = Field(default=None, max_length=255)
    icon_url: str | None = Field(default=None, max_length=500)
    main_photo_url: str | None = Field(default=None, max_length=500)
    detail_photos: list[LocationDetailPhoto] | None = None
    address: str | None = Field(default=None, max_length=500)
    contact_person: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    details: dict | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def default_name_zh_from_en(self) -> "LocationCreate":
        """DB column name_zh is NOT NULL; UI requires English name and Chinese is optional."""
        if not self.name_zh and self.name_en:
            self.name_zh = self.name_en
        return self

    @field_validator(
        "code", "name_zh", "name_en", "location_type", "region", "business_hours",
        "icon_url", "main_photo_url", "address", "contact_person", "phone", "email",
        mode="before",
    )
    @classmethod
    def trim_fields(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("must be a string")
        return _trim_or_none(v)


class LocationUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=100)
    name_zh: str | None = Field(default=None, max_length=255)
    name_en: str | None = Field(default=None, min_length=1, max_length=255)
    location_type: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    business_hours: str | None = Field(default=None, max_length=255)
    icon_url: str | None = Field(default=None, max_length=500)
    main_photo_url: str | None = Field(default=None, max_length=500)
    detail_photos: list[LocationDetailPhoto] | None = None
    address: str | None = Field(default=None, max_length=500)
    contact_person: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    details: dict | None = None
    is_active: bool | None = None

    @field_validator(
        "code", "name_zh", "name_en", "location_type", "region", "business_hours",
        "icon_url", "main_photo_url", "address", "contact_person", "phone", "email",
        mode="before",
    )
    @classmethod
    def trim_fields(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("must be a string")
        return _trim_or_none(v)


class LocationOut(BaseModel):
    id: uuid.UUID
    code: str | None = None
    name_zh: str | None = None
    name_en: str
    location_type: str | None = None
    region: str | None = None
    business_hours: str | None = None
    icon_url: str | None = None
    main_photo_url: str | None = None
    detail_photos: list[LocationDetailPhoto] | None = None
    address: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    details: dict | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
