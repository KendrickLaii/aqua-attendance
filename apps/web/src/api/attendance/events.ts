import { $attendanceApi } from '@/utils/attendanceApi'

export interface AttendanceEvent {
  id: string
  unit_id: string
  unit_code: string | null
  unit_name: string | null
  unit_type: string | null
  event_type: 'check_in' | 'check_out'
  source: string
  recorded_at: string
  created_at: string
  attendance_status: 'checked_in' | 'checked_out' | null
  qr_jti: string | null
  recorded_by_user_id: string | null
  client_device_id: string | null
  location_id: string | null
  location: string | null
  notes: string | null
  voided_at: string | null
}

export interface QRPayload {
  qr_token: string
  token_version: number
}

export async function getQRToken(unitId: string): Promise<QRPayload> {
  return await $attendanceApi(`/qr/token/${unitId}`)
}

export async function refreshQRToken(unitId: string): Promise<QRPayload> {
  return await $attendanceApi(`/qr/token/${unitId}/refresh`, { method: 'POST' })
}

export async function scanQR(payload: {
  qr_token: string
  device_id?: string
  location_id?: string
  location?: string
  event_type?: 'check_in' | 'check_out'
}): Promise<AttendanceEvent> {
  return await $attendanceApi('/attendance/scan', { method: 'POST', body: payload })
}

export interface AttendanceListResult {
  items: AttendanceEvent[]
  total: number
}

export interface AttendanceDayStats {
  total: number
  check_ins_student: number
  check_ins_staff: number
  check_outs_student: number
  check_outs_staff: number
}

export async function getAttendanceDayStats(params?: {
  date_from?: string
  date_to?: string
}): Promise<AttendanceDayStats> {
  return await $attendanceApi<AttendanceDayStats>('/attendance/stats', { params })
}

export async function listAttendance(params?: {
  unit_id?: string
  unit_type?: string
  date_from?: string
  date_to?: string
  event_type?: string
  source?: string
  include_voided?: boolean
  page?: number
  page_size?: number
}): Promise<AttendanceEvent[]> {
  const result = await listAttendanceWithTotal(params)

  return result.items
}

export async function listAttendanceWithTotal(params?: {
  unit_id?: string
  unit_type?: string
  date_from?: string
  date_to?: string
  event_type?: string
  source?: string
  include_voided?: boolean
  page?: number
  page_size?: number
}): Promise<AttendanceListResult> {
  let total = 0

  const items = await $attendanceApi<AttendanceEvent[]>('/attendance', {
    params,
    onResponse({ response }) {
      const header = response.headers.get('X-Total-Count')
      if (header)
        total = Number.parseInt(header, 10) || 0
    },
  })

  return { items, total: total || items.length }
}

export async function createManualCorrection(payload: {
  unit_id: string
  event_type?: string
  recorded_at?: string
  location_id?: string
  location?: string
  notes?: string
}): Promise<AttendanceEvent> {
  return await $attendanceApi('/attendance/manual', { method: 'POST', body: payload })
}

export async function exportAttendanceCSV(params?: {
  unit_id?: string
  unit_type?: string
  date_from?: string
  date_to?: string
  include_voided?: boolean
}): Promise<Blob> {
  return await $attendanceApi<Blob>('/attendance/export/csv', {
    params,
    responseType: 'blob',
  })
}

export async function voidAttendanceEvent(eventId: string): Promise<AttendanceEvent> {
  return await $attendanceApi(`/attendance/${eventId}/void`, { method: 'POST' })
}
