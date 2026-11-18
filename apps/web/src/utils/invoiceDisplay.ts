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

export const INVOICE_CURRENCIES = [
  { code: 'HKD', symbol: 'HK$' },
  { code: 'USD', symbol: 'US$' },
  { code: 'CNY', symbol: 'RMB' },
  { code: 'EUR', symbol: '€' },
  { code: 'GBP', symbol: '£' },
  { code: 'SGD', symbol: 'S$' },
  { code: 'JPY', symbol: 'JP¥' },
] as const

export const DEFAULT_INVOICE_CURRENCY = 'HKD'

export function invoiceCurrencySymbol(currency: string | null | undefined): string {
  const code = currency || DEFAULT_INVOICE_CURRENCY

  return INVOICE_CURRENCIES.find(item => item.code === code)?.symbol ?? code
}

export function formatInvoiceMoney(value: number, currency: string | null | undefined = DEFAULT_INVOICE_CURRENCY): string {
  const amount = Number(value)
  const abs = Math.abs(amount).toLocaleString('en-HK', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

  const symbol = invoiceCurrencySymbol(currency)

  return amount < 0 ? `-${symbol}${abs}` : `${symbol}${abs}`
}

/** Currency codes in display order: HKD first, then the list order, then unknown codes. */
export function sortedCurrencyCodes(codes: Iterable<string>): string[] {
  const order: string[] = INVOICE_CURRENCIES.map(item => item.code)

  const rank = (code: string) => {
    const index = order.indexOf(code)

    return index === -1 ? order.length : index
  }

  return [...new Set(codes)].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b))
}

/** "HK$9,000.00 · US$500.00"; "HK$0.00" when there is nothing to show. */
export function formatMoneyByCurrency(totals: Record<string, number>): string {
  const codes = sortedCurrencyCodes(Object.keys(totals))
  if (codes.length === 0)
    return formatInvoiceMoney(0)

  return codes.map(code => formatInvoiceMoney(totals[code], code)).join(' · ')
}

/** Adds each item's amount into its currency bucket. */
export function sumByCurrency<T>(
  items: Iterable<T>,
  pick: (item: T) => { amount: number; currency: string | null | undefined },
): Record<string, number> {
  const totals: Record<string, number> = {}
  for (const item of items) {
    const { amount, currency } = pick(item)
    const code = currency || DEFAULT_INVOICE_CURRENCY

    totals[code] = (totals[code] ?? 0) + Number(amount)
  }

  return totals
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

export function invoiceLineFormula(line: TuitionInvoiceLine, currency?: string): string {
  return `${formatInvoiceQty(line)} × ${formatInvoiceMoney(Number(line.unit_price), currency)}`
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

const MONTH_PREFIXES = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

/** "Oct-26" / "Sept-26" / "2026-10" -> "2026-10"; '' when unreadable. Mirrors the API rule. */
export function monthLabelToPeriod(label: string | null | undefined): string {
  const text = (label ?? '').trim()
  const iso = /^(\d{4})-(\d{1,2})$/.exec(text)
  if (iso) {
    const month = Number(iso[2])

    return month >= 1 && month <= 12 ? `${iso[1]}-${String(month).padStart(2, '0')}` : ''
  }
  const named = /^([A-Z]+)[-\s']*(\d{2}|\d{4})$/i.exec(text)
  if (!named)
    return ''
  const month = MONTH_PREFIXES.indexOf(named[1].slice(0, 3).toLowerCase()) + 1
  if (!month)
    return ''
  const year = Number(named[2])

  return `${year < 100 ? year + 2000 : year}-${String(month).padStart(2, '0')}`
}

/** Latest month among line labels as "YYYY-MM"; '' when none can be read. */
export function periodFromMonthLabels(labels: Array<string | null | undefined>): string {
  return labels.map(monthLabelToPeriod).filter(Boolean).sort().at(-1) ?? ''
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
