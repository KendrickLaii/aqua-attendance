<script setup lang="ts">
import { createManualCorrection, listAttendance } from '@/api/attendance/events'
import type { AttendanceEvent } from '@/api/attendance/events'
import { getUnit, listUnits } from '@/api/attendance/units'
import type { Unit } from '@/api/attendance/units'
import { dateTimeLocalToIso, eventSourceLabel, formatAttendanceDateTime, getDateRangeIso, getTodayRangeIso } from '@/utils/attendanceDisplay'
import { formatApiError } from '@/utils/formatApiDetail'

type CorrectionMode = 'single' | 'full_day'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    /** When set, the unit field is locked to this unit (Units page quick entry). */
    unit?: Unit | null
    /** Seed list for searchable unit picker (Log page). Ignored when `unit` is set. */
    unitCatalog?: Unit[]
  }>(),
  {
    unit: null,
    unitCatalog: () => [],
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const locked = computed(() => !!props.unit)

const form = reactive({
  mode: 'full_day' as CorrectionMode,
  unit_id: '',
  event_type: 'check_in' as 'check_in' | 'check_out',
  recorded_at: '',
  check_in_at: '',
  check_out_at: '',
  location_id: '',
  notes: '',
})

const unitSearch = ref('')
const unitOptions = ref<Unit[]>([])
const unitSearchLoading = ref(false)
const selectedUnit = ref<Unit | null>(null)
const duplicateEvents = ref<AttendanceEvent[]>([])
const duplicateSummary = ref('')
const duplicateConfirmOpen = ref(false)
const allowDuplicate = ref(false)
const saving = ref(false)
const error = ref('')

const unitItems = computed(() => {
  const opts = unitOptions.value
  const selected = selectedUnit.value
  const list = selected && !opts.some(u => u.id === selected.id)
    ? [selected, ...opts]
    : opts

  return list.map(u => ({
    title: `${u.full_name} (${u.code})`,
    value: u.id,
    subtitle: `${u.code} · ${u.unit_type}`,
    raw: u,
  }))
})

const locationItems = computed(() => {
  const locs = selectedUnit.value?.scan_locations ?? []

  return [
    { title: '— no location —', value: '' },
    ...locs.map(l => ({
      title: `${l.name_zh}${l.name_en ? ` / ${l.name_en}` : ''}`,
      value: l.id,
    })),
  ]
})

const hasDuplicate = computed(() => duplicateEvents.value.length > 0)

const isFullDay = computed(() => form.mode === 'full_day')

const datetimePickerConfig = {
  enableTime: true,
  dateFormat: 'Y-m-d H:i',
  time_24hr: true,
  allowInput: true,
  minuteIncrement: 5,
} as const

const checkOutPickerConfig = computed(() => ({
  ...datetimePickerConfig,
  minDate: form.check_in_at || undefined,
}))

function dateKeyFromLocal(value: string) {
  const raw = value?.trim()
  if (!raw)
    return getTodayRangeIso().dateKey

  const normalized = raw.replace(' ', 'T')
  if (normalized.includes('T'))
    return normalized.split('T')[0]

  if (/^\d{4}-\d{2}-\d{2}/.test(normalized))
    return normalized.slice(0, 10)

  return getTodayRangeIso().dateKey
}

const primaryDateKey = computed(() => {
  if (isFullDay.value)
    return dateKeyFromLocal(form.check_in_at || form.check_out_at)

  return dateKeyFromLocal(form.recorded_at)
})

function typeLabel(type: string) {
  if (type === 'staff')
    return 'Staff'
  if (type === 'student')
    return 'Student'

  return type
}

function eventTypeLabel(type: string) {
  if (type === 'check_in')
    return 'Check In'
  if (type === 'check_out')
    return 'Check Out'

  return type.replaceAll('_', ' ')
}

function seedUnitOptions(query = '') {
  const catalog = props.unitCatalog ?? []
  const q = query.trim().toLowerCase()
  if (!q) {
    unitOptions.value = catalog.slice(0, 30)

    return
  }

  unitOptions.value = catalog
    .filter(u =>
      u.full_name.toLowerCase().includes(q)
      || u.code.toLowerCase().includes(q)
      || (u.english_name?.toLowerCase().includes(q) ?? false),
    )
    .slice(0, 30)
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
      is_active: true,
      page_size: 20,
    })
  }
  catch (e) {
    console.error('Failed to search units for manual correction', e)
    seedUnitOptions(q)
  }
  finally {
    unitSearchLoading.value = false
  }
}, 300)

watch(unitSearch, value => {
  if (!props.modelValue || locked.value)
    return
  if (!value?.trim())
    seedUnitOptions()
  else
    searchUnits()
})

