import uuid
from datetime import date

from pydantic import BaseModel, Field


class StaffProfileCreate(BaseModel):
    employee_id: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    hire_date: date | None = None
    termination_date: date | None = None
    salary_grade: str | None = Field(default=None, max_length=50)
    work_schedule: str | None = Field(default=None, max_length=255)
    supervisor_id: uuid.UUID | None = None
    employment_notes: str | None = None


class StaffProfileUpdate(BaseModel):
    employee_id: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    hire_date: date | None = None
    termination_date: date | None = None
    salary_grade: str | None = Field(default=None, max_length=50)
    work_schedule: str | None = Field(default=None, max_length=255)
    supervisor_id: uuid.UUID | None = None
    employment_notes: str | None = None


class StaffProfileOut(BaseModel):
    id: uuid.UUID
    employee_id: str | None = None
    department: str | None = None
    position: str | None = None
    hire_date: date | None = None
    termination_date: date | None = None
    salary_grade: str | None = None
    work_schedule: str | None = None
    supervisor_id: uuid.UUID | None = None
    employment_notes: str | None = None

    model_config = {"from_attributes": True}
