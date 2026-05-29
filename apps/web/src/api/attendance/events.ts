import { $attendanceApi } from '@/utils/attendanceApi'

export interface AttendanceEvent {
  id: string
  product_id: string
  product_code: string | null
  product_name: string | null
  product_type: string | null
  event_type: 'check_in' | 'check_out' | 'manual_correction'
  recorded_at: string
  attendance_status: 'checked_in' | 'checked_out' | null
  qr_jti: string | null
  recorded_by_user_id: string | null
  client_device_id: string | null
  location_id: string | null
  location: string | null
  notes: string | null
}

export interface QRPayload {
  qr_token: string
  token_version: number
}

export async function getQRToken(productId: string): Promise<QRPayload> {
  return await $attendanceApi(`/qr/token/${productId}`)
}

export async function refreshQRToken(productId: string): Promise<QRPayload> {
  return await $attendanceApi(`/qr/token/${productId}/refresh`, { method: 'POST' })
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

export async function listAttendance(params?: {
  product_id?: string
  product_type?: string
  date_from?: string
  date_to?: string
  event_type?: string
  page?: number
  page_size?: number
}): Promise<AttendanceEvent[]> {
  const result = await listAttendanceWithTotal(params)

  return result.items
}

export async function listAttendanceWithTotal(params?: {
  product_id?: string
  product_type?: string
  date_from?: string
  date_to?: string
  event_type?: string
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
  product_id: string
  event_type?: string
  recorded_at?: string
  location_id?: string
  location?: string
  notes?: string
}): Promise<AttendanceEvent> {
  return await $attendanceApi('/attendance/manual', { method: 'POST', body: payload })
}

export async function exportAttendanceCSV(params?: {
  product_id?: string
  product_type?: string
  date_from?: string
  date_to?: string
}): Promise<Blob> {
  return await $attendanceApi<Blob>('/attendance/export/csv', {
    params,
    responseType: 'blob',
  })
}
