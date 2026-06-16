import { $attendanceApi } from '@/utils/attendanceApi'
import { fetchAttendanceListWithTotal, type AttendanceListResult } from '@/utils/attendanceListApi'

export interface AttendanceSummary {
  id: string
  product_id: string
  product_name: string | null
  product_code: string | null
  summary_date: string
  location_id: string
  first_check_in: string | null
  last_check_out: string | null
  total_work_minutes: number
  total_overtime_minutes: number
  total_break_minutes: number
  is_complete: boolean
  is_holiday: boolean
  is_weekend: boolean
  regular_hours: number
  overtime_hours: number
  holiday_hours: number
  attendance_notes: string | null
  calculation_method: string
  created_at: string
  updated_at: string
}

export async function listSummaries(params?: {
  product_id?: string
  summary_date?: string
  page?: number
  page_size?: number
}): Promise<AttendanceSummary[]> {
  const result = await listSummariesWithTotal(params)

  return result.items
}

export async function listSummariesWithTotal(params?: {
  product_id?: string
  summary_date?: string
  page?: number
  page_size?: number
}): Promise<AttendanceListResult<AttendanceSummary>> {
  return await fetchAttendanceListWithTotal<AttendanceSummary>('/attendance-summaries', params)
}

export async function generateSummaries(year: number, month: number): Promise<{ created: number; updated: number }> {
  return await $attendanceApi(`/attendance-summaries/generate?year=${year}&month=${month}`, { method: 'POST' })
}
