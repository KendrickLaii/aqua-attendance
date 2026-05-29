<script setup lang="ts">
import type { VForm } from 'vuetify/components/VForm'
import {
  maxCharsRule,
  requiredValidator,
} from '@core/utils/validators'
import { createProduct, deleteProduct, listProducts, updateProduct } from '@/api/attendance/products'
import { getQRToken, refreshQRToken } from '@/api/attendance/events'
import type { Product } from '@/api/attendance/products'
import { copyToClipboard } from '@/utils/copyToClipboard'
import { useQrImageUrl } from '@/composables/useQrImageUrl'
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { formatLastAttendance } from '@/utils/attendanceDisplay'

definePage({ meta: {} })

const PRODUCT_PAGE_SIZE = 200
const SEARCH_DEBOUNCE_MS = 300

const authStore = useAttendanceAuthStore()
const router = useRouter()

const products = ref<Product[]>([])
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

const qrDialog = ref(false)
const qrProduct = ref<Product | null>(null)
const qrToken = ref('')
const qrError = ref('')
const qrLoading = ref(false)

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

const productsCapped = computed(() => products.value.length >= PRODUCT_PAGE_SIZE)
const checkedInCount = computed(() => products.value.filter(p => p.attendance_status === 'checked_in').length)

const pageSubtitle = computed(() => {
  const total = products.value.length
  const countLabel = productsCapped.value ? `${PRODUCT_PAGE_SIZE}+` : String(total)

  return `${countLabel} products · ${checkedInCount.value} checked in`
})

const listCaption = computed(() => {
  if (loading.value || products.value.length === 0)
    return ''

  const total = products.value.length
  if (productsCapped.value)
    return `Showing ${total} of ${PRODUCT_PAGE_SIZE}+ products`
  if (searchQuery.value || filterType.value)
    return `Showing ${total} matching product${total === 1 ? '' : 's'}`

  return `${total} product${total === 1 ? '' : 's'}`
})

