<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { createManualCorrection, exportAttendanceCSV, listAttendanceWithTotal } from '@/api/attendance/events'
import { listProducts } from '@/api/attendance/products'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import type { AttendanceEvent } from '@/api/attendance/events'
import type { Product } from '@/api/attendance/products'
import { formatAttendanceDateTime, getDateRangeIso, getTodayRangeIso, shiftDateKey } from '@/utils/attendanceDisplay'
import { formatApiError } from '@/utils/formatApiDetail'

definePage({ meta: {} })

const EVENTS_PAGE_SIZE = 100
const PRODUCT_PAGE_SIZE = 200

const authStore = useAttendanceAuthStore()
const router = useRouter()

const todayKey = getTodayRangeIso().dateKey

const events = ref<AttendanceEvent[]>([])
const totalCount = ref(0)
const products = ref<Product[]>([])
const locations = ref<LocationItem[]>([])
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')

const filters = reactive({
  product_id: '' as string,
  product_type: '' as string,
  date_from: todayKey,
  date_to: todayKey,
  event_type: '' as string,
})

const page = ref(1)

const correctionDialog = ref(false)

const correctionForm = reactive({
  product_id: '',
  event_type: 'manual_correction',
  location_id: '',
  notes: '',
})

const correcting = ref(false)
const correctionError = ref('')
const exporting = ref(false)
const exportError = ref('')

const typeOptions = [
  { title: 'Student', value: 'student' },
  { title: 'Staff', value: 'staff' },
]

const eventTypeOptions = [
  { title: 'All Events', value: '' },
  { title: 'Check In', value: 'check_in' },
  { title: 'Check Out', value: 'check_out' },
  { title: 'Manual Correction', value: 'manual_correction' },
]

const datePresets = [
  { title: 'Today', value: 'today' },
  { title: 'Last 7 days', value: '7d' },
  { title: 'Last 30 days', value: '30d' },
  { title: 'All time', value: 'all' },
] as const

type DatePreset = typeof datePresets[number]['value'] | 'custom'

const activeDatePreset = ref<DatePreset>('today')

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / EVENTS_PAGE_SIZE)))
const hasNextPage = computed(() => page.value < totalPages.value)
const hasPrevPage = computed(() => page.value > 1)

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  const preset = activeDatePreset.value === 'custom'
    ? 'Custom range'
    : datePresets.find(p => p.value === activeDatePreset.value)?.title ?? 'Custom range'

  const pageLabel = totalPages.value > 1 ? ` · page ${page.value} of ${totalPages.value}` : ''

  if (totalCount.value === 0)
    return `${preset} · no records`

  return `${totalCount.value} record${totalCount.value === 1 ? '' : 's'} · ${preset}${pageLabel}`
})

const listCaption = computed(() => {
  if (loading.value || totalCount.value === 0)
    return ''

  const from = (page.value - 1) * EVENTS_PAGE_SIZE + 1
  const to = from + events.value.length - 1

  if (totalCount.value <= EVENTS_PAGE_SIZE)
    return `${totalCount.value} record${totalCount.value === 1 ? '' : 's'}`

  return `${from}–${to} of ${totalCount.value}`
})

const productSelectItems = computed(() => [
  { title: 'All Products', value: '' },
  ...products.value.map(p => ({ title: `${p.full_name} (${p.code})`, value: p.id })),
])

const productsCapped = computed(() => products.value.length >= PRODUCT_PAGE_SIZE)

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

  try {
    products.value = await listProducts({ page_size: PRODUCT_PAGE_SIZE })
  }
  catch (e) {
    console.error('Failed to load products for log filters', e)
  }
  try {
    locations.value = await listLocations({ is_active: true, page_size: 200 })
  }
  catch (e) {
    console.error('Failed to load locations for manual correction', e)
  }
  await loadEvents()
})

function filterDateRange() {
  return getDateRangeIso(filters.date_from, filters.date_to)
}

