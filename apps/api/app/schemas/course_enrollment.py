import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


def _require_start_on_or_before_end(start: date | None, end: date | None) -> None:
    if start is not None and end is not None and end < start:
        raise ValueError("end_date must be on or after start_date")


def _require_positive_quantity(quantity: int | None) -> None:
    if quantity is not None and quantity <= 0:
        raise ValueError("purchased_quantity must be a positive integer")


class CourseEnrollmentCreate(BaseModel):
    unit_id: uuid.UUID
    sku_id: uuid.UUID
    status: str = Field(default="active", max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    purchased_quantity: int | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def start_before_end(self):
        _require_start_on_or_before_end(self.start_date, self.end_date)
        _require_positive_quantity(self.purchased_quantity)
        return self


class CourseEnrollmentUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    purchased_quantity: int | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def start_before_end(self):
        _require_start_on_or_before_end(self.start_date, self.end_date)
        _require_positive_quantity(self.purchased_quantity)
        return self


class CourseEnrollmentOut(BaseModel):
    id: uuid.UUID
    unit_id: uuid.UUID
    sku_id: uuid.UUID
    status: str
    enrolled_at: date
    start_date: date | None = None
    end_date: date | None = None
    purchased_quantity: int | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
