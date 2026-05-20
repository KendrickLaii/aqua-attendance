import { apiRequest } from './api';

export interface QRPayload {
  qr_token: string;
  token_version: number;
}

export interface AttendanceEvent {
  id: string;
  product_id: string;
  product_code: string | null;
  product_name: string | null;
  product_type: string | null;
  event_type: 'check_in' | 'check_out' | 'manual_correction';
  recorded_at: string;
  attendance_status: 'checked_in' | 'checked_out' | null;
  qr_jti: string | null;
  recorded_by_user_id: string | null;
  client_device_id: string | null;
  notes: string | null;
}

export async function getQRToken(productId: string): Promise<QRPayload> {
  return apiRequest(`/qr/token/${productId}`);
}

export async function scanQR(qrToken: string, deviceId?: string): Promise<AttendanceEvent> {
  return apiRequest('/attendance/scan', {
    method: 'POST',
    body: JSON.stringify({ qr_token: qrToken, device_id: deviceId }),
  });
}

export async function listAttendance(params?: Record<string, string>): Promise<AttendanceEvent[]> {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return apiRequest(`/attendance${qs}`);
}
