<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import {
  createLocation,
  deleteLocation,
  listLocationsWithTotal,
  updateLocation,
  type LocationDetailPhoto,
  type LocationItem,
} from '@/api/attendance/locations'
import { formatApiError } from '@/utils/formatApiDetail'

definePage({ meta: {} })

const LOCATION_PAGE_SIZE = 24
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

interface DetailPhotoRow {
  url: string
  caption: string
  previewError: boolean
}

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
const detailPhotoRows = ref<DetailPhotoRow[]>([{ url: '', caption: '', previewError: false }])

// ── business-hours schedule ────────────────────────────────────────────────
interface DaySchedule {
  key: string
  label: string
  short: string
  isOpen: boolean
  openTime: string
  closeTime: string
}

const DAYS: Array<{ key: string; label: string; short: string }> = [
  { key: 'mon', label: 'Monday', short: 'Mon' },
  { key: 'tue', label: 'Tuesday', short: 'Tue' },
  { key: 'wed', label: 'Wednesday', short: 'Wed' },
  { key: 'thu', label: 'Thursday', short: 'Thu' },
  { key: 'fri', label: 'Friday', short: 'Fri' },
  { key: 'sat', label: 'Saturday', short: 'Sat' },
  { key: 'sun', label: 'Sunday', short: 'Sun' },
]

function defaultHoursSchedule(): DaySchedule[] {
  return DAYS.map(d => ({
    ...d,
    isOpen: ['mon', 'tue', 'wed', 'thu', 'fri'].includes(d.key),
    openTime: '09:00',
    closeTime: '18:00',
  }))
}

const hoursSchedule = ref<DaySchedule[]>(defaultHoursSchedule())

function applyPreset(preset: 'weekday' | 'sixday' | 'allday' | 'clear') {
  hoursSchedule.value.forEach((d) => {
    if (preset === 'clear') {
      d.isOpen = false
    }
    else if (preset === 'weekday') {
      d.isOpen = ['mon', 'tue', 'wed', 'thu', 'fri'].includes(d.key)
      if (d.isOpen) { d.openTime = '09:00'; d.closeTime = '18:00' }
    }
    else if (preset === 'sixday') {
      d.isOpen = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat'].includes(d.key)
      if (d.isOpen) { d.openTime = '09:00'; d.closeTime = '18:00' }
    }
    else if (preset === 'allday') {
      d.isOpen = true
      d.openTime = '09:00'
      d.closeTime = '18:00'
    }
  })
}

function buildBusinessHoursString(): string {
  const open = hoursSchedule.value.filter(d => d.isOpen)
  if (!open.length)
    return ''
  return open.map(d => `${d.short} ${d.openTime}–${d.closeTime}`).join(' · ')
}

function loadHoursSchedule(rawDetails: Record<string, unknown> | null) {
  const stored = (rawDetails?.hours_schedule) as Array<{ day: string; isOpen: boolean; openTime: string; closeTime: string }> | undefined
  if (stored?.length) {
    hoursSchedule.value = DAYS.map((d) => {
      const saved = stored.find(s => s.day === d.key)
      return {
        ...d,
        isOpen: saved?.isOpen ?? false,
        openTime: saved?.openTime ?? '09:00',
        closeTime: saved?.closeTime ?? '18:00',
      }
    })
  }
  else {
    hoursSchedule.value = defaultHoursSchedule()
  }
}

// ── region suggestions ──────────────────────────────────────────────────────
const regionOptions = computed(() =>
  [...new Set(locations.value.map(l => l.region).filter((r): r is string => !!r))].sort(),
)

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / LOCATION_PAGE_SIZE)))
const hasNextPage = computed(() => page.value < totalPages.value)
const hasPrevPage = computed(() => page.value > 1)
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

  const from = (page.value - 1) * LOCATION_PAGE_SIZE + 1
  const to = from + locations.value.length - 1

  if (totalCount.value <= LOCATION_PAGE_SIZE)
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
      page_size: LOCATION_PAGE_SIZE,
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

