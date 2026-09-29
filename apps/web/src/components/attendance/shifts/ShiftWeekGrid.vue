<script setup lang="ts">
import type { LocationItem } from '@/api/attendance/locations'
import type { Shift } from '@/api/attendance/shifts'
import type { Unit } from '@/api/attendance/units'
import {
  avatarColor,
  cellKey,
  formatDayHeader,
  formatShiftHours,
  hhmm,
  isWeekend,
  readableTextColor,
  staffInitials,
  totalMinutes,
} from '@/utils/shiftDisplay'

const props = defineProps<{
  dates: string[]
  rows: Unit[]
  shiftsByCell: Map<string, Shift[]>
  overlapIds: Set<string>
  locationById: Map<string, LocationItem>
  showLocation: boolean
  today: string
}>()

const emit = defineEmits<{
  add: [unit: Unit, date: string, target: HTMLElement]
  edit: [shift: Shift]
  drop: [payload: { shiftId: string; unitId: string; date: string; copy: boolean }]
  printStaff: [unit: Unit]
}>()

const cellShifts = (unitId: string, date: string) => props.shiftsByCell.get(cellKey(unitId, date)) ?? []

const allShifts = computed(() => [...props.shiftsByCell.values()].flat())

const rowStats = computed(() => {
  const stats = new Map<string, { minutes: number; count: number }>()
  for (const u of props.rows) {
    const list = allShifts.value.filter(s => s.unit_id === u.id)

    stats.set(u.id, { minutes: totalMinutes(list), count: list.length })
  }

  return stats
})

const dayStats = computed(() => props.dates.map(d => {
  const list = allShifts.value.filter(s => s.shift_date === d && props.rows.some(u => u.id === s.unit_id))

  return { date: d, header: formatDayHeader(d), minutes: totalMinutes(list), count: list.length }
}))

// ---- Drag & drop (hold Ctrl / Alt / ⌘ to copy instead of move) ----

const draggingId = ref<string | null>(null)
const dragOverKey = ref<string | null>(null)

const isCopy = (e: DragEvent) => e.ctrlKey || e.altKey || e.metaKey

function onDragStart(e: DragEvent, shift: Shift) {
  draggingId.value = shift.id
  e.dataTransfer?.setData('text/plain', shift.id)
  if (e.dataTransfer)
    e.dataTransfer.effectAllowed = 'copyMove'
}

function onDragEnd() {
  draggingId.value = null
  dragOverKey.value = null
}

function onDragOver(e: DragEvent, unit: Unit, date: string) {
  if (!draggingId.value || !unit.is_active)
    return
  e.preventDefault()
  if (e.dataTransfer)
    e.dataTransfer.dropEffect = isCopy(e) ? 'copy' : 'move'
  dragOverKey.value = cellKey(unit.id, date)
}

function onDrop(e: DragEvent, unit: Unit, date: string) {
  const shiftId = draggingId.value
  if (!shiftId || !unit.is_active)
    return
  e.preventDefault()
  emit('drop', { shiftId, unitId: unit.id, date, copy: isCopy(e) })
  onDragEnd()
}

function onCellClick(e: MouseEvent, unit: Unit, date: string) {
  if (unit.is_active)
    emit('add', unit, date, e.currentTarget as HTMLElement)
}

function onAddClick(e: MouseEvent, unit: Unit, date: string) {
  const cell = (e.currentTarget as HTMLElement).closest('td') as HTMLElement

  emit('add', unit, date, cell)
}

function shiftLabel(s: Shift, unit: Unit) {
  return [
    `${unit.full_name}`,
    `${hhmm(s.start_time)}–${hhmm(s.end_time)}`,
    s.title,
    props.overlapIds.has(s.id) ? 'overlaps another shift' : null,
  ].filter(Boolean).join(', ')
}
</script>

