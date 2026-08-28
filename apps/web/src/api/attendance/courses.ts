import { $attendanceApi } from '@/utils/attendanceApi'
import { fetchAttendanceListWithTotal, type AttendanceListResult } from '@/utils/attendanceListApi'

/** SPU — course subject/curriculum, e.g. "Primary Math". */
export interface CourseSpu {
  id: string
  code: string
  name_zh: string
  name_en: string | null
  subject: string | null
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CourseSpuPayload {
  code: string
  name_zh: string
  name_en?: string | null
  subject?: string | null
  description?: string | null
  is_active?: boolean
}

export type BillingUnit = 'monthly' | 'per_session'

export type Weekday =
  | 'monday'
  | 'tuesday'
  | 'wednesday'
  | 'thursday'
  | 'friday'
  | 'saturday'
  | 'sunday'

/** SKU — a concrete, enrollable class offering under a CourseSpu. */
export interface CourseSku {
  id: string
  spu_id: string
  code: string
  name_zh: string
  name_en: string | null
  level: string | null
  schedule_note: string | null
  location_id: string | null
  capacity: number | null
  price: number | null
  billing_unit: BillingUnit
  meeting_weekdays: Weekday[]
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CourseSkuPayload {
  spu_id: string
  code: string
  name_zh: string
  name_en?: string | null
  level?: string | null
  schedule_note?: string | null
  location_id?: string | null
  capacity?: number | null
  price?: number | null
  billing_unit?: BillingUnit
  meeting_weekdays?: Weekday[]
  is_active?: boolean
}

export type EnrollmentStatus = 'active' | 'completed' | 'cancelled'

export interface CourseEnrollment {
  id: string
  unit_id: string
  sku_id: string
  status: EnrollmentStatus
  enrolled_at: string
  start_date: string | null
  end_date: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface CourseEnrollmentPayload {
  unit_id: string
  sku_id: string
  status?: EnrollmentStatus
  start_date?: string | null
  end_date?: string | null
  notes?: string | null
}

// ---- SPU ----

async function fetchAllAttendancePages<T>(
  path: string,
  params?: Record<string, unknown>,
): Promise<T[]> {
  const pageSize = 200
  const first = await fetchAttendanceListWithTotal<T>(path, { ...params, page: 1, page_size: pageSize })
  const items = [...first.items]
  let page = 2
  while (items.length < first.total) {
    const next = await fetchAttendanceListWithTotal<T>(path, { ...params, page, page_size: pageSize })
    if (next.items.length === 0)
      break
    items.push(...next.items)
    page += 1
  }
  return items
}

export async function listCourseSpus(params?: { is_active?: boolean, search?: string }): Promise<CourseSpu[]> {
  return await fetchAllAttendancePages<CourseSpu>('/course-spus', params)
}

export async function createCourseSpu(payload: CourseSpuPayload): Promise<CourseSpu> {
  return await $attendanceApi('/course-spus', { method: 'POST', body: payload })
}

export async function updateCourseSpu(id: string, payload: Partial<CourseSpuPayload>): Promise<CourseSpu> {
  return await $attendanceApi(`/course-spus/${id}`, { method: 'PATCH', body: payload })
}

export async function deleteCourseSpu(id: string): Promise<void> {
  await $attendanceApi(`/course-spus/${id}`, { method: 'DELETE' })
}

// ---- SKU ----

export async function listCourseSkus(params?: {
  spu_id?: string
  is_active?: boolean
  search?: string
}): Promise<CourseSku[]> {
  return await fetchAllAttendancePages<CourseSku>('/course-skus', params)
}

export async function createCourseSku(payload: CourseSkuPayload): Promise<CourseSku> {
  return await $attendanceApi('/course-skus', { method: 'POST', body: payload })
}

export async function updateCourseSku(id: string, payload: Partial<CourseSkuPayload>): Promise<CourseSku> {
  return await $attendanceApi(`/course-skus/${id}`, { method: 'PATCH', body: payload })
}

export async function deleteCourseSku(id: string): Promise<void> {
  await $attendanceApi(`/course-skus/${id}`, { method: 'DELETE' })
}

// ---- Enrollments ----

export async function listCourseEnrollmentsWithTotal(params?: {
  unit_id?: string
  sku_id?: string
  status?: EnrollmentStatus
  page?: number
  page_size?: number
}): Promise<AttendanceListResult<CourseEnrollment>> {
  return await fetchAttendanceListWithTotal<CourseEnrollment>('/course-enrollments', params)
}

export async function createCourseEnrollment(payload: CourseEnrollmentPayload): Promise<CourseEnrollment> {
  return await $attendanceApi('/course-enrollments', { method: 'POST', body: payload })
}

export async function updateCourseEnrollment(
  id: string,
  payload: Partial<Pick<CourseEnrollmentPayload, 'status' | 'start_date' | 'end_date' | 'notes'>>,
): Promise<CourseEnrollment> {
  return await $attendanceApi(`/course-enrollments/${id}`, { method: 'PATCH', body: payload })
}

export async function deleteCourseEnrollment(id: string): Promise<void> {
  await $attendanceApi(`/course-enrollments/${id}`, { method: 'DELETE' })
}