function goToPrevPage() {
  if (page.value <= 1)
    return
  page.value -= 1
  loadLocations(true)
}

function goToNextPage() {
  if (!hasNextPage.value)
    return
  page.value += 1
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
  detailPhotoRows.value = [{ url: '', caption: '', previewError: false }]
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
  if (item.detail_photos?.length) {
    detailPhotoRows.value = item.detail_photos.map(p => ({
      url: p.url,
      caption: p.caption || '',
      previewError: false,
    }))
  }
  else {
    detailPhotoRows.value = [{ url: '', caption: '', previewError: false }]
  }

  // Load structured schedule; strip hours_schedule from displayed JSON
  const rawDetails = item.details as Record<string, unknown> | null
  loadHoursSchedule(rawDetails)
  if (rawDetails) {
    const { hours_schedule: _hs, ...rest } = rawDetails as Record<string, unknown>
    form.details_json = Object.keys(rest).length ? JSON.stringify(rest, null, 2) : ''
  }
  else {
    form.details_json = ''
  }

  formTab.value = 'basic'
  dialogOpen.value = true
}

function addDetailPhotoRow() {
  detailPhotoRows.value.push({ url: '', caption: '', previewError: false })
}

function removeDetailPhotoRow(index: number) {
  if (detailPhotoRows.value.length <= 1)
    detailPhotoRows.value[0] = { url: '', caption: '', previewError: false }
  else
    detailPhotoRows.value.splice(index, 1)
}

