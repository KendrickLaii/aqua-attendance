import enum
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator

from app.models.attendance import EventType


class ScanEventType(str, enum.Enum):
    check_in = "check_in"
    check_out = "check_out"


class ScanRequest(BaseModel):
    qr_token: str
    device_id: str | None = Field(default=None, max_length=255)
    location_id: uuid.UUID | None = None
    location: str | None = Field(default=None, max_length=255)
    event_type: ScanEventType | None = Field(
        default=None,
        description="Explicit check-in or check-out. Omit to auto-toggle from product status.",
    )


class AttendanceOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_code: str | None = None
    product_name: str | None = None
    product_type: str | None = None
    event_type: str
    recorded_at: datetime
    attendance_status: str | None = None
    qr_jti: str | None = None
    recorded_by_user_id: uuid.UUID | None = None
    client_device_id: str | None = None
    location_id: uuid.UUID | None = None
    location: str | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class ManualCorrectionRequest(BaseModel):
    product_id: uuid.UUID
    event_type: EventType = EventType.manual_correction
    recorded_at: datetime | None = None
    location_id: uuid.UUID | None = None
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = None

    @field_validator("recorded_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: object) -> datetime | None:
        if v is None:
            return None
        if not isinstance(v, datetime):
            raise ValueError("recorded_at must be a datetime")
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class AttendanceListParams(BaseModel):
    product_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    event_type: EventType | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class AttendanceDayStatsOut(BaseModel):
    total: int
    check_ins_student: int
    check_ins_staff: int
    check_outs_student: int
    check_outs_staff: int
