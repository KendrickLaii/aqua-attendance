<script setup lang="ts">
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import {
  type Shift,
  type ShiftTemplate,
  copyShiftWeek,
  createShift,
  approveShiftRequest,
  listShiftRequests,
  listShiftTemplates,
  listShifts,
  rejectShiftRequest,
  updateShift,
  type ShiftRequest,
} from '@/api/attendance/shifts'
import { type Unit, listAllUnits } from '@/api/attendance/units'
import ShiftDialog from '@/components/attendance/shifts/ShiftDialog.vue'
import ShiftPrintDialog from '@/components/attendance/shifts/ShiftPrintDialog.vue'
import ShiftTemplatesDialog from '@/components/attendance/shifts/ShiftTemplatesDialog.vue'
import ShiftWeekGrid from '@/components/attendance/shifts/ShiftWeekGrid.vue'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { useToast } from '@/composables/useToast'
import { formatApiError } from '@/utils/formatApiDetail'
import {
  ADMIN_PENDING_REQUESTS_HINT,
  ADMIN_REJECT_REASON_HINT,
  ADMIN_SHIFT_PAGE_HINT,
} from '@/utils/shiftStaffCopy'
import { type ShiftPrintChoice, type ShiftPrintPeriod, printShiftWeek } from '@/utils/printShiftWeek'
import {
  addDays,
  buildShiftCsv,
  formatDayHeader,
  formatMonthLabel,
  formatShiftHours,
  formatWeekRange,
  groupShiftsByCell,
  hhmm,
  mondayOf,
  monthDates,
  monthOfWeek,
  monthOptions,
  overlappingShiftIds,
  parseIsoDate,
  staffRowsForLocation,
  toIsoDate,
  totalMinutes,
  weekDates,
  weekFromQuery,
} from '@/utils/shiftDisplay'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()
const toast = useToast()
const route = useRoute()
const router = useRouter()

const loading = ref(true)
const shiftsLoading = ref(false)
const loadError = ref('')

useAutoClearAlerts(loadError)

const staff = ref<Unit[]>([])
const locations = ref<LocationItem[]>([])
const templates = ref<ShiftTemplate[]>([])
const shifts = ref<Shift[]>([])
const pendingRequests = ref<ShiftRequest[]>([])
const rejectTarget = ref<ShiftRequest | null>(null)
const rejectReason = ref('')
const reviewBusy = ref(false)

const today = toIsoDate(new Date())
const thisWeek = mondayOf(new Date())
const weekStart = ref(weekFromQuery(route.query.week))
const locationId = ref<string | null>(typeof route.query.location === 'string' ? route.query.location : null)
const search = ref('')

const dates = computed(() => weekDates(weekStart.value))
const weekLabel = computed(() => formatWeekRange(weekStart.value))
const isThisWeek = computed(() => weekStart.value === thisWeek)

const locationName = (l: LocationItem) => [l.name_en, l.name_zh].filter(Boolean).join(' · ')
const locationById = computed(() => new Map(locations.value.map(l => [l.id, l])))
const locationOptions = computed(() => locations.value.map(l => ({ value: l.id, title: locationName(l) })))
const locationFilterItems = computed(() => [{ value: null, title: 'All locations' }, ...locationOptions.value])

const locationLabel = computed(() => {
  const loc = locationId.value ? locationById.value.get(locationId.value) : null

  return loc ? locationName(loc) : 'All locations'
})

const staffOptions = computed(() =>
  staff.value
    .filter(u => u.is_active)
    .map(u => ({ value: u.id, title: `${u.full_name} · ${u.code}` })),
)

function matchSearch(list: Unit[]) {
  const q = search.value.trim().toLowerCase()
  if (!q)
    return list

  return list.filter(u => [u.full_name, u.english_name, u.code].some(v => v?.toLowerCase().includes(q)))
}

const rows = computed(() => matchSearch(staffRowsForLocation(staff.value, shifts.value, locationId.value)))

const shiftsByCell = computed(() => groupShiftsByCell(shifts.value))
const overlapIds = computed(() => overlappingShiftIds(shifts.value))

