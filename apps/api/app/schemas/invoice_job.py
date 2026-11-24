from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class InvoiceJobCreate(BaseModel):
    location_id: uuid.UUID
    name: str = Field(min_length=1, max_length=80)


class InvoiceJobOut(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}
