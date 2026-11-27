import { $attendanceApi } from '@/utils/attendanceApi'

export interface AttendanceLoginPayload {
  username: string
  password: string
}

export interface AttendanceTokens {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface AttendanceUser {
  id: string
  username: string
  email: string
  full_name: string
  role: 'user' | 'admin' | 'superadmin'
  is_active: boolean
  location_ids?: string[]
  sees_all_teams?: boolean
  created_at: string
  updated_at: string
}

export async function attendanceLogin(payload: AttendanceLoginPayload): Promise<AttendanceTokens> {
  return await $attendanceApi('/auth/login', { method: 'POST', body: payload })
}

export async function attendanceChangePassword(currentPassword: string, newPassword: string): Promise<void> {
  await $attendanceApi('/auth/change-password', {
    method: 'POST',
    body: { current_password: currentPassword, new_password: newPassword },
  })
}

export async function attendanceGetMe(): Promise<AttendanceUser> {
  return await $attendanceApi('/auth/me')
}

/** Revoke refresh token on sign-out (idempotent; safe if token already expired). */
export async function attendanceLogout(refreshToken?: string | null): Promise<void> {
  await $attendanceApi('/auth/logout', {
    method: 'POST',
    body: refreshToken ? { refresh_token: refreshToken } : {},
  })
}
