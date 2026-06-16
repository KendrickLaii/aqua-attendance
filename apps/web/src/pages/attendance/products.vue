<script setup lang="ts">
import type { VForm } from 'vuetify/components/VForm'
import {
  maxCharsRule,
  requiredValidator,
} from '@core/utils/validators'
import { createProduct, deleteProduct, listProductsWithTotal, updateProduct } from '@/api/attendance/products'
import type { Product } from '@/api/attendance/products'
import { listLocations } from '@/api/attendance/locations'
import type { LocationItem } from '@/api/attendance/locations'
import ProductQrDialogs from '@/components/attendance/ProductQrDialogs.vue'
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { formatLastAttendance } from '@/utils/attendanceDisplay'
import { formatApiError } from '@/utils/formatApiDetail'

definePage({ meta: {} })

const PRODUCT_PAGE_SIZE = 50
const SEARCH_DEBOUNCE_MS = 300

const authStore = useAttendanceAuthStore()
const router = useRouter()

const products = ref<Product[]>([])
const locations = ref<LocationItem[]>([])
const totalCount = ref(0)
const page = ref(1)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')
const dialogOpen = ref(false)
const editingProduct = ref<Product | null>(null)

const form = reactive({
  code: '',
  full_name: '',
  english_name: '',
  product_type: 'student' as 'student' | 'staff',
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
  enrollment_date: '',
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
    enrollment_date: '',
    graduation_date: '',
    academic_notes: '',
    guardians: {} as Record<string, unknown>,
  },
  staff_profile: {
    employee_id: '',
    employment_type: '' as '' | 'part_time' | 'full_time',
    department: '',
    position: '',
    hire_date: '',
    termination_date: '',
    salary_grade: '',
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
const qrDialogsRef = ref<InstanceType<typeof ProductQrDialogs> | null>(null)

const deleteConfirmOpen = ref(false)
const deleteTarget = ref<Product | null>(null)
const deleting = ref(false)
const deleteError = ref('')

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

const productFormRef = ref<VForm>()

const codeRules = [requiredValidator, maxCharsRule(100, 'Code')] as const
const fullNameRules = [requiredValidator, maxCharsRule(255, 'Full name')] as const

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / PRODUCT_PAGE_SIZE)))
const hasNextPage = computed(() => page.value < totalPages.value)
const hasPrevPage = computed(() => page.value > 1)

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  const total = totalCount.value
  let label = `${total} product${total === 1 ? '' : 's'}`
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

  const from = (page.value - 1) * PRODUCT_PAGE_SIZE + 1
  const to = from + products.value.length - 1

  if (totalCount.value <= PRODUCT_PAGE_SIZE)
    return `${totalCount.value} product${totalCount.value === 1 ? '' : 's'}`

  return `${from}–${to} of ${totalCount.value}`
})

const showEmptyCreateCta = computed(() =>
  !searchQuery.value && !filterType.value && !filterActive.value && !filterAttendance.value,
)

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) {
    router.replace({ name: 'attendance-login' })

    return
  }
  if (!authStore.isAdmin) {
    router.replace({ name: 'attendance-dashboard' })

    return
  }
  await loadLocations()
  await loadProducts()
})

async function loadLocations() {
  try {
    locations.value = await listLocations({ is_active: true, page_size: 200 })
  }
  catch (e) {
    console.error('Failed to load locations', e)
  }
}