async function resolveSelectedUnit(id: string) {
  let unit = unitOptions.value.find(u => u.id === id)
    || props.unitCatalog?.find(u => u.id === id)
    || (selectedUnit.value?.id === id ? selectedUnit.value : null)
    || (props.unit?.id === id ? props.unit : null)

  if (!unit || !unit.scan_locations) {
    try {
      unit = await getUnit(id)
    }
    catch (e) {
      console.error('Failed to load unit for manual correction', e)
      error.value = formatApiError(e, 'Could not load unit details')
      selectedUnit.value = null
      duplicateEvents.value = []
      duplicateSummary.value = ''

      return
    }
  }

  selectedUnit.value = unit

  const scanIds = unit.scan_locations?.map(l => l.id) ?? []
  if (scanIds.length === 1)
    form.location_id = scanIds[0]

  await checkDuplicates()
}

watch(
  () => form.unit_id,
  async id => {
    if (!props.modelValue)
      return

    allowDuplicate.value = false
    form.location_id = ''

    if (!id) {
      selectedUnit.value = null
      duplicateEvents.value = []
      duplicateSummary.value = ''

      return
    }

    await resolveSelectedUnit(id)
  },
)

watch(
  () => [form.mode, form.event_type, form.recorded_at, form.check_in_at, form.check_out_at] as const,
  () => {
    if (!props.modelValue || !form.unit_id)
      return
    allowDuplicate.value = false
    debouncedCheckDuplicates()
  },
)

async function fetchDayEvents(eventType: 'check_in' | 'check_out', localAt: string) {
  const key = dateKeyFromLocal(localAt)
  const range = getDateRangeIso(key, key)

  const dayEvents = await listAttendance({
    unit_id: form.unit_id,
    date_from: range.date_from,
    date_to: range.date_to,
    event_type: eventType,
    page_size: 20,
  })

  return dayEvents.filter(e => !e.voided_at)
}

async function checkDuplicates() {
  if (!form.unit_id) {
    duplicateEvents.value = []
    duplicateSummary.value = ''

    return
  }

  try {
    if (isFullDay.value) {
      const [ins, outs] = await Promise.all([
        form.check_in_at ? fetchDayEvents('check_in', form.check_in_at) : Promise.resolve([]),
        form.check_out_at ? fetchDayEvents('check_out', form.check_out_at) : Promise.resolve([]),
      ])

      duplicateEvents.value = [...ins, ...outs]
      const parts: string[] = []
      if (ins.length)
        parts.push(`${ins.length} check-in${ins.length === 1 ? '' : 's'}`)
      if (outs.length)
        parts.push(`${outs.length} check-out${outs.length === 1 ? '' : 's'}`)
      duplicateSummary.value = parts.length
        ? `Already has ${parts.join(' and ')} on the selected day(s).`
        : ''
    }
    else {
      const events = await fetchDayEvents(form.event_type, form.recorded_at)

      duplicateEvents.value = events
      duplicateSummary.value = events.length
        ? `Already has ${events.length} ${eventTypeLabel(form.event_type).toLowerCase()}${events.length === 1 ? '' : 's'} on ${primaryDateKey.value}.`
        : ''
    }
  }
  catch (e) {
    console.error('Failed to check existing attendance for correction', e)
    duplicateEvents.value = []
    duplicateSummary.value = ''
  }
}

const debouncedCheckDuplicates = useDebounceFn(checkDuplicates, 400)

function resetForm(presetUnit: Unit | null = null) {
  error.value = ''
  allowDuplicate.value = false
  duplicateConfirmOpen.value = false
  duplicateEvents.value = []
  duplicateSummary.value = ''
  unitSearch.value = ''
  selectedUnit.value = presetUnit

  Object.assign(form, {
    mode: 'full_day' as CorrectionMode,
    unit_id: presetUnit?.id ?? '',
    event_type: 'check_in',
    recorded_at: '',
    check_in_at: '',
    check_out_at: '',
    location_id: '',
    notes: '',
  })

  if (presetUnit) {
    const scanIds = presetUnit.scan_locations?.map(l => l.id) ?? []
    if (scanIds.length === 1)
      form.location_id = scanIds[0]
  }
  else {
    seedUnitOptions()
  }
}

watch(
  () => props.modelValue,
  async open => {
    if (!open)
      return

    if (props.unit) {
      resetForm(props.unit)
      await checkDuplicates()
    }
    else {
      resetForm(null)
    }
  },
)

function close() {
  emit('update:modelValue', false)
  error.value = ''
  allowDuplicate.value = false
  duplicateConfirmOpen.value = false
  duplicateEvents.value = []
  duplicateSummary.value = ''
  selectedUnit.value = null
  unitSearch.value = ''
}

