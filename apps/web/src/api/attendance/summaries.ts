import { $attendanceApi } from '@/utils/attendanceApi'
import { fetchAttendanceListWithTotal, type AttendanceListResult } from '@/utils/attendanceListApi'

export interface AttendanceSummary {
  id: string
  unit_id: string
  unit_name: string | null
  unit_code: string | null
  summary_date: string
  location_id: string
  first_check_in: string | null
  last_check_out: string | null
  total_work_minutes: number
  total_overtime_minutes: number
  is_complete: boolean
  is_holiday: boolean
  is_weekend: boolean
  regular_slots: number
  ot_slots: number
  regular_hours: number
  overtime_hours: number
  holiday_hours: number
  attendance_notes: string | null
  calculation_method: string
  created_at: string
  updated_at: string
}

export interface SummaryOverviewItem {
  unit_id: string
  unit_name: string | null
  unit_code: string | null
  unit_type: string
  days_present: number
  days_complete: number
  days_incomplete: number
  total_regular_hours: number
  total_overtime_hours: number
  total_regular_slots: number
  total_ot_slots: number
  first_date: string | null
  last_date: string | null
}

export async function listSummaries(params?: {
  unit_id?: string
  summary_date?: string
  date_from?: string
  date_to?: string
  unit_type?: string
  is_complete?: boolean
  page?: number
  page_size?: number
}): Promise<AttendanceSummary[]> {
  const result = await listSummariesWithTotal(params)

  return result.items
}

export async function listSummariesWithTotal(params?: {
  unit_id?: string
  summary_date?: string
  date_from?: string
  date_to?: string
  unit_type?: string
  is_complete?: boolean
  page?: number
  page_size?: number
}): Promise<AttendanceListResult<AttendanceSummary>> {
  return await fetchAttendanceListWithTotal<AttendanceSummary>('/attendance-summaries', params)
}

export async function listSummaryOverview(params: {
  date_from: string
  date_to: string
  unit_type?: string
  search?: string
  page?: number
  page_size?: number
}): Promise<AttendanceListResult<SummaryOverviewItem>> {
  return await fetchAttendanceListWithTotal<SummaryOverviewItem>('/attendance-summaries/overview', params)
}

export interface SummaryOverviewStats {
  people: number
  days_present: number
  days_complete: number
  days_incomplete: number
  total_regular_hours: number
  total_overtime_hours: number
  total_regular_slots: number
  total_ot_slots: number
}

export async function getSummaryOverviewStats(params: {
  date_from: string
  date_to: string
  unit_type?: string
  search?: string
}): Promise<SummaryOverviewStats> {
  return await $attendanceApi<SummaryOverviewStats>('/attendance-summaries/overview/stats', { params })
}

export async function generateSummaries(year: number, month: number): Promise<{
  created: number
  updated: number
  total_days: number
  auto_checkouts?: number
  orphans_deleted?: number
}> {
  return await $attendanceApi(`/attendance-summaries/generate?year=${year}&month=${month}`, { method: 'POST' })
}
