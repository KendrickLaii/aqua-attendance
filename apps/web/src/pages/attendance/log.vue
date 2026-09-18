<script setup lang="ts">
import { exportAttendanceCSV, getAttendanceDayStats, listAttendanceWithTotal, voidAttendanceEvent } from '@/api/attendance/events'
import type { AttendanceDayStats, AttendanceEvent } from '@/api/attendance/events'
import { getUnit, listUnits } from '@/api/attendance/units'
import type { Unit } from '@/api/attendance/units'
import { eventSourceColor, eventSourceLabel, formatAttendanceDateTime, formatAttendanceTime, getDateRangeIso, getTodayRangeIso, shiftDateKey } from '@/utils/attendanceDisplay'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

definePage({ meta: {} })

const UNIT_PAGE_SIZE = 200
const UNIT_SEARCH_SIZE = 30
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
const units = ref<Unit[]>([])
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')

const filters = reactive({
  unit_id: '' as string,
  unit_type: '' as string,
  date_from: todayKey,
  date_to: todayKey,
  event_type: '' as string,
  source: '' as string,
  include_voided: false,
})

const correctionDialog = ref(false)

const exporting = ref(false)
const exportError = ref('')

useAutoClearAlerts(loadError, exportError)

const voidingId = ref<string | null>(null)
const voidError = ref('')
const voidConfirmDialog = ref(false)
const voidTarget = ref<AttendanceEvent | null>(null)

const selectedUnit = ref<Unit | null>(null)
const unitSearch = ref('')
const unitOptions = ref<Unit[]>([])
const unitSearchLoading = ref(false)

const typeOptions = [
  { title: 'All', value: '' },
  { title: 'Student', value: 'student' },
  { title: 'Staff', value: 'staff' },
]

const eventTypeOptions = [
  { title: 'All', value: 'all' },
  { title: 'In', value: 'check_in' },
  { title: 'Out', value: 'check_out' },
]

const sourceOptions = [
  { title: 'All', value: 'all' },
  { title: 'Scan', value: 'scan' },
  { title: 'Manual', value: 'manual' },
  { title: 'Auto', value: 'auto_checkout' },
]

const datePresets = [
  { title: 'Today', value: 'today' },
  { title: '7 days', value: '7d' },
  { title: '30 days', value: '30d' },
  { title: 'All time', value: 'all' },
] as const

type DatePreset = typeof datePresets[number]['value'] | 'custom'

const activeDatePreset = ref<DatePreset>('today')

function chipFilterValue(value: unknown): string {
  if (Array.isArray(value))
    return String(value[0] ?? 'all')
  if (value == null || value === '')
    return 'all'

  return String(value)
}

const eventFilter = computed({
  get: () => filters.event_type || 'all',
  set: (value: unknown) => {
    const next = chipFilterValue(value)

    filters.event_type = next === 'all' ? '' : next
  },
})

const sourceFilter = computed({
  get: () => filters.source || 'all',
  set: (value: unknown) => {
    const next = chipFilterValue(value)

    filters.source = next === 'all' ? '' : next
  },
})

const selectedUnitId = computed({
  get: () => filters.unit_id || null,
  set: (value: string | null) => {
    filters.unit_id = value || ''
    if (!value) {
      selectedUnit.value = null

      return
    }

    const found = unitOptions.value.find(u => u.id === value)
      || units.value.find(u => u.id === value)
      || (selectedUnit.value?.id === value ? selectedUnit.value : null)

    if (found) {
      selectedUnit.value = found
      if (found.unit_type)
        filters.unit_type = found.unit_type
    }
  },
})

const unitItems = computed(() => {
  const selected = selectedUnit.value

  const list = selected && !unitOptions.value.some(u => u.id === selected.id)
    ? [selected, ...unitOptions.value]
    : unitOptions.value

  return list.map(u => ({
    title: `${u.full_name} (${u.code})`,
    value: u.id,
    subtitle: `${u.code} · ${typeLabel(u.unit_type)}`,
    raw: u,
  }))
})