function validateForm(): string | null {
  if (!form.unit_id)
    return 'Please select a unit'

  if (isFullDay.value) {
    if (!form.check_in_at?.trim())
      return 'Please enter check-in date & time'
    if (!form.check_out_at?.trim())
      return 'Please enter check-out date & time'

    const inIso = dateTimeLocalToIso(form.check_in_at)
    const outIso = dateTimeLocalToIso(form.check_out_at)
    if (inIso && outIso && new Date(outIso) <= new Date(inIso))
      return 'Check-out must be after check-in'
  }

  return null
}

async function handleSave() {
  const validationError = validateForm()
  if (validationError) {
    error.value = validationError

    return
  }

  if (hasDuplicate.value && !allowDuplicate.value) {
    duplicateConfirmOpen.value = true

    return
  }

  saving.value = true
  error.value = ''
  try {
    const shared = {
      unit_id: form.unit_id,
      location_id: form.location_id || undefined,
      notes: form.notes || undefined,
    }

    if (isFullDay.value) {
      await createManualCorrection({
        ...shared,
        event_type: 'check_in',
        recorded_at: dateTimeLocalToIso(form.check_in_at),
      })
      await createManualCorrection({
        ...shared,
        event_type: 'check_out',
        recorded_at: dateTimeLocalToIso(form.check_out_at),
      })
    }
    else {
      await createManualCorrection({
        ...shared,
        event_type: form.event_type,
        recorded_at: dateTimeLocalToIso(form.recorded_at),
      })
    }

    close()
    emit('saved')
  }
  catch (e: unknown) {
    error.value = formatApiError(e, 'Could not save correction')
  }
  finally {
    saving.value = false
  }
}

function confirmDuplicateSave() {
  allowDuplicate.value = true
  duplicateConfirmOpen.value = false
  handleSave()
}
</script>

