<script setup lang="ts">
import {
  type Shift,
  type ShiftPayload,
  type ShiftTemplate,
  createShift,
  deleteShift,
  updateShift,
} from '@/api/attendance/shifts'
import type { LocationItem } from '@/api/attendance/locations'
import type { Unit } from '@/api/attendance/units'
import { formatApiError } from '@/utils/formatApiDetail'
import { openCloseForLocationDate } from '@/utils/locationHours'
import {
  SHIFT_COLORS,
  findOverlaps,
  formatDayHeader,
  formatShiftHours,
  hhmm,
  readableTextColor,
  shiftMinutes,
  timeToMinutes,
} from '@/utils/shiftDisplay'

interface Option { value: string; title: string }

const props = defineProps<{
  modelValue: boolean
  editingShift: Shift | null
  initialUnitId: string | null
  initialDate: string | null
  initialLocationId: string | null
  staffOptions: Option[]
  locationOptions: Option[]
  locations: LocationItem[]
  templates: ShiftTemplate[]
  existingShifts: Shift[]
  staffById: Map<string, Unit>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const saving = ref(false)
const saveError = ref('')
const deleteConfirmOpen = ref(false)
const deleting = ref(false)
const deleteError = ref('')

const emptyForm = () => ({
  unit_id: '',
  shift_date: '',
  location_id: '',
  start_time: '09:00',
  end_time: '13:00',
  title: '',
  color: SHIFT_COLORS[0] as string,
  notes: '',
  template_id: null as string | null,
})

const form = reactive(emptyForm())

const timesValid = computed(() =>
  /^\d{2}:\d{2}$/.test(form.start_time)
  && /^\d{2}:\d{2}$/.test(form.end_time)
  && timeToMinutes(form.end_time) > timeToMinutes(form.start_time),
)

const canSave = computed(() => !!form.unit_id && !!form.shift_date && !!form.location_id && timesValid.value)

const durationLabel = computed(() =>
  timesValid.value ? formatShiftHours(shiftMinutes({ start_time: form.start_time, end_time: form.end_time })) : '',
)

/** Keep the current (possibly inactive) staff selectable when editing an old shift. */
const staffItems = computed(() => {
  const current = form.unit_id ? props.staffById.get(form.unit_id) : null
  if (!current || props.staffOptions.some(o => o.value === current.id))
    return props.staffOptions

  return [{ value: current.id, title: `${current.full_name} · ${current.code} (inactive)` }, ...props.staffOptions]
})

const headerSubtitle = computed(() => {
  const parts = [props.staffById.get(form.unit_id)?.full_name]
  if (form.shift_date) {
    const { weekday, day } = formatDayHeader(form.shift_date)

    parts.push(`${weekday} ${day}`)
  }
  if (timesValid.value)
    parts.push(`${form.start_time}–${form.end_time} (${durationLabel.value})`)

  return parts.filter(Boolean).join(' · ') || '揀員工、日期同時間'
})

/** Location we filled in automatically; a user-picked location is never overwritten. */
let autoLocation: string | null = null

/** Skip location-hour fills while the form is being loaded from a shift or defaults. */
let suppressLocationHours = false

/** Start/end still match the last location hours we applied, so a date change can refresh them. */
let timesFromLocation = false

let pendingLocationTimes: { start: string; end: string } | null = null

function fillTimesFromLocation(locationId: string) {
  const location = props.locations.find(item => item.id === locationId)
  const span = openCloseForLocationDate(location, form.shift_date)
  if (!span)
    return false

  pendingLocationTimes = { start: span.open, end: span.close }
  form.start_time = span.open
  form.end_time = span.close
  form.template_id = null
  timesFromLocation = true

  return true
}

const homeOf = (unitId: string) => props.staffById.get(unitId)?.registered_location_id ?? null

function onStaffPicked(unitId: string | null) {
  if (props.editingShift || !unitId)
    return
  const home = homeOf(unitId)
  if (home && (!form.location_id || form.location_id === autoLocation)) {
    form.location_id = home
    autoLocation = home
  }
}

const overlaps = computed(() => {
  if (!canSave.value)
    return []

  return findOverlaps(
    { id: props.editingShift?.id, unit_id: form.unit_id, shift_date: form.shift_date, start_time: form.start_time, end_time: form.end_time },
    props.existingShifts,
  )
})

watch(() => props.modelValue, open => {
  if (!open)
    return
  saveError.value = ''
  timesFromLocation = false
  pendingLocationTimes = null

  const s = props.editingShift
  suppressLocationHours = true
  if (s) {
    Object.assign(form, {
      unit_id: s.unit_id,
      shift_date: s.shift_date,
      location_id: s.location_id,
      start_time: hhmm(s.start_time),
      end_time: hhmm(s.end_time),
      title: s.title ?? '',
      color: s.color,
      notes: s.notes ?? '',
      template_id: s.template_id,
    })
  }
  else {
    Object.assign(form, emptyForm(), {
      unit_id: props.initialUnitId ?? '',
      shift_date: props.initialDate ?? '',
      location_id: props.initialLocationId ?? '',
    })
    autoLocation = form.unit_id && form.location_id === homeOf(form.unit_id) ? form.location_id : null
    if (props.templates.length)
      applyTemplate(props.templates[0])
    if (form.location_id)
      fillTimesFromLocation(form.location_id)
  }
  suppressLocationHours = false
})

watch(() => form.location_id, locationId => {
  if (suppressLocationHours || !props.modelValue || !locationId)
    return
  fillTimesFromLocation(locationId)
}, { flush: 'sync' })

watch(() => form.shift_date, () => {
  if (suppressLocationHours || !props.modelValue || !timesFromLocation || !form.location_id)
    return
  fillTimesFromLocation(form.location_id)
}, { flush: 'sync' })

watch(() => [form.start_time, form.end_time] as const, () => {
  if (
    pendingLocationTimes
    && form.start_time === pendingLocationTimes.start
    && form.end_time === pendingLocationTimes.end
  ) {
    timesFromLocation = true

    return
  }

  timesFromLocation = false
})

function applyTemplate(t: ShiftTemplate) {
  timesFromLocation = false
  pendingLocationTimes = null
  Object.assign(form, {
    start_time: hhmm(t.start_time),
    end_time: hhmm(t.end_time),
    title: t.name,
    color: t.color,
    template_id: t.id,
  })
}

function close() {
  emit('update:modelValue', false)
}

async function save() {
  if (!canSave.value)
    return
  saving.value = true
  saveError.value = ''

  const payload: ShiftPayload = {
    unit_id: form.unit_id,
    location_id: form.location_id,
    shift_date: form.shift_date,
    start_time: form.start_time,
    end_time: form.end_time,
    title: form.title.trim() || null,
    color: form.color,
    notes: form.notes.trim() || null,
    template_id: form.template_id,
  }

  try {
    if (props.editingShift)
      await updateShift(props.editingShift.id, payload)
    else
      await createShift(payload)
    close()
    emit('saved')
  }
  catch (e) {
    saveError.value = formatApiError(e, 'Could not save shift.')
  }
  finally {
    saving.value = false
  }
}

async function confirmDelete() {
  if (!props.editingShift)
    return
  deleting.value = true
  deleteError.value = ''
  try {
    await deleteShift(props.editingShift.id)
    deleteConfirmOpen.value = false
    close()
    emit('saved')
  }
  catch (e) {
    deleteError.value = formatApiError(e, 'Could not delete shift.')
  }
  finally {
    deleting.value = false
  }
}
</script>

<template>
  <VDialog
    :model-value="modelValue"
    max-width="560"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <VCard class="shift-dialog">
      <div
        class="shift-dialog-header"
        :style="{ background: form.color, color: readableTextColor(form.color) }"
      >
        <div class="text-h6 font-weight-medium">
          {{ editingShift ? 'Edit shift' : 'Add shift' }}<template v-if="form.title.trim()">
            · {{ form.title.trim() }}
          </template>
        </div>
        <div class="text-body-2 opacity-90">
          {{ headerSubtitle }}
        </div>
        <IconBtn
          class="close-btn"
          aria-label="Close"
          :style="{ color: readableTextColor(form.color) }"
          @click="close"
        >
          <VIcon icon="ri-close-line" />
        </IconBtn>
      </div>
      <VCardText class="pt-5">
        <VAlert
          v-if="saveError"
          type="error"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          {{ saveError }}
        </VAlert>

        <div
          v-if="templates.length"
          class="mb-5"
        >
          <div class="text-overline text-medium-emphasis mb-1">
            Quick pick
          </div>
          <div class="template-tiles">
            <button
              v-for="t in templates"
              :key="t.id"
              type="button"
              class="template-tile"
              :class="{ active: form.template_id === t.id }"
              :style="{ '--tile-color': t.color }"
              :aria-pressed="form.template_id === t.id"
              @click="applyTemplate(t)"
            >
              <span class="tile-name">{{ t.name }}</span>
              <span class="tile-time">{{ hhmm(t.start_time) }}–{{ hhmm(t.end_time) }}</span>
            </button>
          </div>
        </div>

        <VRow>
          <VCol cols="12">
            <VAutocomplete
              v-model="form.unit_id"
              :items="staffItems"
              label="Staff"
              density="comfortable"
              @update:model-value="onStaffPicked"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="form.shift_date"
              type="date"
              label="Date"
              density="comfortable"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VSelect
              v-model="form.location_id"
              :items="locationOptions"
              label="Location"
              density="comfortable"
            />
          </VCol>
          <VCol cols="6">
            <VTextField
              v-model="form.start_time"
              type="time"
              label="Start"
              density="comfortable"
            />
          </VCol>
          <VCol cols="6">
            <VTextField
              v-model="form.end_time"
              type="time"
              label="End"
              density="comfortable"
              :error-messages="form.start_time && form.end_time && !timesValid ? 'End must be after start (same day).' : ''"
              :hint="durationLabel"
              persistent-hint
            />
          </VCol>
          <VCol cols="12">
            <VTextField
              v-model="form.title"
              label="Shift name"
              placeholder="Morning"
              hint="可以唔填。揀模板會自動填。"
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="12">
            <div class="text-body-2 text-medium-emphasis mb-2">
              Colour
            </div>
            <div class="d-flex flex-wrap gap-2">
              <VBtn
                v-for="c in SHIFT_COLORS"
                :key="c"
                :color="c"
                :variant="form.color === c ? 'flat' : 'tonal'"
                size="small"
                icon
                :aria-label="`Colour ${c}`"
                @click="form.color = c"
              >
                <VIcon
                  v-if="form.color === c"
                  icon="ri-check-line"
                />
              </VBtn>
            </div>
          </VCol>
          <VCol cols="12">
            <VTextarea
              v-model="form.notes"
              label="Notes"
              rows="2"
              density="comfortable"
            />
          </VCol>
        </VRow>

        <VAlert
          v-if="overlaps.length"
          type="warning"
          variant="tonal"
          density="compact"
          class="mt-3"
        >
          同一日同 {{ overlaps.map(s => `${hhmm(s.start_time)}–${hhmm(s.end_time)}`).join('、') }} 撞時間，不過照樣可以儲存。
        </VAlert>
      </VCardText>
      <VCardActions>
        <VBtn
          v-if="editingShift"
          color="error"
          variant="text"
          prepend-icon="ri-delete-bin-line"
          @click="deleteError = ''; deleteConfirmOpen = true"
        >
          Delete
        </VBtn>
        <VSpacer />
        <VBtn
          variant="text"
          @click="close"
        >
          Cancel
        </VBtn>
        <VBtn
          color="primary"
          :loading="saving"
          :disabled="!canSave"
          @click="save"
        >
          Save
        </VBtn>
      </VCardActions>
    </VCard>

    <AttendanceConfirmDialog
      v-model="deleteConfirmOpen"
      title="Delete shift?"
      :loading="deleting"
      :error="deleteError"
      @confirm="confirmDelete"
      @clear-error="deleteError = ''"
    >
      呢更會喺更表度刪走。
    </AttendanceConfirmDialog>
  </VDialog>
</template>

<style scoped>
.shift-dialog-header {
  position: relative;
  padding-block: 18px 16px;
  padding-inline: 24px 56px;
  transition: background-color 0.2s ease;
}

.close-btn {
  position: absolute;
  inset-block-start: 10px;
  inset-inline-end: 10px;
}

.template-tiles {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
}

.template-tile {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  background: rgb(var(--v-theme-surface));
  border-inline-start: 5px solid var(--tile-color);
  cursor: pointer;
  font: inherit;
  padding-block: 8px;
  padding-inline: 10px;
  text-align: start;
  transition: box-shadow 0.12s ease, border-color 0.12s ease;
}

.template-tile:hover {
  box-shadow: 0 2px 6px rgba(0, 0, 0, 10%);
}

.template-tile.active {
  border-color: var(--tile-color);
  box-shadow: 0 0 0 1px var(--tile-color);
}

.template-tile:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
}

.tile-name {
  font-size: 0.875rem;
  font-weight: 600;
}

.tile-time {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

@media (prefers-reduced-motion: reduce) {
  .shift-dialog-header,
  .template-tile {
    transition: none;
  }
}
</style>
