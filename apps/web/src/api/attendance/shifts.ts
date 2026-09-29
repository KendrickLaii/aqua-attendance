import { $attendanceApi } from '@/utils/attendanceApi'

/** Reusable preset, e.g. "Morning 09:00–13:00". Times are "HH:MM:SS" from the API. */
export interface ShiftTemplate {
  id: string
  name: string
  start_time: string
  end_time: string
  color: string
  sort_order: number
  created_at: string
  updated_at: string
}

export interface ShiftTemplatePayload {
  name: string
  start_time: string
  end_time: string
  color: string
  sort_order?: number
}

/** One scheduled shift for a staff unit. Record only — not used by attendance or payroll. */
export interface Shift {
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
  created_by_id: string | null
  updated_by_id: string | null
  created_at: string
  updated_at: string
}

export interface ShiftPayload {
  unit_id: string
  location_id: string
  shift_date: string
  start_time: string
  end_time: string
  title?: string | null
  color: string
  notes?: string | null
  template_id?: string | null
}

// ---- Templates ----

export async function listShiftTemplates(): Promise<ShiftTemplate[]> {
  return await $attendanceApi('/shift-templates')
}

export async function createShiftTemplate(payload: ShiftTemplatePayload): Promise<ShiftTemplate> {
  return await $attendanceApi('/shift-templates', { method: 'POST', body: payload })
}

export async function updateShiftTemplate(id: string, payload: Partial<ShiftTemplatePayload>): Promise<ShiftTemplate> {
  return await $attendanceApi(`/shift-templates/${id}`, { method: 'PATCH', body: payload })
}

export async function deleteShiftTemplate(id: string): Promise<void> {
  await $attendanceApi(`/shift-templates/${id}`, { method: 'DELETE' })
}

// ---- Shifts ----

export async function listShifts(params: {
  start: string
  end: string
  location_id?: string
  unit_id?: string
}): Promise<Shift[]> {
  return await $attendanceApi('/shifts', { params })
}

export async function createShift(payload: ShiftPayload): Promise<Shift> {
  return await $attendanceApi('/shifts', { method: 'POST', body: payload })
}

export async function updateShift(id: string, payload: Partial<ShiftPayload>): Promise<Shift> {
  return await $attendanceApi(`/shifts/${id}`, { method: 'PATCH', body: payload })
}

export async function deleteShift(id: string): Promise<void> {
  await $attendanceApi(`/shifts/${id}`, { method: 'DELETE' })
}

export async function copyShiftWeek(payload: {
  source_week_start: string
  target_week_start: string
  location_id?: string
}): Promise<{ created: number; skipped: number }> {
  return await $attendanceApi('/shifts/copy-week', { method: 'POST', body: payload })
}
