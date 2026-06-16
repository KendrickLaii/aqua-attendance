import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class AttendanceSummaryCreate(BaseModel):
    product_id: uuid.UUID
    summary_date: date
    location_id: uuid.UUID
    first_check_in: datetime | None = None
    last_check_out: datetime | None = None
    total_work_minutes: int = Field(default=0, ge=0)
    total_overtime_minutes: int = Field(default=0, ge=0)
    total_break_minutes: int = Field(default=0, ge=0)
    is_complete: bool = False
    is_holiday: bool = False
    is_weekend: bool = False
    regular_hours: float = Field(default=0.0, ge=0)
    overtime_hours: float = Field(default=0.0, ge=0)
    holiday_hours: float = Field(default=0.0, ge=0)
    attendance_notes: str | None = Field(default=None, max_length=500)
    calculation_method: str = Field(default="standard", max_length=50)


class AttendanceSummaryOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    summary_date: date
    location_id: uuid.UUID
    first_check_in: datetime | None = None
    last_check_out: datetime | None = None
    total_work_minutes: int
    total_overtime_minutes: int
    total_break_minutes: int
    is_complete: bool
    is_holiday: bool
    is_weekend: bool
    regular_hours: float
    overtime_hours: float
    holiday_hours: float
    attendance_notes: str | None = None
    calculation_method: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
