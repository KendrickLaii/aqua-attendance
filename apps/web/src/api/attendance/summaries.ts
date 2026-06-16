import { $attendanceApi } from '@/utils/attendanceApi'
import { fetchAttendanceListWithTotal, type AttendanceListResult } from '@/utils/attendanceListApi'

export interface AttendanceSummary {
  id: string
  product_id: string
  location_id: string | null
  summary_date: string
  first_check_in: string | null
  last_check_out: string | null
  total_regular_hours: number
  total_overtime_hours: number
  total_break_hours: number
  expected_hours: number
  status: string
  calculation_notes: string | null
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
