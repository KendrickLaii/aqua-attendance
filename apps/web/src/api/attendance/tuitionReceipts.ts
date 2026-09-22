import { $attendanceApi } from '@/utils/attendanceApi'
import { type AttendanceListResult, fetchAttendanceListWithTotal } from '@/utils/attendanceListApi'
import type { TuitionInvoice } from '@/api/attendance/tuitionInvoices'

export type TuitionReceiptStatus = 'posted' | 'void'

export interface TuitionReceiptPrintLine {
  month: string
  course: string
  fee: number
  qty: number
  amount: number
  invoice_id: string | null
  invoice_no: string | null
}

export interface TuitionReceiptAdjustment {
  month: string
  course: string
  fee: number | null
  qty: number | null
  amount: number
}

export interface TuitionReceiptLinkedInvoice {
  invoice_id: string
  invoice_no: string | null
  amount: number
  invoice_total: number
  status: string
}

export interface TuitionReceipt {
  id: string
  location_id: string
  unit_id: string | null
  unit_name: string | null
  unit_code: string | null
  payer_name: string | null
  paid_by: string
  receipt_no: string
  receipt_date: string
  amount: number
  status: TuitionReceiptStatus
  description: string | null
  primary_url: string | null
  invoices: TuitionReceiptLinkedInvoice[]
  print_lines: TuitionReceiptPrintLine[]
  adjustments: TuitionReceiptAdjustment[]
  created_at: string
  updated_at: string
}

export interface TuitionReceiptCreatePayload {
  location_id: string
  unit_id?: string | null
  payer_name?: string | null
  paid_by: string
  receipt_date: string
  invoice_ids: string[]
  amount?: number
  adjustments?: TuitionReceiptAdjustment[]
  description?: string | null
}

export async function listTuitionReceiptsWithTotal(params?: {
  year?: number
  month?: number
  location_id?: string
  unit_id?: string
  page?: number
  page_size?: number
}): Promise<AttendanceListResult<TuitionReceipt>> {
  return await fetchAttendanceListWithTotal<TuitionReceipt>('/tuition-receipts', params)
}

export async function listAllTuitionReceipts(params: {
  year?: number
  month?: number
  location_id?: string
  unit_id?: string
} = {}): Promise<AttendanceListResult<TuitionReceipt>> {
  const pageSize = 200
  const first = await listTuitionReceiptsWithTotal({ ...params, page: 1, page_size: pageSize })
  const items = [...first.items]
  const total = first.total
  let page = 2
  while (items.length < total) {
    const next = await listTuitionReceiptsWithTotal({ ...params, page, page_size: pageSize })
    if (next.items.length === 0)
      break
    items.push(...next.items)
    page += 1
  }
  return { items, total }
}

export async function getTuitionReceipt(receiptId: string): Promise<TuitionReceipt> {
  return await $attendanceApi(`/tuition-receipts/${receiptId}`)
}

export async function createTuitionReceipt(payload: TuitionReceiptCreatePayload): Promise<TuitionReceipt> {
  return await $attendanceApi('/tuition-receipts', { method: 'POST', body: payload })
}

export async function voidTuitionReceipt(receiptId: string): Promise<TuitionReceipt> {
  return await $attendanceApi(`/tuition-receipts/${receiptId}/void`, { method: 'POST' })
}

export async function deleteTuitionReceipt(receiptId: string): Promise<void> {
  await $attendanceApi(`/tuition-receipts/${receiptId}`, { method: 'DELETE' })
}

export async function getNextReceiptNo(locationId: string, date: string): Promise<string> {
  const result = await $attendanceApi<{ next_no: string }>('/tuition-receipts/next-no', {
    params: { location_id: locationId, date },
  })
  return result.next_no
}

export async function listOpenInvoices(params: {
  location_id: string
  unit_id?: string
  invoice_id?: string
}): Promise<TuitionInvoice[]> {
  return await $attendanceApi('/tuition-receipts/open-invoices', { params })
}
