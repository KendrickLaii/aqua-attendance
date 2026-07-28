import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class GuardianInfo(BaseModel):
    name: str | None = None
    relationship: str | None = None
    phone: str | None = None

    model_config = {"from_attributes": True}


class GuardiansData(BaseModel):
    guardian1: GuardianInfo | None = None
    guardian2: GuardianInfo | None = None

    model_config = {"from_attributes": True}


class StudentProfileCreate(BaseModel):
    school_name: str | None = Field(default=None, max_length=255)
    grade_class: str | None = Field(default=None, max_length=100)
    student_id: str | None = Field(default=None, max_length=100)
    guardians: dict[str, Any] | None = None
    enrollment_date: date | None = None
    graduation_date: date | None = None
    academic_notes: str | None = None


class StudentProfileUpdate(BaseModel):
    school_name: str | None = Field(default=None, max_length=255)
    grade_class: str | None = Field(default=None, max_length=100)
    student_id: str | None = Field(default=None, max_length=100)
    guardians: dict[str, Any] | None = None
    enrollment_date: date | None = None
    graduation_date: date | None = None
    academic_notes: str | None = None


class StudentProfileOut(BaseModel):
    id: uuid.UUID
    school_name: str | None = None
    grade_class: str | None = None
    student_id: str | None = None
    guardians: dict[str, Any] | None = None
    enrollment_date: date | None = None
    graduation_date: date | None = None
    academic_notes: str | None = None

    model_config = {"from_attributes": True}
