import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.location_photo import LocationDetailPhoto

# Structured business hours for OT (see docs/database-changes.md).
# Example: {"monday": {"open": "09:00", "close": "18:00"}, "saturday": null, ...}
BusinessHours = dict[str, dict[str, str] | None]

_DAY_ABBR_TO_FULL = {
    "mon": "monday",
    "tue": "tuesday",
    "wed": "wednesday",
    "thu": "thursday",
    "fri": "friday",
    "sat": "saturday",
    "sun": "sunday",
}

_WEEKDAYS = list(_DAY_ABBR_TO_FULL.values())


def _trim_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def hours_schedule_to_business_hours(schedule: list[Any]) -> BusinessHours | None:
    """Convert UI hours_schedule entries into OT-ready business_hours JSON."""
    if not schedule:
        return None

    result: BusinessHours = {day: None for day in _WEEKDAYS}
    any_open = False
    for entry in schedule:
        if not isinstance(entry, dict):
            continue
        day_raw = entry.get("day")
        if not isinstance(day_raw, str):
            continue
        day_key = day_raw.strip().lower()
        full = _DAY_ABBR_TO_FULL.get(day_key, day_key if day_key in _WEEKDAYS else None)
        if not full:
            continue
        if entry.get("isOpen"):
            open_time = entry.get("openTime") or entry.get("open")
            close_time = entry.get("closeTime") or entry.get("close")
            if isinstance(open_time, str) and isinstance(close_time, str):
                result[full] = {"open": open_time, "close": close_time}
                any_open = True
            else:
                result[full] = None
        else:
            result[full] = None

    return result if any_open else None


def resolve_business_hours(
    business_hours: BusinessHours | str | None,
    details: dict | None,
) -> BusinessHours | str | None:
    """Prefer structured hours; derive from details.hours_schedule when needed."""
    if isinstance(business_hours, dict):
        return business_hours

    schedule = details.get("hours_schedule") if isinstance(details, dict) else None
    if isinstance(schedule, list):
        derived = hours_schedule_to_business_hours(schedule)
        if derived is not None:
            return derived

    return business_hours


class LocationCreate(BaseModel):
    code: str | None = Field(default=None, max_length=100)
    name_zh: str | None = Field(default=None, max_length=255)
    name_en: str = Field(min_length=1, max_length=255)
    location_type: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    business_hours: BusinessHours | str | None = None
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

    @model_validator(mode="after")
    def sync_business_hours(self) -> "LocationCreate":
        self.business_hours = resolve_business_hours(self.business_hours, self.details)
        return self

    @field_validator(
        "code", "name_zh", "name_en", "location_type", "region",
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

    @field_validator("business_hours", mode="before")
    @classmethod
    def normalize_business_hours(cls, v: object) -> BusinessHours | str | None:
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            return _trim_or_none(v)
        raise ValueError("must be a JSON object or string")


class LocationUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=100)
    name_zh: str | None = Field(default=None, max_length=255)
    name_en: str | None = Field(default=None, min_length=1, max_length=255)
    location_type: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    business_hours: BusinessHours | str | None = None
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

    @model_validator(mode="after")
    def sync_business_hours(self) -> "LocationUpdate":
        # Prefer an explicit structured dict; otherwise derive from details.hours_schedule
        # only when details was part of this patch (avoid wiping hours on unrelated updates).
        if isinstance(self.business_hours, dict):
            return self
        if "details" not in self.model_fields_set:
            return self
        derived = resolve_business_hours(self.business_hours, self.details)
        if isinstance(derived, dict):
            self.business_hours = derived
        return self

    @field_validator(
        "code", "name_zh", "name_en", "location_type", "region",
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

    @field_validator("business_hours", mode="before")
    @classmethod
    def normalize_business_hours(cls, v: object) -> BusinessHours | str | None:
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            return _trim_or_none(v)
        raise ValueError("must be a JSON object or string")


class LocationOut(BaseModel):
    id: uuid.UUID
    code: str | None = None
    name_zh: str | None = None
    name_en: str
    location_type: str | None = None
    region: str | None = None
    business_hours: BusinessHours | str | None = None
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
