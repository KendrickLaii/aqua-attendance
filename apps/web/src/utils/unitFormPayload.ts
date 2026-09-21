import type { StaffProfileInput, StudentProfileInput } from '@/api/attendance/units'

export interface UnitGuardianForm {
  name: string
  relationship: string
  phone: string
}

export interface UnitFormState {
  code: string
  full_name: string
  english_name: string
  unit_type: 'student' | 'staff'
  is_active: boolean
  status: string
  gender: string
  date_of_birth: string
  phone: string
  address: string
  email: string
  emergency_contact_name: string
  emergency_contact_phone: string
  photo_url: string
  start_date: string
  exit_date: string
  whatsapp_enabled: boolean
  remarks: string
  registered_location_id: string
  scan_location_ids: string[]
  student_profile: {
    school_name: string
    grade_class: string
    student_id: string
    academic_notes: string
    guardians: Record<string, unknown>
  }
  staff_profile: {
    employee_id: string
    employment_type: '' | 'part_time' | 'full_time'
    department: string
    position: string
    salary_grade: string
    pay_type: '' | 'hourly' | 'monthly'
    hourly_rate: string
    monthly_salary: string
    ot_multiplier: string
    work_schedule: string
    supervisor_id: string
    employment_notes: string
  }
  guardians: UnitGuardianForm[]
}

export interface UnitSavePayload {
  code: string
  full_name: string
  english_name: string | null
  unit_type: 'student' | 'staff'
  status: string
  phone: string | null
  address: string | null
  email: string | null
  emergency_contact_name: string | null
  emergency_contact_phone: string | null
  photo_url: string | null
  start_date: string | null
  exit_date: string | null
  whatsapp_enabled: boolean
  remarks: string | null
  registered_location_id: string
  scan_location_ids: string[]
  is_active: boolean
  student_profile?: StudentProfileInput
  staff_profile?: StaffProfileInput
}

export function emptyUnitForm(defaults?: { registered_location_id?: string; scan_location_ids?: string[] }): UnitFormState {
  return {
    code: '',
    full_name: '',
    english_name: '',
    unit_type: 'student',
    is_active: true,
    status: 'active',
    gender: '',
    date_of_birth: '',
    phone: '',
    address: '',
    email: '',
    emergency_contact_name: '',
    emergency_contact_phone: '',
    photo_url: '',
    start_date: '',
    exit_date: '',
    whatsapp_enabled: true,
    remarks: '',
    registered_location_id: defaults?.registered_location_id ?? '',
    scan_location_ids: defaults?.scan_location_ids ? [...defaults.scan_location_ids] : [],
    student_profile: {
      school_name: '',
      grade_class: '',
      student_id: '',
      academic_notes: '',
      guardians: {},
    },
    staff_profile: {
      employee_id: '',
      employment_type: '',
      department: '',
      position: '',
      salary_grade: '',
      pay_type: '',
      hourly_rate: '',
      monthly_salary: '',
      ot_multiplier: '',
      work_schedule: '',
      supervisor_id: '',
      employment_notes: '',
    },
    guardians: [{ name: '', relationship: '', phone: '' }],
  }
}

export function normalizeFormString(value: string): string | null {
  const normalized = value.trim()

  return normalized.length > 0 ? normalized : null
}

export function normalizeFormNumber(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed)
    return null
  const num = Number(trimmed)

  return Number.isFinite(num) ? num : null
}

export function unitSaveValidationError(form: UnitFormState): string | null {
  if (form.unit_type === 'staff' && !form.staff_profile.employment_type)
    return 'Employment type is required for staff'
  if (!form.registered_location_id)
    return 'Registered location is required'
  if (form.scan_location_ids.length === 0)
    return 'Select at least one scan location'

  return null
}

function guardianRecord(guardians: UnitGuardianForm[]): Record<string, unknown> {
  const record: Record<string, unknown> = {}

  guardians.forEach((g, idx) => {
    if (g.name.trim()) {
      record[`guardian${idx + 1}`] = {
        name: normalizeFormString(g.name),
        relationship: normalizeFormString(g.relationship),
        phone: normalizeFormString(g.phone),
      }
    }
  })

  return record
}

export function buildUnitSavePayload(form: UnitFormState): UnitSavePayload {
  const base: UnitSavePayload = {
    code: form.code.trim(),
    full_name: form.full_name.trim(),
    english_name: normalizeFormString(form.english_name),
    unit_type: form.unit_type,
    status: form.status,
    phone: normalizeFormString(form.phone),
    address: normalizeFormString(form.address),
    email: normalizeFormString(form.email),
    emergency_contact_name: normalizeFormString(form.emergency_contact_name),
    emergency_contact_phone: normalizeFormString(form.emergency_contact_phone),
    photo_url: normalizeFormString(form.photo_url),
    start_date: normalizeFormString(form.start_date),
    exit_date: normalizeFormString(form.exit_date),
    whatsapp_enabled: form.whatsapp_enabled,
    remarks: normalizeFormString(form.remarks),
    registered_location_id: form.registered_location_id,
    scan_location_ids: [...form.scan_location_ids],
    is_active: form.is_active,
  }

  if (form.unit_type === 'student') {
    const guardians = guardianRecord(form.guardians)

    return {
      ...base,
      student_profile: {
        gender: normalizeFormString(form.gender),
        date_of_birth: normalizeFormString(form.date_of_birth),
        school_name: normalizeFormString(form.student_profile.school_name),
        grade_class: normalizeFormString(form.student_profile.grade_class),
        student_id: normalizeFormString(form.student_profile.student_id),
        academic_notes: normalizeFormString(form.student_profile.academic_notes),
        guardians: Object.keys(guardians).length > 0 ? guardians : null,
      },
    }
  }

  return {
    ...base,
    staff_profile: {
      gender: normalizeFormString(form.gender),
      date_of_birth: normalizeFormString(form.date_of_birth),
      employee_id: normalizeFormString(form.staff_profile.employee_id),
      employment_type: normalizeFormString(form.staff_profile.employment_type),
      department: normalizeFormString(form.staff_profile.department),
      position: normalizeFormString(form.staff_profile.position),
      salary_grade: normalizeFormString(form.staff_profile.salary_grade),
      pay_type: normalizeFormString(form.staff_profile.pay_type),
      hourly_rate: normalizeFormNumber(form.staff_profile.hourly_rate),
      monthly_salary: normalizeFormNumber(form.staff_profile.monthly_salary),
      ot_multiplier: normalizeFormNumber(form.staff_profile.ot_multiplier),
      work_schedule: normalizeFormString(form.staff_profile.work_schedule),
      supervisor_id: normalizeFormString(form.staff_profile.supervisor_id),
      employment_notes: normalizeFormString(form.staff_profile.employment_notes),
    },
  }
}
