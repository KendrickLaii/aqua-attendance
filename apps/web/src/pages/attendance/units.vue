<script setup lang="ts">
import type { VForm } from 'vuetify/components/VForm'
import {
  maxCharsRule,
  requiredValidator,
} from '@core/utils/validators'
import { createUnit, deleteUnit, listUnitsWithTotal, updateStaffProfile, updateStudentProfile, updateUnit } from '@/api/attendance/units'
import type { Unit } from '@/api/attendance/units'
import { listLocations } from '@/api/attendance/locations'
import type { LocationItem } from '@/api/attendance/locations'
import { type CourseEnrollment, type CourseSku, listAllCourseEnrollments, listCourseSkus } from '@/api/attendance/courses'
import UnitQrDialogs from '@/components/attendance/UnitQrDialogs.vue'
import AppToastStack from '@/components/AppToastStack.vue'
import { formatLastAttendance } from '@/utils/attendanceDisplay'
import {
  billingUnitShortLabel,
  buildUnitEnrollmentRows,
  enrollmentStatusColor,
  formatEnrollmentRange,
  type UnitEnrollmentRow,
} from '@/utils/courseEnrollmentDisplay'
import { formatApiError } from '@/utils/formatApiDetail'
import { useToast } from '@/composables/useToast'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

definePage({ meta: {} })

const pageSize = ref(40)
const pageSizeOptions = [10, 20, 40, 60, 100]
const SEARCH_DEBOUNCE_MS = 300

const { ensureAccess } = useAttendanceAdminGate()
const { show: showToast } = useToast()

const units = ref<Unit[]>([])
const locations = ref<LocationItem[]>([])
const totalCount = ref(0)
const page = ref(1)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')

useAutoClearAlerts(loadError)

const dialogOpen = ref(false)
const editingUnit = ref<Unit | null>(null)
const correctionDialog = ref(false)
const correctionTarget = ref<Unit | null>(null)

const form = reactive({
  code: '',
  full_name: '',
  english_name: '',
  unit_type: 'student' as 'student' | 'staff',
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
  registered_location_id: '' as string,
  scan_location_ids: [] as string[],

  // Nested profiles (sent in create/update payload)
  student_profile: {
    school_name: '',
    grade_class: '',
    student_id: '',
    academic_notes: '',
    guardians: {} as Record<string, unknown>,
  },
  staff_profile: {
    employee_id: '',
    employment_type: '' as '' | 'part_time' | 'full_time',
    department: '',
    position: '',
    salary_grade: '',
    pay_type: '' as '' | 'hourly' | 'monthly',
    hourly_rate: '',
    monthly_salary: '',
    ot_multiplier: '',
    work_schedule: '',
    supervisor_id: '',
    employment_notes: '',
  },
  guardians: [] as { name: string; relationship: string; phone: string }[],
})

const saving = ref(false)
const saveError = ref<string | null>(null)
const searchQuery = ref('')
const filterType = ref('')
const filterActive = ref('')
const filterAttendance = ref('')
const filterEmployment = ref('')
const qrDialogsRef = ref<InstanceType<typeof UnitQrDialogs> | null>(null)

const deleteConfirmOpen = ref(false)
const deleteTarget = ref<Unit | null>(null)
const deleting = ref(false)
const deleteError = ref('')

const unitEnrollmentRows = ref<UnitEnrollmentRow<CourseEnrollment, CourseSku>[]>([])
const unitEnrollmentsLoading = ref(false)
const unitEnrollmentsError = ref('')
let unitEnrollmentsRequestId = 0

const statusOptions = [
  { title: 'Active', value: 'active' },
  { title: 'Inactive', value: 'inactive' },
  { title: 'Suspended', value: 'suspended' },
]

const typeOptions = [
  { title: 'Student', value: 'student' },
  { title: 'Staff', value: 'staff' },
]

const activeFilterOptions = [
  { title: 'All statuses', value: '' },
  { title: 'Active only', value: 'active' },
  { title: 'Inactive only', value: 'inactive' },
]

const attendanceFilterOptions = [
  { title: 'All attendance', value: '' },
  { title: 'Checked in', value: 'checked_in' },
  { title: 'Checked out', value: 'checked_out' },
]

const employmentFilterOptions = [
  { title: 'All employment', value: '' },
  { title: 'Full-time', value: 'full_time' },
  { title: 'Part-time', value: 'part_time' },
]

const employmentTypeOptions = [
  { title: 'Full-time', value: 'full_time' },
  { title: 'Part-time', value: 'part_time' },
]

const payTypeOptions = [
  { title: 'Hourly', value: 'hourly' },
  { title: 'Monthly', value: 'monthly' },
]

const locationOptions = computed(() =>
  locations.value
    .filter(loc => loc.is_active)
    .map(loc => ({
      title: loc.name_en || loc.name_zh || loc.code || loc.id,
      value: loc.id,
    })),
)

const genderOptions = [
  { title: 'Male', value: 'male' },
  { title: 'Female', value: 'female' },
  { title: 'Other', value: 'other' },
]

const relationshipOptions = [
  'Father',
  'Mother',
  'Guardian',
  'Brother/Sister',
  'Grandparent',
  'Other',
]

const unitFormRef = ref<VForm>()

