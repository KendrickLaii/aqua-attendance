<script setup lang="ts">
import type { AttendanceSummary, SummaryOverviewItem } from '@/api/attendance/summaries'
import SummaryDateCell from '@/components/attendance/SummaryDateCell.vue'
import { formatAttendanceDateTime } from '@/utils/attendanceDisplay'
import { openSummaryPrintPlaceholder, printAttendanceSummaries } from '@/utils/printAttendanceSummaries'
import {
  type DetailStatus,
  type DetailTotals,
  detailStatusFilterIcon,
  detailStatusOptions,
  formatDayHours,
  formatDaySlots,
  formatTotalHours,
  formatTotalSlots,
  summaryStatusColor,
  summaryStatusIcon,
  summaryStatusLabel,
} from '@/utils/summaryDisplay'

const props = defineProps<{
  unit: SummaryOverviewItem | null
  monthLabel: string
  summaries: AttendanceSummary[]
  totals: DetailTotals
  detailStatus: DetailStatus
  detailTotalCount: number
  needsReviewTotal: number
  loading: boolean
}>()

const emit = defineEmits<{
  back: []
  'update:detail-status': [value: DetailStatus]
  openLog: []
}>()

const detailStatusModel = computed({
  get: () => props.detailStatus,
  set: (value: DetailStatus) => emit('update:detail-status', value),
})

function handlePrint() {
  if (!props.unit)
    return

  // Must open the window synchronously (before any await) so browsers don't block the pop-up.
  const printWindow = openSummaryPrintPlaceholder()

  printAttendanceSummaries(printWindow, {
    unitName: props.unit.unit_name || props.unit.unit_code || props.unit.unit_id,
    unitCode: props.unit.unit_code || props.unit.unit_id,
    monthLabel: props.monthLabel,
    summaries: props.summaries,
    totals: props.totals,
  })
}
</script>

