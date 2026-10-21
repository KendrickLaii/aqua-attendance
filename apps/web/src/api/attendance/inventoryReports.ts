import { $attendanceApi } from '@/utils/attendanceApi'

export interface StockValuationRow {
  item_id: string
  sku_code: string
  name_zh: string
  location_id: string
  location_name: string | null
  quantity: number
  reserved: number
  available: number
  avg_cost: number
  value: number
}

export interface StockValuationReport {
  rows: StockValuationRow[]
  location_totals: { location_id: string; location_name: string | null; value: number }[]
  grand_total: number
}

export interface MovementSummaryRow {
  item_id: string
  sku_code: string
  name_zh: string
  qty_in: number
  qty_out: number
  qty_adjust: number
  qty_transfer_in: number
  qty_transfer_out: number
  net_change: number
  reasons: Record<string, number>
}

export interface MovementSummaryReport {
  rows: MovementSummaryRow[]
  totals: Record<string, number>
}

export interface PurchaseReportRow {
  supplier_id: string
  supplier_name: string | null
  item_id: string
  sku_code: string
  name_zh: string
  qty_received: number
  value_received: number
  qty_returned: number
  value_returned: number
  net_qty: number
  net_value: number
}

export interface OpenOrderRow {
  po_id: string
  po_no: string
  supplier_id: string
  supplier_name: string | null
  location_id: string
  order_date: string | null
  expected_date: string | null
  status: string
  outstanding_qty: number
  outstanding_value: number
  overdue: boolean
}

export interface PurchasesReport {
  rows: PurchaseReportRow[]
  totals: Record<string, number>
  open_orders: OpenOrderRow[]
}

export interface SalesReportRow {
  date: string
  customer_id: string
  customer_name: string | null
  item_id: string
  sku_code: string
  name_zh: string
  invoice_count: number
  qty: number
  amount: number
}

export interface SalesReport {
  rows: SalesReportRow[]
  totals: Record<string, number>
}

export interface ReceivableRow {
  invoice_id: string
  invoice_no: string
  customer_id: string
  customer_name: string | null
  location_id: string
  issue_date: string | null
  total: number
  paid: number
  credited: number
  balance: number
  days_outstanding: number
  bucket: string
}

export interface ReceivablesReport {
  rows: ReceivableRow[]
  customer_totals: { customer_id: string; customer_name: string | null; balance: number; count: number }[]
  buckets: Record<string, number>
  grand_total: number
}

export interface WriteOffRow {
  reason_code: string
  item_id: string
  sku_code: string
  name_zh: string
  qty: number
  cost: number
  cost_missing: number
}

export interface WriteOffsReport {
  rows: WriteOffRow[]
  totals: Record<string, number>
}

export interface InventoryDashboard {
  tracked_items: number
  low_stock_count: number
  stock_value: number
  open_purchase_orders: number
  overdue_purchase_orders: number
  open_sales_orders: number
  unshipped_qty: number
  unpaid_invoice_count: number
  receivable_balance: number
  overdue_receivable_balance: number
  month_sales: number
  month_purchases: number
}

export interface LowStockAlert {
  item_id: string
  location_id: string
  sku_code: string
  name_zh: string
  quantity: number
  reorder_level: number
}

export interface OverduePoAlert {
  id: string
  po_no: string
  expected_date: string | null
  status: string
}

export interface OverdueInvoiceAlert {
  id: string
  invoice_no: string
  buyer_name: string
  issue_date: string | null
  balance: number
}

export interface ExpiringProformaAlert {
  id: string
  so_no: string
  pf_no: string
  pf_valid_until: string | null
}

export interface InventoryAlerts {
  low_stock: LowStockAlert[]
  overdue_purchase_orders: OverduePoAlert[]
  overdue_invoices: OverdueInvoiceAlert[]
  expiring_proformas: ExpiringProformaAlert[]
}

export interface NotifyResult {
  created: number
  skipped: number
}

interface ReportParams {
  location_id?: string
  customer_id?: string
  supplier_id?: string
  item_id?: string
  date_from?: string
  date_to?: string
  as_of?: string
}

async function getReport<T>(path: string, params?: ReportParams): Promise<T> {
  return await $attendanceApi<T>(`/inventory/reports/${path}`, { params })
}

export async function getStockValuation(params?: ReportParams): Promise<StockValuationReport> {
  return await getReport('stock-valuation', params)
}

export async function getMovementsSummary(params?: ReportParams): Promise<MovementSummaryReport> {
  return await getReport('movements-summary', params)
}

export async function getPurchasesReport(params?: ReportParams): Promise<PurchasesReport> {
  return await getReport('purchases', params)
}

export async function getSalesReport(params?: ReportParams): Promise<SalesReport> {
  return await getReport('sales', params)
}

export async function getReceivablesReport(params?: ReportParams): Promise<ReceivablesReport> {
  return await getReport('receivables', params)
}

export async function getWriteOffsReport(params?: ReportParams): Promise<WriteOffsReport> {
  return await getReport('write-offs', params)
}

export async function exportReportCSV(path: string, params?: ReportParams): Promise<Blob> {
  return await $attendanceApi<Blob>(`/inventory/reports/${path}`, {
    params: { ...params, format: 'csv' },
    responseType: 'blob',
  })
}

export async function getInventoryDashboard(params?: { location_id?: string }): Promise<InventoryDashboard> {
  return await $attendanceApi<InventoryDashboard>('/inventory/dashboard', { params })
}

export async function getInventoryAlerts(params?: { location_id?: string }): Promise<InventoryAlerts> {
  return await $attendanceApi<InventoryAlerts>('/inventory/alerts', { params })
}

export async function sendInventoryAlerts(params?: { location_id?: string }): Promise<NotifyResult> {
  return await $attendanceApi<NotifyResult>('/inventory/alerts/notify', {
    method: 'POST',
    params,
  })
}
