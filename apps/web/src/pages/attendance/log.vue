<script setup lang="ts">
import { createManualCorrection, exportAttendanceCSV, getAttendanceDayStats, listAttendanceWithTotal, voidAttendanceEvent } from '@/api/attendance/events'
import type { AttendanceDayStats, AttendanceEvent } from '@/api/attendance/events'
import { listProducts } from '@/api/attendance/products'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import type { Product } from '@/api/attendance/products'
import { eventSourceColor, eventSourceLabel, formatAttendanceDateTime, getDateRangeIso, getTodayRangeIso, shiftDateKey } from '@/utils/attendanceDisplay'
import { formatApiError } from '@/utils/formatApiDetail'

definePage({ meta: {} })

const PRODUCT_PAGE_SIZE = 200
const { authStore, ensureAccess } = useAttendanceAdminGate()
const {
  page,
  pageSize,
  pageSizeOptions,
  totalCount,
  totalPages,
  listCaption: pagedListCaption,
  resetPage,
} = usePagedList({ pageSize: 40 })

const todayKey = getTodayRangeIso().dateKey

const events = ref<AttendanceEvent[]>([])
const dayStats = ref<AttendanceDayStats | null>(null)
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
  source: '' as string,
  include_voided: false,
})


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
const voidingId = ref<string | null>(null)
const voidError = ref('')
const voidConfirmDialog = ref(false)
const voidTarget = ref<AttendanceEvent | null>(null)

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

const sourceOptions = [
  { title: 'All sources', value: '' },
  { title: 'Scan', value: 'scan' },
  { title: 'Manual', value: 'manual' },
  { title: 'Auto checkout', value: 'auto_checkout' },
]

const datePresets = [
  { title: 'Today', value: 'today' },
  { title: 'Last 7 days', value: '7d' },
  { title: 'Last 30 days', value: '30d' },
  { title: 'All time', value: 'all' },
] as const

type DatePreset = typeof datePresets[number]['value'] | 'custom'

const activeDatePreset = ref<DatePreset>('today')

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

  return pagedListCaption(events.value.length)
})

const dayStatCards = computed(() => {
  const s = dayStats.value
  if (!s) {
    return [
      { label: 'Events', value: '—', hint: 'selected range', icon: 'ri-file-list-3-line', color: 'primary' },
      { label: 'Check in', value: '—', hint: 'staff + student', icon: 'ri-login-circle-line', color: 'success' },
      { label: 'Check out', value: '—', hint: 'staff + student', icon: 'ri-logout-circle-line', color: 'warning' },
      { label: 'Staff / Student in', value: '—', hint: 'check-ins by type', icon: 'ri-group-line', color: 'info' },
    ]
  }

  const checkIns = s.check_ins_staff + s.check_ins_student
  const checkOuts = s.check_outs_staff + s.check_outs_student

  return [
    {
      label: 'Events',
      value: String(s.total),
      hint: 'selected range total',
      icon: 'ri-file-list-3-line',
      color: 'primary',
    },
    {
      label: 'Check in',
      value: String(checkIns),
      hint: `${s.check_ins_staff} staff · ${s.check_ins_student} student`,
      icon: 'ri-login-circle-line',
      color: 'success',
    },
    {
      label: 'Check out',
      value: String(checkOuts),
      hint: `${s.check_outs_staff} staff · ${s.check_outs_student} student`,
      icon: 'ri-logout-circle-line',
      color: 'warning',
    },
    {
      label: 'Staff / Student in',
      value: `${s.check_ins_staff} / ${s.check_ins_student}`,
      hint: 'check-ins by type',
      icon: 'ri-group-line',
      color: 'info',
    },
  ]
})

const productSelectItems = computed(() => [
  { title: 'All Products', value: '' },
  ...products.value.map(p => ({ title: `${p.full_name} (${p.code})`, value: p.id })),
])

const productsCapped = computed(() => products.value.length >= PRODUCT_PAGE_SIZE)

const filtersReady = ref(false)

onMounted(async () => {
  if (!(await ensureAccess()))
    return

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
  filtersReady.value = true
})

watch(
  () => [
    filters.product_id,
    filters.product_type,
    filters.event_type,
    filters.source,
    filters.date_from,
    filters.date_to,
    filters.include_voided,
  ],
  () => {
    if (!filtersReady.value)
      return
    loadEvents(false, true)
  },
)

function filterDateRange() {
  return getDateRangeIso(filters.date_from, filters.date_to)
}