<template>
  <VCard>
    <VCardTitle class="d-flex flex-wrap align-center justify-space-between gap-2">
      <div class="d-flex flex-wrap align-center gap-2">
        <VBtn
          variant="text"
          prepend-icon="ri-arrow-left-line"
          @click="emit('back')"
        >
          Back to overview
        </VBtn>
        <div>
          <div class="font-weight-medium">
            {{ unit?.unit_name || unit?.unit_code }}
          </div>
          <div class="text-caption text-medium-emphasis">
            {{ monthLabel }}
          </div>
        </div>
      </div>
      <div class="d-flex flex-wrap gap-2">
        <VChip
          color="primary"
          variant="tonal"
          label
          prepend-icon="ri-calendar-line"
        >
          {{ totals.days }} days
        </VChip>
        <VChip
          color="success"
          variant="tonal"
          label
          prepend-icon="ri-time-line"
        >
          {{ formatTotalHours(totals.regular, totals.reliable) }} regular · {{ formatTotalSlots(totals.regularSlots, totals.reliable) }} slots
        </VChip>
        <VChip
          color="info"
          variant="tonal"
          label
          prepend-icon="ri-flashlight-line"
        >
          {{ formatTotalHours(totals.overtime, totals.reliable) }} OT · {{ formatTotalSlots(totals.otSlots, totals.reliable) }} slots
        </VChip>
        <VChip
          v-if="totals.autoCheckoutDays > 0"
          color="warning"
          variant="tonal"
          label
          prepend-icon="ri-time-line"
          title="Days closed by day-boundary auto checkout (23:59)"
        >
          {{ totals.autoCheckoutDays }} auto checkout
        </VChip>
        <VChip
          v-if="totals.needsReviewDays > 0"
          color="warning"
          variant="tonal"
          label
          prepend-icon="ri-alarm-warning-line"
          title="Incomplete or auto-closed days that need a real check-out"
        >
          {{ totals.needsReviewDays }} need review
        </VChip>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-printer-line"
          title="Print this table for payroll records"
          @click="handlePrint"
        >
          Print
        </VBtn>
      </div>
    </VCardTitle>
    <VCardText
      v-if="needsReviewTotal > 0"
      class="pb-0"
    >
      <VAlert
        type="warning"
        variant="tonal"
        density="compact"
        class="mb-2"
      >
        <div class="d-flex flex-wrap align-center justify-space-between gap-2">
          <div>
            <strong>{{ needsReviewTotal }}</strong> Incomplete record{{ needsReviewTotal === 1 ? '' : 's' }}.
            Make sure all data are complete and generate again
          </div>
          <div class="d-flex flex-wrap gap-2">
            <VBtn
              size="small"
              variant="tonal"
              color="warning"
              prepend-icon="ri-filter-line"
              @click="detailStatusModel = 'needs_review'"
            >
              Show incomplete only
            </VBtn>
            <VBtn
              size="small"
              color="warning"
              prepend-icon="ri-edit-box-line"
              @click="emit('openLog')"
            >
              Attendance Log
            </VBtn>
          </div>
        </div>
      </VAlert>
    </VCardText>
    <VCardText class="pb-0">
      <VChipGroup
        v-model="detailStatusModel"
        mandatory
        selected-class="text-primary"
      >
        <VChip
          v-for="option in detailStatusOptions"
          :key="option.value"
          :value="option.value"
          :prepend-icon="detailStatusFilterIcon(option.value)"
          label
        >
          {{ option.title }}
        </VChip>
      </VChipGroup>
    </VCardText>
    <div class="summaries-table-scroll">
      <VTable
        class="summaries-table"
        density="compact"
        hover
      >
        <thead>
          <tr>
            <th>
              <span class="th-label">
                <VIcon
                  icon="ri-calendar-event-line"
                  size="14"
                />
                Date
              </span>
            </th>
            <th>
              <span
                class="th-label"
                title="First check-in"
              >
                <VIcon
                  icon="ri-login-box-line"
                  size="14"
                />
                First In
              </span>
            </th>
            <th>
              <span
                class="th-label"
                title="Last check-out"
              >
                <VIcon
                  icon="ri-logout-box-line"
                  size="14"
                />
                Last Out
              </span>
            </th>
            <th class="text-end">
              <span
                class="th-label"
                title="Regular hours"
              >
                <VIcon
                  icon="ri-time-line"
                  size="14"
                />
                Regular
              </span>
            </th>
            <th class="text-end">
              <span
                class="th-label"
                title="Regular 15-min slots"
              >
                <VIcon
                  icon="ri-grid-line"
                  size="14"
                />
                Reg slots
              </span>
            </th>
            <th class="text-end">
              <span
                class="th-label"
                title="Overtime hours"
              >
                <VIcon
                  icon="ri-flashlight-line"
                  size="14"
                />
                OT
              </span>
            </th>
            <th class="text-end">
              <span
                class="th-label"
                title="Overtime 15-min slots"
              >
                <VIcon
                  icon="ri-apps-2-line"
                  size="14"
                />
                OT slots
              </span>
            </th>
            <th>
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in summaries"
            :key="s.id"
          >
            <td>
              <SummaryDateCell :date="s.summary_date" />
            </td>
            <td>
              <span
                v-if="s.first_check_in"
                class="cell-metric"
                title="First check-in"
              >
                <VIcon
                  icon="ri-login-box-line"
                  size="14"
                  class="text-success"
                />
                <span class="text-caption">{{ formatAttendanceDateTime(s.first_check_in) }}</span>
              </span>
              <span
                v-else
                class="text-medium-emphasis"
              >—</span>
            </td>
            <td>
              <span
                v-if="s.last_check_out"
                class="cell-metric"
                title="Last check-out"
              >
                <VIcon
                  icon="ri-logout-box-line"
                  size="14"
                  class="text-info"
                />
                <span class="text-caption">{{ formatAttendanceDateTime(s.last_check_out) }}</span>
              </span>
              <span
                v-else
                class="text-medium-emphasis"
              >—</span>
            </td>
            <td class="text-end">
              <span
                class="cell-metric"
                title="Regular hours"
              >
                <VIcon
                  icon="ri-time-line"
                  size="14"
                  class="text-success"
                />
                {{ formatDayHours(s, s.regular_hours) }}
              </span>
            </td>
            <td class="text-end">
              <span
                class="cell-metric text-medium-emphasis"
                title="Regular 15-min slots"
              >
                <VIcon
                  icon="ri-grid-line"
                  size="14"
                />
                {{ formatDaySlots(s, s.regular_slots) }}
              </span>
            </td>
            <td class="text-end">
              <span
                class="cell-metric"
                title="Overtime hours"
              >
                <VIcon
                  icon="ri-flashlight-line"
                  size="14"
                  class="text-info"
                />
                {{ formatDayHours(s, s.overtime_hours) }}
              </span>
            </td>
            <td class="text-end">
              <span
                class="cell-metric text-medium-emphasis"
                title="Overtime 15-min slots"
              >
                <VIcon
                  icon="ri-apps-2-line"
                  size="14"
                />
                {{ formatDaySlots(s, s.ot_slots) }}
              </span>
            </td>
            <td>
              <div class="d-flex flex-wrap align-center gap-1">
                <VChip
                  :color="summaryStatusColor(s)"
                  size="small"
                  label
                  :prepend-icon="summaryStatusIcon(s)"
                >
                  {{ summaryStatusLabel(s) }}
                </VChip>
              </div>
            </td>
          </tr>
          <tr
            v-if="summaries.length > 0"
            class="font-weight-bold"
          >
            <td>Total</td>
            <td />
            <td />
            <td class="text-end">
              <span
                class="cell-metric"
                :title="totals.reliable ? 'Regular hours total' : 'Total hidden while incomplete / needs-review days are present'"
              >
                <VIcon
                  icon="ri-time-line"
                  size="14"
                  class="text-success"
                />
                {{ formatTotalHours(totals.regular, totals.reliable) }}
              </span>
            </td>
            <td class="text-end">
              <span
                class="cell-metric text-medium-emphasis"
                :title="totals.reliable ? 'Regular slots total' : 'Total hidden while incomplete / needs-review days are present'"
              >
                <VIcon
                  icon="ri-grid-line"
                  size="14"
                />
                {{ formatTotalSlots(totals.regularSlots, totals.reliable) }}
              </span>
            </td>
            <td class="text-end">
              <span
                class="cell-metric"
                :title="totals.reliable ? 'Overtime hours total' : 'Total hidden while incomplete / needs-review days are present'"
              >
                <VIcon
                  icon="ri-flashlight-line"
                  size="14"
                  class="text-info"
                />
                {{ formatTotalHours(totals.overtime, totals.reliable) }}
              </span>
            </td>
            <td class="text-end">
              <span
                class="cell-metric text-medium-emphasis"
                :title="totals.reliable ? 'Overtime slots total' : 'Total hidden while incomplete / needs-review days are present'"
              >
                <VIcon
                  icon="ri-apps-2-line"
                  size="14"
                />
                {{ formatTotalSlots(totals.otSlots, totals.reliable) }}
              </span>
            </td>
            <td />
          </tr>
          <tr v-if="summaries.length === 0 && !loading">
            <td
              colspan="8"
              class="text-center text-medium-emphasis py-6"
            >
              {{ detailStatus === 'needs_review'
                ? 'No days need review for this month.'
                : 'No daily records match this status filter.' }}
            </td>
          </tr>
        </tbody>
      </VTable>
    </div>
    <div class="text-caption text-medium-emphasis pa-3">
      {{ summaries.length }} shown · {{ detailTotalCount }} records loaded for this month
    </div>
  </VCard>
</template>

<style scoped lang="scss">
.summaries-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.summaries-table :deep(th),
.summaries-table :deep(td) {
  white-space: nowrap;
}

.th-label,
.cell-metric {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.text-end .th-label,
.text-end .cell-metric {
  justify-content: flex-end;
}
</style>
