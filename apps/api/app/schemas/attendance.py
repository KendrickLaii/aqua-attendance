import enum
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field, field_validator

from app.models.attendance import EventType, EventSource


class ScanEventType(str, enum.Enum):
    check_in = "check_in"
    check_out = "check_out"


class EventSourceOut(str, enum.Enum):
    scan = "scan"
    manual = "manual"
    auto_checkout = "auto_checkout"


class ScanRequest(BaseModel):
    qr_token: str
    device_id: str | None = Field(default=None, max_length=255)
    location_id: uuid.UUID | None = None
    location: str | None = Field(default=None, max_length=255)
    event_type: ScanEventType | None = Field(
        default=None,
        description="Explicit check-in or check-out. Omit to auto-toggle from unit status.",
    )


class ScanPreviewRequest(BaseModel):
    qr_token: str
    location_id: uuid.UUID | None = None


class ScanPreviewOut(BaseModel):
    unit_id: uuid.UUID
    unit_code: str | None = None
    unit_name: str | None = None
    unit_type: str | None = None
    attendance_status: str | None = None
    location: str | None = None


class ScanAllowedLocation(BaseModel):
    id: uuid.UUID
    code: str | None = None
    name_zh: str
    name_en: str


class ScanLocationNotAllowedDetail(BaseModel):
    code: str = "location_not_allowed"
    message: str
    unit_name: str | None = None
    unit_code: str | None = None
    allowed_locations: list[ScanAllowedLocation] = Field(default_factory=list)


class AttendanceOut(BaseModel):
    id: uuid.UUID
    unit_id: uuid.UUID
    unit_code: str | None = None
    unit_name: str | None = None
    unit_type: str | None = None
    event_type: str
    source: EventSourceOut
    recorded_at: datetime
    created_at: datetime
    attendance_status: str | None = None
    qr_jti: str | None = None
    recorded_by_user_id: uuid.UUID | None = None
    client_device_id: str | None = None
    location_id: uuid.UUID | None = None
    location: str | None = None
    notes: str | None = None
    voided_at: datetime | None = None

    model_config = {"from_attributes": True}


#: Tolerance for client/server clock skew when checking for future timestamps.
MANUAL_CORRECTION_FUTURE_TOLERANCE = timedelta(minutes=5)


class ManualCorrectionRequest(BaseModel):
    unit_id: uuid.UUID
    event_type: EventType  # 現在必須明確指定 check_in 或 check_out
    recorded_at: datetime | None = None
    location_id: uuid.UUID | None = None
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = None

    @field_validator("recorded_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        else:
            v = v.astimezone(timezone.utc)
        # A corrected event that has not happened yet is always a typo, and it
        # poisons every later query that orders by or filters on recorded_at.
        if v > datetime.now(timezone.utc) + MANUAL_CORRECTION_FUTURE_TOLERANCE:
            raise ValueError("recorded_at cannot be in the future")
        return v


class AttendanceListParams(BaseModel):
    unit_id: uuid.UUID | None = None
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
