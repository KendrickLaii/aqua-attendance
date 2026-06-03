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
  location_id: string | null;
  location: string | null;
  notes: string | null;
}

export async function getQRToken(productId: string): Promise<QRPayload> {
  return apiRequest(`/qr/token/${productId}`);
}

export interface ScanPreview {
  product_id: string;
  product_code: string | null;
  product_name: string | null;
  product_type: string | null;
  attendance_status: 'checked_in' | 'checked_out' | null;
  location: string | null;
}

export async function previewScanQR(
  qrToken: string,
  options?: { locationId?: string },
): Promise<ScanPreview> {
  return apiRequest('/attendance/scan/preview', {
    method: 'POST',
    body: JSON.stringify({
      qr_token: qrToken,
      location_id: options?.locationId || undefined,
    }),
  });
}

export async function scanQR(
  qrToken: string,
  options?: {
    deviceId?: string;
    eventType?: 'check_in' | 'check_out';
    locationId?: string;
  },
): Promise<AttendanceEvent> {
  return apiRequest('/attendance/scan', {
    method: 'POST',
    body: JSON.stringify({
      qr_token: qrToken,
      device_id: options?.deviceId,
      event_type: options?.eventType,
      location_id: options?.locationId || undefined,
    }),
  });
}

export async function listAttendance(params?: Record<string, string>): Promise<AttendanceEvent[]> {
  const qs = params ? `?${new URLSearchParams(params).toString()}` : '';
  return apiRequest(`/attendance${qs}`);
}