async function loadEvents(isRefresh = false, shouldResetPage = false) {
  if (shouldResetPage)
    resetPage()
  if (isRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const range = filterDateRange()
    const listParams = {
      product_id: filters.product_id || undefined,
      product_type: filters.product_type || undefined,
      date_from: range.date_from,
      date_to: range.date_to,
      event_type: filters.event_type || undefined,
      source: filters.source || undefined,
      include_voided: filters.include_voided || undefined,
      page: page.value,
      page_size: pageSize.value,
    }
    const [result, stats] = await Promise.all([
      listAttendanceWithTotal(listParams),
      getAttendanceDayStats({
        date_from: range.date_from,
        date_to: range.date_to,
      }),
    ])

    events.value = result.items
    totalCount.value = result.total
    dayStats.value = stats
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
      include_voided: filters.include_voided || undefined,
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

function openVoidDialog(evt: AttendanceEvent) {
  voidTarget.value = evt
  voidConfirmDialog.value = true
}

function closeVoidDialog() {
  voidConfirmDialog.value = false
  voidTarget.value = null
}

async function confirmVoid() {
  if (!voidTarget.value)
    return
  voidingId.value = voidTarget.value.id
  voidError.value = ''
  try {
    await voidAttendanceEvent(voidTarget.value.id)
    closeVoidDialog()
    await loadEvents(true)
  }
  catch (e: unknown) {
    voidError.value = formatApiError(e, 'Could not void event')
    loadError.value = voidError.value
  }
  finally {
    voidingId.value = null
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
          <VSelect
            v-model="filters.source"
            :items="sourceOptions"
            label="Source"
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
      <!-- <VAlert
        v-if="activeDatePreset === 'today'"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-3"
      >
        Day-end checkout is stored at <strong>23:59</strong>. Older runs used UTC, so they may fall on
        <strong>tomorrow morning</strong> in Hong Kong and will not appear under Today.
        Use <strong>All time</strong> (or extend To to tomorrow) and Source = <strong>Auto checkout</strong> to find them.
      </VAlert> -->
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
        <VCheckbox
          v-model="filters.include_voided"
          label="Show voided"
          density="compact"
          hide-details
          class="ms-sm-2"
        />
      </div>
      <div class="d-flex flex-wrap gap-2 justify-sm-end">
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

    <StatCards :cards="dayStatCards" />

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
              <th width="140">
                Date / Time
              </th>
              <th width="160">
                Product
              </th>
              <th width="80">
                Type
              </th>
              <th width="100">
                Event
              </th>
              <th width="100">
                Source
              </th>
              <th>
                Location
              </th>
              <th class="col-notes">
                Notes
              </th>
              <th class="col-actions">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="evt in events"
              :key="evt.id"
              :class="{ 'event-voided': !!evt.voided_at }"
            >
              <td>
                <span :class="{ 'text-decoration-line-through text-medium-emphasis': evt.voided_at }">
                  {{ formatAttendanceDateTime(evt.recorded_at) }}
                </span>
                <VChip
                  v-if="evt.voided_at"
                  color="error"
                  size="x-small"
                  label
                  class="ms-1"
                >
                  VOIDED
                </VChip>
              </td>
              <td :class="{ 'text-medium-emphasis': evt.voided_at }">
                {{ evt.product_name || evt.product_code || evt.product_id }}
              </td>
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
              <td>
                <VChip
                  :color="eventSourceColor(evt.source)"
                  size="small"
                  label
                  :prepend-icon="evt.source === 'auto_checkout' ? 'ri-time-line' : undefined"
                  :title="evt.source === 'auto_checkout' ? (evt.notes || 'Day-boundary auto checkout (23:59)') : undefined"
                >
                  {{ eventSourceLabel(evt.source) }}
                </VChip>
              </td>
              <td :class="{ 'text-medium-emphasis': evt.voided_at }">
                {{ evt.location || '—' }}
              </td>
              <td class="col-notes" :class="{ 'text-medium-emphasis': evt.voided_at }">
                {{ evt.notes || '—' }}
              </td>
              <td class="col-actions">
                <VBtn
                  v-if="!evt.voided_at && authStore.isAdmin"
                  icon
                  size="small"
                  variant="text"
                  color="error"
                  :loading="voidingId === evt.id"
                  title="Void event"
                  @click="openVoidDialog(evt)"
                >
                  <VIcon icon="ri-forbid-line" />
                </VBtn>
              </td>
            </tr>
            <tr v-if="events.length === 0 && !loading && !loadError">
              <td
                colspan="8"
                class="text-center text-medium-emphasis py-6"
              >
                No attendance records found for the selected filters
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <AttendancePaginationBar
        v-if="!loading && events.length > 0"
        v-model:page="page"
        v-model:page-size="pageSize"
        :total-pages="totalPages"
        :page-size-options="pageSizeOptions"
        @change="loadEvents(true)"
      />
      <div class="text-caption text-medium-emphasis px-4 pb-3 d-md-none">
        Swipe sideways to see all columns. Notes are hidden on small screens.
      </div>
    </VCard>

    <AttendanceFormDialog
      v-model="correctionDialog"
      title="Manual Correction"
      icon="ri-edit-box-line"
      :saving="correcting"
      :error="correctionError"
      @save="handleCorrection"
      @cancel="closeCorrectionDialog"
      @clear-error="correctionError = ''"
    >
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
    </AttendanceFormDialog>

    <VDialog
      v-model="voidConfirmDialog"
      max-width="400"
    >
      <VCard>
        <VCardTitle class="text-h6">
          Confirm Void
        </VCardTitle>
        <VCardText>
          Void attendance event for <strong>{{ voidTarget?.product_name || voidTarget?.product_code || voidTarget?.product_id }}</strong>?<br>
          <span class="text-medium-emphasis">This action cannot be undone.</span>
        </VCardText>
        <VCardActions class="justify-end">
          <VBtn
            variant="text"
            @click="closeVoidDialog"
          >
            Cancel
          </VBtn>
          <VBtn
            color="error"
            variant="flat"
            :loading="voidingId === voidTarget?.id"
            @click="confirmVoid"
          >
            Void Event
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>

<style scoped lang="scss">
.log-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.log-table :deep(thead th),
.log-table :deep(tbody td) {
  vertical-align: middle;
  white-space: nowrap;
}

.log-table :deep(.col-actions) {
  width: 1%;
  white-space: nowrap;
}

.event-voided {
  opacity: 0.65;
}

@media (max-width: 960px) {
  .log-table :deep(.col-notes) {
    display: none;
  }
}
</style>