async function loadProducts(isRefresh = false, resetPage = false) {
  const softRefresh = isRefresh === true

  if (resetPage)
    page.value = 1
  if (softRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const result = await listProductsWithTotal({
      search: searchQuery.value || undefined,
      product_type: filterType.value || undefined,
      is_active: filterActive.value === 'active' ? true : filterActive.value === 'inactive' ? false : undefined,
      attendance_status: filterAttendance.value === 'checked_in' || filterAttendance.value === 'checked_out'
        ? filterAttendance.value
        : undefined,
      page: page.value,
      page_size: PRODUCT_PAGE_SIZE,
    })

    let items = result.items
    // Frontend-only employment filter (no longer supported by backend query)
    if (filterEmployment.value) {
      items = items.filter(
        p => p.staff_profile?.employment_type === filterEmployment.value,
      )
    }

    products.value = items
    totalCount.value = result.total
  }
  catch (e) {
    console.error('Failed to load products', e)
    loadError.value = formatApiError(e, 'Failed to load products. Please try again.')
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

const debouncedLoadProducts = useDebounceFn(() => loadProducts(true, true), SEARCH_DEBOUNCE_MS)

watch(searchQuery, () => {
  debouncedLoadProducts()
})

watch(filterType, () => {
  if (filterType.value === 'student')
    filterEmployment.value = ''
  loadProducts(true, true)
})

watch(filterActive, () => {
  loadProducts(true, true)
})

watch(filterAttendance, () => {
  loadProducts(true, true)
})

watch(filterEmployment, () => {
  loadProducts(true, true)
})

watch(() => form.product_type, type => {
  if (type !== 'staff') {
    form.staff_profile.employment_type = ''
    form.staff_profile.department = ''
    form.staff_profile.position = ''
    form.staff_profile.hire_date = ''
    form.staff_profile.termination_date = ''
    form.staff_profile.salary_grade = ''
    form.staff_profile.work_schedule = ''
    form.staff_profile.supervisor_id = ''
    form.staff_profile.employment_notes = ''
  }
  if (type !== 'student') {
    form.student_profile.school_name = ''
    form.student_profile.grade_class = ''
    form.student_profile.student_id = ''
    form.student_profile.enrollment_date = ''
    form.student_profile.graduation_date = ''
    form.student_profile.academic_notes = ''
    form.student_profile.guardians = {}
    form.guardians = [{ name: '', relationship: '', phone: '' }]
  }
})

function goToPrevPage() {
  if (page.value <= 1)
    return
  page.value -= 1
  loadProducts(true)
}

function goToNextPage() {
  if (!hasNextPage.value)
    return
  page.value += 1
  loadProducts(true)
}

function resetForm() {
  Object.assign(form, {
    code: '',
    full_name: '',
    english_name: '',
    product_type: 'student',
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
    enrollment_date: '',
    exit_date: '',
    whatsapp_enabled: true,
    remarks: '',
    registered_location_id: locations.value[0]?.id ?? '',
    scan_location_ids: locations.value[0] ? [locations.value[0].id] : [],
    student_profile: {
      school_name: '',
      grade_class: '',
      student_id: '',
      enrollment_date: '',
      graduation_date: '',
      academic_notes: '',
      guardians: {},
    },
    guardians: [{ name: '', relationship: '', phone: '' }] as { name: string; relationship: string; phone: string }[],
    staff_profile: {
      employee_id: '',
      employment_type: '',
      department: '',
      position: '',
      hire_date: '',
      termination_date: '',
      salary_grade: '',
      work_schedule: '',
      supervisor_id: '',
      employment_notes: '',
    },
  })
}

function openCreate() {
  saveError.value = null
  editingProduct.value = null
  resetForm()
  dialogOpen.value = true
  nextTick(() => productFormRef.value?.resetValidation())
}

function openEdit(p: Product) {
  saveError.value = null
  editingProduct.value = p
  const sp = p.student_profile
  const stp = p.staff_profile
  Object.assign(form, {
    code: p.code,
    full_name: p.full_name,
    english_name: p.english_name ?? '',
    product_type: p.product_type,
    is_active: p.is_active,
    status: p.status ?? 'active',
    gender: p.gender ?? '',
    date_of_birth: p.date_of_birth ?? '',
    phone: p.phone ?? '',
    address: p.address ?? '',
    email: p.email ?? '',
    emergency_contact_name: p.emergency_contact_name ?? '',
    emergency_contact_phone: p.emergency_contact_phone ?? '',
    photo_url: p.photo_url ?? '',
    enrollment_date: p.enrollment_date ?? '',
    exit_date: p.exit_date ?? '',
    whatsapp_enabled: p.whatsapp_enabled,
    remarks: p.remarks ?? '',
    registered_location_id: p.registered_location_id,
    scan_location_ids: [...p.scan_location_ids],
    student_profile: {
      school_name: sp?.school_name ?? '',
      grade_class: sp?.grade_class ?? '',
      student_id: sp?.student_id ?? '',
      enrollment_date: sp?.enrollment_date ?? '',
      graduation_date: sp?.graduation_date ?? '',
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
      hire_date: stp?.hire_date ?? '',
      termination_date: stp?.termination_date ?? '',
      salary_grade: stp?.salary_grade ?? '',
      work_schedule: stp?.work_schedule ?? '',
      supervisor_id: stp?.supervisor_id ?? '',
      employment_notes: stp?.employment_notes ?? '',
    },
  })
  dialogOpen.value = true
  nextTick(() => productFormRef.value?.resetValidation())
}

function normalizeString(value: string): string | null {
  const normalized = value.trim()

  return normalized.length > 0 ? normalized : null
}

async function handleSave() {
  saveError.value = null

  if (form.product_type === 'staff' && !form.staff_profile.employment_type) {
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

  const validation = await productFormRef.value?.validate()
  if (validation && !validation.valid)
    return

  saving.value = true
  try {
    const basePayload = {
      code: form.code.trim(),
      full_name: form.full_name.trim(),
      english_name: normalizeString(form.english_name),
      product_type: form.product_type,
      status: form.status,
      gender: normalizeString(form.gender),
      date_of_birth: normalizeString(form.date_of_birth),
      phone: normalizeString(form.phone),
      address: normalizeString(form.address),
      email: normalizeString(form.email),
      emergency_contact_name: normalizeString(form.emergency_contact_name),
      emergency_contact_phone: normalizeString(form.emergency_contact_phone),
      photo_url: normalizeString(form.photo_url),
      enrollment_date: normalizeString(form.enrollment_date),
      exit_date: normalizeString(form.exit_date),
      whatsapp_enabled: form.whatsapp_enabled,
      remarks: normalizeString(form.remarks),
      registered_location_id: form.registered_location_id,
      scan_location_ids: [...form.scan_location_ids],
    }

    let payload: Record<string, unknown>

    if (form.product_type === 'student') {
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
          school_name: normalizeString(form.student_profile.school_name),
          grade_class: normalizeString(form.student_profile.grade_class),
          student_id: normalizeString(form.student_profile.student_id),
          enrollment_date: normalizeString(form.student_profile.enrollment_date),
          graduation_date: normalizeString(form.student_profile.graduation_date),
          academic_notes: normalizeString(form.student_profile.academic_notes),
          guardians: Object.keys(guardians).length > 0 ? guardians : null,
        },
      }
    }
    else {
      payload = {
        ...basePayload,
        staff_profile: {
          employee_id: normalizeString(form.staff_profile.employee_id),
          employment_type: normalizeString(form.staff_profile.employment_type),
          department: normalizeString(form.staff_profile.department),
          position: normalizeString(form.staff_profile.position),
          hire_date: normalizeString(form.staff_profile.hire_date),
          termination_date: normalizeString(form.staff_profile.termination_date),
          salary_grade: normalizeString(form.staff_profile.salary_grade),
          work_schedule: normalizeString(form.staff_profile.work_schedule),
          supervisor_id: normalizeString(form.staff_profile.supervisor_id),
          employment_notes: normalizeString(form.staff_profile.employment_notes),
        },
      }
    }

    if (editingProduct.value)
      await updateProduct(editingProduct.value.id, { ...payload, is_active: form.is_active })

    else
      await createProduct(payload as Parameters<typeof createProduct>[0])

    dialogOpen.value = false
    await loadProducts(true)
  }
  catch (e: unknown) {
    saveError.value = formatApiError(e, 'Could not save product')
  }
  finally {
    saving.value = false
  }
}

function openDeleteConfirm(p: Product) {
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
    await deleteProduct(deleteTarget.value.id)
    closeDeleteConfirm()
    await loadProducts(true)
  }
  catch (e: unknown) {
    deleteError.value = formatApiError(e, 'Could not delete product')
  }
  finally {
    deleting.value = false
  }
}