const stats = computed(() => ({
  shifts: shifts.value.length,
  staff: new Set(shifts.value.map(s => s.unit_id)).size,
  hours: formatShiftHours(totalMinutes(shifts.value)),
  overlaps: overlapIds.value.size,
}))

// ---- Loading ----

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  await loadAll()
})

async function loadTemplates() {
  templates.value = await listShiftTemplates()
}

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    const [staffList, locationList] = await Promise.all([
      listAllUnits({ unit_type: 'staff' }),
      listLocations({ is_active: true }),
      loadTemplates(),
    ])

    staff.value = [...staffList].sort((a, b) => a.full_name.localeCompare(b.full_name))
    locations.value = [...locationList].sort((a, b) => a.name_en.localeCompare(b.name_en))
    if (locationId.value && !locations.value.some(l => l.id === locationId.value))
      locationId.value = null
    await Promise.all([loadShifts(), loadPendingRequests()])
  }
  catch (e) {
    console.error('Failed to load shifts', e)
    loadError.value = formatApiError(e, 'Failed to load shift schedule.')
  }
  finally {
    loading.value = false
  }
}

let shiftsRequest = 0

async function loadShifts() {
  const requestId = ++shiftsRequest

  shiftsLoading.value = true
  try {
    const list = await listShifts({
      start: weekStart.value,
      end: addDays(weekStart.value, 6),
      ...(locationId.value ? { location_id: locationId.value } : {}),
    })

    if (requestId === shiftsRequest)
      shifts.value = list
  }
  catch (e) {
    if (requestId === shiftsRequest)
      loadError.value = formatApiError(e, 'Failed to load shifts.')
  }
  finally {
    if (requestId === shiftsRequest)
      shiftsLoading.value = false
  }
}

watch([weekStart, locationId], ([week, location]) => {
  router.replace({ query: { ...route.query, week, location: location ?? undefined } })
  if (!loading.value)
    loadShifts()
})

function shiftWeek(delta: number) {
  weekStart.value = addDays(weekStart.value, delta * 7)
}

const datePickerOpen = ref(false)

function jumpTo(value: unknown) {
  if (!value)
    return
  weekStart.value = mondayOf(value instanceof Date ? value : new Date(String(value)))
  datePickerOpen.value = false
}

// ---- Add / edit ----

const shiftDialogOpen = ref(false)
const editingShift = ref<Shift | null>(null)
const newShift = reactive({ unitId: null as string | null, date: null as string | null, locationId: null as string | null })
const templatesDialogOpen = ref(false)

const quickMenu = reactive({ open: false, target: null as HTMLElement | null, unit: null as Unit | null, date: '' })
const quickAdding = ref(false)

const quickMenuTitle = computed(() => {
  if (!quickMenu.unit)
    return ''
  const { weekday, day } = formatDayHeader(quickMenu.date)

  return `${quickMenu.unit.full_name} · ${weekday} ${day}`
})

const defaultLocationFor = (unit: Unit) => locationId.value ?? unit.registered_location_id

function openCreate(unit: Unit | null, date: string | null) {
  editingShift.value = null
  Object.assign(newShift, {
    unitId: unit?.id ?? null,
    date: date ?? (dates.value.includes(today) ? today : weekStart.value),
    locationId: unit ? defaultLocationFor(unit) : locationId.value,
  })
  shiftDialogOpen.value = true
}

function onCellAdd(unit: Unit, date: string, target: HTMLElement) {
  if (!templates.value.length) {
    openCreate(unit, date)

    return
  }
  Object.assign(quickMenu, { open: true, target, unit, date })
}

function openCustomFromMenu() {
  quickMenu.open = false
  openCreate(quickMenu.unit, quickMenu.date)
}

async function quickAdd(t: ShiftTemplate) {
  const unit = quickMenu.unit
  if (!unit)
    return
  quickAdding.value = true
  try {
    await createShift({
      unit_id: unit.id,
      location_id: defaultLocationFor(unit),
      shift_date: quickMenu.date,
      start_time: hhmm(t.start_time),
      end_time: hhmm(t.end_time),
      title: t.name,
      color: t.color,
      template_id: t.id,
    })
    quickMenu.open = false
    toast.show(`Added ${t.name} for ${unit.full_name}.`)
    await loadShifts()
  }
  catch (e) {
    toast.show(formatApiError(e, 'Could not add shift.'), 'error', 5000)
  }
  finally {
    quickAdding.value = false
  }
}

