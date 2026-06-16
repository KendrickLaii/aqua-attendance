import enum
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NotificationType(str, enum.Enum):
    attendance_alert = "attendance_alert"
    system_announcement = "system_announcement"
    payroll_notice = "payroll_notice"
    reminder = "reminder"


class NotificationPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class NotificationCreate(BaseModel):
    user_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1)
    notification_type: str = Field(default=NotificationType.attendance_alert.value)
    priority: str = Field(default=NotificationPriority.medium.value)
    action_url: str | None = Field(default=None, max_length=500)
    extra_data: dict | None = None
    expires_at: datetime | None = None


class NotificationUpdate(BaseModel):
    is_read: bool | None = None
    read_at: datetime | None = None


class NotificationOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    title: str
    message: str
    notification_type: str
    priority: str
    is_read: bool
    read_at: datetime | None = None
    action_url: str | None = None
    extra_data: str | None = None
    created_at: datetime
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}