<template>
  <div class="shift-grid-wrap">
    <table class="shift-grid">
      <thead>
        <tr>
          <th class="staff-col">
            <span class="text-overline">Staff · {{ rows.length }}</span>
          </th>
          <th
            v-for="d in dayStats"
            :key="d.date"
            class="day-head"
            :class="{ today: d.date === today, weekend: isWeekend(d.date) }"
          >
            <div class="day-weekday">
              {{ d.header.weekday }}
            </div>
            <div class="day-date">
              <span class="day-num">{{ d.header.day.split(' ')[0] }}</span>
              <span class="text-medium-emphasis">{{ d.header.day.split(' ')[1] }}</span>
            </div>
            <div class="day-meta">
              <template v-if="d.count">
                {{ d.count }} shift{{ d.count === 1 ? '' : 's' }} · {{ formatShiftHours(d.minutes) }}
              </template>
              <template v-else>
                —
              </template>
            </div>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="u in rows"
          :key="u.id"
        >
          <th
            class="staff-col staff-cell"
            scope="row"
          >
            <div class="d-flex align-center gap-3">
              <VAvatar
                size="34"
                :color="avatarColor(u.id)"
                class="flex-shrink-0"
              >
                <span
                  class="text-body-2 font-weight-medium"
                  :style="{ color: readableTextColor(avatarColor(u.id)) }"
                >{{ staffInitials(u.full_name) }}</span>
              </VAvatar>
              <div class="staff-text">
                <div class="staff-name text-truncate">
                  {{ u.full_name }}
                </div>
                <div class="text-caption text-medium-emphasis text-truncate">
                  <template v-if="rowStats.get(u.id)?.count">
                    <b class="text-high-emphasis">{{ formatShiftHours(rowStats.get(u.id)!.minutes) }}</b>
                    · {{ rowStats.get(u.id)!.count }} shift{{ rowStats.get(u.id)!.count === 1 ? '' : 's' }}
                  </template>
                  <template v-else>
                    {{ u.code }}
                  </template>
                  <VChip
                    v-if="!u.is_active"
                    size="x-small"
                    class="ms-1"
                  >
                    inactive
                  </VChip>
                </div>
              </div>
              <IconBtn
                size="small"
                class="row-print ms-auto"
                :aria-label="`Print ${u.full_name}'s schedule`"
                @click="emit('printStaff', u)"
              >
                <VIcon
                  icon="ri-printer-line"
                  size="18"
                />
                <VTooltip
                  activator="parent"
                  location="top"
                >
                  列印 {{ u.full_name }} 嘅更表
                </VTooltip>
              </IconBtn>
            </div>
          </th>
          <td
            v-for="d in dates"
            :key="d"
            class="day-cell"
            :class="{
              'today': d === today,
              'weekend': isWeekend(d),
              'clickable': u.is_active,
              'drag-over': dragOverKey === cellKey(u.id, d),
            }"
            @click="onCellClick($event, u, d)"
            @dragover="onDragOver($event, u, d)"
            @dragleave="dragOverKey === cellKey(u.id, d) && (dragOverKey = null)"
            @drop="onDrop($event, u, d)"
          >
            <div class="cell-stack">
              <button
                v-for="s in cellShifts(u.id, d)"
                :key="s.id"
                type="button"
                class="shift-block"
                :class="{ dragging: draggingId === s.id, overlap: overlapIds.has(s.id) }"
                :style="{ '--shift-bg': s.color, 'color': readableTextColor(s.color) }"
                :draggable="u.is_active"
                :aria-label="`Edit shift: ${shiftLabel(s, u)}`"
                @click.stop="emit('edit', s)"
                @dragstart="onDragStart($event, s)"
                @dragend="onDragEnd"
              >
                <span class="shift-time">
                  {{ hhmm(s.start_time) }}–{{ hhmm(s.end_time) }}
                  <VIcon
                    v-if="overlapIds.has(s.id)"
                    icon="ri-error-warning-fill"
                    size="14"
                    class="ms-1"
                  />
                  <VIcon
                    v-if="s.notes"
                    icon="ri-sticky-note-line"
                    size="13"
                    class="ms-1 opacity-80"
                  />
                </span>
                <span
                  v-if="s.title"
                  class="shift-title"
                >{{ s.title }}</span>
                <span
                  v-if="showLocation && locationById.get(s.location_id)"
                  class="shift-sub"
                >{{ locationById.get(s.location_id)?.name_en }}</span>
                <VTooltip
                  v-if="s.notes || overlapIds.has(s.id)"
                  activator="parent"
                  location="top"
                  max-width="260"
                >
                  <div v-if="overlapIds.has(s.id)">
                    同一日有另一更撞時間。
                  </div>
                  <div v-if="s.notes">
                    {{ s.notes }}
                  </div>
                </VTooltip>
              </button>

              <button
                v-if="u.is_active"
                type="button"
                class="add-slot"
                :class="{ empty: !cellShifts(u.id, d).length }"
                :aria-label="`Add shift for ${u.full_name} on ${d}`"
                @click.stop="onAddClick($event, u, d)"
              >
                <VIcon
                  icon="ri-add-line"
                  size="16"
                />
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.shift-grid-wrap {
  overflow-x: auto;
}