function openEdit(shift: Shift) {
  editingShift.value = shift
  shiftDialogOpen.value = true
}

async function onDrop({ shiftId, unitId, date, copy }: { shiftId: string; unitId: string; date: string; copy: boolean }) {
  const shift = shifts.value.find(s => s.id === shiftId)
  if (!shift || (!copy && shift.unit_id === unitId && shift.shift_date === date))
    return

  try {
    if (copy) {
      await createShift({
        unit_id: unitId,
        shift_date: date,
        location_id: shift.location_id,
        start_time: shift.start_time,
        end_time: shift.end_time,
        title: shift.title,
        color: shift.color,
        notes: shift.notes,
        template_id: shift.template_id,
      })
      toast.show('Shift copied.')
    }
    else {
      shifts.value = shifts.value.map(s => (s.id === shiftId ? { ...s, unit_id: unitId, shift_date: date } : s))
      await updateShift(shiftId, { unit_id: unitId, shift_date: date })
      toast.show('Shift moved.')
    }
  }
  catch (e) {
    toast.show(formatApiError(e, 'Could not move shift.'), 'error', 5000)
  }
  await loadShifts()
}

async function onTemplatesChanged() {
  try {
    await loadTemplates()
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Failed to reload templates.')
  }
}

// ---- Copy last week ----

const copyConfirmOpen = ref(false)
const copying = ref(false)
const copyError = ref('')

async function confirmCopy() {
  copying.value = true
  copyError.value = ''
  try {
    const result = await copyShiftWeek({
      source_week_start: addDays(weekStart.value, -7),
      target_week_start: weekStart.value,
      ...(locationId.value ? { location_id: locationId.value } : {}),
    })

    copyConfirmOpen.value = false
    toast.show(`Copied ${result.created} shift${result.created === 1 ? '' : 's'}${result.skipped ? ` · ${result.skipped} skipped` : ''}.`)
    await loadShifts()
  }
  catch (e) {
    copyError.value = formatApiError(e, 'Could not copy last week.')
  }
  finally {
    copying.value = false
  }
}

// ---- Print / export ----

const unitById = computed(() => new Map(staff.value.map(u => [u.id, u])))

const printDialogOpen = ref(false)
const printPreselected = ref<string[] | null>(null)
const printPeriod = ref<ShiftPrintPeriod>('week')
const printMonth = ref(monthOfWeek(weekStart.value))
const printMonthItems = computed(() => monthOptions(monthOfWeek(weekStart.value)))
const monthShifts = ref<Shift[]>([])
const monthLoading = ref(false)

const printShifts = computed(() => (printPeriod.value === 'month' ? monthShifts.value : shifts.value))
const printDates = computed(() => (printPeriod.value === 'month' ? monthDates(printMonth.value) : dates.value))
const printPeriodLabel = computed(() => (printPeriod.value === 'month' ? formatMonthLabel(printMonth.value) : weekLabel.value))

const printRows = computed(() =>
  printPeriod.value === 'month'
    ? matchSearch(staffRowsForLocation(staff.value, monthShifts.value, locationId.value))
    : rows.value,
)

const printShiftCounts = computed(() => {
  const counts = new Map<string, number>()
  for (const s of printShifts.value)
    counts.set(s.unit_id, (counts.get(s.unit_id) ?? 0) + 1)

  return counts
})

let monthRequest = 0

async function loadMonthShifts() {
  const requestId = ++monthRequest
  const days = monthDates(printMonth.value)

  monthLoading.value = true
  try {
    const list = await listShifts({
      start: days[0],
      end: days.at(-1)!,
      ...(locationId.value ? { location_id: locationId.value } : {}),
    })

    if (requestId === monthRequest)
      monthShifts.value = list
  }
  catch (e) {
    if (requestId === monthRequest)
      toast.show(formatApiError(e, 'Could not load the month.'), 'error', 5000)
  }
  finally {
    if (requestId === monthRequest)
      monthLoading.value = false
  }
}

