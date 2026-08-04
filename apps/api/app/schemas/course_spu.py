import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CourseSpuCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name_zh: str = Field(min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    subject: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_active: bool = True


class CourseSpuUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name_zh: str | None = Field(default=None, min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    subject: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_active: bool | None = None


class CourseSpuOut(BaseModel):
    id: uuid.UUID
    code: str
    name_zh: str
    name_en: str | None = None
    subject: str | None = None
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
