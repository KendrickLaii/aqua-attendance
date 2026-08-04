import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class CourseEnrollmentCreate(BaseModel):
    unit_id: uuid.UUID
    sku_id: uuid.UUID
    status: str = Field(default="active", max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None


class CourseEnrollmentUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None


class CourseEnrollmentOut(BaseModel):
    id: uuid.UUID
    unit_id: uuid.UUID
    sku_id: uuid.UUID
    status: str
    enrolled_at: date
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
