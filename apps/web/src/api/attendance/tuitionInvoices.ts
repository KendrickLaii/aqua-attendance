import { $attendanceApi } from '@/utils/attendanceApi'
import { fetchAttendanceListWithTotal, type AttendanceListResult } from '@/utils/attendanceListApi'

export type TuitionInvoiceStatus = 'draft' | 'issued' | 'paid' | 'void'

export interface TuitionInvoiceLine {
  id: string
  invoice_id: string
  enrollment_id: string | null
  sku_id: string | null
  sku_code: string
  name_zh: string
  billing_unit: string
  unit_price: number
  quantity: number
  amount: number
  created_at: string
}

export interface TuitionInvoice {
  id: string
  unit_id: string
  unit_name: string | null
  unit_code: string | null
  period_start: string
  period_end: string
  status: TuitionInvoiceStatus
  total: number
  notes: string | null
  lines: TuitionInvoiceLine[]
  created_at: string
  updated_at: string
}

export interface TuitionInvoiceGenerateResult {
  created: number
  updated: number
  skipped: number
}

export async function listTuitionInvoicesWithTotal(params?: {
  year?: number
  month?: number
  status?: string
  page?: number
  page_size?: number
}): Promise<AttendanceListResult<TuitionInvoice>> {
  return await fetchAttendanceListWithTotal<TuitionInvoice>('/tuition-invoices', params)
}

export async function generateTuitionInvoices(
  year: number,
  month: number,
): Promise<TuitionInvoiceGenerateResult> {
  const params = new URLSearchParams()
  params.set('year', String(year))
  params.set('month', String(month))

  return await $attendanceApi(`/tuition-invoices/generate?${params.toString()}`, { method: 'POST' })
}

export async function updateTuitionInvoice(
  invoiceId: string,
  payload: { status?: TuitionInvoiceStatus; notes?: string | null },
): Promise<TuitionInvoice> {
  return await $attendanceApi(`/tuition-invoices/${invoiceId}`, { method: 'PATCH', body: payload })
}
