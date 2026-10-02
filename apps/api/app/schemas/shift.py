import uuid
from datetime import date, datetime, time
from typing import Self

from pydantic import BaseModel, Field, model_validator

HEX_COLOR = r"^#[0-9A-Fa-f]{6}$"


def _check_times(start: time | None, end: time | None) -> None:
    if start is not None and end is not None and end <= start:
        raise ValueError("end_time must be after start_time")


class ShiftTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    start_time: time
    end_time: time
    color: str = Field(pattern=HEX_COLOR)
    sort_order: int = 0

    @model_validator(mode="after")
    def _validate_times(self) -> Self:
        _check_times(self.start_time, self.end_time)
        return self


class ShiftTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    start_time: time | None = None
    end_time: time | None = None
    color: str | None = Field(default=None, pattern=HEX_COLOR)
    sort_order: int | None = None


class ShiftTemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    start_time: time
    end_time: time
    color: str
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShiftCreate(BaseModel):
    unit_id: uuid.UUID
    location_id: uuid.UUID
    shift_date: date
    start_time: time
    end_time: time
    title: str | None = Field(default=None, max_length=100)
    color: str = Field(pattern=HEX_COLOR)
    notes: str | None = None
    template_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _validate_times(self) -> Self:
        _check_times(self.start_time, self.end_time)
        return self


class ShiftUpdate(BaseModel):
    unit_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    shift_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    title: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, pattern=HEX_COLOR)
    notes: str | None = None
    template_id: uuid.UUID | None = None


class ShiftOut(BaseModel):
    id: uuid.UUID
    unit_id: uuid.UUID
    location_id: uuid.UUID
    shift_date: date
    start_time: time
    end_time: time
    title: str | None = None
    color: str
    notes: str | None = None
    template_id: uuid.UUID | None = None
    created_by_id: uuid.UUID | None = None
    updated_by_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShiftCopyWeek(BaseModel):
    source_week_start: date
    target_week_start: date
    location_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _validate_weeks(self) -> Self:
        if self.source_week_start.weekday() != 0 or self.target_week_start.weekday() != 0:
            raise ValueError("source_week_start and target_week_start must be Mondays")
        if self.source_week_start == self.target_week_start:
            raise ValueError("source and target weeks must differ")
        return self


class ShiftCopyWeekResult(BaseModel):
    created: int
    skipped: int


class ShiftRequestCreate(BaseModel):
    location_id: uuid.UUID
    shift_date: date
    start_time: time
    end_time: time
    title: str | None = Field(default=None, max_length=100)
    color: str = Field(pattern=HEX_COLOR)
    notes: str | None = None
    template_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _validate_times(self) -> Self:
        _check_times(self.start_time, self.end_time)
        return self


class ShiftRequestOut(BaseModel):
    id: uuid.UUID
    unit_id: uuid.UUID
    location_id: uuid.UUID
    shift_date: date
    start_time: time
    end_time: time
    title: str | None = None
    color: str
    notes: str | None = None
    template_id: uuid.UUID | None = None
    status: str
    reject_reason: str | None = None
    shift_id: uuid.UUID | None = None
    reviewed_by_id: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    unit_code: str | None = None
    unit_name: str | None = None

    model_config = {"from_attributes": True}


class ShiftRequestReject(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class StaffShiftLogin(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    pin: str = Field(min_length=6, max_length=6)


class StaffShiftMe(BaseModel):
    id: uuid.UUID
    code: str
    full_name: str


class StaffShiftLoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    unit: StaffShiftMe


class StaffShiftWeek(BaseModel):
    shifts: list[ShiftOut]
    requests: list[ShiftRequestOut]


class StaffLocationOut(BaseModel):
    id: uuid.UUID
    name_en: str
    name_zh: str | None = None

    model_config = {"from_attributes": True}
