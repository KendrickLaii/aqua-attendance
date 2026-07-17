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
    is_complete: bool = False
    is_holiday: bool = False
    is_weekend: bool = False
    regular_slots: int = Field(default=0, ge=0)
    ot_slots: int = Field(default=0, ge=0)
    regular_hours: float = Field(default=0.0, ge=0)
    overtime_hours: float = Field(default=0.0, ge=0)
    holiday_hours: float = Field(default=0.0, ge=0)
    attendance_notes: str | None = Field(default=None, max_length=500)
    calculation_method: str = Field(default="standard", max_length=50)


class AttendanceSummaryOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    product_code: str | None = None
    summary_date: date
    location_id: uuid.UUID
    first_check_in: datetime | None = None
    last_check_out: datetime | None = None
    total_work_minutes: int
    total_overtime_minutes: int
    is_complete: bool
    is_holiday: bool
    is_weekend: bool
    regular_slots: int = 0
    ot_slots: int = 0
    regular_hours: float
    overtime_hours: float
    holiday_hours: float
    attendance_notes: str | None = None
    calculation_method: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AttendanceSummaryOverviewOut(BaseModel):
    product_id: uuid.UUID
    product_name: str | None = None
    product_code: str | None = None
    product_type: str
    days_present: int
    days_complete: int
    days_incomplete: int
    total_regular_hours: float
    total_overtime_hours: float
    total_regular_slots: int = 0
    total_ot_slots: int = 0
    first_date: date | None = None
    last_date: date | None = None


class AttendanceSummaryOverviewStatsOut(BaseModel):
    """Month-wide overview totals (not limited to the current page)."""

    people: int
    days_present: int
    days_complete: int
    days_incomplete: int
    total_regular_hours: float
    total_overtime_hours: float
    total_regular_slots: int = 0
    total_ot_slots: int = 0