const showEmptyCreateCta = computed(() =>
  !searchQuery.value && !filterType.value,
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

async function loadProducts(isRefresh = false) {
  if (isRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    products.value = await listProducts({
      search: searchQuery.value || undefined,
      product_type: filterType.value || undefined,
      page_size: PRODUCT_PAGE_SIZE,
    })
  }
  catch (e) {
    console.error('Failed to load products', e)
    loadError.value = 'Failed to load products. Please try again.'
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

const debouncedLoadProducts = useDebounceFn(loadProducts, SEARCH_DEBOUNCE_MS)

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

function formatApiDetail(detail: unknown): string {
  if (detail == null)
    return ''
  if (typeof detail === 'string')
    return detail
  if (Array.isArray(detail)) {
    return detail
      .filter((e): e is Record<string, unknown> => Boolean(e && typeof e === 'object'))
      .map(e => {
        const loc = e.loc
        const msg = e.msg
        const path = Array.isArray(loc) ? loc.filter((x): x is string => typeof x === 'string' && x !== 'body').join('.') : ''

        return path ? `${path}: ${msg}` : String(msg ?? 'Invalid value')
      })
      .join(' · ')
  }

  return String(detail)
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
    await loadProducts()
  }
  catch (e: unknown) {
    const data = e && typeof e === 'object' && 'data' in e ? (e as { data?: { detail?: unknown } }).data : undefined

    saveError.value = formatApiDetail(data?.detail) || (e instanceof Error ? e.message : 'Could not save product')
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
    await loadProducts()
  }
  catch (e: unknown) {
    const data = e && typeof e === 'object' && 'data' in e ? (e as { data?: { detail?: unknown } }).data : undefined

    deleteError.value = formatApiDetail(data?.detail) || (e instanceof Error ? e.message : 'Could not delete product')
  }
  finally {
    deleting.value = false
  }
}

async function openQR(p: Product) {
  qrProduct.value = p
  qrLoading.value = true
  qrToken.value = ''
  qrError.value = ''
  qrDialog.value = true
  try {
    const data = await getQRToken(p.id)

    qrToken.value = data.qr_token
  }
  catch (e: any) {
    qrToken.value = ''
    qrError.value = e?.data?.detail || 'Failed to load QR token'
  }
  finally {
    qrLoading.value = false
  }
}

const rotateConfirmOpen = ref(false)
const rotating = ref(false)
const rotateError = ref('')

function openRotateConfirm() {
  rotateError.value = ''
  rotateConfirmOpen.value = true
}

async function confirmRotate() {
  if (!qrProduct.value)
    return
  rotating.value = true
  rotateError.value = ''
  try {
    const data = await refreshQRToken(qrProduct.value.id)

    qrToken.value = data.qr_token
    qrProduct.value = { ...qrProduct.value, qr_token_version: data.token_version }
    rotateConfirmOpen.value = false
    await loadProducts()
  }
  catch (e: unknown) {
    const data = e && typeof e === 'object' && 'data' in e ? (e as { data?: { detail?: unknown } }).data : undefined

    rotateError.value = formatApiDetail(data?.detail) || (e instanceof Error ? e.message : 'Could not rotate QR code')
  }
  finally {
    rotating.value = false
  }
}

const copied = ref(false)
const copyFailOpen = ref(false)
let copiedHideTimer: ReturnType<typeof setTimeout> | null = null

async function copyQrToken() {
  if (!qrToken.value)
    return
  const ok = await copyToClipboard(qrToken.value)
  if (ok) {
    copyFailOpen.value = false
    copied.value = true
    if (copiedHideTimer)
      clearTimeout(copiedHideTimer)
    copiedHideTimer = setTimeout(() => {
      copied.value = false
    }, 2500)
  }
  else {
    copied.value = false
    copyFailOpen.value = true
  }
}

function selectTokenField(ev: FocusEvent) {
  const el = ev.target as HTMLInputElement | null

  el?.select()
}

const SCAN_TOKEN_SESSION_KEY = 'attendance-scan-token'

function openWebScanner() {
  if (qrToken.value && typeof sessionStorage !== 'undefined')
    sessionStorage.setItem(SCAN_TOKEN_SESSION_KEY, qrToken.value)
  qrDialog.value = false
  router.push({ name: 'attendance-scanner' })
}

const { qrImageUrl, qrImageError, qrImageLoading } = useQrImageUrl(qrToken, 280)

function typeColor(type: string) {
  return type === 'staff' ? 'info' : 'success'
}

function statusColor(status: string) {
  if (status === 'active')
    return 'success'
  if (status === 'suspended')
    return 'warning'

  return 'grey'
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

    <!-- Attendance filter (checked in / out): deferred — see docs/KNOWN-GAPS.md -->
    <VRow
      class="mb-4"
      align="center"
    >
      <VCol
        cols="12"
        sm="4"
      >
        <VTextField
          v-model="searchQuery"
          placeholder="Search products..."
          prepend-inner-icon="ri-search-line"
          density="compact"
          hide-details
          clearable
          @update:model-value="debouncedLoadProducts"
        />
      </VCol>
      <VCol
        cols="12"
        sm="3"
      >
        <VSelect
          v-model="filterType"
          :items="[{ title: 'All Types', value: '' }, ...typeOptions]"
          label="Type"
          density="compact"
          hide-details
          @update:model-value="loadProducts"
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
      <VTable>
        <thead>
          <tr>
            <th>Code</th>
            <th>Full Name</th>
            <th>Type</th>
            <th>Status</th>
            <th>Last check-in / out</th>
            <th>Phone</th>
            <th>School / Class</th>
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
                {{ p.product_type }}
              </VChip>
            </td>
            <td>
              <VChip
                :color="statusColor(p.status)"
                size="small"
                label
              >
                {{ p.status }}
              </VChip>
            </td>
            <td style="min-width: 220px">
              <div
                class="text-caption"
                :class="p.last_event_at && p.attendance_status === 'checked_in' ? 'text-success' : 'text-medium-emphasis'"
              >
                {{ formatLastAttendance(p) }}
              </div>
            </td>
            <td>{{ p.phone || '-' }}</td>
            <td>{{ p.school_name ? `${p.school_name} / ${p.grade_class || '-'}` : '-' }}</td>
            <td>
              <VBtn
                icon
                size="small"
                variant="text"
                color="primary"
                :disabled="!p.is_active"
                :title="p.is_active ? 'QR Code' : 'QR unavailable — product is inactive'"
                @click="openQR(p)"
              >
                <VIcon icon="ri-qr-code-line" />
              </VBtn>
              <VBtn
                icon
                size="small"
                variant="text"
                title="Edit"
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
                {{ searchQuery || filterType ? 'No products match your search or filters' : 'No products yet' }}
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
                label="Active"
                class="mt-1"
              />
              <div class="d-flex justify-end gap-2 mt-4">
                <VBtn
                  variant="text"
                  density="compact"
                  @click="dialogOpen = false"
                >
                  Cancel
                </VBtn>
                <VBtn
                  type="submit"
                  color="primary"
                  density="compact"
                  size="small"
                  :loading="saving"
                >
                  Save
                </VBtn>
              </div>
            </VDefaultsProvider>
          </VForm>
        </VCardText>
      </VCard>
    </VDialog>

    <!-- QR Code Dialog -->
    <VDialog
      v-model="qrDialog"
      max-width="400"
    >
      <VCard class="text-center pa-6">
        <VCardTitle>{{ qrProduct?.full_name }}</VCardTitle>
        <VCardSubtitle>{{ qrProduct?.code }} ({{ qrProduct?.product_type }})</VCardSubtitle>
        <div
          v-if="qrLoading"
          class="py-12"
        >
          <VProgressCircular
            indeterminate
            color="primary"
            size="48"
          />
        </div>
        <template v-else-if="qrToken">
          <div
            class="my-4 d-flex justify-center align-center"
            style="min-height: 280px"
          >
            <VProgressCircular
              v-if="qrImageLoading"
              indeterminate
              color="primary"
              size="40"
            />
            <VAlert
              v-else-if="qrImageError"
              type="error"
              variant="tonal"
              density="compact"
            >
              Could not render QR image.
            </VAlert>
            <VImg
              v-else-if="qrImageUrl"
              :src="qrImageUrl"
              width="280"
              height="280"
              class="rounded"
              style="border: 4px solid rgb(var(--v-theme-primary))"
            />
          </div>
          <div class="text-caption text-medium-emphasis mb-3">
            This QR stays valid until you rotate it. On scan, choose Check In or Check Out
            (mobile app or web scanner). Same code works every day.
          </div>
          <div class="d-flex justify-center flex-wrap gap-2 mb-2">
            <VBtn
              variant="tonal"
              size="small"
              color="primary"
              prepend-icon="ri-qr-scan-2-line"
              @click="openWebScanner"
            >
              Web scanner
            </VBtn>
            <VBtn
              variant="outlined"
              size="small"
              :prepend-icon="copied ? 'ri-check-line' : 'ri-file-copy-line'"
              :color="copied ? 'success' : undefined"
              @click="copyQrToken"
            >
              {{ copied ? 'Copied' : 'Copy token' }}
            </VBtn>
            <VBtn
              variant="text"
              size="small"
              color="warning"
              prepend-icon="ri-refresh-line"
              @click="openRotateConfirm"
            >
              Rotate QR
            </VBtn>
          </div>
          <VTextField
            :model-value="qrToken"
            readonly
            label="Raw token (tap to select, then copy)"
            density="compact"
            variant="outlined"
            class="text-start mt-4"
            hide-details
            @focus="selectTokenField"
          />
          <div class="text-caption text-disabled mt-2">
            Token version: {{ qrProduct?.qr_token_version }}
          </div>
        </template>
        <VAlert
          v-else
          type="error"
          variant="tonal"
          class="mt-4"
        >
          {{ qrError || 'Failed to generate QR code' }}
        </VAlert>
        <VCardActions class="justify-center">
          <VBtn @click="qrDialog = false">
            Close
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <!-- Rotate confirmation -->
    <VDialog
      v-model="rotateConfirmOpen"
      max-width="420"
      persistent
    >
      <VCard>
        <VCardTitle>Rotate QR for {{ qrProduct?.full_name }}?</VCardTitle>
        <VCardText>
          <VAlert
            v-if="rotateError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-3"
            closable
            @click:close="rotateError = ''"
          >
            {{ rotateError }}
          </VAlert>
          The current QR will stop working. Use this only if the printed
          code was lost or shared with someone who shouldn't have it.
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="rotateConfirmOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="warning"
            :loading="rotating"
            @click="confirmRotate"
          >
            Rotate
          </VBtn>
        </VCardActions>
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
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="closeDeleteConfirm"
          >
            Cancel
          </VBtn>
          <VBtn
            color="error"
            :loading="deleting"
            @click="confirmDelete"
          >
            Delete
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VSnackbar
      v-model="copyFailOpen"
      color="error"
      location="bottom"
      :timeout="7000"
    >
      Could not copy automatically. Select the text in the field above and copy manually (Ctrl+C or long-press).
    </VSnackbar>
  </VContainer>
</template>

<style scoped lang="scss">
.dense-form-row :deep(.v-col) {
  padding-block: 4px !important;
}

.product-row-inactive {
  opacity: 0.55;
}
</style>