watch([printDialogOpen, printPeriod, printMonth, locationId], ([open, period]) => {
  if (open && period === 'month')
    loadMonthShifts()
})

function openPrint(unit: Unit | null = null) {
  printPreselected.value = unit ? [unit.id] : null
  printMonth.value = monthOfWeek(weekStart.value)
  printDialogOpen.value = true
}

/** Runs inside the dialog's click handler so the pop-up is not blocked. */
function print(choice: ShiftPrintChoice) {
  const picked = new Set(choice.staffIds)

  try {
    printShiftWeek({
      ...choice,
      periodLabel: printPeriodLabel.value,
      locationLabel: locationLabel.value,
      dates: printDates.value,
      staff: printRows.value.filter(u => picked.has(u.id)).map(u => ({ id: u.id, name: u.full_name, code: u.code })),
      shiftsByCell: groupShiftsByCell(printShifts.value),
      locationNames: locationId.value
        ? undefined
        : new Map(locations.value.map(l => [l.id, locationName(l)])),
      printedAt: new Date().toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' }),
    })
    printDialogOpen.value = false
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Could not open print window.')
  }
}

async function loadPendingRequests() {
  pendingRequests.value = await listShiftRequests('pending')
}

async function approveRequest(request: ShiftRequest) {
  reviewBusy.value = true
  try {
    await approveShiftRequest(request.id)
    toast.show('Shift request approved.')
    await Promise.all([loadShifts(), loadPendingRequests()])
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Could not approve this request.')
  }
  finally {
    reviewBusy.value = false
  }
}

async function confirmReject() {
  if (!rejectTarget.value)
    return
  reviewBusy.value = true
  try {
    await rejectShiftRequest(rejectTarget.value.id, rejectReason.value.trim())
    toast.show('Shift request rejected.')
    rejectTarget.value = null
    rejectReason.value = ''
    await loadPendingRequests()
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Could not reject this request.')
  }
  finally {
    reviewBusy.value = false
  }
}

