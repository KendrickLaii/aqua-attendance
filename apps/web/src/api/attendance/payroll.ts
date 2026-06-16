import { $attendanceApi } from '@/utils/attendanceApi'
import { fetchAttendanceListWithTotal, type AttendanceListResult } from '@/utils/attendanceListApi'

export interface PayrollRecord {
  id: string
  product_id: string
  product_name: string | null
  product_code: string | null
  payroll_period_start: string
  payroll_period_end: string
  total_regular_hours: number
  total_overtime_hours: number
  total_holiday_hours: number
  total_work_days: number
  total_leave_days: number
  base_salary: number
  overtime_pay: number
  holiday_pay: number
  allowance: number
  deduction: number
  bonus: number
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
  product_id?: string
  status?: string
  page?: number
  page_size?: number
}): Promise<PayrollRecord[]> {
  const result = await listPayrollRecordsWithTotal(params)

  return result.items
}

export async function listPayrollRecordsWithTotal(params?: {
  product_id?: string
  status?: string
  page?: number
  page_size?: number
}): Promise<AttendanceListResult<PayrollRecord>> {
  return await fetchAttendanceListWithTotal<PayrollRecord>('/payroll-records', params)
}

export async function createPayrollRecord(payload: {
  product_id: string
  payroll_period_start: string
  payroll_period_end: string
  total_regular_hours?: number
  total_overtime_hours?: number
  total_holiday_hours?: number
  total_work_days?: number
  total_leave_days?: number
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
}): Promise<PayrollRecord> {
  return await $attendanceApi(`/payroll-records/${recordId}`, { method: 'PATCH', body: payload })
}

export async function deletePayrollRecord(recordId: string): Promise<void> {
  await $attendanceApi(`/payroll-records/${recordId}`, { method: 'DELETE' })
}
