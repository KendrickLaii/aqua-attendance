import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class TuitionInvoiceLineOut(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    enrollment_id: uuid.UUID | None = None
    sku_id: uuid.UUID | None = None
    sku_code: str
    name_zh: str
    billing_unit: str
    unit_price: float
    quantity: float
    amount: float
    created_at: datetime

    model_config = {"from_attributes": True}


class TuitionInvoiceOut(BaseModel):
    id: uuid.UUID
    unit_id: uuid.UUID
    unit_name: str | None = None
    unit_code: str | None = None
    period_start: date
    period_end: date
    status: str
    total: float
    notes: str | None = None
    lines: list[TuitionInvoiceLineOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TuitionInvoiceUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=20)
    notes: str | None = None


class TuitionInvoiceGenerateResult(BaseModel):
    created: int
    updated: int
    skipped: int
    deleted: int = 0
