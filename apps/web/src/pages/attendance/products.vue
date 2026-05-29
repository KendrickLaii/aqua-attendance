<script setup lang="ts">
import type { VForm } from 'vuetify/components/VForm'
import {
  maxCharsRule,
  requiredValidator,
} from '@core/utils/validators'
import { createProduct, deleteProduct, listProductsWithTotal, updateProduct } from '@/api/attendance/products'
import type { Product } from '@/api/attendance/products'
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
  product_type: 'student' as string,
  is_active: true,
  status: 'active',
  gender: '',
  date_of_birth: '',
  phone: '',
  address: '',
  email: '',
  emergency_contact_name: '',
  emergency_contact_phone: '',
  school_name: '',
  grade_class: '',
  guardian1_name: '',
  guardian1_relationship: '',
  guardian1_phone: '',
  guardian2_name: '',
  guardian2_relationship: '',
  guardian2_phone: '',
  whatsapp_enabled: true,
  remarks: '',
})

const saving = ref(false)
const saveError = ref<string | null>(null)
const searchQuery = ref('')
const filterType = ref('')
const filterActive = ref('')
const filterAttendance = ref('')
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
  await loadProducts()
})

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

    products.value = result.items
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
  loadProducts(true, true)
})

watch(filterActive, () => {
  loadProducts(true, true)
})

watch(filterAttendance, () => {
  loadProducts(true, true)
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

function openCreate() {
  saveError.value = null
  editingProduct.value = null
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
    school_name: '',
    grade_class: '',
    guardian1_name: '',
    guardian1_relationship: '',
    guardian1_phone: '',
    guardian2_name: '',
    guardian2_relationship: '',
    guardian2_phone: '',
    whatsapp_enabled: true,
    remarks: '',
  })
  dialogOpen.value = true
  nextTick(() => productFormRef.value?.resetValidation())
}

