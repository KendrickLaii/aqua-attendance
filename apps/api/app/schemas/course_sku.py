import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

BillingUnit = Literal["monthly", "per_session"]


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
    is_active: bool = True


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
    is_active: bool | None = None


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
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