const personSearchPlaceholder = computed(() => {
  if (filters.unit_type === 'staff')
    return 'Search staff name or code'
  if (filters.unit_type === 'student')
    return 'Search student name or code'

  return 'Search name or code'
})

const selectedTypeLabel = computed(() =>
  typeOptions.find(o => o.value === filters.unit_type)?.title ?? 'All',
)

const hasActiveFilters = computed(() =>
  Boolean(filters.unit_id)
  || Boolean(filters.unit_type)
  || Boolean(filters.event_type)
  || Boolean(filters.source)
  || filters.include_voided
  || activeDatePreset.value !== 'today',
)

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  const preset = activeDatePreset.value === 'custom'
    ? 'Custom range'
    : datePresets.find(p => p.value === activeDatePreset.value)?.title ?? 'Custom range'

  const who = selectedUnit.value
    ? selectedUnit.value.full_name
    : selectedTypeLabel.value === 'All' ? 'Everyone' : `${selectedTypeLabel.value}s`

  const pageLabel = totalPages.value > 1 ? ` · page ${page.value} of ${totalPages.value}` : ''

  if (totalCount.value === 0)
    return `${who} · ${preset} · no records`

  return `${totalCount.value} record${totalCount.value === 1 ? '' : 's'} · ${who} · ${preset}${pageLabel}`
})

const listCaption = computed(() => {
  if (loading.value || totalCount.value === 0)
    return ''

  return pagedListCaption(events.value.length)
})

const recordsTitle = computed(() => {
  if (selectedUnit.value)
    return selectedUnit.value.full_name

  if (filters.unit_type === 'staff')
    return 'Staff records'

  if (filters.unit_type === 'student')
    return 'Student records'

  return 'Records'
})

const emptyStateMessage = computed(() => {
  if (selectedUnit.value)
    return `No events for ${selectedUnit.value.full_name} in this range`

  if (hasActiveFilters.value)
    return 'No records match these filters'

  return 'No attendance records today'
})

const statsCaption = computed(() => {
  if (!selectedUnit.value)
    return ''

  return `Totals below are for this date range, not only ${selectedUnit.value.full_name}.`
})

const dayStatCards = computed(() => {
  const s = dayStats.value
  const type = filters.unit_type
  const typeHint = type === 'staff' ? 'staff' : type === 'student' ? 'student' : 'staff + student'

  if (!s) {
    return [
      { label: 'Events', value: '—', hint: 'selected range', icon: 'ri-file-list-3-line', color: 'primary' },
      { label: 'Check in', value: '—', hint: typeHint, icon: 'ri-login-circle-line', color: 'success' },
      { label: 'Check out', value: '—', hint: typeHint, icon: 'ri-logout-circle-line', color: 'warning' },
      { label: 'Staff / Student in', value: '—', hint: 'all types in this date range', icon: 'ri-group-line', color: 'info' },
    ]
  }

  const checkIns = type === 'staff'
    ? s.check_ins_staff
    : type === 'student'
      ? s.check_ins_student
      : s.check_ins_staff + s.check_ins_student

  const checkOuts = type === 'staff'
    ? s.check_outs_staff
    : type === 'student'
      ? s.check_outs_student
      : s.check_outs_staff + s.check_outs_student

  return [
    {
      label: 'Events',
      value: String(type ? checkIns + checkOuts : s.total),
      hint: type ? `${typeHint} in selected range` : 'selected range total',
      icon: 'ri-file-list-3-line',
      color: 'primary',
    },
    {
      label: 'Check in',
      value: String(checkIns),
      hint: type
        ? typeHint
        : `${s.check_ins_staff} staff · ${s.check_ins_student} student`,
      icon: 'ri-login-circle-line',
      color: 'success',
    },
    {
      label: 'Check out',
      value: String(checkOuts),
      hint: type
        ? typeHint
        : `${s.check_outs_staff} staff · ${s.check_outs_student} student`,
      icon: 'ri-logout-circle-line',
      color: 'warning',
    },
    {
      label: 'Staff / Student in',
      value: `${s.check_ins_staff} / ${s.check_ins_student}`,
      hint: 'all types in this date range',
      icon: 'ri-group-line',
      color: 'info',
    },
  ]
})

