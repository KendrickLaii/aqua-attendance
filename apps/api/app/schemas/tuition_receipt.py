import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class TuitionReceiptPrintLine(BaseModel):
    month: str
    course: str
    fee: float
    qty: float
    amount: float
    invoice_id: uuid.UUID | None = None
    invoice_no: str | None = None


class TuitionReceiptAdjustment(BaseModel):
    month: str = ""
    course: str = "調整"
    fee: float | None = None
    qty: float | None = None
    amount: float

    @field_validator("month")
    @classmethod
    def strip_month(cls, value: str) -> str:
        return (value or "").strip()

    @field_validator("course")
    @classmethod
    def strip_course(cls, value: str) -> str:
        cleaned = (value or "").strip()
        return cleaned or "調整"


class TuitionReceiptLinkedInvoice(BaseModel):
    invoice_id: uuid.UUID
    invoice_no: str | None = None
    amount: float
    invoice_total: float
    status: str


class TuitionReceiptOut(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    unit_id: uuid.UUID | None = None
    unit_name: str | None = None
    unit_code: str | None = None
    payer_name: str | None = None
    paid_by: str
    receipt_no: str
    receipt_date: date
    amount: float
    status: str
    description: str | None = None
    primary_url: str | None = None
    invoices: list[TuitionReceiptLinkedInvoice] = Field(default_factory=list)
    print_lines: list[TuitionReceiptPrintLine] = Field(default_factory=list)
    adjustments: list[TuitionReceiptAdjustment] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TuitionReceiptCreate(BaseModel):
    location_id: uuid.UUID
    unit_id: uuid.UUID | None = None
    payer_name: str | None = Field(default=None, max_length=255)
    paid_by: str = Field(..., min_length=1, max_length=100)
    receipt_no: str = Field(..., min_length=1, max_length=50)
    receipt_date: date
    invoice_ids: list[uuid.UUID] = Field(..., min_length=1)
    amount: float | None = None
    adjustments: list[TuitionReceiptAdjustment] = Field(default_factory=list)
    description: str | None = None

    @field_validator("paid_by")
    @classmethod
    def strip_paid_by(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("paid_by is required")
        return cleaned

    @field_validator("receipt_no")
    @classmethod
    def strip_receipt_no(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("receipt_no is required")
        return cleaned

    @field_validator("payer_name")
    @classmethod
    def strip_payer_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("invoice_ids")
    @classmethod
    def unique_invoice_ids(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        return list(dict.fromkeys(value))