const codeRules = [requiredValidator, maxCharsRule(100, 'Code')] as const
const fullNameRules = [requiredValidator, maxCharsRule(255, 'Full name')] as const

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  const total = totalCount.value
  let label = `${total} unit${total === 1 ? '' : 's'}`
  if (filterAttendance.value === 'checked_in')
    label += ' · checked in'
  else if (filterAttendance.value === 'checked_out')
    label += ' · checked out'
  if (totalPages.value > 1)
    label += ` · page ${page.value} of ${totalPages.value}`

  return label
})

const listCaption = computed(() => {
  if (loading.value || totalCount.value === 0)
    return ''

  const from = (page.value - 1) * pageSize.value + 1
  const to = from + units.value.length - 1

  if (totalCount.value <= pageSize.value)
    return `${totalCount.value} unit${totalCount.value === 1 ? '' : 's'}`

  return `${from}–${to} of ${totalCount.value}`
})

const showEmptyCreateCta = computed(() =>
  !searchQuery.value && !filterType.value && !filterActive.value && !filterAttendance.value,
)

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  await loadLocations()
  await loadUnits()
})

async function loadLocations() {
  try {
    locations.value = await listLocations({ is_active: true, page_size: 200 })
  }
  catch (e) {
    console.error('Failed to load locations', e)
  }
}

