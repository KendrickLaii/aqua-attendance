import { $attendanceApi } from '@/utils/attendanceApi'
import { fetchAttendanceListWithTotal } from '@/utils/attendanceListApi'
import type { DeliveryOrder, SalesOrder } from '@/api/attendance/inventorySales'

// ---- Invoices ----

export type InventoryInvoiceStatus = 'draft' | 'issued' | 'void'
export type InventoryPaymentStatus = 'unpaid' | 'partial' | 'paid' | 'void'

export interface InventoryInvoiceLine {
  id: string
  do_line_id: string
  so_line_id: string
  item_id: string
  sku_code: string
  name_zh: string
  unit_price: number
  qty: number
  discount_amount: number
  amount: number
  credited_qty: number
}

export interface InvoiceReceiptSummary {
  id: string
  receipt_no: string
  amount: number
  paid_by: string
  receipt_date: string
  status: string
}

export interface InvoiceCreditNoteSummary {
  id: string
  scn_no: string
  total: number
  credit_date: string
  status: string
}

export interface InventoryInvoice {
  id: string
  invoice_no: string | null
  do_id: string
  do_no: string
  so_id: string
  so_no: string
  customer_id: string
  customer_name: string | null
  buyer_name: string
  location_id: string
  issue_date: string | null
  status: InventoryInvoiceStatus
  discount_amount: number
  subtotal: number
  total: number
  paid_total: number
  credited_total: number
  balance: number
  payment_status: InventoryPaymentStatus
  notes: string | null
  issued_at: string | null
  created_by: string | null
  created_at: string
  updated_at: string
  lines: InventoryInvoiceLine[]
  receipts: InvoiceReceiptSummary[]
  credit_notes: InvoiceCreditNoteSummary[]
}

export interface InventoryInvoiceLinePayload {
  do_line_id: string
  qty: number
  unit_price?: number | null
  discount_amount?: number
}

export interface InventoryInvoicePayload {
  do_id: string
  issue_date?: string | null
  discount_amount?: number | null
  notes?: string | null
  lines?: InventoryInvoiceLinePayload[]
}

export interface InventoryInvoicePrintDoc {
  invoice_no: string
  issue_date: string | null
  issued_at: string | null
  buyer_name: string
  customer_code: string
  customer_name_zh: string | null
  customer_name_en: string | null
  customer_contact: string | null
  customer_phone: string | null
  customer_email: string | null
  customer_address: string | null
  location_name_zh: string | null
  location_name_en: string | null
  location_address: string | null
  location_phone: string | null
  so_no: string
  do_no: string
  lines: InventoryInvoiceLine[]
  discount_amount: number
  subtotal: number
  total: number
  paid_total: number
  credited_total: number
  balance: number
  payment_status: string
  notes: string | null
}

export async function listInvoices(params?: {
  customer_id?: string
  location_id?: string
  status?: InventoryInvoiceStatus
  payment_status?: InventoryPaymentStatus
  date_from?: string
  date_to?: string
  search?: string
  page?: number
  page_size?: number
}) {
  return await fetchAttendanceListWithTotal<InventoryInvoice>('/inventory/invoices', params)
}

export async function getInvoice(id: string): Promise<InventoryInvoice> {
  return await $attendanceApi(`/inventory/invoices/${id}`)
}

export async function createInvoice(payload: InventoryInvoicePayload): Promise<InventoryInvoice> {
  return await $attendanceApi('/inventory/invoices', { method: 'POST', body: payload })
}

export async function updateInvoice(
  id: string,
  payload: { issue_date?: string; discount_amount?: number; notes?: string | null; lines?: InventoryInvoiceLinePayload[] },
): Promise<InventoryInvoice> {
  return await $attendanceApi(`/inventory/invoices/${id}`, { method: 'PATCH', body: payload })
}

export async function deleteInvoice(id: string): Promise<void> {
  return await $attendanceApi(`/inventory/invoices/${id}`, { method: 'DELETE' })
}

export async function issueInvoice(id: string): Promise<InventoryInvoice> {
  return await $attendanceApi(`/inventory/invoices/${id}/issue`, { method: 'POST' })
}

export async function voidInvoice(id: string): Promise<InventoryInvoice> {
  return await $attendanceApi(`/inventory/invoices/${id}/void`, { method: 'POST' })
}

export async function getInvoicePrint(id: string): Promise<InventoryInvoicePrintDoc> {
  return await $attendanceApi(`/inventory/invoices/${id}/print`)
}

// ---- Receipts ----

export type InventoryReceiptPaidBy = 'cash' | 'cheque' | 'bank_transfer' | 'card' | 'other'
export type InventoryReceiptStatus = 'posted' | 'void'

export const RECEIPT_PAID_BY_OPTIONS: { value: InventoryReceiptPaidBy; label: string }[] = [
  { value: 'cash', label: 'Cash' },
  { value: 'cheque', label: 'Cheque' },
  { value: 'bank_transfer', label: 'Bank Transfer' },
  { value: 'card', label: 'Card' },
  { value: 'other', label: 'Other' },
]

