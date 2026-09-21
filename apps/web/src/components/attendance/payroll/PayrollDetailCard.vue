<script setup lang="ts">
import type { PayrollRecord } from '@/api/attendance/payroll'
import type { AttendanceSummary } from '@/api/attendance/summaries'
import AutoCheckoutChip from '@/components/attendance/AutoCheckoutChip.vue'
import SummaryDateCell from '@/components/attendance/SummaryDateCell.vue'
import { formatAttendanceDateTime, isAutoCheckoutSummaryDay } from '@/utils/attendanceDisplay'
import {
  canApprovePayroll,
  canPayPayroll,
  formatPayrollChequeNumber,
  formatPayrollCurrency,
  formatPayrollHours,
  payrollDetailTotals,
  payrollStatusColorMap,
  payrollStatusIcon,
  payrollSummaryStatusColor,
  payrollSummaryStatusIcon,
  payrollSummaryStatusLabel,
} from '@/utils/payrollDisplay'

const props = defineProps<{
  record: PayrollRecord
  monthLabel: string
  summaries: AttendanceSummary[]
  loading: boolean
  detailTotalCount: number
}>()

const emit = defineEmits<{
  approve: [record: PayrollRecord]
  pay: [record: PayrollRecord]
  print: [record: PayrollRecord]
}>()

const detailTotals = computed(() =>
  payrollDetailTotals(
    props.summaries,
    props.summaries.filter(s => isAutoCheckoutSummaryDay(s)).length,
  ),
)
</script>

