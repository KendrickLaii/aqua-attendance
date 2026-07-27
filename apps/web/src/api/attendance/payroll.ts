import { $attendanceApi } from '@/utils/attendanceApi'
import { type AttendanceListResult, fetchAttendanceListWithTotal } from '@/utils/attendanceListApi'

export interface PayrollRecord {
  id: string
  unit_id: string
  unit_name: string | null
  unit_code: string | null
  payroll_period_start: string
  payroll_period_end: string
  total_regular_hours: number
  total_overtime_hours: number
  total_holiday_hours: number
  total_work_days: number
  total_leave_days: number
  regular_slots: number
  ot_slots: number
  hourly_rate_snapshot: number | null
  ot_multiplier_snapshot: number | null
  base_salary: number
  overtime_pay: number
  holiday_pay: number
  allowance: number
  deduction: number
  bonus: number
  adjustment_1: number
  adjustment_2: number
  adjustment_1_remark: string | null
  adjustment_2_remark: string | null
  gross_pay: number
  net_pay: number
  status: 'draft' | 'calculated' | 'approved' | 'paid' | 'cancelled'
  calculation_date: string
  approval_date: string | null
  payment_date: string | null
  payroll_notes: string | null
  calculation_method: string
  approved_by_user_id: string | null
  created_at: string
  updated_at: string
}

export async function listPayrollRecords(params?: {
  unit_id?: string
  status?: string
  unit_type?: string
  year?: number
  month?: number
  page?: number
  page_size?: number
}): Promise<PayrollRecord[]> {
  const result = await listPayrollRecordsWithTotal(params)

  return result.items
}

export async function listPayrollRecordsWithTotal(params?: {
  unit_id?: string
  status?: string
  unit_type?: string
  year?: number
  month?: number
  page?: number
  page_size?: number
}): Promise<AttendanceListResult<PayrollRecord>> {
  return await fetchAttendanceListWithTotal<PayrollRecord>('/payroll-records', params)
}

export interface PayrollStats {
  records: number
  total_gross_pay: number
  total_net_pay: number
  approved: number
  paid: number
  pending: number
}

export async function getPayrollStats(params?: {
  unit_id?: string
  status?: string
  unit_type?: string
  year?: number
  month?: number
}): Promise<PayrollStats> {
  return await $attendanceApi<PayrollStats>('/payroll-records/stats', { params })
}

export async function createPayrollRecord(payload: {
  unit_id: string
  payroll_period_start: string
  payroll_period_end: string
  total_regular_hours?: number
  total_overtime_hours?: number
  total_holiday_hours?: number
  total_work_days?: number
  total_leave_days?: number
  regular_slots?: number
  ot_slots?: number
  hourly_rate_snapshot?: number | null
  ot_multiplier_snapshot?: number | null
  base_salary?: number
  overtime_pay?: number
  holiday_pay?: number
  allowance?: number
  deduction?: number
  bonus?: number
  gross_pay?: number
  net_pay?: number
  status?: string
  payroll_notes?: string | null
  calculation_method?: string
}): Promise<PayrollRecord> {
  return await $attendanceApi('/payroll-records', { method: 'POST', body: payload })
}

export async function updatePayrollRecord(recordId: string, payload: {
  status?: string
  payroll_notes?: string | null
  adjustment_1?: number
  adjustment_2?: number
  adjustment_1_remark?: string | null
  adjustment_2_remark?: string | null
  gross_pay?: number
  net_pay?: number
}): Promise<PayrollRecord> {
  return await $attendanceApi(`/payroll-records/${recordId}`, { method: 'PATCH', body: payload })
}

export async function deletePayrollRecord(recordId: string): Promise<void> {
  await $attendanceApi(`/payroll-records/${recordId}`, { method: 'DELETE' })
}

export interface StaleSummaryUnit {
  unit_id: string
  unit_code: string | null
  unit_name: string | null
  reason: 'no_summary' | 'outdated'
}

export async function generatePayroll(
  year: number,
  month: number,
  unitType?: string,
  unitIds?: string[],
): Promise<{ created: number; updated: number; skipped: number; stale_summaries?: StaleSummaryUnit[] }> {
  const params = new URLSearchParams()

  params.set('year', String(year))
  params.set('month', String(month))
  if (unitType)
    params.set('unit_type', unitType)
  unitIds?.forEach(id => params.append('unit_ids', id))

  return await $attendanceApi(`/payroll-records/generate?${params.toString()}`, { method: 'POST' })
}