.shift-grid {
  border-collapse: separate;
  border-spacing: 0;
  inline-size: 100%;
  min-inline-size: 1040px;
  table-layout: fixed;
}

.shift-grid th,
.shift-grid td {
  border-block-end: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-inline-end: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * 0.6));
  text-align: start;
  vertical-align: top;
}

/* ---- Header ---- */
.shift-grid thead th {
  position: sticky;
  z-index: 2;
  background: rgb(var(--v-theme-surface));
  inset-block-start: 0;
  padding-block: 10px 8px;
  padding-inline: 10px;
}

.day-weekday {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.day-date {
  display: flex;
  align-items: baseline;
  gap: 4px;
  font-size: 0.8125rem;
}

.day-num {
  font-size: 1.375rem;
  font-weight: 600;
  line-height: 1.4;
}

.day-head.today .day-num {
  display: inline-grid;
  border-radius: 999px;
  background: rgb(var(--v-theme-primary));
  block-size: 32px;
  color: rgb(var(--v-theme-on-primary));
  inline-size: 32px;
  place-items: center;
  font-size: 1rem;
}

.day-head.today .day-weekday {
  color: rgb(var(--v-theme-primary));
}

.day-meta {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  font-size: 0.75rem;
  font-weight: 400;
  white-space: nowrap;
}

/* ---- Staff column ---- */
.staff-col {
  position: sticky;
  z-index: 1;
  background: rgb(var(--v-theme-surface));
  inline-size: 210px;
  inset-inline-start: 0;
}

thead .staff-col {
  z-index: 3;
  vertical-align: bottom !important;
}

.staff-cell {
  padding-block: 10px;
  padding-inline: 12px;
  font-weight: 400;
}

.staff-text {
  min-inline-size: 0;
}

.staff-name {
  font-size: 0.875rem;
  font-weight: 500;
}

.row-print {
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.12s ease;
}

.staff-cell:hover .row-print,
.row-print:focus-visible {
  opacity: 1;
}

@media (hover: none) {
  .row-print {
    opacity: 0.6;
  }
}

/* ---- Day cells ---- */
.day-cell {
  padding: 6px;
  block-size: 72px;
  transition: background-color 0.15s ease;
}

.weekend {
  background: rgba(var(--v-theme-on-surface), 0.018);
}

.today {
  background: rgba(var(--v-theme-primary), 0.05);
}

.day-cell.clickable {
  cursor: pointer;
}

.day-cell.clickable:hover {
  background: rgba(var(--v-theme-primary), 0.07);
}

.day-cell.drag-over {
  background: rgba(var(--v-theme-primary), 0.14);
  outline: 2px dashed rgb(var(--v-theme-primary));
  outline-offset: -3px;
}

.cell-stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
  block-size: 100%;
}

/* ---- Shift block ---- */
.shift-block {
  display: flex;
  flex-direction: column;
  border: 0;
  border-radius: 6px;
  background: var(--shift-bg);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 12%);
  cursor: grab;
  font: inherit;
  inline-size: 100%;
  line-height: 1.25;
  padding-block: 5px;
  padding-inline: 8px;
  text-align: start;
  transition: transform 0.12s ease, box-shadow 0.12s ease, opacity 0.12s ease;
}

.shift-block:hover {
  box-shadow: 0 3px 8px rgba(0, 0, 0, 18%);
  transform: translateY(-1px);
}

.shift-block:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
}

.shift-block.dragging {
  opacity: 0.45;
}

.shift-block.overlap {
  box-shadow: 0 0 0 2px rgb(var(--v-theme-warning));
}

.shift-time {
  display: inline-flex;
  align-items: center;
  font-size: 0.8125rem;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.shift-title,
.shift-sub {
  overflow: hidden;
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.shift-sub {
  opacity: 0.85;
}

/* ---- Add slot ---- */
.add-slot {
  display: grid;
  border: 1px dashed transparent;
  border-radius: 6px;
  background: transparent;
  block-size: 24px;
  color: rgb(var(--v-theme-primary));
  cursor: pointer;
  opacity: 0;
  place-items: center;
  transition: opacity 0.12s ease;
}

.add-slot.empty {
  flex: 1;
  min-block-size: 40px;
}

.day-cell.clickable:hover .add-slot,
.add-slot:focus-visible {
  border-color: rgba(var(--v-theme-primary), 0.5);
  opacity: 1;
}

.add-slot:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
}

@media (prefers-reduced-motion: reduce) {
  .shift-block,
  .add-slot,
  .day-cell {
    transition: none;
  }

  .shift-block:hover {
    transform: none;
  }
}
</style>