async function loadEvents(isRefresh = false, resetPage = false) {
  if (resetPage)
    page.value = 1
  if (isRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const range = filterDateRange()

    const result = await listAttendanceWithTotal({
      product_id: filters.product_id || undefined,
      product_type: filters.product_type || undefined,
      date_from: range.date_from,
      date_to: range.date_to,
      event_type: filters.event_type || undefined,
      page: page.value,
      page_size: EVENTS_PAGE_SIZE,
    })

    events.value = result.items
    totalCount.value = result.total
  }
  catch (e) {
    console.error('Failed to load attendance log', e)
    loadError.value = formatApiError(e, 'Failed to load attendance records. Please try again.')
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

function applyFilters() {
  loadEvents(false, true)
}

function applyDatePreset(preset: DatePreset) {
  activeDatePreset.value = preset

  const today = getTodayRangeIso().dateKey

  if (preset === 'today') {
    filters.date_from = today
    filters.date_to = today
  }
  else if (preset === '7d') {
    filters.date_from = shiftDateKey(today, -6)
    filters.date_to = today
  }
  else if (preset === '30d') {
    filters.date_from = shiftDateKey(today, -29)
    filters.date_to = today
  }
  else {
    filters.date_from = ''
    filters.date_to = ''
  }

  applyFilters()
}

function onManualDateChange() {
  const today = getTodayRangeIso().dateKey

  if (!filters.date_from && !filters.date_to)
    activeDatePreset.value = 'all'
  else if (filters.date_from === today && filters.date_to === today)
    activeDatePreset.value = 'today'
  else if (filters.date_from === shiftDateKey(today, -6) && filters.date_to === today)
    activeDatePreset.value = '7d'
  else if (filters.date_from === shiftDateKey(today, -29) && filters.date_to === today)
    activeDatePreset.value = '30d'
  else
    activeDatePreset.value = 'custom'
}

function goToPrevPage() {
  if (page.value <= 1)
    return
  page.value -= 1
  loadEvents(true)
}

function goToNextPage() {
  if (!hasNextPage.value)
    return
  page.value += 1
  loadEvents(true)
}

function eventColor(type: string) {
  if (type === 'check_in')
    return 'success'
  if (type === 'check_out')
    return 'warning'

  return 'info'
}

function typeLabel(type: string) {
  return typeOptions.find(o => o.value === type)?.title ?? type
}

function eventTypeLabel(type: string) {
  return eventTypeOptions.find(o => o.value === type)?.title ?? type.replaceAll('_', ' ')
}

function openCorrectionDialog() {
  correctionError.value = ''
  Object.assign(correctionForm, {
    product_id: '',
    event_type: 'manual_correction',
    location_id: '',
    notes: '',
  })
  correctionDialog.value = true
}

function closeCorrectionDialog() {
  correctionDialog.value = false
  correctionError.value = ''
}

async function handleExport() {
  exporting.value = true
  exportError.value = ''
  try {
    const range = filterDateRange()

    const blob = await exportAttendanceCSV({
      product_id: filters.product_id || undefined,
      product_type: filters.product_type || undefined,
      date_from: range.date_from,
      date_to: range.date_to,
    })

    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const fromPart = filters.date_from || 'all'
    const toPart = filters.date_to || 'all'

    link.href = url
    link.download = `attendance_${fromPart}_${toPart}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }
  catch (e: unknown) {
    exportError.value = formatApiError(e, 'Export failed')
  }
  finally {
    exporting.value = false
  }
}

async function handleCorrection() {
  if (!correctionForm.product_id) {
    correctionError.value = 'Please select a product'

    return
  }
  correcting.value = true
  correctionError.value = ''
  try {
    await createManualCorrection({
      product_id: correctionForm.product_id,
      event_type: correctionForm.event_type,
      location_id: correctionForm.location_id || undefined,
      notes: correctionForm.notes || undefined,
    })
    closeCorrectionDialog()
    await loadEvents(true)
  }
  catch (e: unknown) {
    correctionError.value = formatApiError(e, 'Could not save correction')
  }
  finally {
    correcting.value = false
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
          Attendance Log
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
          @click="loadEvents(true)"
        >
          Refresh
        </VBtn>
      </VCol>
    </VRow>

    <VCard class="mb-4 pa-4">
      <VRow
        dense
        align="end"
        class="mb-2"
      >
        <VCol
          cols="12"
          sm="4"
        >
          <VSelect
            v-model="filters.product_id"
            :items="productSelectItems"
            :label="productsCapped ? 'Product (200+ loaded)' : 'Product'"
            density="compact"
            hide-details
          />
        </VCol>
        <VCol
          cols="12"
          sm="2"
        >
          <VSelect
            v-model="filters.product_type"
            :items="[{ title: 'All Types', value: '' }, ...typeOptions]"
            label="Type"
            density="compact"
            hide-details
          />
        </VCol>
        <VCol
          cols="12"
          sm="2"
        >
          <VSelect
            v-model="filters.event_type"
            :items="eventTypeOptions"
            label="Event"
            density="compact"
            hide-details
          />
        </VCol>
        <VCol
          cols="12"
          sm="2"
        >
          <VTextField
            v-model="filters.date_from"
            label="From"
            type="date"
            density="compact"
            hide-details
            @update:model-value="onManualDateChange"
          />
        </VCol>
        <VCol
          cols="12"
          sm="2"
        >
          <VTextField
            v-model="filters.date_to"
            label="To"
            type="date"
            density="compact"
            hide-details
            @update:model-value="onManualDateChange"
          />
        </VCol>
      </VRow>
      <div class="d-flex flex-wrap align-center gap-2 mb-3">
        <span class="text-caption text-medium-emphasis me-1">Quick range:</span>
        <VBtn
          v-for="preset in datePresets"
          :key="preset.value"
          size="small"
          :variant="activeDatePreset === preset.value ? 'flat' : 'tonal'"
          :color="activeDatePreset === preset.value ? 'primary' : undefined"
          @click="applyDatePreset(preset.value)"
        >
          {{ preset.title }}
        </VBtn>
      </div>
      <div class="d-flex flex-wrap gap-2 justify-sm-end">
        <VBtn
          color="primary"
          prepend-icon="ri-search-line"
          @click="applyFilters"
        >
          Filter
        </VBtn>
        <VBtn
          variant="outlined"
          :loading="exporting"
          :disabled="exporting"
          prepend-icon="ri-download-line"
          @click="handleExport"
        >
          CSV
        </VBtn>
        <VBtn
          variant="tonal"
          color="info"
          prepend-icon="ri-add-line"
          @click="openCorrectionDialog"
        >
          Manual
        </VBtn>
      </div>
    </VCard>

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
          @click="loadEvents(true)"
        >
          Retry
        </VBtn>
      </template>
    </VAlert>

    <VAlert
      v-if="exportError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="exportError = ''"
    >
      {{ exportError }}
    </VAlert>

    <VCard :loading="loading">
      <VCardTitle class="d-flex align-center justify-space-between flex-wrap gap-2">
        <span>Records</span>
        <span
          v-if="listCaption"
          class="text-caption text-medium-emphasis"
        >
          {{ listCaption }}
        </span>
      </VCardTitle>
      <div class="log-table-scroll">
        <VTable class="log-table">
          <thead>
            <tr>
              <th>Date / Time</th>
              <th>Product</th>
              <th>Type</th>
              <th>Event</th>
              <th>Location</th>
              <th class="col-notes">
                Notes
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="evt in events"
              :key="evt.id"
            >
              <td>{{ formatAttendanceDateTime(evt.recorded_at) }}</td>
              <td>{{ evt.product_name || evt.product_code || evt.product_id }}</td>
              <td>
                <VChip
                  v-if="evt.product_type"
                  :color="evt.product_type === 'staff' ? 'info' : 'success'"
                  size="x-small"
                  label
                >
                  {{ typeLabel(evt.product_type) }}
                </VChip>
                <span v-else>—</span>
              </td>
              <td>
                <VChip
                  :color="eventColor(evt.event_type)"
                  size="small"
                  label
                >
                  {{ eventTypeLabel(evt.event_type) }}
                </VChip>
              </td>
              <td>{{ evt.location || '—' }}</td>
              <td class="col-notes">
                {{ evt.notes || '—' }}
              </td>
            </tr>
            <tr v-if="events.length === 0 && !loading && !loadError">
              <td
                colspan="6"
                class="text-center text-medium-emphasis py-6"
              >
                No attendance records found for the selected filters
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <div
        v-if="!loading && events.length > 0"
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
        Swipe sideways to see all columns. Notes are hidden on small screens.
      </div>
    </VCard>

    <VDialog
      v-model="correctionDialog"
      max-width="500"
      scrollable
    >
      <VCard>
        <VCardTitle>Manual Correction</VCardTitle>
        <VDivider />
        <VCardText class="pa-4">
          <VAlert
            v-if="correctionError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-4"
            closable
            @click:close="correctionError = ''"
          >
            {{ correctionError }}
          </VAlert>
          <VForm @submit.prevent="handleCorrection">
            <VSelect
              v-model="correctionForm.product_id"
              :items="products.map(p => ({ title: `${p.full_name} (${p.code})`, value: p.id }))"
              label="Product *"
              density="compact"
              variant="outlined"
              class="mb-3"
            />
            <VSelect
              v-model="correctionForm.event_type"
              :items="eventTypeOptions.filter(o => o.value !== '')"
              label="Event Type"
              density="compact"
              variant="outlined"
              class="mb-3"
            />
            <VSelect
              v-model="correctionForm.location_id"
              :items="[{ title: '— no location —', value: '' }, ...locations.map(l => ({ title: `${l.name_zh}${l.name_en ? ` / ${l.name_en}` : ''}`, value: l.id }))]"
              label="Location"
              prepend-inner-icon="ri-map-pin-line"
              density="compact"
              variant="outlined"
              class="mb-3"
            />
            <VTextarea
              v-model="correctionForm.notes"
              label="Notes"
              rows="2"
              density="compact"
              variant="outlined"
            />
          </VForm>
        </VCardText>
        <VDivider />
        <DialogFooter>
          <VBtn
            variant="outlined"
            color="primary"
            @click="closeCorrectionDialog"
          >
            Cancel
          </VBtn>
          <VBtn
            variant="flat"
            color="primary"
            :loading="correcting"
            @click="handleCorrection"
          >
            Save
          </VBtn>
        </DialogFooter>
      </VCard>
    </VDialog>
  </VContainer>
</template>

<style scoped lang="scss">
.log-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

@media (max-width: 960px) {
  .log-table :deep(.col-notes) {
    display: none;
  }
}
</style>
