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
