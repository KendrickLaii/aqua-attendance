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
}): Promise<AttendanceUser> {
  return await $attendanceApi('/users', { method: 'POST', body: payload })
}

export async function updateUser(userId: string, payload: {
  email?: string
  full_name?: string
  role?: string
  is_active?: boolean
}): Promise<AttendanceUser> {
  return await $attendanceApi(`/users/${userId}`, { method: 'PATCH', body: payload })
}

export async function deleteUser(userId: string): Promise<void> {
  await $attendanceApi(`/users/${userId}`, { method: 'DELETE' })
}
