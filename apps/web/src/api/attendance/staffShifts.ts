import { ofetch } from 'ofetch'
import type { Shift, ShiftTemplate } from '@/api/attendance/shifts'

const TOKEN_COOKIE = 'staffShiftToken'

function baseURL(): string {
  return import.meta.env.VITE_ATTENDANCE_API_URL || 'http://localhost:8000/api'
}

export function useStaffShiftToken() {
  return useCookie<string | null>(TOKEN_COOKIE, { maxAge: 12 * 60 * 60 })
}

async function staffFetch<T>(path: string, options?: Parameters<typeof ofetch>[1]): Promise<T> {
  const token = useStaffShiftToken().value

  return await ofetch<T>(path, {
    baseURL: baseURL(),
    credentials: 'include',
    ...options,
    headers: {
      ...(options?.headers as Record<string, string> | undefined),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
}

export interface StaffShiftMe {
  id: string
  code: string
  full_name: string
}

export interface StaffLocation {
  id: string
  name_en: string
  name_zh: string | null
}

export interface StaffShiftRequest {
  id: string
  unit_id: string
  location_id: string
  shift_date: string
  start_time: string
  end_time: string
  title: string | null
  color: string
  notes: string | null
  template_id: string | null
  status: 'pending' | 'approved' | 'rejected' | 'cancelled'
  reject_reason: string | null
  shift_id: string | null
}

export async function loginStaffShift(code: string, pin: string): Promise<StaffShiftMe> {
  const data = await staffFetch<{ access_token: string; unit: StaffShiftMe }>('/staff-shifts/login', {
    method: 'POST',
    body: { code, pin },
  })

  useStaffShiftToken().value = data.access_token

  return data.unit
}

export async function logoutStaffShift(): Promise<void> {
  try {
    await staffFetch('/staff-shifts/logout', { method: 'POST' })
  }
  finally {
    useStaffShiftToken().value = null
  }
}

export async function fetchStaffMe(): Promise<StaffShiftMe> {
  return await staffFetch('/staff-shifts/me')
}

export async function fetchStaffWeek(start: string, end: string): Promise<{ shifts: Shift[]; requests: StaffShiftRequest[] }> {
  return await staffFetch('/staff-shifts/week', { params: { start, end } })
}

export async function fetchStaffTemplates(): Promise<ShiftTemplate[]> {
  return await staffFetch('/staff-shifts/templates')
}

export async function fetchStaffLocations(): Promise<StaffLocation[]> {
  return await staffFetch('/staff-shifts/locations')
}

export async function createStaffShiftRequest(payload: {
  location_id: string
  shift_date: string
  start_time: string
  end_time: string
  title?: string | null
  color: string
  notes?: string | null
  template_id?: string | null
}): Promise<StaffShiftRequest> {
  return await staffFetch('/staff-shifts/requests', { method: 'POST', body: payload })
}

export async function cancelStaffShiftRequest(id: string): Promise<StaffShiftRequest> {
  return await staffFetch(`/staff-shifts/requests/${id}`, { method: 'DELETE' })
}
