from datetime import date

from pydantic import BaseModel


class StockValuationRow(BaseModel):
    item_id: str
    sku_code: str
    name_zh: str
    location_id: str
    location_name: str | None
    quantity: int
    reserved: int
    available: int
    avg_cost: float
    value: float


class StockValuationReport(BaseModel):
    rows: list[StockValuationRow]
    location_totals: list[dict]
    grand_total: float


class MovementSummaryRow(BaseModel):
    item_id: str
    sku_code: str
    name_zh: str
    qty_in: int
    qty_out: int
    qty_adjust: int
    qty_transfer_in: int
    qty_transfer_out: int
    net_change: int
    reasons: dict[str, int]


class MovementSummaryReport(BaseModel):
    rows: list[MovementSummaryRow]
    totals: dict


class PurchaseReportRow(BaseModel):
    supplier_id: str
    supplier_name: str | None
    item_id: str
    sku_code: str
    name_zh: str
    qty_received: int
    value_received: float
    qty_returned: int
    value_returned: float
    net_qty: int
    net_value: float


class OpenOrderRow(BaseModel):
    po_id: str
    po_no: str
    supplier_id: str
    supplier_name: str | None
    location_id: str
    order_date: date | None
    expected_date: date | None
    status: str
    outstanding_qty: int
    outstanding_value: float
    overdue: bool


class PurchasesReport(BaseModel):
    rows: list[PurchaseReportRow]
    totals: dict
    open_orders: list[OpenOrderRow]


class SalesReportRow(BaseModel):
    date: date
    customer_id: str
    customer_name: str | None
    item_id: str
    sku_code: str
    name_zh: str
    invoice_count: int
    qty: int
    amount: float


class SalesReport(BaseModel):
    rows: list[SalesReportRow]
    totals: dict


class ReceivableRow(BaseModel):
    invoice_id: str
    invoice_no: str
    customer_id: str
    customer_name: str | None
    location_id: str
    issue_date: date | None
    total: float
    paid: float
    credited: float
    balance: float
    days_outstanding: int
    bucket: str


class ReceivablesReport(BaseModel):
    rows: list[ReceivableRow]
    customer_totals: list[dict]
    buckets: dict[str, float]
    grand_total: float


class WriteOffRow(BaseModel):
    reason_code: str
    item_id: str
    sku_code: str
    name_zh: str
    qty: int
    cost: float
    cost_missing: int


class WriteOffsReport(BaseModel):
    rows: list[WriteOffRow]
    totals: dict


class InventoryDashboard(BaseModel):
    tracked_items: int
    low_stock_count: int
    stock_value: float
    open_purchase_orders: int
    overdue_purchase_orders: int
    open_sales_orders: int
    unshipped_qty: int
    unpaid_invoice_count: int
    receivable_balance: float
    overdue_receivable_balance: float
    month_sales: float
    month_purchases: float
    month_invoiced: float
    month_credited: float
    month_purchases_gross: float
    month_purchase_returns: float


class AlertsOut(BaseModel):
    low_stock: list[dict]
    overdue_purchase_orders: list[dict]
    overdue_invoices: list[dict]
    expiring_proformas: list[dict]


class NotifyResult(BaseModel):
    created: int
    skipped: int
    locked: bool = False
