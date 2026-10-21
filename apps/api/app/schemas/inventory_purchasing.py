from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

PoStatus = Literal["draft", "ordered", "partial", "received", "cancelled"]
ReceiptStatus = Literal["draft", "confirmed", "void"]


class SupplierCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name_zh: str = Field(min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    contact_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    payment_terms: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class SupplierUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name_zh: str | None = Field(default=None, min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    contact_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    payment_terms: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class SupplierOut(BaseModel):
    id: uuid.UUID
    code: str
    name_zh: str
    name_en: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    payment_terms: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PurchaseOrderLineIn(BaseModel):
    item_id: uuid.UUID
    ordered_qty: int = Field(gt=0)
    unit_cost: float = Field(ge=0)
    discount_amount: float = Field(default=0, ge=0)


class PurchaseOrderLineOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    sku_code: str
    name_zh: str
    ordered_qty: int
    received_qty: int
    unit_cost: float
    discount_amount: float
    amount: float

    model_config = {"from_attributes": True}


class PurchaseOrderCreate(BaseModel):
    supplier_id: uuid.UUID
    location_id: uuid.UUID
    order_date: date
    expected_date: date | None = None
    discount_amount: float = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=500)
    lines: list[PurchaseOrderLineIn] = Field(default_factory=list)


class PurchaseOrderUpdate(BaseModel):
    supplier_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    order_date: date | None = None
    expected_date: date | None = None
    discount_amount: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=500)
    lines: list[PurchaseOrderLineIn] | None = None


class PurchaseOrderOut(BaseModel):
    id: uuid.UUID
    po_no: str
    supplier_id: uuid.UUID
    location_id: uuid.UUID
    order_date: date
    expected_date: date | None = None
    status: PoStatus
    discount_amount: float
    total: float
    notes: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[PurchaseOrderLineOut] = Field(default_factory=list)

    supplier_name: str | None = None
    location_name: str | None = None

    model_config = {"from_attributes": True}


class GoodsReceiptLineIn(BaseModel):
    item_id: uuid.UUID
    qty: int = Field(gt=0)
    unit_cost: float = Field(ge=0)
    po_line_id: uuid.UUID | None = None


class GoodsReceiptLineOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    po_line_id: uuid.UUID | None = None
    qty: int
    unit_cost: float
    sku_code: str | None = None
    name_zh: str | None = None

    model_config = {"from_attributes": True}


class GoodsReceiptCreate(BaseModel):
    po_id: uuid.UUID | None = None
    supplier_id: uuid.UUID
    location_id: uuid.UUID
    receipt_date: date
    notes: str | None = Field(default=None, max_length=500)
    allow_over_receipt: bool = False
    lines: list[GoodsReceiptLineIn] = Field(default_factory=list)


class GoodsReceiptUpdate(BaseModel):
    receipt_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)
    allow_over_receipt: bool = False
    lines: list[GoodsReceiptLineIn] | None = None


class GoodsReceiptOut(BaseModel):
    id: uuid.UUID
    grn_no: str
    po_id: uuid.UUID | None = None
    supplier_id: uuid.UUID
    location_id: uuid.UUID
    receipt_date: date
    status: ReceiptStatus
    notes: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[GoodsReceiptLineOut] = Field(default_factory=list)

    supplier_name: str | None = None
    location_name: str | None = None
    po_no: str | None = None

    model_config = {"from_attributes": True}


class PurchaseReturnLineIn(BaseModel):
    item_id: uuid.UUID
    qty: int = Field(gt=0)
    unit_cost: float = Field(ge=0)


class PurchaseReturnLineOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    qty: int
    unit_cost: float
    sku_code: str | None = None
    name_zh: str | None = None

    model_config = {"from_attributes": True}


class PurchaseReturnCreate(BaseModel):
    supplier_id: uuid.UUID
    location_id: uuid.UUID
    grn_id: uuid.UUID | None = None
    return_date: date
    notes: str | None = Field(default=None, max_length=500)
    lines: list[PurchaseReturnLineIn] = Field(default_factory=list)


class PurchaseReturnUpdate(BaseModel):
    grn_id: uuid.UUID | None = None
    return_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)
    lines: list[PurchaseReturnLineIn] | None = None


class PurchaseReturnOut(BaseModel):
    id: uuid.UUID
    prt_no: str
    supplier_id: uuid.UUID
    location_id: uuid.UUID
    grn_id: uuid.UUID | None = None
    return_date: date
    status: ReceiptStatus
    notes: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[PurchaseReturnLineOut] = Field(default_factory=list)

    supplier_name: str | None = None
    location_name: str | None = None
    grn_no: str | None = None

    model_config = {"from_attributes": True}
