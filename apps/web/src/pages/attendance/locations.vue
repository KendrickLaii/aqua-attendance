<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import {
  type LocationItem,
  createLocation,
  deleteLocation,
  listLocationsWithTotal,
  updateLocation,
} from '@/api/attendance/locations'
import { formatApiError } from '@/utils/formatApiDetail'
import {
  type DaySchedule,
  buildBusinessHoursString,
  defaultHoursSchedule,
  hoursScheduleToPayload,
  loadHoursSchedule,
} from '@/utils/locationHours'
import {
  type DetailPhotoRow,
  buildDetailPhotos,
  defaultDetailPhotoRows,
  detailPhotosToRows,
} from '@/utils/locationPhotos'

definePage({ meta: {} })

const pageSize = ref(24)
const pageSizeOptions = [12, 24, 40, 60, 100]
const SEARCH_DEBOUNCE_MS = 300

const authStore = useAttendanceAuthStore()
const router = useRouter()

const locations = ref<LocationItem[]>([])
const totalCount = ref(0)
const page = ref(1)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')
const search = ref('')
const showInactive = ref(false)

const dialogOpen = ref(false)
const saving = ref(false)
const saveError = ref('')
const editing = ref<LocationItem | null>(null)

const deleteConfirmOpen = ref(false)
const deleteTarget = ref<LocationItem | null>(null)
const deleting = ref(false)
const deleteError = ref('')
const formTab = ref('basic')

const form = reactive({
  code: '',
  name_zh: '',
  name_en: '',
  location_type: '',
  region: '',
  business_hours: '',
  icon_url: '',
  main_photo_url: '',
  address: '',
  contact_person: '',
  phone: '',
  email: '',
  notes: '',
  details_json: '',
  is_active: true,
})

const iconPreviewError = ref(false)
const mainPreviewError = ref(false)
const detailPhotoRows = ref<DetailPhotoRow[]>(defaultDetailPhotoRows())
const hoursSchedule = ref<DaySchedule[]>(defaultHoursSchedule())

const regionOptions = computed(() =>
  [...new Set(locations.value.map(l => l.region).filter((r): r is string => !!r))].sort(),
)

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const activeCount = computed(() => locations.value.filter(l => l.is_active).length)

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  const total = totalCount.value
  let label = `${total} location${total === 1 ? '' : 's'} · ${activeCount.value} active on this page`
  if (totalPages.value > 1)
    label += ` · page ${page.value} of ${totalPages.value}`

  return label
})

const listCaption = computed(() => {
  if (loading.value || totalCount.value === 0)
    return ''

  const from = (page.value - 1) * pageSize.value + 1
  const to = from + locations.value.length - 1

  if (totalCount.value <= pageSize.value)
    return `${totalCount.value} location${totalCount.value === 1 ? '' : 's'}`

  return `${from}–${to} of ${totalCount.value}`
})

const showEmptyCreateCta = computed(() => !search.value.trim() && !showInactive.value)

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
})