export interface InventoryReceipt {
  id: string
  receipt_no: string
  invoice_id: string
  invoice_no: string | null
  customer_id: string
  customer_name: string | null
  location_id: string
  amount: number
  paid_by: InventoryReceiptPaidBy
  reference_no: string | null
  receipt_date: string
  status: InventoryReceiptStatus
  notes: string | null
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface InventoryReceiptPayload {
  invoice_id: string
  amount: number
  paid_by: InventoryReceiptPaidBy
  reference_no?: string | null
  receipt_date?: string | null
  notes?: string | null
}

export interface InventoryReceiptPrintDoc {
  receipt_no: string
  receipt_date: string
  status: string
  invoice_no: string | null
  invoice_total: number
  invoice_paid_total: number
  invoice_balance: number
  buyer_name: string
  customer_code: string
  customer_name_zh: string | null
  customer_name_en: string | null
  location_name_zh: string | null
  location_name_en: string | null
  location_address: string | null
  location_phone: string | null
  amount: number
  paid_by: string
  reference_no: string | null
  notes: string | null
}

export async function listReceipts(params?: {
  invoice_id?: string
  customer_id?: string
  location_id?: string
  status?: InventoryReceiptStatus
  date_from?: string
  date_to?: string
  search?: string
  page?: number
  page_size?: number
}) {
  return await fetchAttendanceListWithTotal<InventoryReceipt>('/inventory/receipts', params)
}

export async function getReceipt(id: string): Promise<InventoryReceipt> {
  return await $attendanceApi(`/inventory/receipts/${id}`)
}

export async function createReceipt(payload: InventoryReceiptPayload): Promise<InventoryReceipt> {
  return await $attendanceApi('/inventory/receipts', { method: 'POST', body: payload })
}

export async function voidReceipt(id: string): Promise<InventoryReceipt> {
  return await $attendanceApi(`/inventory/receipts/${id}/void`, { method: 'POST' })
}

export async function getReceiptPrint(id: string): Promise<InventoryReceiptPrintDoc> {
  return await $attendanceApi(`/inventory/receipts/${id}/print`)
}

// ---- Credit notes ----

export type InventoryCreditNoteStatus = 'draft' | 'confirmed' | 'void'

export interface InventoryCreditNoteLine {
  id: string
  invoice_line_id: string
  item_id: string
  sku_code: string | null
  name_zh: string | null
  qty: number
  unit_amount: number
  amount: number
  restock: boolean
}

export interface InventoryCreditNote {
  id: string
  scn_no: string
  invoice_id: string
  invoice_no: string | null
  customer_id: string
  customer_name: string | null
  location_id: string
  credit_date: string
  reason: string
  status: InventoryCreditNoteStatus
  total: number
  created_by: string | null
  created_at: string
  updated_at: string
  lines: InventoryCreditNoteLine[]
}

export interface InventoryCreditNoteLinePayload {
  invoice_line_id: string
  qty: number
  restock?: boolean
}

export interface InventoryCreditNotePayload {
  invoice_id: string
  credit_date?: string | null
  reason: string
  lines: InventoryCreditNoteLinePayload[]
}

export interface InventoryCreditNotePrintDoc {
  scn_no: string
  credit_date: string
  status: string
  invoice_no: string | null
  buyer_name: string
  customer_code: string
  customer_name_zh: string | null
  customer_name_en: string | null
  location_name_zh: string | null
  location_name_en: string | null
  location_address: string | null
  location_phone: string | null
  reason: string
  lines: InventoryCreditNoteLine[]
  total: number
}

export async function listCreditNotes(params?: {
  invoice_id?: string
  customer_id?: string
  location_id?: string
  status?: InventoryCreditNoteStatus
  date_from?: string
  date_to?: string
  search?: string
  page?: number
  page_size?: number
}) {
  return await fetchAttendanceListWithTotal<InventoryCreditNote>('/inventory/credit-notes', params)
}

export async function getCreditNote(id: string): Promise<InventoryCreditNote> {
  return await $attendanceApi(`/inventory/credit-notes/${id}`)
}

export async function createCreditNote(payload: InventoryCreditNotePayload): Promise<InventoryCreditNote> {
  return await $attendanceApi('/inventory/credit-notes', { method: 'POST', body: payload })
}

export async function updateCreditNote(
  id: string,
  payload: { credit_date?: string; reason?: string; lines?: InventoryCreditNoteLinePayload[] },
): Promise<InventoryCreditNote> {
  return await $attendanceApi(`/inventory/credit-notes/${id}`, { method: 'PATCH', body: payload })
}

export async function deleteCreditNote(id: string): Promise<void> {
  return await $attendanceApi(`/inventory/credit-notes/${id}`, { method: 'DELETE' })
}

export async function confirmCreditNote(id: string): Promise<InventoryCreditNote> {
  return await $attendanceApi(`/inventory/credit-notes/${id}/confirm`, { method: 'POST' })
}

export async function voidCreditNote(id: string): Promise<InventoryCreditNote> {
  return await $attendanceApi(`/inventory/credit-notes/${id}/void`, { method: 'POST' })
}

export async function getCreditNotePrint(id: string): Promise<InventoryCreditNotePrintDoc> {
  return await $attendanceApi(`/inventory/credit-notes/${id}/print`)
}

// ---- Quick fulfill ----

export interface QuickFulfillResult {
  so: SalesOrder
  delivery_order: DeliveryOrder
  invoice: InventoryInvoice
  receipt: InventoryReceipt | null
}

export async function quickFulfill(
  soId: string,
  payload: { pay?: { amount: number; paid_by: InventoryReceiptPaidBy; reference_no?: string | null }; issue_date?: string },
): Promise<QuickFulfillResult> {
  return await $attendanceApi(`/inventory/sales-orders/${soId}/quick-fulfill`, {
    method: 'POST',
    body: payload,
  })
}
