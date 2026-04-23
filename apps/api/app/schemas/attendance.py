import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.attendance import EventType


class ScanRequest(BaseModel):
    qr_token: str
    device_id: str | None = Field(default=None, max_length=255)


class AttendanceOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    username: str | None = None
    full_name: str | None = None
    event_type: str
    recorded_at: datetime
    qr_jti: str | None = None
    scanner_user_id: uuid.UUID | None = None
    client_device_id: str | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class ManualCorrectionRequest(BaseModel):
    user_id: uuid.UUID
    event_type: EventType = EventType.manual_correction
    recorded_at: datetime | None = None
    notes: str | None = None


class AttendanceListParams(BaseModel):
    user_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    event_type: EventType | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)
