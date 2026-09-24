import type { LocationItem } from '@/api/attendance/locations'
import type { TuitionInvoice, TuitionInvoiceLine, TuitionInvoiceStatus } from '@/api/attendance/tuitionInvoices'
import type { TuitionInvoicePrintHeader } from '@/utils/printTuitionInvoice'

export const invoiceStatusColor: Record<string, string> = {
  draft: 'warning',
  issued: 'info',
  paid: 'success',
  void: 'grey',
}

export const invoiceStatusLabel: Record<string, string> = {
  draft: 'Draft',
  issued: 'Issued',
  paid: 'Paid',
  void: 'Cancelled',
}

export const invoiceStatusFilters: { title: string; value: 'all' | TuitionInvoiceStatus }[] = [
  { title: 'All', value: 'all' },
  { title: 'Draft', value: 'draft' },
  { title: 'Issued', value: 'issued' },
  { title: 'Paid', value: 'paid' },
  { title: 'Cancelled', value: 'void' },
]

export function formatInvoiceMoney(value: number): string {
  const amount = Number(value)
  const abs = Math.abs(amount).toLocaleString('en-HK', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

  return amount < 0 ? `-HK$${abs}` : `HK$${abs}`
}

export function isCreditInvoice(invoice: { total: number }): boolean {
  return Number(invoice.total) < 0
}

export function isChargeInvoice(invoice: { total: number }): boolean {
  return !isCreditInvoice(invoice)
}

/** Class price shown on a credit-note line — always a negative amount. */
export function defaultCreditFee(price: number | null | undefined): string {
  if (price == null || Number.isNaN(Number(price)))
    return ''

  return String(-Math.abs(Number(price)))
}

export function invoiceLinesEditable(status: string): boolean {
  return status === 'draft' || status === 'issued'
}

export function billingLabel(unit: string): string {
  if (unit === 'per_session')
    return 'Per class'
  if (unit === 'manual')
    return 'Manual'

  return 'Monthly'
}

export function formatInvoiceQty(line: TuitionInvoiceLine): string {
  const qty = Number(line.quantity)
  const whole = Number.isInteger(qty) ? String(qty) : qty.toFixed(2)
  if (line.billing_unit === 'per_session')
    return `${whole} ${qty === 1 ? 'session' : 'sessions'}`

  if (line.billing_unit === 'manual')
    return whole

  return qty === 1 ? '1 month' : `${whole} months`
}

export function invoiceLineFormula(line: TuitionInvoiceLine): string {
  return `${formatInvoiceQty(line)} × ${formatInvoiceMoney(Number(line.unit_price))}`
}

export function invoiceClassNames(invoice: TuitionInvoice): string[] {
  return invoice.lines.map(line => line.name_zh || line.sku_code)
}

export function classPreview(invoice: TuitionInvoice): string {
  const names = invoiceClassNames(invoice)
  if (names.length === 0)
    return 'No lines'
  if (names.length === 1)
    return names[0]

  return `${names[0]} +${names.length - 1}`
}

export function invoicePeriodLabel(invoice: TuitionInvoice): string {
  if (invoice.period_start === invoice.period_end)
    return invoice.period_start

  return `${invoice.period_start} – ${invoice.period_end}`
}

export function invoiceStudentLabel(invoice: TuitionInvoice): string {
  return invoice.unit_name ?? invoice.manual_student_name ?? '—'
}

export function invoiceOpenedBy(invoice: TuitionInvoice): string {
  return (invoice.staff_name ?? '').trim()
}

export function creditLinesFromInvoice(invoice: TuitionInvoice): Array<{
  month: string
  course: string
  fee: number
  qty: number
}> {
  return invoice.lines.map(line => ({
    month: line.month_label ?? '',
    course: line.name_zh,
    fee: -Math.abs(Number(line.unit_price)),
    qty: Number(line.quantity),
  }))
}

export function invoicePrintHeaderFromLocation(location: LocationItem): TuitionInvoicePrintHeader {
  const details = (location.details ?? {}) as Record<string, unknown>

  return {
    nameEn: location.name_en,
    nameZh: location.name_zh ?? '',
    regNo: typeof details.school_reg_no === 'string' ? details.school_reg_no : '',
    address: location.address ?? '',
    phone: location.phone ?? '',
  }
}

export function locationTitle(location: Pick<LocationItem, 'name_zh' | 'name_en'>): string {
  return location.name_zh || location.name_en
}

export function filterTuitionInvoices(
  invoices: TuitionInvoice[],
  opts: { status: 'all' | TuitionInvoiceStatus; query: string },
): TuitionInvoice[] {
  const query = opts.query.trim().toLowerCase()

  return invoices.filter(invoice => {
    if (opts.status !== 'all' && invoice.status !== opts.status)
      return false
    if (!query)
      return true

    const haystack = [
      invoice.unit_name,
      invoice.unit_code,
      invoice.manual_student_name,
      invoice.invoice_no,
      invoice.receipt_no,
      invoice.staff_name,
      invoice.notes,
      ...invoice.lines.flatMap(line => [line.sku_code, line.name_zh, line.staff_name]),
    ].join(' ').toLowerCase()

    return haystack.includes(query)
  })
}

export function filterChargeInvoices(
  invoices: TuitionInvoice[],
  opts: { status: 'all' | TuitionInvoiceStatus; query: string },
): TuitionInvoice[] {
  return filterTuitionInvoices(invoices.filter(isChargeInvoice), opts)
}

export function filterCreditNoteInvoices(
  invoices: TuitionInvoice[],
  opts: { status: 'all' | TuitionInvoiceStatus; query: string },
): TuitionInvoice[] {
  return filterTuitionInvoices(invoices.filter(isCreditInvoice), opts)
}
