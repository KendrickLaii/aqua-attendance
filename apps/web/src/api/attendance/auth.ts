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
  role: 'admin' | 'staff' | 'student'
  is_active: boolean
  status: string
  gender: string | null
  date_of_birth: string | null
  phone: string | null
  address: string | null
  emergency_contact_name: string | null
  emergency_contact_phone: string | null
  remarks: string | null
  student_code: string | null
  english_name: string | null
  school_name: string | null
  grade_class: string | null
  guardian1_name: string | null
  guardian1_relationship: string | null
  guardian1_phone: string | null
  guardian2_name: string | null
  guardian2_relationship: string | null
  guardian2_phone: string | null
  whatsapp_enabled: boolean
  created_at: string
  updated_at: string
}

export async function attendanceLogin(payload: AttendanceLoginPayload): Promise<AttendanceTokens> {
  return await $attendanceApi('/auth/login', { method: 'POST', body: payload })
}

export async function attendanceGetMe(): Promise<AttendanceUser> {
  return await $attendanceApi('/auth/me')
}

export async function attendanceRegister(payload: {
  username: string
  email: string
  password: string
  full_name: string
  role: string
  status?: string
  gender?: string | null
  date_of_birth?: string | null
  phone?: string | null
  address?: string | null
  emergency_contact_name?: string | null
  emergency_contact_phone?: string | null
  remarks?: string | null
  student_code?: string | null
  english_name?: string | null
  school_name?: string | null
  grade_class?: string | null
  guardian1_name?: string | null
  guardian1_relationship?: string | null
  guardian1_phone?: string | null
  guardian2_name?: string | null
  guardian2_relationship?: string | null
  guardian2_phone?: string | null
  whatsapp_enabled?: boolean
}): Promise<AttendanceUser> {
  return await $attendanceApi('/auth/register', { method: 'POST', body: payload })
}