const filtersReady = ref(false)
const route = useRoute()

onMounted(async () => {
  if (!(await ensureAccess()))
    return

  const unitFromQuery = typeof route.query.unit_id === 'string' ? route.query.unit_id : ''
  if (unitFromQuery) {
    filters.unit_id = unitFromQuery
    activeDatePreset.value = 'all'
    filters.date_from = ''
    filters.date_to = ''
  }

  try {
    units.value = await listUnits({ page_size: UNIT_PAGE_SIZE })
  }
  catch (e) {
    console.error('Failed to load units for log filters', e)
  }

  if (unitFromQuery)
    await resolveSelectedUnit(unitFromQuery)

  seedUnitOptions()
  await loadEvents()
  filtersReady.value = true
})

watch(
  () => [
    filters.unit_id,
    filters.unit_type,
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

function seedUnitOptions(query = '') {
  const q = (query || unitSearch.value).trim().toLowerCase()
  let list = units.value

  if (filters.unit_type)
    list = list.filter(u => u.unit_type === filters.unit_type)

  if (q) {
    list = list.filter(u =>
      u.full_name.toLowerCase().includes(q)
      || u.code.toLowerCase().includes(q)
      || (u.english_name?.toLowerCase().includes(q) ?? false),
    )
  }

  unitOptions.value = list.slice(0, 30)
}

const searchUnits = useDebounceFn(async () => {
  const q = unitSearch.value.trim()
  if (!q) {
    seedUnitOptions()

    return
  }

  unitSearchLoading.value = true
  try {
    unitOptions.value = await listUnits({
      search: q,
      unit_type: filters.unit_type || undefined,
      page_size: UNIT_SEARCH_SIZE,
    })
  }
  catch (e) {
    console.error('Failed to search people for log filters', e)
    seedUnitOptions(q)
  }
  finally {
    unitSearchLoading.value = false
  }
}, 300)

watch(unitSearch, value => {
  const selectedTitle = selectedUnit.value
    ? `${selectedUnit.value.full_name} (${selectedUnit.value.code})`
    : ''

  if (!value?.trim() || value === selectedTitle)
    seedUnitOptions()
  else
    searchUnits()
})

async function resolveSelectedUnit(id: string) {
  const found = units.value.find(u => u.id === id)
    || unitOptions.value.find(u => u.id === id)
    || (selectedUnit.value?.id === id ? selectedUnit.value : null)

  if (found) {
    selectedUnit.value = found
    if (!filters.unit_type)
      filters.unit_type = found.unit_type

    return
  }

  try {
    selectedUnit.value = await getUnit(id)
    if (!filters.unit_type && selectedUnit.value)
      filters.unit_type = selectedUnit.value.unit_type
  }
  catch (e) {
    console.error('Failed to load person for log filters', e)
    selectedUnit.value = null
  }
}

function setUnitType(value: string) {
  filters.unit_type = value

  if (selectedUnit.value && value && selectedUnit.value.unit_type !== value) {
    selectedUnit.value = null
    filters.unit_id = ''
    unitSearch.value = ''
  }

  if (unitSearch.value.trim())
    searchUnits()
  else
    seedUnitOptions()
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
      unit_id: filters.unit_id || undefined,
      unit_type: filters.unit_type || undefined,
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
        include_voided: filters.include_voided || undefined,
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

function applyDatePreset(preset: Exclude<DatePreset, 'custom'>) {
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
  else if (preset === 'all') {
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

function resetFilters() {
  selectedUnit.value = null
  unitSearch.value = ''
  filters.unit_id = ''
  filters.unit_type = ''
  filters.event_type = ''
  filters.source = ''
  filters.include_voided = false
  applyDatePreset('today')
  seedUnitOptions()
}

function eventColor(type: string) {
  if (type === 'check_in')
    return 'success'
  if (type === 'check_out')
    return 'warning'

  return 'info'
}

function typeLabel(type: string) {
  if (type === 'student')
    return 'Student'
  if (type === 'staff')
    return 'Staff'

  return type
}

function eventTypeLabel(type: string) {
  if (type === 'check_in')
    return 'Check in'
  if (type === 'check_out')
    return 'Check out'

  return type.replaceAll('_', ' ')
}

function eventDateLabel(iso: string) {
  const full = formatAttendanceDateTime(iso)
  const time = formatAttendanceTime(iso)
  if (full === '—' || time === '—')
    return full

  return full.endsWith(` ${time}`)
    ? full.slice(0, -(time.length + 1))
    : full
}

function openCorrectionDialog() {
  correctionDialog.value = true
}

async function handleExport() {
  exporting.value = true
  exportError.value = ''
  try {
    const range = filterDateRange()

    const blob = await exportAttendanceCSV({
      unit_id: filters.unit_id || undefined,
      unit_type: filters.unit_type || undefined,
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
        sm="7"
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
        sm="5"
        class="d-flex flex-wrap justify-sm-end gap-2"
      >
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

    <VCard class="mb-4">
      <VCardText class="pa-4">
        <div class="filter-primary mb-4">
          <div
            class="d-flex flex-wrap align-center gap-2"
            role="group"
            aria-label="Person type"
          >
            <VBtn
              v-for="opt in typeOptions"
              :key="opt.value || 'all'"
              :variant="filters.unit_type === opt.value ? 'flat' : 'tonal'"
              :color="filters.unit_type === opt.value ? 'primary' : undefined"
              :aria-pressed="filters.unit_type === opt.value"
              @click="setUnitType(opt.value)"
            >
              {{ opt.title }}
            </VBtn>
          </div>

          <VAutocomplete
            v-model="selectedUnitId"
            v-model:search="unitSearch"
            :items="unitItems"
            :loading="unitSearchLoading"
            item-title="title"
            item-value="value"
            :label="filters.unit_type === 'staff' ? 'Staff' : filters.unit_type === 'student' ? 'Student' : 'Person'"
            :placeholder="personSearchPlaceholder"
            prepend-inner-icon="ri-search-line"
            density="compact"
            hide-details
            clearable
            no-filter
            class="filter-person"
          >
            <template #item="{ props: itemProps, item }">
              <VListItem
                v-bind="itemProps"
                :title="item.raw.title"
                :subtitle="item.raw.subtitle"
              />
            </template>
          </VAutocomplete>
        </div>

        <div class="filter-dates mb-4">
          <span class="text-caption text-medium-emphasis filter-dates__label">Date</span>
          <div class="d-flex flex-wrap align-center gap-2">
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
            <VBtn
              v-if="activeDatePreset === 'custom'"
              size="small"
              variant="flat"
              color="primary"
            >
              Custom
            </VBtn>
          </div>
          <VTextField
            v-model="filters.date_from"
            label="From"
            type="date"
            density="compact"
            hide-details
            class="filter-date-field"
            @update:model-value="onManualDateChange"
          />
          <VTextField
            v-model="filters.date_to"
            label="To"
            type="date"
            density="compact"
            hide-details
            class="filter-date-field"
            @update:model-value="onManualDateChange"
          />
        </div>

        <div class="filter-secondary">
          <div class="filter-chip-block">
            <span class="text-caption text-medium-emphasis">Event</span>
            <VChipGroup
              v-model="eventFilter"
              mandatory
              selected-class="text-primary"
            >
              <VChip
                v-for="opt in eventTypeOptions"
                :key="opt.value"
                :value="opt.value"
                size="small"
                variant="outlined"
                filter
                class="text-no-wrap"
              >
                {{ opt.title }}
              </VChip>
            </VChipGroup>
          </div>

          <div class="filter-chip-block">
            <span class="text-caption text-medium-emphasis">Source</span>
            <VChipGroup
              v-model="sourceFilter"
              mandatory
              selected-class="text-primary"
            >
              <VChip
                v-for="opt in sourceOptions"
                :key="opt.value"
                :value="opt.value"
                size="small"
                variant="outlined"
                filter
                class="text-no-wrap"
                :title="opt.value === 'auto_checkout' ? 'Day-end auto checkout' : undefined"
              >
                {{ opt.title }}
              </VChip>
            </VChipGroup>
          </div>

          <VCheckbox
            v-model="filters.include_voided"
            label="Show voided"
            density="compact"
            hide-details
          />

          <VSpacer />

          <VBtn
            v-if="hasActiveFilters"
            size="small"
            variant="text"
            prepend-icon="ri-filter-off-line"
            @click="resetFilters"
          >
            Reset
          </VBtn>
        </div>
      </VCardText>
    </VCard>

    <div
      v-if="statsCaption"
      class="text-caption text-medium-emphasis mb-2"
    >
      {{ statsCaption }}
    </div>
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
        <span>{{ recordsTitle }}</span>
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
              <th width="150">
                Date / Time
              </th>
              <th width="220">
                Person
              </th>
              <th width="110">
                Event
              </th>
              <th width="120">
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
                <div :class="{ 'text-decoration-line-through text-medium-emphasis': evt.voided_at }">
                  <div class="text-body-2">
                    {{ eventDateLabel(evt.recorded_at) }}
                  </div>
                  <div class="text-caption text-medium-emphasis">
                    {{ formatAttendanceTime(evt.recorded_at) }}
                  </div>
                </div>
                <VChip
                  v-if="evt.voided_at"
                  color="error"
                  size="x-small"
                  label
                  class="mt-1"
                >
                  VOIDED
                </VChip>
              </td>
              <td>
                <div class="d-flex align-center gap-2">
                  <div :class="{ 'text-medium-emphasis': evt.voided_at }">
                    <div class="font-weight-medium">
                      {{ evt.unit_name || evt.unit_code || evt.unit_id }}
                    </div>
                    <div
                      v-if="evt.unit_code && evt.unit_name"
                      class="text-caption text-medium-emphasis"
                    >
                      {{ evt.unit_code }}
                    </div>
                  </div>
                  <VChip
                    v-if="evt.unit_type"
                    :color="evt.unit_type === 'staff' ? 'info' : 'success'"
                    size="x-small"
                    label
                    class="flex-shrink-0"
                  >
                    {{ typeLabel(evt.unit_type) }}
                  </VChip>
                </div>
              </td>
              <td>
                <VChip
                  :color="eventColor(evt.event_type)"
                  size="small"
                  label
                  :prepend-icon="evt.event_type === 'check_in' ? 'ri-login-circle-line' : 'ri-logout-circle-line'"
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
              <td
                class="col-notes"
                :class="{ 'text-medium-emphasis': evt.voided_at }"
              >
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
                colspan="7"
                class="text-center py-8"
              >
                <div class="text-medium-emphasis mb-3">
                  {{ emptyStateMessage }}
                </div>
                <VBtn
                  v-if="hasActiveFilters"
                  size="small"
                  variant="tonal"
                  prepend-icon="ri-filter-off-line"
                  @click="resetFilters"
                >
                  Reset filters
                </VBtn>
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

    <ManualCorrectionDialog
      v-model="correctionDialog"
      :unit-catalog="units"
      @saved="loadEvents(true)"
    />

    <VDialog
      v-model="voidConfirmDialog"
      max-width="400"
    >
      <VCard>
        <VCardTitle class="text-h6">
          Confirm Void
        </VCardTitle>
        <VCardText>
          Void attendance event for <strong>{{ voidTarget?.unit_name || voidTarget?.unit_code || voidTarget?.unit_id }}</strong>?<br>
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
.filter-primary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.filter-person {
  flex: 1 1 240px;
  min-width: min(100%, 220px);
  max-width: 420px;
}

.filter-dates {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
}

.filter-dates__label {
  width: 100%;
}

.filter-date-field {
  width: 160px;
  max-width: 100%;
}

.filter-secondary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  align-items: center;
}

.filter-chip-block {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
  align-items: center;
}

.log-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.log-table :deep(thead th),
.log-table :deep(tbody td) {
  vertical-align: middle;
}

.log-table :deep(thead th) {
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
