import uuid
from datetime import date

from pydantic import BaseModel, Field


class StaffProfileCreate(BaseModel):
    gender: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    employee_id: str | None = Field(default=None, max_length=100)
    employment_type: str | None = Field(default=None, max_length=20)
    department: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    salary_grade: str | None = Field(default=None, max_length=50)
    pay_type: str | None = Field(default=None, max_length=20)
    hourly_rate: float | None = Field(default=None, ge=0)
    monthly_salary: float | None = Field(default=None, ge=0)
    ot_multiplier: float | None = Field(default=None, ge=0)
    work_schedule: str | None = Field(default=None, max_length=255)
    supervisor_id: uuid.UUID | None = None
    employment_notes: str | None = None


class StaffProfileUpdate(BaseModel):
    gender: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    employee_id: str | None = Field(default=None, max_length=100)
    employment_type: str | None = Field(default=None, max_length=20)
    department: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    salary_grade: str | None = Field(default=None, max_length=50)
    pay_type: str | None = Field(default=None, max_length=20)
    hourly_rate: float | None = Field(default=None, ge=0)
    monthly_salary: float | None = Field(default=None, ge=0)
    ot_multiplier: float | None = Field(default=None, ge=0)
    work_schedule: str | None = Field(default=None, max_length=255)
    supervisor_id: uuid.UUID | None = None
    employment_notes: str | None = None


class StaffProfileOut(BaseModel):
    id: uuid.UUID
    gender: str | None = None
    date_of_birth: date | None = None
    employee_id: str | None = None
    employment_type: str | None = None
    department: str | None = None
    position: str | None = None
    salary_grade: str | None = None
    pay_type: str | None = None
    hourly_rate: float | None = None
    monthly_salary: float | None = None
    ot_multiplier: float | None = None
    work_schedule: str | None = None
    supervisor_id: uuid.UUID | None = None
    employment_notes: str | None = None

    model_config = {"from_attributes": True}
