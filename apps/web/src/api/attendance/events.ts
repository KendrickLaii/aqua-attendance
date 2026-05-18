import { $attendanceApi } from '@/utils/attendanceApi'

export interface AttendanceEvent {
  id: string
  product_id: string
  product_code: string | null
  product_name: string | null
  product_type: string | null
  event_type: 'check_in' | 'check_out' | 'manual_correction'
  recorded_at: string
  qr_jti: string | null
  recorded_by_user_id: string | null
  client_device_id: string | null
  notes: string | null
}

export interface QRPayload {
  qr_token: string
  expires_in: number
}

export async function getQRToken(productId: string): Promise<QRPayload> {
  return await $attendanceApi(`/qr/token/${productId}`)
}

export async function scanQR(payload: { qr_token: string; device_id?: string }): Promise<AttendanceEvent> {
  return await $attendanceApi('/attendance/scan', { method: 'POST', body: payload })
}

export async function listAttendance(params?: {
  product_id?: string
  product_type?: string
  date_from?: string
  date_to?: string
  event_type?: string
  page?: number
  page_size?: number
}): Promise<AttendanceEvent[]> {
  return await $attendanceApi('/attendance', { params })
}

export async function createManualCorrection(payload: {
  product_id: string
  event_type?: string
  recorded_at?: string
  notes?: string
}): Promise<AttendanceEvent> {
  return await $attendanceApi('/attendance/manual', { method: 'POST', body: payload })
}

export function getExportCSVUrl(params?: {
  product_id?: string
  product_type?: string
  date_from?: string
  date_to?: string
}): string {
  const base = import.meta.env.VITE_ATTENDANCE_API_URL || 'http://localhost:8000/api'
  const qs = new URLSearchParams()
  if (params?.product_id) qs.set('product_id', params.product_id)
  if (params?.product_type) qs.set('product_type', params.product_type)
  if (params?.date_from) qs.set('date_from', params.date_from)
  if (params?.date_to) qs.set('date_to', params.date_to)
  return `${base}/attendance/export/csv?${qs.toString()}`
}