<template>
  <AttendanceFormDialog
    :model-value="modelValue"
    title="Manual Correction !"
    icon="ri-edit-box-line"
    :max-width="520"
    :saving="saving"
    :error="error"
    :save-label="isFullDay ? 'Save' : 'Save'"
    persistent
    @update:model-value="emit('update:modelValue', $event)"
    @save="handleSave"
    @cancel="close"
    @clear-error="error = ''"
  >
    <VForm @submit.prevent="handleSave">
      <!-- Locked unit (from Units page) -->
      <template v-if="locked && selectedUnit">
        <div class="mb-3">
          <div class="text-body-1 font-weight-medium">
            {{ selectedUnit.full_name }}
            <span class="text-medium-emphasis">({{ selectedUnit.code }})</span>
          </div>
          <div class="d-flex flex-wrap align-center gap-2 mt-2">
            <VChip
              :color="selectedUnit.unit_type === 'staff' ? 'info' : 'success'"
              size="small"
              label
            >
              {{ typeLabel(selectedUnit.unit_type) }}
            </VChip>
            <VChip
              :color="selectedUnit.attendance_status === 'checked_in' ? 'success' : 'default'"
              size="small"
              label
              :prepend-icon="selectedUnit.attendance_status === 'checked_in' ? 'ri-login-circle-line' : 'ri-logout-circle-line'"
            >
              {{ selectedUnit.attendance_status === 'checked_in' ? 'Currently in' : 'Currently out' }}
            </VChip>
          </div>
        </div>
      </template>

      <!-- Searchable unit (from Log page) -->
      <template v-else>
        <VAutocomplete
          v-model="form.unit_id"
          v-model:search="unitSearch"
          :items="unitItems"
          :loading="unitSearchLoading"
          item-title="title"
          item-value="value"
          label="Unit *"
          placeholder="Search by name or code…"
          prepend-inner-icon="ri-search-line"
          clearable
          no-filter
          class="mb-3"
        >
          <template #item="{ props: itemProps, item }">
            <VListItem
              v-bind="itemProps"
              :title="item.raw.title"
              :subtitle="item.raw.subtitle"
            />
          </template>
        </VAutocomplete>

        <div
          v-if="selectedUnit"
          class="d-flex flex-wrap align-center gap-2 mb-3"
        >
          <VChip
            :color="selectedUnit.unit_type === 'staff' ? 'info' : 'success'"
            size="small"
            label
          >
            {{ typeLabel(selectedUnit.unit_type) }}
          </VChip>
          <VChip
            :color="selectedUnit.attendance_status === 'checked_in' ? 'success' : 'default'"
            size="small"
            label
            :prepend-icon="selectedUnit.attendance_status === 'checked_in' ? 'ri-login-circle-line' : 'ri-logout-circle-line'"
          >
            {{ selectedUnit.attendance_status === 'checked_in' ? 'Currently in' : 'Currently out' }}
          </VChip>
        </div>
      </template>

      <div
        class="segmented mb-3"
        role="group"
        aria-label="Correction mode"
      >
        <button
          type="button"
          class="segmented__btn"
          :class="{ 'segmented__btn--active': form.mode === 'full_day' }"
          @click="form.mode = 'full_day'"
        >
          <VIcon
            icon="ri-calendar-check-line"
            size="18"
            class="me-1"
          />
          Full day
        </button>
        <button
          type="button"
          class="segmented__btn"
          :class="{ 'segmented__btn--active': form.mode === 'single' }"
          @click="form.mode = 'single'"
        >
          <VIcon
            icon="ri-file-list-3-line"
            size="18"
            class="me-1"
          />
          Single
        </button>
      </div>

      <template v-if="isFullDay">
        <AppDateTimePicker
          v-model="form.check_in_at"
          label="Check in *"
          placeholder="Select check-in date & time"
          density="compact"
          clearable
          prepend-inner-icon="ri-login-circle-line"
          :config="datetimePickerConfig"
          class="mb-3"
        />
        <AppDateTimePicker
          :key="`check-out-${form.check_in_at || 'none'}`"
          v-model="form.check_out_at"
          label="Check out *"
          placeholder="Select check-out date & time"
          density="compact"
          clearable
          prepend-inner-icon="ri-logout-circle-line"
          :config="checkOutPickerConfig"
          class="mb-3"
        />
      </template>

      <template v-else>
        <div
          class="segmented mb-3"
          role="group"
          aria-label="Event type"
        >
          <button
            type="button"
            class="segmented__btn"
            :class="{ 'segmented__btn--active segmented__btn--in': form.event_type === 'check_in' }"
            @click="form.event_type = 'check_in'"
          >
            <VIcon
              icon="ri-login-circle-line"
              size="18"
              class="me-1"
            />
            Check In
          </button>
          <button
            type="button"
            class="segmented__btn"
            :class="{ 'segmented__btn--active segmented__btn--out': form.event_type === 'check_out' }"
            @click="form.event_type = 'check_out'"
          >
            <VIcon
              icon="ri-logout-circle-line"
              size="18"
              class="me-1"
            />
            Check Out
          </button>
        </div>

        <AppDateTimePicker
          v-model="form.recorded_at"
          label="Date & time"
          placeholder="Now (or select date & time)"
          density="compact"
          clearable
          prepend-inner-icon="ri-calendar-schedule-line"
          hint="Leave blank to use the current time"
          persistent-hint
          :config="datetimePickerConfig"
          class="mb-3"
        />
      </template>

      <VSelect
        v-model="form.location_id"
        :items="locationItems"
        :disabled="!selectedUnit"
        label="Location"
        prepend-inner-icon="ri-map-pin-line"
        :hint="selectedUnit
          ? (selectedUnit.scan_locations?.length
            ? 'Scan locations for this unit'
            : 'No scan locations assigned to this unit')
          : 'Select a unit first'"
        persistent-hint
        class="mb-3"
      />

      <VTextarea
        v-model="form.notes"
        label="Notes"
        rows="2"
      />
    </VForm>
  </AttendanceFormDialog>

  <VDialog
    v-model="duplicateConfirmOpen"
    max-width="420"
  >
    <VCard>
      <VCardTitle class="text-h6">
        Existing attendance
      </VCardTitle>
      <VCardText>
        {{ duplicateSummary || 'Matching attendance already exists for this day.' }}
        <template v-if="duplicateEvents[0]">
          <br>
          <span class="text-caption text-medium-emphasis">
            Latest: {{ formatAttendanceDateTime(duplicateEvents[0].recorded_at) }}
            · {{ eventSourceLabel(duplicateEvents[0].source) }}
            · {{ eventTypeLabel(duplicateEvents[0].event_type) }}
          </span>
        </template>
        <br>
        Save anyway?
      </VCardText>
      <VCardActions class="justify-end">
        <VBtn
          variant="text"
          @click="duplicateConfirmOpen = false"
        >
          Cancel
        </VBtn>
        <VBtn
          color="warning"
          variant="flat"
          :loading="saving"
          @click="confirmDuplicateSave"
        >
          Save anyway
        </VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>

<style scoped lang="scss">
.segmented {
  display: flex;
  width: 100%;
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.segmented__btn {
  display: inline-flex;
  flex: 1 1 0;
  align-items: center;
  justify-content: center;
  min-width: 0;
  margin: 0;
  padding: 10px 12px;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: rgba(var(--v-theme-on-surface), 0.7);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 500;
  line-height: 1.25;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;

  &:not(:last-child) {
    border-inline-end: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  }

  &:hover:not(.segmented__btn--active) {
    background: rgba(var(--v-theme-on-surface), 0.06);
  }
}

.segmented__btn--active {
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
}

.segmented__btn--active.segmented__btn--in {
  background: rgb(var(--v-theme-success));
  color: rgb(var(--v-theme-on-success));
}

.segmented__btn--active.segmented__btn--out {
  background: rgb(var(--v-theme-warning));
  color: rgb(var(--v-theme-on-warning));
}
</style>
