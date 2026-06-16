import { $attendanceApi } from '@/utils/attendanceApi'
import { fetchAttendanceListWithTotal, type AttendanceListResult } from '@/utils/attendanceListApi'

export interface AuditLog {
  id: string
  user_id: string | null
  action: string
  table_name: string
  record_id: string | null
  old_values: Record<string, unknown> | null
  new_values: Record<string, unknown> | null
  description: string | null
  ip_address: string | null
  user_agent: string | null
  session_id: string | null
  request_id: string | null
  batch_operation: boolean
  created_at: string
}

export async function listAuditLogs(params?: {
  user_id?: string
  action?: string
  table_name?: string
  record_id?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}): Promise<AuditLog[]> {
  const result = await listAuditLogsWithTotal(params)

  return result.items
}

export async function listAuditLogsWithTotal(params?: {
  user_id?: string
  action?: string
  table_name?: string
  record_id?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}): Promise<AttendanceListResult<AuditLog>> {
  return await fetchAttendanceListWithTotal<AuditLog>('/audit-logs', params)
}