async function loadUnits(isRefresh = false, resetPage = false) {
  const softRefresh = isRefresh === true

  if (resetPage)
    page.value = 1
  if (softRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const result = await listUnitsWithTotal({
      search: searchQuery.value || undefined,
      unit_type: filterType.value || undefined,
      is_active: filterActive.value === 'active' ? true : filterActive.value === 'inactive' ? false : undefined,
      attendance_status: filterAttendance.value === 'checked_in' || filterAttendance.value === 'checked_out'
        ? filterAttendance.value
        : undefined,
      page: page.value,
      page_size: pageSize.value,
    })

    let items = result.items

    // Frontend-only employment filter (no longer supported by backend query)
    if (filterEmployment.value) {
      items = items.filter(
        p => p.staff_profile?.employment_type === filterEmployment.value,
      )
    }

    units.value = items
    totalCount.value = result.total
  }
  catch (e) {
    console.error('Failed to load units', e)
    loadError.value = formatApiError(e, 'Failed to load units. Please try again.')
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

const debouncedLoadUnits = useDebounceFn(() => loadUnits(true, true), SEARCH_DEBOUNCE_MS)

watch(searchQuery, () => {
  debouncedLoadUnits()
})

watch(filterType, () => {
  if (filterType.value === 'student')
    filterEmployment.value = ''
  loadUnits(true, true)
})

watch(filterActive, () => {
  loadUnits(true, true)
})

watch(filterAttendance, () => {
  loadUnits(true, true)
})

watch(filterEmployment, () => {
  loadUnits(true, true)
})

watch(() => form.staff_profile.pay_type, payType => {
  if (payType === 'hourly') {
    form.staff_profile.monthly_salary = ''
  }
  else if (payType === 'monthly') {
    form.staff_profile.hourly_rate = ''
  }
  else {
    form.staff_profile.hourly_rate = ''
    form.staff_profile.monthly_salary = ''
  }
  if (payType && !form.staff_profile.ot_multiplier)
    form.staff_profile.ot_multiplier = '1.5'
})

watch(() => form.unit_type, type => {
  if (type !== 'staff') {
    form.staff_profile.employment_type = ''
    form.staff_profile.department = ''
    form.staff_profile.position = ''
    form.staff_profile.salary_grade = ''
    form.staff_profile.pay_type = ''
    form.staff_profile.hourly_rate = ''
    form.staff_profile.monthly_salary = ''
    form.staff_profile.ot_multiplier = ''
    form.staff_profile.work_schedule = ''
    form.staff_profile.supervisor_id = ''
    form.staff_profile.employment_notes = ''
  }
  if (type !== 'student') {
    form.student_profile.school_name = ''
    form.student_profile.grade_class = ''
    form.student_profile.student_id = ''
    form.student_profile.academic_notes = ''
    form.student_profile.guardians = {}
    form.guardians = [{ name: '', relationship: '', phone: '' }]
  }
})

watch(() => form.is_active, val => {
  form.status = val ? 'active' : 'inactive'
})

watch(() => form.status, val => {
  form.is_active = val !== 'inactive'
})

function onPageSizeChange() {
  page.value = 1
  loadUnits(true)
}

function resetForm() {
  Object.assign(form, {
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
    registered_location_id: locations.value[0]?.id ?? '',
    scan_location_ids: locations.value[0] ? [locations.value[0].id] : [],
    student_profile: {
      school_name: '',
      grade_class: '',
      student_id: '',
      academic_notes: '',
      guardians: {},
    },
    guardians: [{ name: '', relationship: '', phone: '' }] as { name: string; relationship: string; phone: string }[],
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
  })
}

function openCreate() {
  saveError.value = null
  editingUnit.value = null
  resetForm()
  void loadStudentEnrollments(null)
  dialogOpen.value = true
  nextTick(() => unitFormRef.value?.resetValidation())
}

function openEdit(p: Unit) {
  saveError.value = null
  editingUnit.value = p

  const sp = p.student_profile
  const stp = p.staff_profile

  Object.assign(form, {
    code: p.code,
    full_name: p.full_name,
    english_name: p.english_name ?? '',
    unit_type: p.unit_type,
    is_active: p.is_active,
    status: p.status ?? 'active',
    gender: p.unit_type === 'staff' ? stp?.gender ?? '' : sp?.gender ?? '',
    date_of_birth: p.unit_type === 'staff' ? stp?.date_of_birth ?? '' : sp?.date_of_birth ?? '',
    phone: p.phone ?? '',
    address: p.address ?? '',
    email: p.email ?? '',
    emergency_contact_name: p.emergency_contact_name ?? '',
    emergency_contact_phone: p.emergency_contact_phone ?? '',
    photo_url: p.photo_url ?? '',
    start_date: p.start_date ?? '',
    exit_date: p.exit_date ?? '',
    whatsapp_enabled: p.whatsapp_enabled,
    remarks: p.remarks ?? '',
    registered_location_id: p.registered_location_id,
    scan_location_ids: [...p.scan_location_ids],
    student_profile: {
      school_name: sp?.school_name ?? '',
      grade_class: sp?.grade_class ?? '',
      student_id: sp?.student_id ?? '',
      academic_notes: sp?.academic_notes ?? '',
      guardians: sp?.guardians ?? {},
    },
    guardians: sp?.guardians
      ? Object.values(sp.guardians).map((g: any) => ({
        name: String(g?.name ?? ''),
        relationship: String(g?.relationship ?? ''),
        phone: String(g?.phone ?? ''),
      })).filter(g => g.name)
      : [],
    staff_profile: {
      employee_id: stp?.employee_id ?? '',
      employment_type: stp?.employment_type ?? '',
      department: stp?.department ?? '',
      position: stp?.position ?? '',
      salary_grade: stp?.salary_grade ?? '',
      pay_type: (stp?.pay_type ?? '') as '' | 'hourly' | 'monthly',
      hourly_rate: stp?.hourly_rate != null ? String(stp.hourly_rate) : '',
      monthly_salary: stp?.monthly_salary != null ? String(stp.monthly_salary) : '',
      ot_multiplier: stp?.ot_multiplier != null ? String(stp.ot_multiplier) : '',
      work_schedule: stp?.work_schedule ?? '',
      supervisor_id: stp?.supervisor_id ?? '',
      employment_notes: stp?.employment_notes ?? '',
    },
  })
  void loadStudentEnrollments(p.unit_type === 'student' ? p.id : null)
  dialogOpen.value = true
  nextTick(() => unitFormRef.value?.resetValidation())
}

async function loadStudentEnrollments(unitId: string | null) {
  const requestId = ++unitEnrollmentsRequestId

  unitEnrollmentRows.value = []
  unitEnrollmentsError.value = ''
  if (!unitId) {
    unitEnrollmentsLoading.value = false

    return
  }

  unitEnrollmentsLoading.value = true
  try {
    const [enrollments, skuList] = await Promise.all([
      listAllCourseEnrollments({ unit_id: unitId }),
      listCourseSkus(),
    ])
    if (requestId !== unitEnrollmentsRequestId)
      return
    unitEnrollmentRows.value = buildUnitEnrollmentRows(enrollments, skuList)
  }
  catch (e) {
    console.error('Failed to load student enrollments', e)
    if (requestId === unitEnrollmentsRequestId)
      unitEnrollmentsError.value = formatApiError(e, 'Could not load enrolled classes.')
  }
  finally {
    if (requestId === unitEnrollmentsRequestId)
      unitEnrollmentsLoading.value = false
  }
}

function normalizeString(value: string): string | null {
  const normalized = value.trim()

  return normalized.length > 0 ? normalized : null
}

function normalizeNumber(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed)
    return null
  const num = Number(trimmed)

  return Number.isFinite(num) ? num : null
}

async function handleSave() {
  saveError.value = null

  if (form.unit_type === 'staff' && !form.staff_profile.employment_type) {
    saveError.value = 'Employment type is required for staff'

    return
  }

  if (!form.registered_location_id) {
    saveError.value = 'Registered location is required'

    return
  }

  if (form.scan_location_ids.length === 0) {
    saveError.value = 'Select at least one scan location'

    return
  }

  const validation = await unitFormRef.value?.validate()
  if (validation && !validation.valid)
    return

  saving.value = true
  try {
    const basePayload = {
      code: form.code.trim(),
      full_name: form.full_name.trim(),
      english_name: normalizeString(form.english_name),
      unit_type: form.unit_type,
      status: form.status,
      phone: normalizeString(form.phone),
      address: normalizeString(form.address),
      email: normalizeString(form.email),
      emergency_contact_name: normalizeString(form.emergency_contact_name),
      emergency_contact_phone: normalizeString(form.emergency_contact_phone),
      photo_url: normalizeString(form.photo_url),
      start_date: normalizeString(form.start_date),
      exit_date: normalizeString(form.exit_date),
      whatsapp_enabled: form.whatsapp_enabled,
      remarks: normalizeString(form.remarks),
      registered_location_id: form.registered_location_id,
      scan_location_ids: [...form.scan_location_ids],
    }

    let payload: Record<string, unknown>

    if (form.unit_type === 'student') {
      const guardians: Record<string, unknown> = {}

      form.guardians.forEach((g, idx) => {
        if (g.name.trim()) {
          guardians[`guardian${idx + 1}`] = {
            name: normalizeString(g.name),
            relationship: normalizeString(g.relationship),
            phone: normalizeString(g.phone),
          }
        }
      })
      payload = {
        ...basePayload,
        student_profile: {
          gender: normalizeString(form.gender),
          date_of_birth: normalizeString(form.date_of_birth),
          school_name: normalizeString(form.student_profile.school_name),
          grade_class: normalizeString(form.student_profile.grade_class),
          student_id: normalizeString(form.student_profile.student_id),
          academic_notes: normalizeString(form.student_profile.academic_notes),
          guardians: Object.keys(guardians).length > 0 ? guardians : null,
        },
      }
    }
    else {
      payload = {
        ...basePayload,
        staff_profile: {
          gender: normalizeString(form.gender),
          date_of_birth: normalizeString(form.date_of_birth),
          employee_id: normalizeString(form.staff_profile.employee_id),
          employment_type: normalizeString(form.staff_profile.employment_type),
          department: normalizeString(form.staff_profile.department),
          position: normalizeString(form.staff_profile.position),
          salary_grade: normalizeString(form.staff_profile.salary_grade),
          pay_type: normalizeString(form.staff_profile.pay_type),
          hourly_rate: normalizeNumber(form.staff_profile.hourly_rate),
          monthly_salary: normalizeNumber(form.staff_profile.monthly_salary),
          ot_multiplier: normalizeNumber(form.staff_profile.ot_multiplier),
          work_schedule: normalizeString(form.staff_profile.work_schedule),
          supervisor_id: normalizeString(form.staff_profile.supervisor_id),
          employment_notes: normalizeString(form.staff_profile.employment_notes),
        },
      }
    }

    const finalPayload = { ...payload, is_active: form.is_active }

    if (editingUnit.value) {
      await updateUnit(editingUnit.value.id, finalPayload)

      // Update nested profile via dedicated endpoint (PATCH /units does not handle profiles)
      if (form.unit_type === 'staff') {
        await updateStaffProfile(editingUnit.value.id, {
          gender: normalizeString(form.gender),
          date_of_birth: normalizeString(form.date_of_birth),
          employee_id: normalizeString(form.staff_profile.employee_id),
          employment_type: normalizeString(form.staff_profile.employment_type),
          department: normalizeString(form.staff_profile.department),
          position: normalizeString(form.staff_profile.position),
          salary_grade: normalizeString(form.staff_profile.salary_grade),
          pay_type: normalizeString(form.staff_profile.pay_type),
          hourly_rate: normalizeNumber(form.staff_profile.hourly_rate),
          monthly_salary: normalizeNumber(form.staff_profile.monthly_salary),
          ot_multiplier: normalizeNumber(form.staff_profile.ot_multiplier),
          work_schedule: normalizeString(form.staff_profile.work_schedule),
          supervisor_id: normalizeString(form.staff_profile.supervisor_id),
          employment_notes: normalizeString(form.staff_profile.employment_notes),
        })
      }
      else if (form.unit_type === 'student') {
        const guardians: Record<string, unknown> = {}

        form.guardians.forEach((g, idx) => {
          if (g.name.trim()) {
            guardians[`guardian${idx + 1}`] = {
              name: normalizeString(g.name),
              relationship: normalizeString(g.relationship),
              phone: normalizeString(g.phone),
            }
          }
        })
        await updateStudentProfile(editingUnit.value.id, {
          gender: normalizeString(form.gender),
          date_of_birth: normalizeString(form.date_of_birth),
          school_name: normalizeString(form.student_profile.school_name),
          grade_class: normalizeString(form.student_profile.grade_class),
          student_id: normalizeString(form.student_profile.student_id),
          academic_notes: normalizeString(form.student_profile.academic_notes),
          guardians: Object.keys(guardians).length > 0 ? guardians : null,
        })
      }
    }
    else {
      await createUnit(finalPayload as Parameters<typeof createUnit>[0])
    }

    dialogOpen.value = false
    await loadUnits(true)
    showToast(editingUnit.value ? 'Unit updated successfully.' : 'Unit created successfully.', 'success')
  }
  catch (e: unknown) {
    saveError.value = formatApiError(e, 'Could not save unit')
    showToast(saveError.value, 'error')
  }
  finally {
    saving.value = false
  }
}

function openDeleteConfirm(p: Unit) {
  deleteError.value = ''
  deleteTarget.value = p
  deleteConfirmOpen.value = true
}

function closeDeleteConfirm() {
  deleteConfirmOpen.value = false
  deleteError.value = ''
  deleteTarget.value = null
}

async function confirmDelete() {
  if (!deleteTarget.value)
    return

  deleting.value = true
  deleteError.value = ''
  try {
    await deleteUnit(deleteTarget.value.id)
    closeDeleteConfirm()
    await loadUnits(true)
  }
  catch (e: unknown) {
    deleteError.value = formatApiError(e, 'Could not delete unit')
  }
  finally {
    deleting.value = false
  }
}

function openQR(p: Unit) {
  qrDialogsRef.value?.openQR(p)
}

function openManualCorrection(p: Unit) {
  correctionTarget.value = p
  correctionDialog.value = true
}

function typeColor(type: string) {
  return type === 'staff' ? 'info' : 'success'
}

function typeLabel(type: string) {
  return typeOptions.find(o => o.value === type)?.title ?? type
}

function employmentTypeLabel(value: string | null | undefined) {
  if (value === 'full_time')
    return 'Full-time'
  if (value === 'part_time')
    return 'Part-time'

  return '—'
}

function locationLabel(location: Unit['registered_location']) {
  if (!location)
    return '—'

  return location.name_en || location.name_zh || location.code || '—'
}

function scanLocationsLabel(p: Unit) {
  if (!p.scan_locations?.length)
    return '—'

  return p.scan_locations
    .map(loc => loc.name_en || loc.name_zh || loc.code || '')
    .filter(Boolean)
    .join(', ')
}

function statusColor(status: string) {
  if (status === 'active')
    return 'success'
  if (status === 'suspended')
    return 'warning'

  return 'grey'
}

function statusLabel(status: string) {
  return statusOptions.find(o => o.value === status)?.title ?? status
}

function rowStatusChip(p: Unit) {
  if (!p.is_active) {
    return {
      color: 'grey',
      label: 'Disabled',
      title: `Deactivated for attendance — record status: ${statusLabel(p.status)}`,
    }
  }

  return {
    color: statusColor(p.status),
    label: statusLabel(p.status),
    title: undefined as string | undefined,
  }
}
</script>

<template>
  <VContainer>
    <VRow
      class="mb-2"
      align="center"
    >
      <VCol
        cols="12"
        sm="8"
      >
        <div class="text-h5 font-weight-medium">
          Unit Management
        </div>
        <div class="text-body-2 text-medium-emphasis">
          {{ pageSubtitle }}
        </div>
      </VCol>
      <VCol
        cols="12"
        sm="4"
        class="d-flex flex-wrap justify-sm-end gap-2"
      >
        <VBtn
          variant="outlined"
          color="primary"
          prepend-icon="ri-qr-code-line"
          :to="{ name: 'attendance-qr-codes' }"
        >
          QR Codes
        </VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="refreshing"
          @click="loadUnits(true)"
        >
          Refresh
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          @click="openCreate"
        >
          Add Unit
        </VBtn>
      </VCol>
    </VRow>

    <!-- Attendance filter uses server-side attendance_status — see GET /api/units -->
    <VRow
      class="mb-4"
      align="center"
    >
      <VCol
        cols="12"
        sm="4"
        md="3"
      >
        <VTextField
          v-model="searchQuery"
          placeholder="Search units..."
          prepend-inner-icon="ri-search-line"
          density="compact"
          hide-details
          clearable
        />
      </VCol>
      <VCol
        cols="12"
        sm="4"
        md="3"
      >
        <VSelect
          v-model="filterType"
          :items="[{ title: 'All Types', value: '' }, ...typeOptions]"
          label="Type"
          density="compact"
          hide-details
        />
      </VCol>
      <VCol
        cols="12"
        sm="4"
        md="3"
      >
        <VSelect
          v-model="filterActive"
          :items="activeFilterOptions"
          label="Active status"
          density="compact"
          hide-details
        />
      </VCol>
      <VCol
        cols="12"
        sm="4"
        md="3"
      >
        <VSelect
          v-model="filterAttendance"
          :items="attendanceFilterOptions"
          label="Attendance"
          density="compact"
          hide-details
        />
      </VCol>
      <VCol
        cols="12"
        sm="4"
        md="3"
      >
        <VSelect
          v-model="filterEmployment"
          :items="employmentFilterOptions"
          label="Employment"
          density="compact"
          hide-details
          :disabled="filterType === 'student'"
        />
      </VCol>
    </VRow>

    <VAlert
      v-if="loadError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="loadError = ''"
    >
      {{ loadError }}
      <template #append>
        <VBtn
          variant="text"
          size="small"
          @click="loadUnits(true)"
        >
          Retry
        </VBtn>
      </template>
    </VAlert>

    <VCard :loading="loading">
      <VCardTitle class="d-flex align-center justify-space-between flex-wrap gap-2">
        <span>Units</span>
        <span
          v-if="listCaption"
          class="text-caption text-medium-emphasis"
        >
          {{ listCaption }}
        </span>
      </VCardTitle>
      <div class="units-table-scroll">
        <VTable class="units-table">
          <thead>
            <tr>
              <th width="100">
                Code
              </th>
              <th width="130">
                Full Name
              </th>
              <th width="80">
                Type
              </th>
              <th width="120">
                Registered location
              </th>
              <th width="120">
                Scan locations
              </th>
              <th width="100">
                Employment
              </th>
              <th width="90">
                Status
              </th>
              <th width="180">
                Last check-in / out
              </th>
              <th
                class="col-phone"
                width="110"
              >
                Phone
              </th>
              <th
                class="col-school"
                width="130"
              >
                School / Class
              </th>
              <th class="col-actions">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="p in units"
              :key="p.id"
              :class="{ 'unit-row-inactive': !p.is_active }"
            >
              <td class="font-weight-medium">
                {{ p.code }}
              </td>
              <td>{{ p.full_name }}</td>
              <td>
                <VChip
                  :color="typeColor(p.unit_type)"
                  size="small"
                  label
                >
                  {{ typeLabel(p.unit_type) }}
                </VChip>
              </td>
              <td>{{ locationLabel(p.registered_location) }}</td>
              <td class="col-school">
                {{ scanLocationsLabel(p) }}
              </td>
              <td>
                <span v-if="p.unit_type === 'staff'">{{ employmentTypeLabel(p.staff_profile?.employment_type) }}</span>
                <span
                  v-else
                  class="text-medium-emphasis"
                >—</span>
              </td>
              <td>
                <VChip
                  :color="rowStatusChip(p).color"
                  size="small"
                  label
                  :title="rowStatusChip(p).title"
                >
                  {{ rowStatusChip(p).label }}
                </VChip>
              </td>
              <td>
                <div
                  class="text-caption"
                  :class="p.last_event_at && p.attendance_status === 'checked_in' ? 'text-success' : 'text-medium-emphasis'"
                >
                  {{ formatLastAttendance(p, { compact: true }) }}
                </div>
              </td>
              <td class="col-phone">
                {{ p.phone || '-' }}
              </td>
              <td class="col-school">
                {{ p.student_profile?.school_name ? `${p.student_profile.school_name} / ${p.student_profile.grade_class || '-'}` : '-' }}
              </td>
              <td class="col-actions">
                <div class="d-flex flex-nowrap align-center">
                  <VBtn
                    icon
                    size="small"
                    variant="text"
                    color="primary"
                    :disabled="!p.is_active"
                    :title="p.is_active ? 'QR Code' : 'QR unavailable — unit is inactive'"
                    :aria-label="`View QR code for ${p.full_name}`"
                    @click="openQR(p)"
                  >
                    <VIcon icon="ri-qr-code-line" />
                  </VBtn>
                  <VBtn
                    icon
                    size="small"
                    variant="text"
                    color="info"
                    title="Manual"
                    :aria-label="`Manual correction for ${p.full_name}`"
                    @click="openManualCorrection(p)"
                  >
                    <VIcon icon="ri-edit-box-line" />
                  </VBtn>
                  <VBtn
                    icon
                    size="small"
                    variant="text"
                    title="Edit"
                    :aria-label="`Edit ${p.full_name}`"
                    @click="openEdit(p)"
                  >
                    <VIcon icon="ri-edit-line" />
                  </VBtn>
                  <VBtn
                    icon
                    size="small"
                    variant="text"
                    color="error"
                    title="Delete"
                    :aria-label="`Delete ${p.full_name}`"
                    @click="openDeleteConfirm(p)"
                  >
                    <VIcon icon="ri-delete-bin-line" />
                  </VBtn>
                </div>
              </td>
            </tr>
            <tr v-if="units.length === 0 && !loading">
              <td
                colspan="8"
                class="text-center text-medium-emphasis py-6"
              >
                <div class="mb-3">
                  {{ searchQuery || filterType || filterActive || filterAttendance ? 'No units match your search or filters' : 'No units yet' }}
                </div>
                <VBtn
                  v-if="showEmptyCreateCta"
                  color="primary"
                  prepend-icon="ri-add-line"
                  @click="openCreate"
                >
                  Add Unit
                </VBtn>
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <div
        v-if="!loading && units.length > 0"
        class="d-flex flex-wrap align-center justify-space-between gap-2 pa-4 pt-0"
      >
        <div class="d-flex align-center gap-2">
          <span class="text-caption text-medium-emphasis">
            Page {{ page }} of {{ totalPages }}
          </span>
          <VSelect
            v-model="pageSize"
            :items="pageSizeOptions"
            density="compact"
            variant="plain"
            hide-details
            style="max-width: 70px;"
            @update:model-value="onPageSizeChange"
          />
          <span class="text-caption text-medium-emphasis">per page</span>
        </div>
        <VPagination
          v-model="page"
          :length="totalPages"
          :total-visible="5"
          density="compact"
          size="small"
          @update:model-value="loadUnits(true)"
        />
      </div>
      <div class="text-caption text-medium-emphasis px-4 pb-3 d-md-none">
        Swipe sideways to see more columns. Phone and school are hidden on small screens.
      </div>
    </VCard>

    <AttendanceFormDialog
      v-model="dialogOpen"
      :title="editingUnit ? 'Edit Unit' : 'Create Unit'"
      icon="ri-group-line"
      :max-width="900"
      :saving="saving"
      :error="saveError"
      @save="handleSave"
      @cancel="dialogOpen = false"
      @clear-error="saveError = null"
    >
      <VForm
        ref="unitFormRef"
        @submit.prevent="handleSave"
      >
        <h4 class="text-subtitle-2 text-medium-emphasis mb-2">
          Basic info
        </h4>
        <VRow class="dense-form-row">
          <VCol
            cols="12"
            sm="6"
            md="4"
          >
            <VTextField
              v-model="form.code"
              label="Code *"
              :disabled="!!editingUnit"
              maxlength="100"
              :rules="codeRules"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
            md="4"
          >
            <VSelect
              v-model="form.unit_type"
              :items="typeOptions"
              item-title="title"
              item-value="value"
              label="Type *"
              :disabled="!!editingUnit"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
            md="4"
          >
            <VSelect
              v-model="form.status"
              :items="statusOptions"
              item-title="title"
              item-value="value"
              label="Status"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="form.full_name"
              label="Full name *"
              maxlength="255"
              :rules="fullNameRules"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="form.english_name"
              label="English name"
              maxlength="255"
              :rules="[maxCharsRule(255, 'English name')]"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="form.email"
              label="Email"
              maxlength="255"
              :rules="[maxCharsRule(255, 'Email')]"
            />
          </VCol>
        </VRow>

        <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
          Locations
        </h4>
        <VRow class="dense-form-row">
          <VCol
            cols="12"
            sm="6"
          >
            <VSelect
              v-model="form.registered_location_id"
              :items="locationOptions"
              item-title="title"
              item-value="value"
              label="Registered location *"
              :rules="[v => !!v || 'Required']"
              :disabled="locationOptions.length === 0"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VSelect
              v-model="form.scan_location_ids"
              :items="locationOptions"
              item-title="title"
              item-value="value"
              label="Scan locations *"
              hint="Check-in and check-out at these locations"
              multiple
              chips
              closable-chips
              :rules="[v => Array.isArray(v) && v.length > 0 || 'Select at least one']"
              :disabled="locationOptions.length === 0"
            />
          </VCol>
        </VRow>
        <p
          v-if="locationOptions.length === 0"
          class="text-caption text-warning mb-0"
        >
          No active locations found. Create locations first.
        </p>

        <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
          Contact & personal
        </h4>
        <VRow class="dense-form-row">
          <VCol
            cols="12"
            sm="6"
            md="4"
          >
            <VSelect
              v-model="form.gender"
              :items="genderOptions"
              item-title="title"
              item-value="value"
              label="Gender"
              clearable
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
            md="4"
          >
            <VTextField
              v-model="form.date_of_birth"
              label="Date of birth"
              type="date"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
            md="4"
          >
            <VTextField
              v-model="form.phone"
              label="Phone"
              maxlength="50"
              :rules="[maxCharsRule(50, 'Phone')]"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
            md="4"
            class="d-flex align-center"
          >
            <VSwitch
              v-model="form.whatsapp_enabled"
              label="WhatsApp enabled"
            />
          </VCol>
          <VCol cols="12">
            <VTextField
              v-model="form.address"
              label="Address"
              maxlength="500"
              :rules="[maxCharsRule(500, 'Address')]"
            />
          </VCol>
        </VRow>

        <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
          Additional info
        </h4>
        <VRow class="dense-form-row">
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="form.photo_url"
              label="Photo URL"
              maxlength="500"
              :rules="[maxCharsRule(500, 'Photo URL')]"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
            md="3"
          >
            <VTextField
              v-model="form.start_date"
              label="Start date"
              type="date"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
            md="3"
          >
            <VTextField
              v-model="form.exit_date"
              label="Exit date"
              type="date"
            />
          </VCol>
        </VRow>

        <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
          Emergency contact
        </h4>
        <VRow class="dense-form-row">
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="form.emergency_contact_name"
              label="Emergency contact name"
              maxlength="255"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="form.emergency_contact_phone"
              label="Emergency contact phone"
              maxlength="50"
            />
          </VCol>
        </VRow>

        <template v-if="form.unit_type === 'student'">
          <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
            School & guardian
          </h4>
          <VRow class="dense-form-row">
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="form.student_profile.school_name"
                label="School name"
                maxlength="255"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="form.student_profile.grade_class"
                label="Grade / class"
                maxlength="100"
              />
            </VCol>
            <template
              v-for="(g, idx) in form.guardians"
              :key="idx"
            >
              <VCol cols="12">
                <div class="d-flex align-center">
                  <span class="text-caption text-medium-emphasis me-2">Guardian {{ idx + 1 }}</span>
                  <VBtn
                    icon
                    size="x-small"
                    variant="text"
                    color="error"
                    :disabled="form.guardians.length <= 1"
                    @click="form.guardians.splice(idx, 1)"
                  >
                    <VIcon>ri-delete-bin-line</VIcon>
                  </VBtn>
                </div>
              </VCol>
              <VCol
                cols="12"
                sm="6"
                md="4"
              >
                <VTextField
                  v-model="g.name"
                  label="Name"
                  maxlength="255"
                />
              </VCol>
              <VCol
                cols="12"
                sm="6"
                md="4"
              >
                <VSelect
                  v-model="g.relationship"
                  :items="relationshipOptions"
                  label="Relationship"
                  clearable
                />
              </VCol>
              <VCol
                cols="12"
                sm="6"
                md="4"
              >
                <VTextField
                  v-model="g.phone"
                  label="Phone"
                  maxlength="50"
                />
              </VCol>
            </template>
            <VCol cols="12">
              <VBtn
                size="small"
                variant="text"
                prepend-icon="ri-add-line"
                @click="form.guardians.push({ name: '', relationship: '', phone: '' })"
              >
                Add guardian
              </VBtn>
            </VCol>
          </VRow>
        </template>

        <template v-if="form.unit_type === 'student'">
          <h4 class="text-subtitle-2 text-medium-emphasis mb-1 mt-4">
            Enrolled classes
          </h4>
          <p class="text-caption text-medium-emphasis mb-2">
            Read-only. Enroll, change dates, or cancel on Courses.
          </p>
          <div
            v-if="!editingUnit"
            class="text-body-2 text-medium-emphasis"
          >
            Save this student first, then enroll from Courses.
          </div>
          <div
            v-else-if="unitEnrollmentsLoading"
            class="text-body-2 text-medium-emphasis"
          >
            Loading classes…
          </div>
          <p
            v-else-if="unitEnrollmentsError"
            class="text-caption text-error mb-0"
          >
            {{ unitEnrollmentsError }}
          </p>
          <div
            v-else-if="unitEnrollmentRows.length === 0"
            class="d-flex align-center flex-wrap ga-2"
          >
            <span class="text-body-2 text-medium-emphasis">Not enrolled in any class.</span>
            <VBtn
              type="button"
              size="small"
              variant="text"
              color="primary"
              :to="{ name: 'attendance-courses' }"
            >
              Open Courses
            </VBtn>
          </div>
          <div
            v-else
            class="unit-enrollment-list"
          >
            <div
              v-for="row in unitEnrollmentRows"
              :key="row.enrollment.id"
              class="unit-enrollment-row"
            >
              <div class="unit-enrollment-copy">
                <div class="d-flex align-center flex-wrap ga-2">
                  <span class="font-weight-medium">{{ row.sku?.name_zh ?? 'Unknown class' }}</span>
                  <VChip
                    size="x-small"
                    :color="enrollmentStatusColor[row.enrollment.status] ?? 'grey'"
                  >
                    {{ row.enrollment.status }}
                  </VChip>
                </div>
                <div class="text-caption text-medium-emphasis">
                  {{ row.sku ? `${row.sku.code} · ${billingUnitShortLabel(row.sku.billing_unit)}` : row.enrollment.sku_id }}
                  · {{ formatEnrollmentRange(row.enrollment.start_date, row.enrollment.end_date) }}
                </div>
              </div>
              <VBtn
                v-if="row.sku"
                type="button"
                size="small"
                variant="text"
                color="primary"
                append-icon="ri-arrow-right-s-line"
                :to="{ name: 'attendance-courses', query: { sku: row.sku.id } }"
              >
                Roster
              </VBtn>
            </div>
          </div>
        </template>

        <template v-if="form.unit_type === 'staff'">
          <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
            Staff profile
          </h4>
          <VRow class="dense-form-row">
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VSelect
                v-model="form.staff_profile.employment_type"
                :items="employmentTypeOptions"
                item-title="title"
                item-value="value"
                label="Employment type *"
                :rules="[v => !!v || 'Required for staff']"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="form.staff_profile.employee_id"
                label="Employee ID"
                maxlength="100"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="form.staff_profile.department"
                label="Department"
                maxlength="100"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="form.staff_profile.position"
                label="Position"
                maxlength="100"
              />
            </VCol>
          </VRow>

          <h5 class="text-caption text-medium-emphasis mb-2 mt-4">
            Compensation
          </h5>
          <VRow class="dense-form-row">
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VSelect
                v-model="form.staff_profile.pay_type"
                :items="payTypeOptions"
                item-title="title"
                item-value="value"
                label="Pay type *"
                clearable
                :rules="[v => !!v || 'Required for staff']"
              />
            </VCol>
            <VCol
              v-if="form.staff_profile.pay_type === 'hourly'"
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="form.staff_profile.hourly_rate"
                label="Hourly rate"
                type="number"
                min="0"
                step="0.01"
              />
            </VCol>
            <VCol
              v-if="form.staff_profile.pay_type === 'monthly'"
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="form.staff_profile.monthly_salary"
                label="Monthly salary"
                type="number"
                min="0"
                step="0.01"
              />
            </VCol>
            <VCol
              v-if="form.staff_profile.pay_type"
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="form.staff_profile.ot_multiplier"
                label="OT multiplier"
                type="number"
                min="0"
                step="0.01"
                hint="Defaults to 1.5x when left blank"
                persistent-hint
              />
            </VCol>
          </VRow>
        </template>

        <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
          Notes
        </h4>
        <VTextarea
          v-model="form.remarks"
          label="Remarks"
          rows="2"
          auto-grow
          class="mb-2"
        />

        <VSwitch
          v-model="form.is_active"
          label="Active (can scan QR and appear in attendance)"
          class="mt-1"
        />
      </VForm>
    </AttendanceFormDialog>

    <AttendanceConfirmDialog
      v-model="deleteConfirmOpen"
      :title="`Delete ${deleteTarget?.full_name}?`"
      :loading="deleting"
      :error="deleteError"
      @confirm="confirmDelete"
      @cancel="closeDeleteConfirm"
      @clear-error="deleteError = ''"
    >
      This will permanently remove
      <strong>{{ deleteTarget?.full_name }}</strong> ({{ deleteTarget?.code }}).
      This action cannot be undone.
    </AttendanceConfirmDialog>

    <AppToastStack />

    <UnitQrDialogs
      ref="qrDialogsRef"
      @rotated="loadUnits(true)"
    />

    <ManualCorrectionDialog
      v-model="correctionDialog"
      :unit="correctionTarget"
      @saved="loadUnits(true)"
    />
  </VContainer>
</template>

<style scoped lang="scss">
.dense-form-row :deep(.v-col) {
  padding-block: 4px !important;
}

.unit-row-inactive {
  opacity: 0.55;
}

.unit-enrollment-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.unit-enrollment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
}

.unit-enrollment-copy {
  min-width: 0;
}

.units-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.units-table :deep(thead th),
.units-table :deep(tbody td) {
  vertical-align: middle;
  white-space: nowrap;
}

.units-table :deep(.col-actions) {
  position: sticky;
  right: 0;
  background: rgb(var(--v-theme-surface));
  white-space: nowrap;
  width: 1%;
  z-index: 2;
  border-left: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.units-table :deep(thead th.col-actions) {
  z-index: 3;
}

@media (max-width: 960px) {
  .units-table :deep(.col-phone),
  .units-table :deep(.col-school) {
    display: none;
  }
}
</style>
