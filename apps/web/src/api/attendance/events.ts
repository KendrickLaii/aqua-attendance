import { $attendanceApi } from '@/utils/attendanceApi'

export interface AttendanceEvent {
  id: string
  user_id: string
  username: string | null
  full_name: string | null
  event_type: 'check_in' | 'check_out' | 'manual_correction'
  recorded_at: string
  qr_jti: string | null
  scanner_user_id: string | null
  client_device_id: string | null
  notes: string | null
}

export interface QRPayload {
  qr_token: string
  expires_in: number
}

export async function getQRToken(): Promise<QRPayload> {
  return await $attendanceApi('/qr/token')
}

export async function scanQR(payload: { qr_token: string; device_id?: string }): Promise<AttendanceEvent> {
  return await $attendanceApi('/attendance/scan', { method: 'POST', body: payload })
}

export async function listAttendance(params?: {
  target_user_id?: string
  date_from?: string
  date_to?: string
  event_type?: string
  page?: number
  page_size?: number
}): Promise<AttendanceEvent[]> {
  return await $attendanceApi('/attendance', { params })
}

export async function createManualCorrection(payload: {
  user_id: string
  event_type?: string
  recorded_at?: string
  notes?: string
}): Promise<AttendanceEvent> {
  return await $attendanceApi('/attendance/manual', { method: 'POST', body: payload })
}

export function getExportCSVUrl(params?: {
  target_user_id?: string
  date_from?: string
  date_to?: string
}): string {
  const base = import.meta.env.VITE_ATTENDANCE_API_URL || 'http://localhost:8000/api'
  const qs = new URLSearchParams()
  if (params?.target_user_id) qs.set('target_user_id', params.target_user_id)
  if (params?.date_from) qs.set('date_from', params.date_from)
  if (params?.date_to) qs.set('date_to', params.date_to)
  return `${base}/attendance/export/csv?${qs.toString()}`
}
