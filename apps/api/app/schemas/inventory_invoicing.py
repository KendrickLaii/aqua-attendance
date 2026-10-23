import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.inventory_sales import DeliveryOrderOut, SalesOrderOut

InvoiceStatus = Literal["draft", "issued", "void"]
PaymentStatus = Literal["unpaid", "partial", "paid", "void"]
ReceiptPaidBy = Literal["cash", "cheque", "bank_transfer", "card", "other"]
ReceiptStatus = Literal["posted", "void"]
CreditNoteStatus = Literal["draft", "confirmed", "void"]


class InventoryInvoiceLineIn(BaseModel):
    so_line_id: uuid.UUID
    qty: int = Field(gt=0)


class InventoryInvoiceLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    so_line_id: uuid.UUID
    item_id: uuid.UUID
    sku_code: str
    name_zh: str
    unit_price: float
    qty: int
    discount_amount: float
    amount: float
    credited_qty: int
    delivered_qty: int


class InventoryInvoiceCreate(BaseModel):
    so_id: uuid.UUID
    issue_date: date | None = None
    discount_amount: float | None = Field(default=None, ge=0)
    notes: str | None = None
    lines: list[InventoryInvoiceLineIn] = []


class InventoryInvoiceUpdate(BaseModel):
    issue_date: date | None = None
    discount_amount: float | None = Field(default=None, ge=0)
    notes: str | None = None
    lines: list[InventoryInvoiceLineIn] | None = None


class InvoiceReceiptSummary(BaseModel):
    id: uuid.UUID
    receipt_no: str
    amount: float
    paid_by: str
    receipt_date: date
    status: str


class InvoiceCreditNoteSummary(BaseModel):
    id: uuid.UUID
    scn_no: str
    total: float
    credit_date: date
    status: str


class InvoiceDeliveryOrderSummary(BaseModel):
    id: uuid.UUID
    do_no: str
    delivery_date: date
    status: str


class InventoryInvoiceOut(BaseModel):
    id: uuid.UUID
    invoice_no: str | None
    so_id: uuid.UUID
    so_no: str
    customer_id: uuid.UUID
    customer_name: str | None
    buyer_name: str
    location_id: uuid.UUID
    issue_date: date | None
    status: str
    discount_amount: float
    subtotal: float
    total: float
    paid_total: float
    credited_total: float
    balance: float
    payment_status: str
    notes: str | None
    issued_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    lines: list[InventoryInvoiceLineOut]
    receipts: list[InvoiceReceiptSummary]
    credit_notes: list[InvoiceCreditNoteSummary]
    delivery_orders: list[InvoiceDeliveryOrderSummary]


class InventoryInvoicePrint(BaseModel):
    invoice_no: str
    issue_date: date | None
    issued_at: datetime | None
    buyer_name: str
    customer_code: str
    customer_name_zh: str | None
    customer_name_en: str | None
    customer_contact: str | None
    customer_phone: str | None
    customer_email: str | None
    customer_address: str | None
    location_name_zh: str | None
    location_name_en: str | None
    location_address: str | None
    location_phone: str | None
    so_no: str
    lines: list[InventoryInvoiceLineOut]
    discount_amount: float
    subtotal: float
    total: float
    paid_total: float
    credited_total: float
    balance: float
    payment_status: str
    notes: str | None


class InventoryReceiptCreate(BaseModel):
    invoice_id: uuid.UUID
    amount: float = Field(gt=0)
    paid_by: ReceiptPaidBy
    reference_no: str | None = None
    receipt_date: date | None = None
    notes: str | None = None


class InventoryReceiptOut(BaseModel):
    id: uuid.UUID
    receipt_no: str
    invoice_id: uuid.UUID
    invoice_no: str | None
    customer_id: uuid.UUID
    customer_name: str | None
    location_id: uuid.UUID
    amount: float
    paid_by: str
    reference_no: str | None
    receipt_date: date
    status: str
    notes: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class InventoryReceiptPrint(BaseModel):
    receipt_no: str
    receipt_date: date
    status: str
    invoice_no: str | None
    invoice_total: float
    invoice_paid_total: float
    invoice_balance: float
    buyer_name: str
    customer_code: str
    customer_name_zh: str | None
    customer_name_en: str | None
    location_name_zh: str | None
    location_name_en: str | None
    location_address: str | None
    location_phone: str | None
    amount: float
    paid_by: str
    reference_no: str | None
    notes: str | None


class InventoryCreditNoteLineIn(BaseModel):
    invoice_line_id: uuid.UUID
    qty: int = Field(gt=0)
    restock: bool = True


class InventoryCreditNoteLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_line_id: uuid.UUID
    item_id: uuid.UUID
    sku_code: str | None = None
    name_zh: str | None = None
    qty: int
    unit_amount: float
    amount: float
    restock: bool


class InventoryCreditNoteCreate(BaseModel):
    invoice_id: uuid.UUID
    credit_date: date | None = None
    reason: str = Field(min_length=1)
    lines: list[InventoryCreditNoteLineIn] = Field(min_length=1)


class InventoryCreditNoteUpdate(BaseModel):
    credit_date: date | None = None
    reason: str | None = Field(default=None, min_length=1)
    lines: list[InventoryCreditNoteLineIn] | None = None


class InventoryCreditNoteOut(BaseModel):
    id: uuid.UUID
    scn_no: str
    invoice_id: uuid.UUID
    invoice_no: str | None
    customer_id: uuid.UUID
    customer_name: str | None
    location_id: uuid.UUID
    credit_date: date
    reason: str
    status: str
    total: float
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    lines: list[InventoryCreditNoteLineOut]


class InventoryCreditNotePrint(BaseModel):
    scn_no: str
    credit_date: date
    status: str
    invoice_no: str | None
    buyer_name: str
    customer_code: str
    customer_name_zh: str | None
    customer_name_en: str | None
    location_name_zh: str | None
    location_name_en: str | None
    location_address: str | None
    location_phone: str | None
    reason: str
    lines: list[InventoryCreditNoteLineOut]
    total: float


class QuickFulfillPay(BaseModel):
    amount: float = Field(gt=0)
    paid_by: ReceiptPaidBy
    reference_no: str | None = None


class QuickFulfillRequest(BaseModel):
    pay: QuickFulfillPay | None = None
    issue_date: date | None = None
    deliver_now: bool = True


class QuickFulfillResult(BaseModel):
    so: SalesOrderOut
    delivery_order: DeliveryOrderOut | None
    invoice: InventoryInvoiceOut
    receipt: InventoryReceiptOut | None