function buildDetailPhotos(): LocationDetailPhoto[] | null {
  const items = detailPhotoRows.value
    .map((row, i) => ({ url: row.url.trim(), caption: row.caption.trim() || null, sort_order: i }))
    .filter(r => r.url)
  return items.length ? items : null
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
  const schedule = hoursSchedule.value.map(d => ({
    day: d.key,
    isOpen: d.isOpen,
    openTime: d.openTime,
    closeTime: d.closeTime,
  }))
  return { ...base, hours_schedule: schedule }
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
      business_hours: buildBusinessHoursString() || null,
      icon_url: form.icon_url.trim() || null,
      main_photo_url: form.main_photo_url.trim() || null,
      detail_photos: buildDetailPhotos(),
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

const DAY_ORDER = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const

interface HoursScheduleEntry {
  day: string
  isOpen: boolean
  openTime: string
  closeTime: string
}

function compressDayRange(dayKeys: string[]): string {
  const sorted = [...new Set(dayKeys)].sort(
    (a, b) => DAY_ORDER.indexOf(a as typeof DAY_ORDER[number]) - DAY_ORDER.indexOf(b as typeof DAY_ORDER[number]),
  )
  const joined = sorted.join(',')

  if (joined === 'mon,tue,wed,thu,fri,sat,sun')
    return 'Daily'
  if (joined === 'mon,tue,wed,thu,fri')
    return 'Mon–Fri'
  if (joined === 'mon,tue,wed,thu,fri,sat')
    return 'Mon–Sat'

  return sorted.map(k => DAYS.find(d => d.key === k)?.short ?? k).join(', ')
}

/** Short one-line summary for location cards (avoids wall-of-text business hours). */
function formatCardBusinessHours(l: LocationItem): string {
  const rawSchedule = l.details?.hours_schedule
  const schedule = Array.isArray(rawSchedule) ? rawSchedule as HoursScheduleEntry[] : undefined

  if (schedule?.length) {
    const open = schedule.filter(s => s.isOpen)
    if (!open.length)
      return ''

    const first = open[0]
    const sameHours = open.every(s => s.openTime === first.openTime && s.closeTime === first.closeTime)

    if (sameHours)
      return `${compressDayRange(open.map(s => s.day))} ${first.openTime}–${first.closeTime}`

    const preview = open.slice(0, 2).map((s) => {
      const short = DAYS.find(d => d.key === s.day)?.short ?? s.day

      return `${short} ${s.openTime}–${s.closeTime}`
    }).join(' · ')

    return open.length > 2 ? `${preview}…` : preview
  }

  const raw = l.business_hours?.trim()
  if (!raw)
    return ''

  const parts = raw.split(' · ')
  if (parts.length <= 2)
    return raw

  const timePattern = /\d{2}:\d{2}[–-]\d{2}:\d{2}$/
  const times = parts.map(p => p.match(timePattern)?.[0]).filter(Boolean)

  if (times.length === parts.length && new Set(times).size === 1) {
    if (parts.length === 7)
      return `Daily ${times[0]}`
    if (parts.length === 5)
      return `Mon–Fri ${times[0]}`
    if (parts.length === 6)
      return `Mon–Sat ${times[0]}`

    return `${parts.length} days · ${times[0]}`
  }

  return `${parts[0]} · ${parts[1]}…`
}

function showCardIcon(l: LocationItem): boolean {
  return !!l.icon_url && l.icon_url !== l.main_photo_url
}

function cardCoverUrl(l: LocationItem): string | null {
  return l.main_photo_url || l.icon_url || null
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
        <VCard
          class="location-card d-flex flex-column"
          hover
          height="100%"
          :class="{ 'location-card--inactive': !l.is_active }"
        >
          <div class="location-card__cover">
            <VImg
              v-if="cardCoverUrl(l)"
              :src="cardCoverUrl(l) || ''"
              height="128"
              cover
              class="location-card__cover-img"
            />
            <div
              v-else
              class="location-card__cover-placeholder"
            >
              <VIcon
                icon="ri-map-pin-line"
                size="40"
                color="primary"
              />
            </div>
            <VChip
              class="location-card__status"
              :color="l.is_active ? 'success' : 'grey'"
              size="small"
              variant="flat"
              label
            >
              {{ l.is_active ? 'Active' : 'Inactive' }}
            </VChip>
          </div>

          <VCardText class="location-card__body pa-4">
            <div class="location-card__header">
              <div class="min-w-0 flex-grow-1">
                <div
                  class="location-card__title text-truncate"
                  :title="l.name_en"
                >
                  {{ l.name_en }}
                </div>
                <div
                  v-if="l.name_zh"
                  class="location-card__subtitle text-truncate"
                  :title="l.name_zh"
                >
                  {{ l.name_zh }}
                </div>
                <div
                  v-if="l.code"
                  class="location-card__code text-truncate"
                >
                  {{ l.code }}
                </div>
              </div>
              <VAvatar
                v-if="showCardIcon(l)"
                size="36"
                rounded="lg"
                class="location-card__avatar flex-shrink-0"
              >
                <VImg
                  :src="l.icon_url || ''"
                  cover
                />
              </VAvatar>
            </div>

            <div
              v-if="l.location_type || l.region"
              class="location-card__chips"
            >
              <VChip
                v-if="l.location_type"
                size="x-small"
                color="primary"
                variant="tonal"
                label
              >
                {{ l.location_type }}
              </VChip>
              <VChip
                v-if="l.region"
                size="x-small"
                color="primary"
                variant="tonal"
                label
              >
                {{ l.region }}
              </VChip>
            </div>

            <div
              v-if="formatCardBusinessHours(l) || l.address"
              class="location-card__meta-block"
            >
              <div
                v-if="formatCardBusinessHours(l)"
                class="location-card__meta"
              >
                <VIcon
                  icon="ri-time-line"
                  size="15"
                  class="location-card__meta-icon"
                />
                <span>{{ formatCardBusinessHours(l) }}</span>
              </div>
              <div
                v-if="l.address"
                class="location-card__meta"
              >
                <VIcon
                  icon="ri-road-map-line"
                  size="15"
                  class="location-card__meta-icon"
                />
                <span class="location-card__address">{{ l.address }}</span>
              </div>
            </div>

            <div class="location-card__actions">
              <VBtn
                icon
                size="small"
                variant="text"
                color="default"
                title="Edit"
                :aria-label="`Edit ${l.name_en}`"
                @click="openEdit(l)"
              >
                <VIcon icon="ri-edit-line" />
              </VBtn>
              <VBtn
                icon
                size="small"
                variant="text"
                color="error"
                title="Delete"
                :aria-label="`Delete ${l.name_en}`"
                @click="openDeleteConfirm(l)"
              >
                <VIcon icon="ri-delete-bin-line" />
              </VBtn>
            </div>
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <div
      v-if="!loading && !loadError && locations.length > 0 && totalPages > 1"
      class="d-flex flex-wrap align-center justify-space-between gap-2 mb-6"
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
            <!-- tab: basic -->
            <VWindowItem value="basic">
              <VRow class="mt-1">
                <VCol cols="12" sm="8">
                  <VTextField
                    v-model="form.name_en"
                    label="English Name *"
                    prepend-inner-icon="ri-translate-2"
                    :rules="[v => !!v.trim() || 'English name is required']"
                    autofocus
                  />
                </VCol>
                <VCol cols="12" sm="4">
                  <VTextField v-model="form.code" label="Code" prepend-inner-icon="ri-hashtag" />
                </VCol>
                <VCol cols="12" sm="8">
                  <VTextField
                    v-model="form.name_zh"
                    label="Chinese Name"
                    hint="Optional — defaults to English name if left blank"
                    persistent-hint
                    prepend-inner-icon="ri-translate"
                  />
                </VCol>
                <VCol cols="12" sm="4">
                  <VSwitch v-model="form.is_active" label="Active" inset color="success" hide-details />
                </VCol>
                <VCol cols="12" sm="6">
                  <VTextField v-model="form.location_type" label="Type" prepend-inner-icon="ri-store-2-line" placeholder="e.g. Classroom, Branch" />
                </VCol>
                <VCol cols="12" sm="6">
                  <VCombobox
                    v-model="form.region"
                    :items="regionOptions"
                    label="Region / District"
                    prepend-inner-icon="ri-map-2-line"
                    clearable
                    hint="Select existing or type a new region"
                    persistent-hint
                  />
                </VCol>

                <!-- business hours timetable -->
                <VCol cols="12">
                  <VDivider class="mb-3" />
                  <div class="d-flex align-center mb-2" style="gap:6px;">
                    <VIcon icon="ri-time-line" size="16" />
                    <span class="text-subtitle-2">Business Hours</span>
                  </div>

                  <!-- presets -->
                  <div class="d-flex flex-wrap mb-3" style="gap:6px;">
                    <VBtn size="x-small" variant="tonal" @click="applyPreset('weekday')">
                      Mon–Fri 9–18
                    </VBtn>
                    <VBtn size="x-small" variant="tonal" @click="applyPreset('sixday')">
                      Mon–Sat 9–18
                    </VBtn>
                    <VBtn size="x-small" variant="tonal" @click="applyPreset('allday')">
                      All 9–18
                    </VBtn>
                    <VBtn size="x-small" variant="tonal" color="error" @click="applyPreset('clear')">
                      Clear All
                    </VBtn>
                  </div>

                  <!-- schedule rows -->
                  <table style="width:100%; border-collapse:separate; border-spacing:0 2px;">
                    <tbody>
                      <tr v-for="d in hoursSchedule" :key="d.key">
                        <td style="width:44px; vertical-align:middle;" class="text-body-2 font-weight-medium pe-1">
                          {{ d.short }}
                        </td>
                        <td style="width:48px; vertical-align:middle;">
                          <VCheckbox v-model="d.isOpen" density="compact" hide-details class="ma-0 pa-0" />
                        </td>
                        <td style="vertical-align:middle; padding:2px 0;">
                          <div v-if="d.isOpen" class="d-flex align-center" style="gap:4px;">
                            <VTextField
                              v-model="d.openTime"
                              type="time"
                              density="compact"
                              hide-details
                              style="width:130px; min-width:100px;"
                            />
                            <span class="text-caption px-1">–</span>
                            <VTextField
                              v-model="d.closeTime"
                              type="time"
                              density="compact"
                              hide-details
                              style="width:130px; min-width:100px;"
                            />
                          </div>
                          <span v-else class="text-caption text-medium-emphasis ps-1">Closed</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </VCol>
              </VRow>
            </VWindowItem>

            <!-- tab: photos -->
            <VWindowItem value="photos">
              <VRow class="mt-1">
                <!-- icon -->
                <VCol cols="12">
                  <div class="text-subtitle-2 mb-2">
                    <VIcon icon="ri-image-circle-line" size="16" class="me-1" />Icon URL
                    <span class="text-caption text-medium-emphasis ml-1">— small image for lists</span>
                  </div>
                  <VTextField
                    v-model="form.icon_url"
                    placeholder="https://..."
                    density="compact"
                    @update:model-value="iconPreviewError = false"
                  />
                  <div v-if="form.icon_url.trim()" class="mt-2 mb-3">
                    <VImg
                      v-if="!iconPreviewError"
                      :src="form.icon_url.trim()"
                      max-height="100"
                      max-width="100"
                      rounded="lg"
                      class="border"
                      @error="iconPreviewError = true"
                    />
                    <div v-else class="text-caption text-error">
                      <VIcon icon="ri-error-warning-line" size="14" class="me-1" />Cannot load image
                    </div>
                  </div>
                </VCol>

                <!-- main photo -->
                <VCol cols="12">
                  <VDivider class="mb-3" />
                  <div class="text-subtitle-2 mb-2">
                    <VIcon icon="ri-image-2-line" size="16" class="me-1" />Main Photo URL
                    <span class="text-caption text-medium-emphasis ml-1">— cover / hero image</span>
                  </div>
                  <VTextField
                    v-model="form.main_photo_url"
                    placeholder="https://..."
                    density="compact"
                    @update:model-value="mainPreviewError = false"
                  />
                  <div v-if="form.main_photo_url.trim()" class="mt-2 mb-3">
                    <VImg
                      v-if="!mainPreviewError"
                      :src="form.main_photo_url.trim()"
                      max-height="200"
                      rounded="lg"
                      class="border"
                      @error="mainPreviewError = true"
                    />
                    <div v-else class="text-caption text-error">
                      <VIcon icon="ri-error-warning-line" size="14" class="me-1" />Cannot load image
                    </div>
                  </div>
                </VCol>

                <!-- detail gallery -->
                <VCol cols="12">
                  <VDivider class="mb-3" />
                  <div class="text-subtitle-2 mb-2">
                    <VIcon icon="ri-gallery-line" size="16" class="me-1" />Detail Photos
                    <span class="text-caption text-medium-emphasis ml-1">— gallery / additional images</span>
                  </div>
                  <div
                    v-for="(row, index) in detailPhotoRows"
                    :key="index"
                    class="mb-3"
                  >
                    <VCard variant="outlined" class="pa-3">
                      <VRow dense align="center">
                        <VCol cols="12" sm="7">
                          <VTextField
                            v-model="row.url"
                            label="Photo URL"
                            density="compact"
                            hide-details
                            placeholder="https://..."
                            @update:model-value="row.previewError = false"
                          />
                        </VCol>
                        <VCol cols="12" sm="4">
                          <VTextField
                            v-model="row.caption"
                            label="Caption"
                            density="compact"
                            hide-details
                          />
                        </VCol>
                        <VCol cols="auto">
                          <VBtn icon size="small" variant="text" color="error" @click="removeDetailPhotoRow(index)">
                            <VIcon icon="ri-delete-bin-line" />
                          </VBtn>
                        </VCol>
                      </VRow>
                      <!-- inline preview -->
                      <div v-if="row.url.trim()" class="mt-2">
                        <VImg
                          v-if="!row.previewError"
                          :src="row.url.trim()"
                          max-height="120"
                          max-width="180"
                          rounded="md"
                          class="border"
                          @error="row.previewError = true"
                        />
                        <div v-else class="text-caption text-error">
                          <VIcon icon="ri-error-warning-line" size="14" class="me-1" />Cannot load image
                        </div>
                      </div>
                    </VCard>
                  </div>
                  <VBtn size="small" variant="tonal" prepend-icon="ri-add-line" @click="addDetailPhotoRow">
                    Add photo
                  </VBtn>
                </VCol>
              </VRow>
            </VWindowItem>

            <!-- tab: contact -->
            <VWindowItem value="contact">
              <VRow class="mt-1">
                <VCol cols="12">
                  <VTextField v-model="form.address" label="Address" prepend-inner-icon="ri-road-map-line" />
                </VCol>
                <VCol cols="12" sm="4">
                  <VTextField v-model="form.contact_person" label="Contact Person" prepend-inner-icon="ri-user-line" />
                </VCol>
                <VCol cols="12" sm="4">
                  <VTextField v-model="form.phone" label="Phone" prepend-inner-icon="ri-phone-line" />
                </VCol>
                <VCol cols="12" sm="4">
                  <VTextField v-model="form.email" label="Email" prepend-inner-icon="ri-mail-line" />
                </VCol>
              </VRow>
            </VWindowItem>

            <!-- tab: notes / extra -->
            <VWindowItem value="extra">
              <VRow class="mt-1">
                <VCol cols="12">
                  <VTextarea v-model="form.notes" label="Notes" rows="3" prepend-inner-icon="ri-sticky-note-line" />
                </VCol>
                <VCol cols="12">
                  <VTextarea
                    v-model="form.details_json"
                    label="Extra Details (JSON)"
                    rows="4"
                    hint='Free-form key/value pairs. Example: {"floor":"2F","room":"A-01"}'
                    persistent-hint
                    prepend-inner-icon="ri-code-line"
                    :rules="[v => { if (!v.trim()) return true; try { JSON.parse(v); return true } catch { return 'Invalid JSON' } }]"
                  />
                </VCol>
              </VRow>
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

<style scoped lang="scss">
.location-card {
  overflow: hidden;
  transition: box-shadow 0.2s ease;

  &--inactive {
    opacity: 0.72;
  }

  &__cover {
    position: relative;
    overflow: hidden;
  }

  &__cover-img {
    background: rgb(var(--v-theme-surface-variant));
  }

  &__cover-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 128px;
    background: rgba(var(--v-theme-primary), 0.06);
  }

  &__status {
    position: absolute;
    top: 10px;
    right: 10px;
    font-weight: 600;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
  }

  &__body {
    display: flex;
    flex: 1;
    flex-direction: column;
  }

  &__header {
    display: flex;
    align-items: flex-start;
    gap: 10px;
  }

  &__title {
    font-size: 1rem;
    font-weight: 600;
    line-height: 1.35;
  }

  &__subtitle {
    font-size: 0.8125rem;
    color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
    line-height: 1.35;
    margin-top: 2px;
  }

  &__code {
    font-size: 0.75rem;
    color: rgba(var(--v-theme-on-surface), var(--v-disabled-opacity));
    margin-top: 2px;
  }

  &__avatar {
    border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  }

  &__chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 12px;
  }

  &__meta-block {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 12px;
  }

  &__meta {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    font-size: 0.8125rem;
    line-height: 1.4;
    color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  }

  &__meta-icon {
    flex-shrink: 0;
    margin-top: 1px;
    opacity: 0.7;
  }

  &__address {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  &__actions {
    display: flex;
    justify-content: flex-end;
    gap: 2px;
    margin-top: auto;
    padding-top: 12px;
    border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  }
}
</style>
