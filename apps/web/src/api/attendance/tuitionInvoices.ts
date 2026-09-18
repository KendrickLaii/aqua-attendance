import { $attendanceApi } from '@/utils/attendanceApi'
import { type AttendanceListResult, fetchAttendanceListWithTotal } from '@/utils/attendanceListApi'

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
  month_label: string | null
  staff_name: string | null
  created_at: string
}

export type TuitionInvoiceKind = 'tuition' | 'manual'

export interface TuitionInvoice {
  id: string
  unit_id: string | null
  unit_name: string | null
  unit_code: string | null
  manual_student_name: string | null
  staff_name: string | null
  location_id: string
  period_start: string
  period_end: string
  status: TuitionInvoiceStatus
  kind: TuitionInvoiceKind
  total: number
  notes: string | null
  invoice_no: string | null
  receipt_no?: string | null
  issued_at: string | null
  lines: TuitionInvoiceLine[]
  created_at: string
  updated_at: string
}

export interface TuitionInvoiceGenerateResult {
  created: number
  updated: number
  skipped: number
  deleted?: number
}

export async function listTuitionInvoicesWithTotal(params?: {
  year?: number
  month?: number
  status?: string
  location_id?: string
  page?: number
  page_size?: number
}): Promise<AttendanceListResult<TuitionInvoice>> {
  return await fetchAttendanceListWithTotal<TuitionInvoice>('/tuition-invoices', params)
}

export async function listAllTuitionInvoices(params: {
  year?: number
  month?: number
  status?: string
  location_id?: string
} = {}): Promise<AttendanceListResult<TuitionInvoice>> {
  const pageSize = 200

  const first = await listTuitionInvoicesWithTotal({
    ...params,
    page: 1,
    page_size: pageSize,
  })

  const items = [...first.items]
  const total = first.total
  let page = 2
  while (items.length < total) {
    const next = await listTuitionInvoicesWithTotal({
      ...params,
      page,
      page_size: pageSize,
    })

    if (next.items.length === 0)
      break
    items.push(...next.items)
    page += 1
  }

  return { items, total }
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

export async function getNextInvoiceNo(locationId: string): Promise<number> {
  const result = await $attendanceApi<{ next_no: number }>(`/tuition-invoices/next-no?location_id=${locationId}`)

  return result.next_no
}

export async function allocateInvoiceNo(locationId: string): Promise<number> {
  const result = await $attendanceApi<{ next_no: number }>(
    `/tuition-invoices/allocate-no?location_id=${locationId}`,
    { method: 'POST' },
  )

  return result.next_no
}

export interface ManualInvoiceLine {
  month: string
  course: string
  fee: number
  qty: number
  staff_name?: string | null

  /** Set to settle an unbilled per-session purchase; qty comes from the purchase. */
  purchase_id?: string
}

export interface ManualInvoicePayload {
  date: string
  location_id: string
  unit_id?: string | null
  manual_student_name?: string | null

  /** Invoice-level 開單人 — who issued it, for commission records. */
  staff_name?: string | null
  invoice_no?: string | null
  notes?: string | null
  lines: ManualInvoiceLine[]
}

export async function createManualTuitionInvoice(payload: ManualInvoicePayload): Promise<TuitionInvoice> {
  return await $attendanceApi('/tuition-invoices/manual', { method: 'POST', body: payload })
}

export async function updateTuitionInvoice(
  invoiceId: string,
  payload: { status?: TuitionInvoiceStatus; notes?: string | null; invoice_no?: string | null; staff_name?: string | null },
): Promise<TuitionInvoice> {
  return await $attendanceApi(`/tuition-invoices/${invoiceId}`, { method: 'PATCH', body: payload })
}