async function loadLocations(isRefresh = false, resetPage = false) {
  const softRefresh = isRefresh === true

  if (resetPage)
    page.value = 1
  if (softRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const result = await listLocationsWithTotal({
      is_active: showInactive.value ? undefined : true,
      search: search.value.trim() || undefined,
      page: page.value,
      page_size: pageSize.value,
    })

    locations.value = result.items
    totalCount.value = result.total
  }
  catch (e) {
    console.error('Failed to load locations', e)
    loadError.value = formatApiError(e, 'Failed to load locations. Please try again.')
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

const debouncedLoadLocations = useDebounceFn(() => loadLocations(true, true), SEARCH_DEBOUNCE_MS)

watch(search, () => {
  debouncedLoadLocations()
})

watch(showInactive, () => {
  loadLocations(true, true)
})

function onPageSizeChange() {
  page.value = 1
  loadLocations(true)
}

function resetForm() {
  Object.assign(form, {
    code: '',
    name_zh: '',
    name_en: '',
    location_type: '',
    region: '',
    business_hours: '',
    icon_url: '',
    main_photo_url: '',
    address: '',
    contact_person: '',
    phone: '',
    email: '',
    notes: '',
    details_json: '',
    is_active: true,
  })
  iconPreviewError.value = false
  mainPreviewError.value = false
  detailPhotoRows.value = defaultDetailPhotoRows()
  hoursSchedule.value = defaultHoursSchedule()
  formTab.value = 'basic'
}

function closeEditDialog() {
  dialogOpen.value = false
  saveError.value = ''
}

function openCreate() {
  saveError.value = ''
  editing.value = null
  resetForm()
  dialogOpen.value = true
}

function openEdit(item: LocationItem) {
  saveError.value = ''
  editing.value = item
  Object.assign(form, {
    code: item.code || '',
    name_zh: item.name_zh || '',
    name_en: item.name_en,
    location_type: item.location_type || '',
    region: item.region || '',
    business_hours: item.business_hours || '',
    icon_url: item.icon_url || '',
    main_photo_url: item.main_photo_url || '',
    address: item.address || '',
    contact_person: item.contact_person || '',
    phone: item.phone || '',
    email: item.email || '',
    notes: item.notes || '',
    details_json: '',
    is_active: item.is_active,
  })
  iconPreviewError.value = false
  mainPreviewError.value = false
  detailPhotoRows.value = detailPhotosToRows(item.detail_photos)

  const rawDetails = item.details as Record<string, unknown> | null

  hoursSchedule.value = loadHoursSchedule(rawDetails)

  if (rawDetails) {
    const rest = { ...rawDetails }

    delete rest.hours_schedule
    form.details_json = Object.keys(rest).length ? JSON.stringify(rest, null, 2) : ''
  }
  else {
    form.details_json = ''
  }

  formTab.value = 'basic'
  dialogOpen.value = true
}

function buildPayloadDetails(): Record<string, unknown> {
  let base: Record<string, unknown> = {}
  const raw = form.details_json.trim()
  if (raw) {
    try {
      base = JSON.parse(raw)
    }
    catch {
      throw new Error('Details JSON is invalid — please check the format')
    }
  }

  return { ...base, hours_schedule: hoursScheduleToPayload(hoursSchedule.value) }
}

async function handleSave() {
  if (!form.name_en.trim()) {
    saveError.value = 'English name is required'
    formTab.value = 'basic'

    return
  }
  saving.value = true
  saveError.value = ''
  try {
    const englishName = form.name_en.trim()

    const payload = {
      code: form.code.trim() || null,
      name_zh: form.name_zh.trim() || englishName,
      name_en: englishName,
      location_type: form.location_type.trim() || null,
      region: (form.region as string)?.trim() || null,
      business_hours: buildBusinessHoursString(hoursSchedule.value) || null,
      icon_url: form.icon_url.trim() || null,
      main_photo_url: form.main_photo_url.trim() || null,
      detail_photos: buildDetailPhotos(detailPhotoRows.value),
      address: form.address.trim() || null,
      contact_person: form.contact_person.trim() || null,
      phone: form.phone.trim() || null,
      email: form.email.trim() || null,
      notes: form.notes.trim() || null,
      details: buildPayloadDetails(),
      is_active: form.is_active,
    }

    if (editing.value)
      await updateLocation(editing.value.id, payload)
    else
      await createLocation(payload)

    closeEditDialog()
    await loadLocations(true)
  }
  catch (e: unknown) {
    saveError.value = formatApiError(e, 'Could not save location')
  }
  finally {
    saving.value = false
  }
}

function openDeleteConfirm(item: LocationItem) {
  deleteError.value = ''
  deleteTarget.value = item
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
    await deleteLocation(deleteTarget.value.id)
    closeDeleteConfirm()
    await loadLocations(true)
  }
  catch (e: unknown) {
    deleteError.value = formatApiError(e, 'Could not delete location')
  }
  finally {
    deleting.value = false
  }
}

function displayName(l: LocationItem) {
  if (l.name_zh)
    return `${l.name_zh} / ${l.name_en}`

  return l.name_en
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
          Location Management
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
          :disabled="loading"
          @click="loadLocations(true)"
        >
          Refresh
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          @click="openCreate"
        >
          Add Location
        </VBtn>
      </VCol>
    </VRow>

    <VRow
      class="mb-4"
      align="center"
    >
      <VCol
        cols="12"
        sm="6"
      >
        <VTextField
          v-model="search"
          placeholder="Search locations..."
          prepend-inner-icon="ri-search-line"
          density="compact"
          hide-details
          clearable
        />
      </VCol>
      <VCol cols="auto">
        <VCheckbox
          v-model="showInactive"
          label="Show inactive"
          hide-details
          density="compact"
        />
      </VCol>
      <VCol
        v-if="listCaption"
        cols="auto"
        class="ms-sm-auto"
      >
        <span class="text-caption text-medium-emphasis">{{ listCaption }}</span>
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
          @click="loadLocations(true)"
        >
          Retry
        </VBtn>
      </template>
    </VAlert>

    <VRow v-if="loading && !refreshing">
      <VCol
        cols="12"
        class="text-center py-12"
      >
        <VProgressCircular
          indeterminate
          color="primary"
          size="48"
        />
      </VCol>
    </VRow>

    <div
      v-else-if="locations.length === 0 && !loadError"
      class="text-center text-medium-emphasis py-12"
    >
      <VIcon
        icon="ri-map-pin-line"
        size="48"
        class="mb-3"
      />
      <div class="mb-3">
        <template v-if="showEmptyCreateCta">
          No locations yet. Click <strong>Add Location</strong> to get started.
        </template>
        <template v-else>
          No locations match your filters.
        </template>
      </div>
      <VBtn
        v-if="showEmptyCreateCta"
        color="primary"
        prepend-icon="ri-add-line"
        @click="openCreate"
      >
        Add Location
      </VBtn>
    </div>

    <VRow v-else-if="!loadError">
      <VCol
        v-for="l in locations"
        :key="l.id"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <LocationCard
          :location="l"
          @edit="openEdit(l)"
          @delete="openDeleteConfirm(l)"
        />
      </VCol>
    </VRow>

    <div
      v-if="!loading && !loadError && locations.length > 0"
      class="d-flex flex-wrap align-center justify-space-between gap-2 mb-6"
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
        @update:model-value="loadLocations(true)"
      />
    </div>

    <AttendanceFormDialog
      v-model="dialogOpen"
      :max-width="760"
      :title="editing ? `Edit — ${editing.name_en || editing.name_zh}` : 'Create Location'"
      :icon="editing ? 'ri-edit-line' : 'ri-map-pin-add-line'"
      :saving="saving"
      :error="saveError"
      body-class="pa-4"
      :body-style="{ height: '62vh', overflowY: 'auto' }"
      @save="handleSave"
      @cancel="closeEditDialog"
      @clear-error="saveError = ''"
    >
      <template #header-after>
        <VTabs
          v-model="formTab"
          class="px-4"
        >
          <VTab value="basic">
            Basic Info
          </VTab>
          <VTab value="photos">
            Photos
          </VTab>
          <VTab value="contact">
            Contact
          </VTab>
          <VTab value="extra">
            Notes / Extra
          </VTab>
        </VTabs>
        <VDivider />
      </template>
      <VAlert
        type="info"
        variant="tonal"
        density="compact"
        class="mb-4"
        icon="ri-information-line"
      >
        Photos use external URLs in v1. File upload is planned later.
      </VAlert>

      <VWindow v-model="formTab">
        <VWindowItem value="basic">
          <LocationBasicTab
            v-model:hours-schedule="hoursSchedule"
            :form="form"
            :region-options="regionOptions"
          />
        </VWindowItem>
        <VWindowItem value="photos">
          <LocationPhotosTab
            v-model:detail-photo-rows="detailPhotoRows"
            v-model:icon-preview-error="iconPreviewError"
            v-model:main-preview-error="mainPreviewError"
            :form="form"
          />
        </VWindowItem>
        <VWindowItem value="contact">
          <LocationContactTab :form="form" />
        </VWindowItem>
        <VWindowItem value="extra">
          <LocationExtraTab :form="form" />
        </VWindowItem>
      </VWindow>
    </AttendanceFormDialog>

    <AttendanceConfirmDialog
      v-model="deleteConfirmOpen"
      :title="`Delete ${deleteTarget ? displayName(deleteTarget) : 'location'}?`"
      :loading="deleting"
      :error="deleteError"
      @confirm="confirmDelete"
      @cancel="closeDeleteConfirm"
      @clear-error="deleteError = ''"
    >
      <template v-if="deleteTarget">
        This will permanently remove
        <strong>{{ displayName(deleteTarget) }}</strong>
        <span v-if="deleteTarget.code"> ({{ deleteTarget.code }})</span>.
        Locations referenced by attendance records cannot be deleted.
      </template>
    </AttendanceConfirmDialog>
  </VContainer>
</template>