<template>
  <VCard>
    <VCardTitle class="d-flex flex-wrap align-center justify-space-between gap-2">
      <div>
        <div class="font-weight-medium">
          {{ record.unit_name || record.unit_code }}
        </div>
        <div class="text-caption text-medium-emphasis">
          {{ monthLabel }} · {{ record.payroll_period_start }} – {{ record.payroll_period_end }}
        </div>
      </div>
      <div class="d-flex flex-wrap gap-2">
        <VChip
          :color="payrollStatusColorMap[record.status] ?? 'grey'"
          label
          :prepend-icon="payrollStatusIcon(record.status)"
        >
          {{ record.status }}
        </VChip>
        <VChip
          color="success"
          label
          prepend-icon="ri-time-line"
        >
          {{ formatPayrollHours(record.total_regular_hours) }} regular
        </VChip>
        <VChip
          color="info"
          label
          prepend-icon="ri-flashlight-line"
        >
          {{ formatPayrollHours(record.total_overtime_hours) }} OT
        </VChip>
        <VChip
          color="primary"
          label
          prepend-icon="ri-wallet-3-line"
        >
          Net {{ formatPayrollCurrency(record.net_pay) }}
        </VChip>
        <VChip
          v-if="detailTotals.autoCheckoutDays > 0"
          color="warning"
          label
          prepend-icon="ri-time-line"
          title="Days closed by day-boundary auto checkout (23:59)"
        >
          {{ detailTotals.autoCheckoutDays }} auto checkout
        </VChip>
        <VBtn
          v-if="canApprovePayroll(record)"
          size="small"
          variant="tonal"
          color="success"
          prepend-icon="ri-checkbox-circle-line"
          @click="emit('approve', record)"
        >
          Approve
        </VBtn>
        <VBtn
          v-if="canPayPayroll(record)"
          size="small"
          variant="tonal"
          color="primary"
          prepend-icon="ri-money-dollar-circle-line"
          @click="emit('pay', record)"
        >
          Pay
        </VBtn>
        <VBtn
          size="small"
          variant="tonal"
          color="primary"
          prepend-icon="ri-printer-line"
          @click="emit('print', record)"
        >
          Print
        </VBtn>
      </div>
    </VCardTitle>
    <VCardText class="pb-0">
      <div class="payroll-metrics">
        <div class="payroll-metric">
          <div class="text-caption text-medium-emphasis">
            Base
          </div>
          <div class="text-h6 font-weight-bold">
            {{ formatPayrollCurrency(record.base_salary) }}
          </div>
          <div class="text-caption text-medium-emphasis mt-1">
            OT {{ formatPayrollCurrency(record.overtime_pay) }}
            · Holiday {{ formatPayrollCurrency(record.holiday_pay) }}
          </div>
        </div>
        <div class="payroll-metric">
          <div class="text-caption text-medium-emphasis">
            Adjustment 1
          </div>
          <div class="text-h6 font-weight-bold">
            {{ formatPayrollCurrency(record.adjustment_1) }}
          </div>
          <div class="text-caption text-medium-emphasis mt-1">
            {{ record.adjustment_1_remark || '—' }}
          </div>
          <div class="text-caption text-medium-emphasis mt-1">
            Base + OT + Holiday + Adj1 = Gross
          </div>
        </div>
        <div class="payroll-metric">
          <div class="text-caption text-medium-emphasis">
            Gross pay
          </div>
          <div class="text-h6 font-weight-bold">
            {{ formatPayrollCurrency(record.gross_pay) }}
          </div>
        </div>
        <div class="payroll-metric">
          <div class="text-caption text-medium-emphasis">
            Adjustment 2
          </div>
          <div class="text-h6 font-weight-bold">
            {{ formatPayrollCurrency(record.adjustment_2) }}
          </div>
          <div class="text-caption text-medium-emphasis mt-1">
            {{ record.adjustment_2_remark || '—' }}
          </div>
          <div class="text-caption text-medium-emphasis mt-1">
            Gross + Adj2 = Net
          </div>
        </div>
        <div class="payroll-metric">
          <div class="text-caption text-medium-emphasis">
            Net pay
          </div>
          <div class="text-h6 font-weight-bold text-primary">
            {{ formatPayrollCurrency(record.net_pay) }}
          </div>
        </div>
        <div class="payroll-metric">
          <div class="text-caption text-medium-emphasis">
            Cheque#
          </div>
          <div class="text-h6 font-weight-bold">
            {{ formatPayrollChequeNumber(record.cheque_number) }}
          </div>
        </div>
        <div class="payroll-metric">
          <div class="text-caption text-medium-emphasis">
            Cheque amount
          </div>
          <div class="text-h6 font-weight-bold">
            {{ formatPayrollCurrency(record.cheque_amount) }}
          </div>
        </div>
        <div class="payroll-metric">
          <div class="text-caption text-medium-emphasis">
            Cash amount
          </div>
          <div class="text-h6 font-weight-bold">
            {{ formatPayrollCurrency(record.cash_amount) }}
          </div>
          <div class="text-caption text-medium-emphasis mt-1">
            Cheque + Cash
          </div>
        </div>
      </div>
    </VCardText>
    <VCardText class="text-caption text-medium-emphasis pb-0">
      Daily attendance summaries used to calculate this payroll record. Adjustments can be edited on calculated slips only.
    </VCardText>
    <div class="payroll-table-scroll">
      <VTable
        class="payroll-table"
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
            <th>Status</th>
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
                {{ formatPayrollHours(s.regular_hours) }}
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
                {{ s.regular_slots }}
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
                {{ formatPayrollHours(s.overtime_hours) }}
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
                {{ s.ot_slots }}
              </span>
            </td>
            <td>
              <div class="d-flex flex-wrap align-center gap-1">
                <VChip
                  :color="payrollSummaryStatusColor(s)"
                  size="small"
                  label
                  :prepend-icon="payrollSummaryStatusIcon(s, isAutoCheckoutSummaryDay(s))"
                >
                  {{ payrollSummaryStatusLabel(s) }}
                </VChip>
                <AutoCheckoutChip
                  :notes="s.attendance_notes"
                  :last-check-out="s.last_check_out"
                />
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
                title="Regular hours total"
              >
                <VIcon
                  icon="ri-time-line"
                  size="14"
                  class="text-success"
                />
                {{ formatPayrollHours(detailTotals.regular) }}
              </span>
            </td>
            <td class="text-end">
              <span
                class="cell-metric text-medium-emphasis"
                title="Regular slots total"
              >
                <VIcon
                  icon="ri-grid-line"
                  size="14"
                />
                {{ detailTotals.regularSlots }}
              </span>
            </td>
            <td class="text-end">
              <span
                class="cell-metric"
                title="Overtime hours total"
              >
                <VIcon
                  icon="ri-flashlight-line"
                  size="14"
                  class="text-info"
                />
                {{ formatPayrollHours(detailTotals.overtime) }}
              </span>
            </td>
            <td class="text-end">
              <span
                class="cell-metric text-medium-emphasis"
                title="Overtime slots total"
              >
                <VIcon
                  icon="ri-apps-2-line"
                  size="14"
                />
                {{ detailTotals.otSlots }}
              </span>
            </td>
            <td />
          </tr>
          <tr v-if="summaries.length === 0 && !loading">
            <td
              colspan="8"
              class="text-center text-medium-emphasis py-6"
            >
              No daily summaries found for this unit in {{ monthLabel }}.
            </td>
          </tr>
        </tbody>
      </VTable>
    </div>
    <div class="text-caption text-medium-emphasis pa-3">
      {{ detailTotals.days }} day{{ detailTotals.days === 1 ? '' : 's' }} · {{ detailTotalCount }} records loaded for this month
    </div>
  </VCard>
</template>

<style scoped lang="scss">
.payroll-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 12px;
}

.payroll-metric {
  min-width: 118px;
  flex: 1 1 118px;
}

.payroll-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.payroll-table :deep(th),
.payroll-table :deep(td) {
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