function exportCsv() {
  const csvRows = [...shifts.value]
    .sort((a, b) => a.shift_date.localeCompare(b.shift_date) || a.start_time.localeCompare(b.start_time))
    .map(s => {
      const unit = unitById.value.get(s.unit_id)
      const loc = locationById.value.get(s.location_id)

      return {
        date: s.shift_date,
        staffName: unit?.full_name ?? '',
        staffCode: unit?.code ?? '',
        locationName: loc ? locationName(loc) : '',
        shift: s,
      }
    })

  const blob = new Blob([buildShiftCsv(csvRows)], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = `shifts_${weekStart.value}.csv`
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <VContainer fluid>
    <!-- Title + primary actions -->
    <div class="d-flex flex-wrap align-center gap-4 mb-4">
      <div class="me-auto">
        <div class="text-h5 font-weight-medium">
          Shift Schedule
        </div>
        <div class="text-body-2 text-medium-emphasis">
          {{ ADMIN_SHIFT_PAGE_HINT }}
        </div>
      </div>
      <VBtn
        variant="text"
        color="secondary"
        prepend-icon="ri-palette-line"
        @click="templatesDialogOpen = true"
      >
        Templates
      </VBtn>
      <VBtn
        variant="tonal"
        color="primary"
        prepend-icon="ri-file-copy-line"
        :disabled="loading"
        @click="copyError = ''; copyConfirmOpen = true"
      >
        Copy last week
        <VTooltip
          activator="parent"
          location="bottom"
        >
          將上星期嘅更，照樣抄落而家顯示緊嘅嗰週
        </VTooltip>
      </VBtn>
      <VMenu location="bottom end">
        <template #activator="{ props: menuProps }">
          <VBtn
            v-bind="menuProps"
            variant="tonal"
            color="primary"
            prepend-icon="ri-share-forward-line"
            append-icon="ri-arrow-down-s-line"
            :disabled="loading"
          >
            Export
          </VBtn>
        </template>
        <VList density="compact">
          <VListItem
            prepend-icon="ri-printer-line"
            title="Print…"
            subtitle="週更表或者逐個員工印"
            @click="openPrint(null)"
          />
          <VListItem
            prepend-icon="ri-file-excel-2-line"
            title="Download CSV"
            :disabled="!shifts.length"
            @click="exportCsv"
          />
        </VList>
      </VMenu>
      <VBtn
        color="primary"
        prepend-icon="ri-add-line"
        :disabled="loading"
        @click="openCreate(null, null)"
      >
        Add shift
      </VBtn>
    </div>

    <VAlert
      v-if="loadError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="loadError = ''"
    >
      {{ loadError }}
    </VAlert>

    <section
      v-if="pendingRequests.length"
      class="request-inbox mb-4"
      aria-label="Pending staff requests"
    >
      <header>
        <span>Pending staff requests</span>
        <strong>{{ pendingRequests.length }}</strong>
        <em>{{ ADMIN_PENDING_REQUESTS_HINT }}</em>
      </header>
      <ul>
        <li
          v-for="request in pendingRequests"
          :key="request.id"
        >
          <div
            class="request-mark"
            :style="{ background: request.color }"
          />
          <div class="request-when">
            <span>{{ formatDayHeader(request.shift_date).weekday }}</span>
            <strong>{{ formatDayHeader(request.shift_date).day }}</strong>
          </div>
          <div class="request-copy">
            <strong>{{ request.unit_name }}</strong>
            <span>
              {{ hhmm(request.start_time) }}–{{ hhmm(request.end_time) }}
              <template v-if="request.title">
                · {{ request.title }}
              </template>
              <template v-if="locationById.get(request.location_id)">
                · {{ locationById.get(request.location_id)?.name_zh || locationById.get(request.location_id)?.name_en }}
              </template>
            </span>
            <em>{{ request.unit_code }}</em>
          </div>
          <div class="request-actions">
            <VBtn
              size="small"
              color="primary"
              :loading="reviewBusy"
              @click="approveRequest(request)"
            >
              Approve
            </VBtn>
            <VBtn
              size="small"
              variant="text"
              color="error"
              :disabled="reviewBusy"
              @click="rejectTarget = request; rejectReason = ''"
            >
              Reject
            </VBtn>
          </div>
        </li>
      </ul>
    </section>

    <VCard>
      <!-- Toolbar: week navigation, filters, stats -->
      <div class="toolbar d-flex flex-wrap align-center gap-3 pa-4">
        <div class="d-flex align-center">
          <IconBtn
            aria-label="Previous week"
            @click="shiftWeek(-1)"
          >
            <VIcon icon="ri-arrow-left-s-line" />
          </IconBtn>
          <VMenu
            v-model="datePickerOpen"
            :close-on-content-click="false"
          >
            <template #activator="{ props: menuProps }">
              <VBtn
                v-bind="menuProps"
                variant="text"
                class="week-btn text-h6 px-2"
                append-icon="ri-calendar-line"
              >
                {{ weekLabel }}
              </VBtn>
            </template>
            <VDatePicker
              :model-value="parseIsoDate(weekStart)"
              first-day-of-week="1"
              show-adjacent-months
              @update:model-value="jumpTo"
            />
          </VMenu>
          <IconBtn
            aria-label="Next week"
            @click="shiftWeek(1)"
          >
            <VIcon icon="ri-arrow-right-s-line" />
          </IconBtn>
          <VBtn
            v-if="!isThisWeek"
            variant="outlined"
            size="small"
            class="ms-2"
            @click="weekStart = thisWeek"
          >
            This week
          </VBtn>
          <VProgressCircular
            v-if="shiftsLoading && !loading"
            indeterminate
            size="18"
            width="2"
            color="primary"
            class="ms-3"
          />
        </div>

        <VSpacer />

        <VTextField
          v-model="search"
          placeholder="Search staff"
          prepend-inner-icon="ri-search-line"
          density="compact"
          hide-details
          clearable
          class="filter-field"
        />
        <VSelect
          v-model="locationId"
          :items="locationFilterItems"
          prepend-inner-icon="ri-map-pin-line"
          density="compact"
          hide-details
          class="filter-field"
        />
      </div>

      <div class="stats d-flex flex-wrap gap-2 px-4 pb-3">
        <VChip
          size="small"
          variant="tonal"
          prepend-icon="ri-calendar-check-line"
        >
          {{ stats.shifts }} shift{{ stats.shifts === 1 ? '' : 's' }}
        </VChip>
        <VChip
          size="small"
          variant="tonal"
          prepend-icon="ri-user-line"
        >
          {{ stats.staff }} staff scheduled
        </VChip>
        <VChip
          size="small"
          variant="tonal"
          prepend-icon="ri-time-line"
        >
          {{ stats.hours }} total
        </VChip>
        <VChip
          v-if="stats.overlaps"
          size="small"
          variant="tonal"
          color="warning"
          prepend-icon="ri-error-warning-line"
        >
          {{ stats.overlaps }} overlapping
        </VChip>

        <VDivider
          vertical
          class="mx-2"
        />

        <template v-if="templates.length">
          <VChip
            v-for="t in templates"
            :key="t.id"
            size="small"
            variant="text"
            class="legend-chip"
            @click="templatesDialogOpen = true"
          >
            <span
              class="legend-dot"
              :style="{ background: t.color }"
            />
            {{ t.name }} {{ hhmm(t.start_time) }}–{{ hhmm(t.end_time) }}
          </VChip>
        </template>
        <VBtn
          v-else
          size="small"
          variant="text"
          color="primary"
          prepend-icon="ri-magic-line"
          @click="templatesDialogOpen = true"
        >
          Create templates for one-click shifts
          <VTooltip
            activator="parent"
            location="bottom"
          >
            整定時間同顏色，之後撳格仔一撳就排到更
          </VTooltip>
        </VBtn>
      </div>

      <VDivider />

      <VSkeletonLoader
        v-if="loading"
        type="table-thead, table-row@6"
      />

      <template v-else>
        <ShiftWeekGrid
          v-if="rows.length"
          :dates="dates"
          :rows="rows"
          :shifts-by-cell="shiftsByCell"
          :overlap-ids="overlapIds"
          :location-by-id="locationById"
          :show-location="!locationId"
          :today="today"
          @add="onCellAdd"
          @edit="openEdit"
          @drop="onDrop"
          @print-staff="openPrint"
        />
        <div
          v-else
          class="empty-state text-center pa-12"
        >
          <VAvatar
            size="64"
            color="primary"
            variant="tonal"
            class="mb-4"
          >
            <VIcon
              icon="ri-team-line"
              size="32"
            />
          </VAvatar>
          <div class="text-h6 mb-1">
            {{ search ? 'No staff match your search' : 'No staff at this location' }}
          </div>
          <div class="text-body-2 text-medium-emphasis">
            {{ search ? '試下其他名或者員工編號。' : '去員工管理加員工，或者揀第二間分店。' }}
          </div>
        </div>
      </template>
    </VCard>

    <!-- One-click add from a template -->
    <VMenu
      v-model="quickMenu.open"
      :target="quickMenu.target ?? undefined"
      location="bottom start"
      :close-on-content-click="false"
      min-width="240"
    >
      <VCard>
        <VCardSubtitle class="pt-3 pb-1">
          {{ quickMenuTitle }}
        </VCardSubtitle>
        <VList
          density="compact"
          :disabled="quickAdding"
        >
          <VListItem
            v-for="t in templates"
            :key="t.id"
            @click="quickAdd(t)"
          >
            <template #prepend>
              <span
                class="legend-dot me-3"
                :style="{ background: t.color }"
              />
            </template>
            <VListItemTitle>{{ t.name }}</VListItemTitle>
            <template #append>
              <span class="text-caption text-medium-emphasis ms-4">{{ hhmm(t.start_time) }}–{{ hhmm(t.end_time) }}</span>
            </template>
          </VListItem>
          <VDivider class="my-1" />
          <VListItem
            prepend-icon="ri-edit-2-line"
            title="Custom shift…"
            @click="openCustomFromMenu"
          />
        </VList>
      </VCard>
    </VMenu>

    <ShiftDialog
      v-model="shiftDialogOpen"
      :editing-shift="editingShift"
      :initial-unit-id="newShift.unitId"
      :initial-date="newShift.date"
      :initial-location-id="newShift.locationId"
      :staff-options="staffOptions"
      :location-options="locationOptions"
      :locations="locations"
      :templates="templates"
      :existing-shifts="shifts"
      :staff-by-id="unitById"
      @saved="loadShifts"
    />
    <ShiftPrintDialog
      v-model="printDialogOpen"
      v-model:period="printPeriod"
      v-model:month="printMonth"
      :month-items="printMonthItems"
      :rows="printRows"
      :shift-counts="printShiftCounts"
      :preselected-ids="printPreselected"
      :period-label="printPeriodLabel"
      :loading="printPeriod === 'month' && monthLoading"
      @print="print"
    />
    <ShiftTemplatesDialog
      v-model="templatesDialogOpen"
      :templates="templates"
      @changed="onTemplatesChanged"
    />
    <AttendanceConfirmDialog
      v-model="copyConfirmOpen"
      title="Copy last week?"
      confirm-label="Copy"
      confirm-color="primary"
      :loading="copying"
      :error="copyError"
      @confirm="confirmCopy"
      @clear-error="copyError = ''"
    >
      會將 {{ formatWeekRange(addDays(weekStart, -7)) }} 嘅更，抄落 {{ weekLabel }}（{{ locationLabel }}）。
      呢週已經有嘅更會跳過、唔會抄重複；已停用嘅員工都會跳過。
    </AttendanceConfirmDialog>

    <VDialog
      :model-value="!!rejectTarget"
      max-width="420"
      @update:model-value="open => { if (!open) rejectTarget = null }"
    >
      <VCard>
        <VCardTitle>Reject shift request</VCardTitle>
        <VCardText>
          <VTextField
            v-model="rejectReason"
            label="Reason"
            placeholder="Optional note the staff member will see"
            :hint="ADMIN_REJECT_REASON_HINT"
            persistent-hint
            autofocus
          />
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="rejectTarget = null"
          >
            Cancel
          </VBtn>
          <VBtn
            color="error"
            :loading="reviewBusy"
            @click="confirmReject"
          >
            Reject
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>

<style scoped>
.filter-field {
  max-inline-size: 240px;
  min-inline-size: 180px;
}

.week-btn {
  letter-spacing: normal;
  text-transform: none;
}

.legend-chip {
  cursor: pointer;
}

.legend-dot {
  display: inline-block;
  border-radius: 3px;
  block-size: 10px;
  inline-size: 10px;
  margin-inline-end: 6px;
}

.request-inbox {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 12px;
  background: rgb(var(--v-theme-surface));
}

.request-inbox header {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 14px 16px 0;
}

.request-inbox header span {
  font-size: 0.95rem;
  font-weight: 500;
}

.request-inbox header em {
  color: rgba(var(--v-theme-on-surface), 0.6);
  font-size: 0.75rem;
  font-style: normal;
}

.request-inbox ul {
  list-style: none;
  margin: 0;
  padding: 8px;
}

.request-inbox li {
  display: grid;
  grid-template-columns: 6px 72px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 10px 8px;
  border-radius: 10px;
}

.request-inbox li + li {
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.request-mark {
  align-self: stretch;
  border-radius: 99px;
}

.request-when {
  display: grid;
}

.request-when span {
  color: rgba(var(--v-theme-on-surface), 0.55);
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.request-copy {
  display: grid;
  min-width: 0;
}

.request-copy span,
.request-copy em {
  overflow: hidden;
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 0.82rem;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.request-actions {
  display: flex;
  gap: 4px;
}

@media (max-width: 720px) {
  .request-inbox li {
    grid-template-columns: 6px 1fr;
  }

  .request-when,
  .request-actions {
    grid-column: 2;
  }
}
</style>
