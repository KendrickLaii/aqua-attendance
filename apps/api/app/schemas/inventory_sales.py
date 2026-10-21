from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

CustomerType = Literal["individual", "company"]
SoStatus = Literal["draft", "confirmed", "partial", "fulfilled", "cancelled"]
DoStatus = Literal["draft", "confirmed", "void"]


class CustomerCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name_zh: str = Field(min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    type: CustomerType = "individual"
    contact_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    student_unit_id: uuid.UUID | None = None
    is_active: bool = True


class CustomerUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name_zh: str | None = Field(default=None, min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    type: CustomerType | None = None
    contact_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class CustomerOut(BaseModel):
    id: uuid.UUID
    code: str
    name_zh: str
    name_en: str | None = None
    type: CustomerType
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    student_unit_id: uuid.UUID | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SalesOrderLineIn(BaseModel):
    item_id: uuid.UUID
    qty: int = Field(gt=0)
    unit_price: float = Field(ge=0)
    discount_amount: float = Field(default=0, ge=0)


class SalesOrderLineOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    sku_code: str
    name_zh: str
    qty: int
    shipped_qty: int
    unit_price: float
    discount_amount: float
    amount: float

    model_config = {"from_attributes": True}


class SalesOrderCreate(BaseModel):
    customer_id: uuid.UUID
    location_id: uuid.UUID
    order_date: date
    discount_amount: float = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=500)
    lines: list[SalesOrderLineIn] = Field(default_factory=list)


class SalesOrderUpdate(BaseModel):
    customer_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    order_date: date | None = None
    discount_amount: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=500)
    lines: list[SalesOrderLineIn] | None = None


class SalesOrderOut(BaseModel):
    id: uuid.UUID
    so_no: str
    customer_id: uuid.UUID
    buyer_name: str
    location_id: uuid.UUID
    order_date: date
    status: SoStatus
    discount_amount: float
    total: float
    notes: str | None = None
    pf_no: str | None = None
    pf_issued_at: datetime | None = None
    pf_valid_until: date | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[SalesOrderLineOut] = Field(default_factory=list)

    customer_name: str | None = None
    customer_code: str | None = None
    location_name: str | None = None

    model_config = {"from_attributes": True}


class ProformaRequest(BaseModel):
    pf_valid_until: date | None = None


class ProformaDoc(BaseModel):
    pf_no: str
    so_no: str
    issued_at: datetime
    valid_until: date | None = None
    order_date: date

    location_name_zh: str | None = None
    location_name_en: str | None = None
    location_address: str | None = None
    location_phone: str | None = None
    location_email: str | None = None

    customer_name: str
    customer_code: str | None = None
    customer_contact: str | None = None
    customer_phone: str | None = None
    customer_email: str | None = None
    customer_address: str | None = None

    lines: list[SalesOrderLineOut] = Field(default_factory=list)
    discount_amount: float = 0
    subtotal: float = 0
    total: float = 0
    notes: str | None = None


class DeliveryOrderLineIn(BaseModel):
    so_line_id: uuid.UUID
    item_id: uuid.UUID
    qty: int = Field(gt=0)


class DeliveryOrderLineOut(BaseModel):
    id: uuid.UUID
    so_line_id: uuid.UUID
    item_id: uuid.UUID
    qty: int
    sku_code: str | None = None
    name_zh: str | None = None

    model_config = {"from_attributes": True}


class DeliveryOrderCreate(BaseModel):
    so_id: uuid.UUID
    delivery_date: date
    notes: str | None = Field(default=None, max_length=500)
    lines: list[DeliveryOrderLineIn] = Field(default_factory=list)


class DeliveryOrderUpdate(BaseModel):
    delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)
    lines: list[DeliveryOrderLineIn] | None = None


class DeliveryOrderOut(BaseModel):
    id: uuid.UUID
    do_no: str
    so_id: uuid.UUID
    customer_id: uuid.UUID
    location_id: uuid.UUID
    delivery_date: date
    status: DoStatus
    notes: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[DeliveryOrderLineOut] = Field(default_factory=list)

    so_no_ref: str | None = None
    customer_name: str | None = None
    location_name: str | None = None

    model_config = {"from_attributes": True}
