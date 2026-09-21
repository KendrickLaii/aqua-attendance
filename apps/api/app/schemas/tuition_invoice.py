import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


TuitionInvoiceStatusLiteral = Literal["draft", "issued", "paid", "void"]


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
    month_label: str | None = None
    staff_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TuitionInvoiceOut(BaseModel):
    id: uuid.UUID
    unit_id: uuid.UUID | None = None
    unit_name: str | None = None
    unit_code: str | None = None
    manual_student_name: str | None = None
    staff_name: str | None = None
    location_id: uuid.UUID
    period_start: date
    period_end: date
    status: TuitionInvoiceStatusLiteral
    kind: str
    total: float
    notes: str | None = None
    invoice_no: str | None = None
    receipt_no: str | None = None
    issued_at: datetime | None = None
    lines: list[TuitionInvoiceLineOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TuitionInvoiceUpdate(BaseModel):
    status: TuitionInvoiceStatusLiteral | None = None
    notes: str | None = None
    invoice_no: str | None = Field(default=None, max_length=50)
    staff_name: str | None = Field(default=None, max_length=255)


class LeftoverPurchaseOut(BaseModel):
    unit_code: str | None = None
    unit_name: str | None = None
    sku_code: str | None = None
    purchased_at: date
    purchased_quantity: int


class TuitionInvoiceGenerateResult(BaseModel):
    created: int
    updated: int
    skipped: int
    deleted: int = 0
    leftover_unbilled: int = 0
    leftover_purchases: list[LeftoverPurchaseOut] = Field(default_factory=list)


class TuitionInvoiceNextNo(BaseModel):
    next_no: int


class TuitionInvoiceManualLine(BaseModel):
    month: str = Field(..., max_length=50)
    course: str = Field(..., max_length=255)
    fee: float = Field(..., ge=0)
    qty: float = Field(..., gt=0)
    staff_name: str | None = Field(default=None, max_length=255)
    # Set when this line settles an unbilled per-session EnrollmentPurchase:
    # the typed `fee` is the charged price (purchases may have no price yet);
    # quantity always comes from the purchase so a package is billed whole.
    purchase_id: uuid.UUID | None = None


class TuitionInvoiceManualCreate(BaseModel):
    date: date
    location_id: uuid.UUID
    unit_id: uuid.UUID | None = None
    manual_student_name: str | None = Field(default=None, max_length=255)
    # 開單人 — staff/teacher who opened the invoice (commission record).
    staff_name: str | None = Field(default=None, max_length=255)
    invoice_no: str | None = Field(default=None, max_length=50)
    notes: str | None = None
    lines: list[TuitionInvoiceManualLine] = Field(default_factory=list)

    @model_validator(mode="after")
    def student_or_name(self):
        if self.unit_id is None and not (self.manual_student_name and self.manual_student_name.strip()):
            raise ValueError("Either unit_id or manual_student_name is required")
        if not self.lines:
            raise ValueError("At least one line is required")
        return self
