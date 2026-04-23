import { apiRequest } from './api';

export interface QRPayload {
  qr_token: string;
  expires_in: number;
}

export interface AttendanceEvent {
  id: string;
  user_id: string;
  username: string | null;
  full_name: string | null;
  event_type: 'check_in' | 'check_out' | 'manual_correction';
  recorded_at: string;
  qr_jti: string | null;
  scanner_user_id: string | null;
  client_device_id: string | null;
  notes: string | null;
}

export async function getQRToken(): Promise<QRPayload> {
  return apiRequest('/qr/token');
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