function openEdit(p: Product) {
  saveError.value = null
  editingProduct.value = p
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
    school_name: p.school_name ?? '',
    grade_class: p.grade_class ?? '',
    guardian1_name: p.guardian1_name ?? '',
    guardian1_relationship: p.guardian1_relationship ?? '',
    guardian1_phone: p.guardian1_phone ?? '',
    guardian2_name: p.guardian2_name ?? '',
    guardian2_relationship: p.guardian2_relationship ?? '',
    guardian2_phone: p.guardian2_phone ?? '',
    whatsapp_enabled: p.whatsapp_enabled,
    remarks: p.remarks ?? '',
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

  const validation = await productFormRef.value?.validate()
  if (validation && !validation.valid)
    return

  saving.value = true
  try {
    const payload = {
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
      school_name: normalizeString(form.school_name),
      grade_class: normalizeString(form.grade_class),
      guardian1_name: normalizeString(form.guardian1_name),
      guardian1_relationship: normalizeString(form.guardian1_relationship),
      guardian1_phone: normalizeString(form.guardian1_phone),
      guardian2_name: normalizeString(form.guardian2_name),
      guardian2_relationship: normalizeString(form.guardian2_relationship),
      guardian2_phone: normalizeString(form.guardian2_phone),
      whatsapp_enabled: form.whatsapp_enabled,
      remarks: normalizeString(form.remarks),
    }

    if (editingProduct.value)
      await updateProduct(editingProduct.value.id, { ...payload, is_active: form.is_active })

    else
      await createProduct(payload)

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
              <th>Status</th>
              <th>Last check-in / out</th>
              <th class="col-phone">
                Phone
              </th>
              <th class="col-school">
                School / Class
              </th>
              <th>Actions</th>
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
                {{ p.school_name ? `${p.school_name} / ${p.grade_class || '-'}` : '-' }}
              </td>
              <td>
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

    <!-- Create/Edit Dialog -->
    <VDialog
      v-model="dialogOpen"
      max-width="900"
      scrollable
    >
      <VCard>
        <VCardTitle class="text-h6 py-4">
          {{ editingProduct ? 'Edit Product' : 'Create Product' }}
        </VCardTitle>
        <VDivider />
        <VCardText class="pa-4">
          <VAlert
            v-if="saveError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-4"
            closable
            @click:close="saveError = null"
          >
            {{ saveError }}
          </VAlert>
          <VForm
            ref="productFormRef"
            @submit.prevent="handleSave"
          >
            <VDefaultsProvider
              :defaults="{
                VTextField: { density: 'compact', variant: 'outlined', hideDetails: 'auto' },
                VSelect: { density: 'compact', variant: 'outlined', hideDetails: 'auto' },
                VTextarea: { density: 'compact', variant: 'outlined', hideDetails: 'auto' },
                VSwitch: { density: 'compact', hideDetails: true },
              }"
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
                    v-model="form.school_name"
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
                    v-model="form.grade_class"
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
                <VCol
                  cols="12"
                  sm="6"
                  md="4"
                >
                  <VTextField
                    v-model="form.guardian1_name"
                    label="Guardian 1 name"
                    maxlength="255"
                  />
                </VCol>
                <VCol
                  cols="12"
                  sm="6"
                  md="4"
                >
                  <VSelect
                    v-model="form.guardian1_relationship"
                    :items="relationshipOptions"
                    label="Guardian 1 relationship"
                    clearable
                  />
                </VCol>
                <VCol
                  cols="12"
                  sm="6"
                  md="4"
                >
                  <VTextField
                    v-model="form.guardian1_phone"
                    label="Guardian 1 phone"
                    maxlength="50"
                  />
                </VCol>
                <VCol
                  cols="12"
                  sm="6"
                  md="4"
                >
                  <VTextField
                    v-model="form.guardian2_name"
                    label="Guardian 2 name"
                    maxlength="255"
                  />
                </VCol>
                <VCol
                  cols="12"
                  sm="6"
                  md="4"
                >
                  <VSelect
                    v-model="form.guardian2_relationship"
                    :items="relationshipOptions"
                    label="Guardian 2 relationship"
                    clearable
                  />
                </VCol>
                <VCol
                  cols="12"
                  sm="6"
                  md="4"
                >
                  <VTextField
                    v-model="form.guardian2_phone"
                    label="Guardian 2 phone"
                    maxlength="50"
                  />
                </VCol>
              </VRow>

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
            </VDefaultsProvider>
          </VForm>
        </VCardText>
        <VDivider />
        <DialogFooter>
          <VBtn
            variant="outlined"
            color="primary"
            @click="dialogOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            variant="flat"
            color="primary"
            :loading="saving"
            @click="handleSave"
          >
            Save
          </VBtn>
        </DialogFooter>
      </VCard>
    </VDialog>

    <!-- Delete confirmation -->
    <VDialog
      v-model="deleteConfirmOpen"
      max-width="420"
      persistent
    >
      <VCard>
        <VCardTitle>Delete {{ deleteTarget?.full_name }}?</VCardTitle>
        <VCardText>
          <VAlert
            v-if="deleteError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-3"
            closable
            @click:close="deleteError = ''"
          >
            {{ deleteError }}
          </VAlert>
          This will permanently remove
          <strong>{{ deleteTarget?.full_name }}</strong> ({{ deleteTarget?.code }}).
          This action cannot be undone.
        </VCardText>
        <VDivider />
        <DialogFooter>
          <VBtn
            variant="outlined"
            color="primary"
            @click="closeDeleteConfirm"
          >
            Cancel
          </VBtn>
          <VBtn
            variant="flat"
            color="error"
            :loading="deleting"
            @click="confirmDelete"
          >
            Delete
          </VBtn>
        </DialogFooter>
      </VCard>
    </VDialog>

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

@media (max-width: 960px) {
  .products-table :deep(.col-phone),
  .products-table :deep(.col-school) {
    display: none;
  }
}
</style>
