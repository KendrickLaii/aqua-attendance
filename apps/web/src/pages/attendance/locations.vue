<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import {
  createLocation,
  deleteLocation,
  listLocations,
  updateLocation,
  type LocationDetailPhoto,
  type LocationItem,
} from '@/api/attendance/locations'

definePage({ meta: {} })

const authStore = useAttendanceAuthStore()
const router = useRouter()

const locations = ref<LocationItem[]>([])
const loading = ref(true)
const search = ref('')
const showInactive = ref(false)
const error = ref('')

const dialogOpen = ref(false)
const saving = ref(false)
const editing = ref<LocationItem | null>(null)
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

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) {
    router.replace({ name: 'attendance-login' })
    return
  }
  await loadLocations()
})

async function loadLocations() {
  loading.value = true
  error.value = ''
  try {
    locations.value = await listLocations({
      is_active: showInactive.value ? undefined : true,
      search: search.value.trim() || undefined,
      page: 1,
      page_size: 200,
    })
  }
  catch (e: any) {
    error.value = e?.data?.detail || 'Failed to load locations'
  }
  finally {
    loading.value = false
  }
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

function openCreate() {
  editing.value = null
  resetForm()
  dialogOpen.value = true
}

function openEdit(item: LocationItem) {
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
    error.value = 'English name is required'
    formTab.value = 'basic'
    return
  }
  saving.value = true
  error.value = ''
  try {
    const payload = {
      code: form.code.trim() || null,
      name_zh: form.name_zh.trim() || null,
      name_en: form.name_en.trim(),
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

    dialogOpen.value = false
    await loadLocations()
  }
  catch (e: any) {
    error.value = e?.data?.detail || e?.message || 'Save failed'
  }
  finally {
    saving.value = false
  }
}

async function handleDelete(item: LocationItem) {
  const label = item.name_en || item.name_zh || item.id
  const ok = window.confirm(`Delete location "${label}"?`)
  if (!ok)
    return
  error.value = ''
  try {
    await deleteLocation(item.id)
    await loadLocations()
  }
  catch (e: any) {
    error.value = e?.data?.detail || 'Delete failed'
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
    <!-- toolbar -->
    <VRow class="mb-4" align="center">
      <VCol cols="12" sm="5">
        <VTextField
          v-model="search"
          placeholder="Search locations..."
          prepend-inner-icon="ri-search-line"
          density="compact"
          hide-details
          clearable
          @update:model-value="loadLocations"
        />
      </VCol>
      <VCol cols="auto">
        <VCheckbox
          v-model="showInactive"
          label="Show inactive"
          hide-details
          density="compact"
          @update:model-value="loadLocations"
        />
      </VCol>
      <VCol class="text-end">
        <VBtn color="primary" prepend-icon="ri-map-pin-add-line" @click="openCreate">
          Add Location
        </VBtn>
      </VCol>
    </VRow>

    <VAlert v-if="error" type="error" variant="tonal" class="mb-4" closable @click:close="error = ''">
      {{ error }}
    </VAlert>

    <!-- location card grid -->
    <VRow v-if="loading">
      <VCol cols="12" class="text-center py-12">
        <VProgressCircular indeterminate color="primary" size="48" />
      </VCol>
    </VRow>

    <VRow v-else-if="locations.length === 0">
      <VCol cols="12">
        <VCard>
          <VCardText class="text-center text-medium-emphasis py-12">
            <VIcon icon="ri-map-pin-line" size="48" class="mb-3" />
            <div>No locations found. Click <strong>Add Location</strong> to get started.</div>
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <VRow v-else>
      <VCol
        v-for="l in locations"
        :key="l.id"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <VCard :opacity="l.is_active ? 1 : 0.6" height="100%">
          <!-- cover image -->
          <VImg
            v-if="l.main_photo_url || l.icon_url"
            :src="l.main_photo_url || l.icon_url || ''"
            height="140"
            cover
            class="bg-grey-lighten-3"
          />
          <div v-else class="bg-grey-lighten-4 d-flex align-center justify-center" style="height:140px">
            <VIcon icon="ri-image-line" size="40" color="grey" />
          </div>

          <VCardText class="pa-3">
            <div class="d-flex align-start gap-2 mb-1">
              <!-- icon thumbnail -->
              <VAvatar v-if="l.icon_url" size="32" rounded="sm" class="flex-shrink-0 mt-1">
                <VImg :src="l.icon_url" cover />
              </VAvatar>
              <div class="flex-grow-1 min-w-0">
                <div class="text-subtitle-2 font-weight-bold text-truncate">
                  {{ l.name_en }}
                </div>
                <div v-if="l.name_zh" class="text-caption text-medium-emphasis text-truncate">
                  {{ l.name_zh }}
                </div>
              </div>
            </div>

            <div class="d-flex flex-wrap gap-1 my-2">
              <VChip v-if="l.location_type" size="x-small" color="primary" variant="tonal">
                {{ l.location_type }}
              </VChip>
              <VChip v-if="l.region" size="x-small" color="secondary" variant="tonal" prepend-icon="ri-map-pin-line">
                {{ l.region }}
              </VChip>
              <VChip v-if="l.code" size="x-small" variant="outlined">
                {{ l.code }}
              </VChip>
              <VChip :color="l.is_active ? 'success' : 'grey'" size="x-small" label>
                {{ l.is_active ? 'Active' : 'Inactive' }}
              </VChip>
            </div>

            <div v-if="l.business_hours" class="text-caption text-medium-emphasis mb-1">
              <VIcon icon="ri-time-line" size="13" class="me-1" />{{ l.business_hours }}
            </div>
            <div v-if="l.address" class="text-caption text-medium-emphasis">
              <VIcon icon="ri-road-map-line" size="13" class="me-1" />{{ l.address }}
            </div>
          </VCardText>

          <VDivider />
          <VCardActions class="pa-1 justify-end">
            <VBtn size="small" variant="text" prepend-icon="ri-edit-line" @click="openEdit(l)">
              Edit
            </VBtn>
            <VBtn size="small" variant="text" color="error" prepend-icon="ri-delete-bin-line" @click="handleDelete(l)">
              Delete
            </VBtn>
          </VCardActions>
        </VCard>
      </VCol>
    </VRow>

    <!-- create / edit dialog -->
    <VDialog v-model="dialogOpen" max-width="760" scrollable>
      <VCard>
        <VCardTitle class="d-flex align-center pa-4 pb-0">
          <VIcon :icon="editing ? 'ri-edit-line' : 'ri-map-pin-add-line'" class="me-2" />
          {{ editing ? `Edit — ${editing.name_en || editing.name_zh}` : 'Create Location' }}
          <VSpacer />
          <VBtn icon variant="text" size="small" @click="dialogOpen = false">
            <VIcon icon="ri-close-line" />
          </VBtn>
        </VCardTitle>

        <VTabs v-model="formTab" class="px-4">
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

        <VCardText style="height: 62vh; overflow-y: auto">
          <VAlert type="info" variant="tonal" density="compact" class="mb-4" icon="ri-information-line">
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
        </VCardText>

        <VDivider />
        <VCardActions class="pa-4 justify-space-between">
          <VAlert
            v-if="error"
            type="error"
            variant="tonal"
            density="compact"
            class="flex-grow-1 me-4 ma-0 pa-2"
            :text="error"
          />
          <VSpacer v-else />
          <VBtn variant="outlined" @click="dialogOpen = false">
            Cancel
          </VBtn>
          <VBtn color="primary" :loading="saving" prepend-icon="ri-save-line" @click="handleSave">
            Save
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>