function openQR(p: Product) {
  qrDialogsRef.value?.openQR(p)
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

function locationLabel(location: Product['registered_location']) {
  if (!location)
    return '—'

  return location.name_en || location.name_zh || location.code || '—'
}

function scanLocationsLabel(p: Product) {
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

function rowStatusChip(p: Product) {
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
          Product Management
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
          @click="loadProducts(true)"
        >
          Refresh
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          @click="openCreate"
        >
          Add Product
        </VBtn>
      </VCol>
    </VRow>

    <!-- Attendance filter uses server-side attendance_status — see GET /api/products -->
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
          placeholder="Search products..."
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
          @click="loadProducts(true)"
        >
          Retry
        </VBtn>
      </template>
    </VAlert>

    <VCard :loading="loading">
      <VCardTitle class="d-flex align-center justify-space-between flex-wrap gap-2">
        <span>Products</span>
        <span
          v-if="listCaption"
          class="text-caption text-medium-emphasis"
        >
          {{ listCaption }}
        </span>
      </VCardTitle>
      <div class="products-table-scroll">
        <VTable class="products-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Full Name</th>
              <th>Type</th>
              <th>Registered location</th>
              <th>Scan locations</th>
              <th>Employment</th>
              <th>Status</th>
              <th>Last check-in / out</th>
              <th class="col-phone">
                Phone
              </th>
              <th class="col-school">
                School / Class
              </th>
              <th class="col-actions">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="p in products"
              :key="p.id"
              :class="{ 'product-row-inactive': !p.is_active }"
            >
              <td class="font-weight-medium">
                {{ p.code }}
              </td>
              <td>{{ p.full_name }}</td>
              <td>
                <VChip
                  :color="typeColor(p.product_type)"
                  size="small"
                  label
                >
                  {{ typeLabel(p.product_type) }}
                </VChip>
              </td>
              <td>{{ locationLabel(p.registered_location) }}</td>
              <td class="col-school">
                {{ scanLocationsLabel(p) }}
              </td>
              <td>
                <span v-if="p.product_type === 'staff'">{{ employmentTypeLabel(p.staff_profile?.employment_type) }}</span>
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
              <td style="min-width: 220px">
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
                    :title="p.is_active ? 'QR Code' : 'QR unavailable — product is inactive'"
                    :aria-label="`View QR code for ${p.full_name}`"
                    @click="openQR(p)"
                  >
                    <VIcon icon="ri-qr-code-line" />
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
            <tr v-if="products.length === 0 && !loading">
              <td
                colspan="8"
                class="text-center text-medium-emphasis py-6"
              >
                <div class="mb-3">
                  {{ searchQuery || filterType || filterActive || filterAttendance ? 'No products match your search or filters' : 'No products yet' }}
                </div>
                <VBtn
                  v-if="showEmptyCreateCta"
                  color="primary"
                  prepend-icon="ri-add-line"
                  @click="openCreate"
                >
                  Add Product
                </VBtn>
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <div
        v-if="!loading && products.length > 0 && totalPages > 1"
        class="d-flex flex-wrap align-center justify-space-between gap-2 pa-4 pt-0"
      >
        <span class="text-caption text-medium-emphasis">
          Page {{ page }} of {{ totalPages }}
        </span>
        <div class="d-flex gap-2">
          <VBtn
            variant="tonal"
            size="small"
            :disabled="!hasPrevPage || refreshing"
            @click="goToPrevPage"
          >
            Previous
          </VBtn>
          <VBtn
            variant="tonal"
            size="small"
            :disabled="!hasNextPage || refreshing"
            @click="goToNextPage"
          >
            Next
          </VBtn>
        </div>
      </div>
      <div class="text-caption text-medium-emphasis px-4 pb-3 d-md-none">
        Swipe sideways to see more columns. Phone and school are hidden on small screens.
      </div>
    </VCard>

    <AttendanceFormDialog
      v-model="dialogOpen"
      :title="editingProduct ? 'Edit Product' : 'Create Product'"
      icon="ri-group-line"
      :max-width="900"
      :saving="saving"
      :error="saveError"
      @save="handleSave"
      @cancel="dialogOpen = false"
      @clear-error="saveError = null"
    >
      <VForm
        ref="productFormRef"
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
              :disabled="!!editingProduct"
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
              v-model="form.product_type"
              :items="typeOptions"
              item-title="title"
              item-value="value"
              label="Type *"
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
            v-if="form.product_type === 'staff'"
            cols="12"
            sm="6"
            md="4"
          >
            <VSelect
              v-model="form.staff_profile.employment_type"
              :items="employmentTypeOptions"
              item-title="title"
              item-value="value"
              label="Employment *"
              :rules="[v => !!v || 'Required for staff']"
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
              v-model="form.enrollment_date"
              label="Enrollment date"
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

        <template v-if="form.product_type === 'student'">
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
                    <VIcon>tabler-trash</VIcon>
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
                prepend-icon="tabler-plus"
                @click="form.guardians.push({ name: '', relationship: '', phone: '' })"
              >
                Add guardian
              </VBtn>
            </VCol>
          </VRow>
        </template>

        <template v-if="form.product_type === 'staff'">
          <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
            Staff profile
          </h4>
          <VRow class="dense-form-row">
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
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="form.staff_profile.hire_date"
                label="Hire date"
                type="date"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="form.staff_profile.termination_date"
                label="Termination date"
                type="date"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="form.staff_profile.salary_grade"
                label="Salary grade"
                maxlength="50"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="form.staff_profile.work_schedule"
                label="Work schedule"
                maxlength="100"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="form.staff_profile.supervisor_id"
                label="Supervisor ID"
                maxlength="36"
              />
            </VCol>
            <VCol cols="12">
              <VTextarea
                v-model="form.staff_profile.employment_notes"
                label="Employment notes"
                rows="2"
                auto-grow
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
          v-if="editingProduct"
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

    <ProductQrDialogs
      ref="qrDialogsRef"
      @rotated="loadProducts(true)"
    />
  </VContainer>
</template>

<style scoped lang="scss">
.dense-form-row :deep(.v-col) {
  padding-block: 4px !important;
}

.product-row-inactive {
  opacity: 0.55;
}

.products-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.products-table :deep(.col-actions) {
  width: 1%;
  white-space: nowrap;
  vertical-align: middle;
}

@media (max-width: 960px) {
  .products-table :deep(.col-phone),
  .products-table :deep(.col-school) {
    display: none;
  }
}
</style>
