from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

BillingUnit = Literal["monthly", "per_session"]
Weekday = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _normalize_weekdays(days: list[Weekday]) -> list[Weekday]:
    seen: set[str] = set()
    out: list[Weekday] = []
    for day in days:
        if day not in seen:
            seen.add(day)
            out.append(day)
    return out


class CourseSkuCreate(BaseModel):
    spu_id: uuid.UUID
    code: str = Field(min_length=1, max_length=100)
    name_zh: str = Field(min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    level: str | None = Field(default=None, max_length=100)
    schedule_note: str | None = Field(default=None, max_length=255)
    location_id: uuid.UUID | None = None
    capacity: int | None = Field(default=None, ge=0)
    price: float | None = Field(default=None, ge=0)
    billing_unit: BillingUnit = "monthly"
    meeting_weekdays: list[Weekday] = Field(default_factory=list)
    is_active: bool = True

    @field_validator("meeting_weekdays")
    @classmethod
    def unique_weekdays(cls, value: list[Weekday]) -> list[Weekday]:
        return _normalize_weekdays(value)


class CourseSkuUpdate(BaseModel):
    spu_id: uuid.UUID | None = None
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name_zh: str | None = Field(default=None, min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    level: str | None = Field(default=None, max_length=100)
    schedule_note: str | None = Field(default=None, max_length=255)
    location_id: uuid.UUID | None = None
    capacity: int | None = Field(default=None, ge=0)
    price: float | None = Field(default=None, ge=0)
    billing_unit: BillingUnit | None = None
    meeting_weekdays: list[Weekday] | None = None
    is_active: bool | None = None

    @field_validator("meeting_weekdays")
    @classmethod
    def unique_weekdays(cls, value: list[Weekday] | None) -> list[Weekday] | None:
        if value is None:
            return value
        return _normalize_weekdays(value)


class CourseSkuOut(BaseModel):
    id: uuid.UUID
    spu_id: uuid.UUID
    code: str
    name_zh: str
    name_en: str | None = None
    level: str | None = None
    schedule_note: str | None = None
    location_id: uuid.UUID | None = None
    capacity: int | None = None
    price: float | None = None
    billing_unit: BillingUnit
    meeting_weekdays: list[Weekday] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
