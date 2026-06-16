import { $attendanceApi } from '@/utils/attendanceApi'
import { fetchAttendanceListWithTotal, type AttendanceListResult } from '@/utils/attendanceListApi'

export interface ProductLocationRef {
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
  work_schedule: string | null
  supervisor_id: string | null
  employment_notes: string | null
}

export interface Product {
  id: string
  code: string
  full_name: string
  english_name: string | null
  product_type: 'student' | 'staff'
  is_active: boolean
  status: string
  attendance_status: 'checked_in' | 'checked_out'
  qr_token_version: number
  registered_location_id: string
  registered_location: ProductLocationRef | null
  scan_location_ids: string[]
  scan_locations: ProductLocationRef[]
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
  work_schedule?: string | null
  supervisor_id?: string | null
  employment_notes?: string | null
}

export async function listProducts(params?: {
  product_type?: string
  is_active?: boolean
  attendance_status?: 'checked_in' | 'checked_out'
  search?: string
  page?: number
  page_size?: number
}): Promise<Product[]> {
  const result = await listProductsWithTotal(params)

  return result.items
}

export async function listProductsWithTotal(params?: {
  product_type?: string
  is_active?: boolean
  attendance_status?: 'checked_in' | 'checked_out'
  search?: string
  page?: number
  page_size?: number
}): Promise<AttendanceListResult<Product>> {
  return await fetchAttendanceListWithTotal<Product>('/products', params)
}

export async function getProduct(productId: string): Promise<Product> {
  return await $attendanceApi(`/products/${productId}`)
}

export async function createProduct(payload: {
  code: string
  full_name: string
  english_name?: string | null
  product_type: 'student' | 'staff'
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
}): Promise<Product> {
  return await $attendanceApi('/products', { method: 'POST', body: payload })
}

export async function updateProduct(productId: string, payload: {
  code?: string
  full_name?: string
  english_name?: string | null
  product_type?: 'student' | 'staff'
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
}): Promise<Product> {
  return await $attendanceApi(`/products/${productId}`, { method: 'PATCH', body: payload })
}

export async function deleteProduct(productId: string): Promise<void> {
  await $attendanceApi(`/products/${productId}`, { method: 'DELETE' })
}

export async function updateStaffProfile(productId: string, payload: StaffProfileInput): Promise<void> {
  await $attendanceApi(`/staff-profiles/${productId}`, { method: 'PATCH', body: payload })
}

export async function updateStudentProfile(productId: string, payload: StudentProfileInput): Promise<void> {
  await $attendanceApi(`/student-profiles/${productId}`, { method: 'PATCH', body: payload })
}
