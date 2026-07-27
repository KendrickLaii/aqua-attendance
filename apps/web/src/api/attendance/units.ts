import { $attendanceApi } from '@/utils/attendanceApi'
import { fetchAttendanceListWithTotal, type AttendanceListResult } from '@/utils/attendanceListApi'

export interface UnitLocationRef {
  id: string
  code: string | null
  name_zh: string
  name_en: string
}

export interface GuardianInfo {
  name?: string | null
  relationship?: string | null
  phone?: string | null
}

export interface StudentProfileOut {
  id: string
  school_name: string | null
  grade_class: string | null
  student_id: string | null
  guardians: Record<string, unknown> | null
  enrollment_date: string | null
  graduation_date: string | null
  academic_notes: string | null
}

export interface StaffProfileOut {
  id: string
  employee_id: string | null
  employment_type: string | null
  department: string | null
  position: string | null
  hire_date: string | null
  termination_date: string | null
  salary_grade: string | null
  pay_type: string | null
  hourly_rate: number | null
  monthly_salary: number | null
  ot_multiplier: number | null
  work_schedule: string | null
  supervisor_id: string | null
  employment_notes: string | null
}

export interface Unit {
  id: string
  code: string
  full_name: string
  english_name: string | null
  unit_type: 'student' | 'staff'
  is_active: boolean
  status: string
  attendance_status: 'checked_in' | 'checked_out'
  qr_token_version: number
  registered_location_id: string
  registered_location: UnitLocationRef | null
  scan_location_ids: string[]
  scan_locations: UnitLocationRef[]
  last_event_at: string | null
  last_event_location: string | null
  gender: string | null
  date_of_birth: string | null
  phone: string | null
  address: string | null
  email: string | null
  emergency_contact_name: string | null
  emergency_contact_phone: string | null
  photo_url: string | null
  enrollment_date: string | null
  exit_date: string | null
  whatsapp_enabled: boolean
  remarks: string | null
  created_at: string
  updated_at: string
  student_profile: StudentProfileOut | null
  staff_profile: StaffProfileOut | null
}

export interface StudentProfileInput {
  school_name?: string | null
  grade_class?: string | null
  student_id?: string | null
  guardians?: Record<string, unknown> | null
  enrollment_date?: string | null
  graduation_date?: string | null
  academic_notes?: string | null
}

export interface StaffProfileInput {
  employee_id?: string | null
  employment_type?: string | null
  department?: string | null
  position?: string | null
  hire_date?: string | null
  termination_date?: string | null
  salary_grade?: string | null
  pay_type?: string | null
  hourly_rate?: number | null
  monthly_salary?: number | null
  ot_multiplier?: number | null
  work_schedule?: string | null
  supervisor_id?: string | null
  employment_notes?: string | null
}

export async function listUnits(params?: {
  unit_type?: string
  is_active?: boolean
  attendance_status?: 'checked_in' | 'checked_out'
  search?: string
  page?: number
  page_size?: number
}): Promise<Unit[]> {
  const result = await listUnitsWithTotal(params)

  return result.items
}

export async function listUnitsWithTotal(params?: {
  unit_type?: string
  is_active?: boolean
  attendance_status?: 'checked_in' | 'checked_out'
  search?: string
  page?: number
  page_size?: number
}): Promise<AttendanceListResult<Unit>> {
  return await fetchAttendanceListWithTotal<Unit>('/units', params)
}

export async function getUnit(unitId: string): Promise<Unit> {
  return await $attendanceApi(`/units/${unitId}`)
}

export async function createUnit(payload: {
  code: string
  full_name: string
  english_name?: string | null
  unit_type: 'student' | 'staff'
  is_active?: boolean
  status?: string
  registered_location_id: string
  scan_location_ids: string[]
  gender?: string | null
  date_of_birth?: string | null
  phone?: string | null
  address?: string | null
  email?: string | null
  emergency_contact_name?: string | null
  emergency_contact_phone?: string | null
  photo_url?: string | null
  enrollment_date?: string | null
  exit_date?: string | null
  whatsapp_enabled?: boolean
  remarks?: string | null
  student_profile?: StudentProfileInput | null
  staff_profile?: StaffProfileInput | null
}): Promise<Unit> {
  return await $attendanceApi('/units', { method: 'POST', body: payload })
}

export async function updateUnit(unitId: string, payload: {
  code?: string
  full_name?: string
  english_name?: string | null
  unit_type?: 'student' | 'staff'
  is_active?: boolean
  status?: string
  registered_location_id?: string
  scan_location_ids?: string[]
  gender?: string | null
  date_of_birth?: string | null
  phone?: string | null
  address?: string | null
  email?: string | null
  emergency_contact_name?: string | null
  emergency_contact_phone?: string | null
  photo_url?: string | null
  enrollment_date?: string | null
  exit_date?: string | null
  whatsapp_enabled?: boolean
  remarks?: string | null
  student_profile?: StudentProfileInput | null
  staff_profile?: StaffProfileInput | null
}): Promise<Unit> {
  return await $attendanceApi(`/units/${unitId}`, { method: 'PATCH', body: payload })
}

export async function deleteUnit(unitId: string): Promise<void> {
  await $attendanceApi(`/units/${unitId}`, { method: 'DELETE' })
}

export async function updateStaffProfile(unitId: string, payload: StaffProfileInput): Promise<void> {
  await $attendanceApi(`/staff-profiles/${unitId}`, { method: 'PATCH', body: payload })
}

export async function updateStudentProfile(unitId: string, payload: StudentProfileInput): Promise<void> {
  await $attendanceApi(`/student-profiles/${unitId}`, { method: 'PATCH', body: payload })
}
