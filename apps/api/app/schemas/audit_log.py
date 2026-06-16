import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditLogCreate(BaseModel):
    user_id: uuid.UUID | None = None
    action: str = Field(min_length=1, max_length=50)
    table_name: str = Field(min_length=1, max_length=100)
    record_id: uuid.UUID | None = None
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    description: str | None = None
    ip_address: str | None = Field(default=None, max_length=45)
    user_agent: str | None = None
    session_id: str | None = Field(default=None, max_length=255)
    request_id: str | None = Field(default=None, max_length=100)
    batch_operation: bool = False


class AuditLogOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    username: str | None = None
    user_full_name: str | None = None
    action: str
    table_name: str
    record_id: uuid.UUID | None = None
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    description: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    batch_operation: bool
    created_at: datetime

    model_config = {"from_attributes": True}
