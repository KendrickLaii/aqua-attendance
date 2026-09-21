import type { PayrollRecord } from '@/api/attendance/payroll'

export const payrollStatusOptions = [
  { title: 'All statuses', value: '' },
  { title: 'Calculated', value: 'calculated' },
  { title: 'Approved', value: 'approved' },
  { title: 'Paid', value: 'paid' },
  { title: 'Cancelled', value: 'cancelled' },
]

export const payrollReviewFilterChips = [
  { title: 'All', value: '' },
  { title: 'Calculated', value: 'calculated' },
  { title: 'Approved', value: 'approved' },
  { title: 'Paid', value: 'paid' },
]

export const payrollStatusColorMap: Record<string, string> = {
  draft: 'grey',
  calculated: 'info',
  approved: 'success',
  paid: 'primary',
  cancelled: 'error',
}

const payrollStatusIconMap: Record<string, string> = {
  draft: 'ri-draft-line',
  calculated: 'ri-calculator-line',
  approved: 'ri-checkbox-circle-line',
  paid: 'ri-money-dollar-circle-line',
  cancelled: 'ri-close-circle-line',
}

export function payrollStatusIcon(status: string) {
  return payrollStatusIconMap[status] ?? 'ri-file-list-line'
}

export function canEditPayrollAdjustments(record: PayrollRecord) {
  return record.status === 'draft' || record.status === 'calculated'
}

export function canApprovePayroll(record: PayrollRecord) {
  return record.status === 'draft' || record.status === 'calculated'
}

export function canPayPayroll(record: PayrollRecord) {
  return record.status === 'approved'
}

export function formatPayrollHours(h: number) {
  return Number.isFinite(h) ? h.toFixed(2) : '-'
}

export function safePayrollNumber(value: number) {
  return Number.isFinite(value) ? value : 0
}

export function formatPayrollCurrency(n: number | null | undefined) {
  const value = Number.isFinite(n) ? Number(n) : 0

  return value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export function formatPayrollDashAmount(n: number | null | undefined) {
  const value = Number.isFinite(n) ? Number(n) : 0
  if (value === 0)
    return '-'

  return formatPayrollCurrency(value)
}

export function formatPayrollChequeNumber(value: string | null | undefined) {
  const text = (value ?? '').trim()

  return text || '—'
}

export function parsePayrollCurrencyInput(display: string | number | null | undefined) {
  const s = String(display ?? '').replace(/,/g, '').trim()
  if (s === '' || s === '-' || s === '.' || s === '-.')
    return 0
  const n = Number(s)

  return Number.isFinite(n) ? n : 0
}

export function payrollPaySplitError(input: {
  cheque: number
  cash: number
  net: number
  chequeNumber: string
}): string | null {
  const cheque = Number(input.cheque) || 0
  const cash = Number(input.cash) || 0
  const net = Number(input.net) || 0
  if (cheque < 0 || cash < 0)
    return 'Cheque and cash amounts cannot be negative.'
  if (cheque > 0 && !input.chequeNumber.trim())
    return 'Enter a cheque number when cheque amount is greater than 0.'
  if (Math.abs(cheque + cash - net) > 0.009)
    return 'Cheque + cash must equal net pay.'

  return null
}

type PayrollSummaryStatus = {
  is_holiday: boolean
  is_weekend: boolean
  is_complete: boolean
}

export function payrollSummaryStatusLabel(s: PayrollSummaryStatus): string {
  if (s.is_holiday)
    return 'Holiday'
  if (s.is_weekend)
    return 'Weekend'

  return s.is_complete ? 'Complete' : 'Incomplete'
}

export function payrollSummaryStatusColor(s: PayrollSummaryStatus): string {
  if (s.is_holiday || s.is_weekend)
    return 'info'

  return s.is_complete ? 'success' : 'warning'
}

export function payrollSummaryStatusIcon(s: PayrollSummaryStatus, autoCheckout: boolean): string {
  if (s.is_holiday)
    return 'ri-calendar-event-line'
  if (s.is_weekend)
    return 'ri-calendar-2-line'
  if (autoCheckout)
    return 'ri-alarm-warning-line'
  if (!s.is_complete)
    return 'ri-error-warning-line'

  return 'ri-checkbox-circle-line'
}

export function payrollDetailTotals(
  summaries: Array<{
    regular_hours: number
    regular_slots: number
    overtime_hours: number
    ot_slots: number
  }>,
  autoCheckoutDays: number,
) {
  const regular = summaries.reduce((sum, s) => sum + safePayrollNumber(s.regular_hours), 0)
  const regularSlots = summaries.reduce((sum, s) => sum + safePayrollNumber(s.regular_slots), 0)
  const overtime = summaries.reduce((sum, s) => sum + safePayrollNumber(s.overtime_hours), 0)
  const otSlots = summaries.reduce((sum, s) => sum + safePayrollNumber(s.ot_slots), 0)

  return {
    regular,
    regularSlots,
    overtime,
    otSlots,
    days: summaries.length,
    autoCheckoutDays,
  }
}
