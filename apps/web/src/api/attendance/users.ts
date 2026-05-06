import { $attendanceApi } from '@/utils/attendanceApi'
import type { AttendanceUser } from './auth'

export async function listUsers(params?: {
  role?: string
  is_active?: boolean
  search?: string
  page?: number
  page_size?: number
}): Promise<AttendanceUser[]> {
  return await $attendanceApi('/users', { params })
}

export async function createUser(payload: {
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
  return await $attendanceApi('/users', { method: 'POST', body: payload })
}

export async function updateUser(userId: string, payload: {
  email?: string
  full_name?: string
  role?: string
  is_active?: boolean
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
  return await $attendanceApi(`/users/${userId}`, { method: 'PATCH', body: payload })
}

export async function deleteUser(userId: string): Promise<void> {
  await $attendanceApi(`/users/${userId}`, { method: 'DELETE' })
}
