import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LocationAttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    location_id: uuid.UUID
    month: str
    original_name: str
    content_type: str
    size: int
    caption: str | None
    created_at: datetime


class AttachmentLimitsOut(BaseModel):
    earliest_month: str
    current_month: str
    per_month: int
    items: list[LocationAttachmentOut]
