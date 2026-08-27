<script setup lang="ts">
import type { PayrollRecord } from '@/api/attendance/payroll'
import {
  canApprovePayroll,
  canEditPayrollAdjustments,
  canPayPayroll,
  formatPayrollCurrency,
  formatPayrollHours,
  payrollReviewFilterChips,
  payrollStatusColorMap,
  payrollStatusIcon,
  safePayrollNumber,
} from '@/utils/payrollDisplay'

const props = defineProps<{
  monthLabel: string
  slips: PayrollRecord[]
  loading: boolean
  refreshing: boolean
  error: string
  search: string
  status: string
  canDelete: boolean
}>()

const emit = defineEmits<{
  'update:search': [value: string]
  'update:status': [value: string]
  refresh: []
  generate: []
  approve: [record: PayrollRecord]
  pay: [record: PayrollRecord]
  detail: [record: PayrollRecord]
  delete: [record: PayrollRecord]
  adjChange: [record: PayrollRecord]
}>()

const searchModel = computed({
  get: () => props.search,
  set: (value: string) => emit('update:search', value ?? ''),
})

type AdjField = 'adjustment_1' | 'adjustment_2'
const focusedAdjKey = ref<string | null>(null)
const focusedAdjRaw = ref('')

const visibleSlips = computed(() => {
  const q = props.search.trim().toLowerCase()
  const status = props.status

  return props.slips.filter(r => {
    if (status && r.status !== status)
      return false
    if (!q)
      return true

    return (r.unit_name || '').toLowerCase().includes(q)
      || (r.unit_code || '').toLowerCase().includes(q)
  }).sort((a, b) => {
    const order: Record<string, number> = {
      calculated: 0,
      draft: 1,
      approved: 2,
      paid: 3,
      cancelled: 4,
    }

    const byStatus = (order[a.status] ?? 9) - (order[b.status] ?? 9)
    if (byStatus !== 0)
      return byStatus

    return (a.unit_name || a.unit_code || '').localeCompare(b.unit_name || b.unit_code || '')
  })
})

const totals = computed(() => {
  const slips = visibleSlips.value
  const all = props.slips
  const gross = slips.reduce((sum, r) => sum + safePayrollNumber(r.gross_pay), 0)
  const net = slips.reduce((sum, r) => sum + safePayrollNumber(r.net_pay), 0)
  const pending = all.filter(r => r.status === 'draft' || r.status === 'calculated').length
  const approved = all.filter(r => r.status === 'approved').length
  const paid = all.filter(r => r.status === 'paid').length

  return { gross, net, count: slips.length, pending, approved, paid }
})

const statCards = computed(() => {
  const hint = props.search.trim() || props.status
    ? 'matching filters'
    : props.monthLabel

  return [
    {
      label: 'Slips',
      value: String(totals.value.count),
      hint,
      icon: 'ri-file-paper-2-line',
      color: 'primary',
    },
    {
      label: 'Gross pay',
      value: formatPayrollCurrency(totals.value.gross),
      hint,
      icon: 'ri-money-dollar-circle-line',
      color: 'info',
    },
    {
      label: 'Net pay',
      value: formatPayrollCurrency(totals.value.net),
      hint,
      icon: 'ri-wallet-3-line',
      color: 'success',
    },
    {
      label: 'Progress',
      value: String(totals.value.paid),
      hint: `${totals.value.approved} approved · ${totals.value.pending} pending`,
      icon: 'ri-checkbox-circle-line',
      color: 'secondary',
    },
  ]
})

function adjFocusKey(record: PayrollRecord, field: AdjField) {
  return `${record.id}:${field}`
}

function parseCurrencyInput(display: string | number | null | undefined) {
  const s = String(display ?? '').replace(/,/g, '').trim()
  if (s === '' || s === '-' || s === '.' || s === '-.')
    return 0
  const n = Number(s)

  return Number.isFinite(n) ? n : 0
}

function adjDisplayValue(record: PayrollRecord, field: AdjField) {
  if (focusedAdjKey.value === adjFocusKey(record, field))
    return focusedAdjRaw.value

  return formatPayrollCurrency(record[field])
}

function onAdjFocus(record: PayrollRecord, field: AdjField) {
  if (!canEditPayrollAdjustments(record))
    return

  focusedAdjKey.value = adjFocusKey(record, field)

  const n = Number(record[field])

  focusedAdjRaw.value = Number.isFinite(n) ? String(n) : '0'
}

function onAdjInput(record: PayrollRecord, field: AdjField, v: string | number | null) {
  if (!canEditPayrollAdjustments(record))
    return

  focusedAdjRaw.value = v == null ? '' : String(v)
  record[field] = parseCurrencyInput(focusedAdjRaw.value)
  emit('adjChange', record)
}

function onAdjBlur(record: PayrollRecord, field: AdjField) {
  if (!canEditPayrollAdjustments(record))
    return

  record[field] = parseCurrencyInput(focusedAdjRaw.value)
  focusedAdjKey.value = null
  focusedAdjRaw.value = ''
}

function onRemarkChange(record: PayrollRecord) {
  emit('adjChange', record)
}
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-center justify-space-between gap-3 mb-3">
      <div>
        <div class="text-subtitle-1 font-weight-medium">
          Review slips
        </div>
        <div class="text-body-2 text-medium-emphasis">
          Edit adjustments, then approve. Paid slips stay in History.
        </div>
      </div>
      <div class="d-flex flex-wrap align-center gap-2">
        <VBtn
          color="primary"
          prepend-icon="ri-magic-line"
          @click="emit('generate')"
        >
          Generate
        </VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="refreshing"
          @click="emit('refresh')"
        >
          Refresh
        </VBtn>
      </div>
    </div>

    <StatCards :cards="statCards" />

    <div class="d-flex flex-wrap align-center justify-space-between gap-3 mb-4">
      <div class="d-flex flex-wrap align-center gap-2">
        <VChip
          v-for="chip in payrollReviewFilterChips"
          :key="chip.value || 'all'"
          :color="status === chip.value ? 'primary' : undefined"
          :variant="status === chip.value ? 'flat' : 'tonal'"
          label
          class="review-filter-chip"
          @click="emit('update:status', chip.value)"
        >
          {{ chip.title }}
        </VChip>
      </div>
      <VTextField
        v-model="searchModel"
        label="Search staff"
        density="compact"
        prepend-inner-icon="ri-search-line"
        clearable
        hide-details
        class="review-search"
      />
    </div>

    <VAlert
      v-if="error"
      type="error"
      variant="tonal"
      density="compact"
      class="mb-4"
    >
      {{ error }}
    </VAlert>

    <VProgressLinear
      v-if="loading && !refreshing"
      indeterminate
      color="primary"
      class="mb-4"
    />

    <VRow v-if="!loading || refreshing">
      <VCol
        v-for="record in visibleSlips"
        :key="record.id"
        cols="12"
        md="6"
        xl="4"
        class="d-flex"
      >
        <VCard class="payroll-invoice h-100 w-100 d-flex flex-column">
          <VCardItem class="invoice-header">
            <template #prepend>
              <VAvatar
                color="primary"
                variant="tonal"
                size="40"
                rounded
              >
                <VIcon icon="ri-user-line" />
              </VAvatar>
            </template>
            <template #title>
              <div class="d-flex align-center gap-2 flex-wrap">
                <span class="text-h6 font-weight-bold">
                  {{ record.unit_name || '—' }}
                </span>
                <VChip
                  :color="payrollStatusColorMap[record.status] ?? 'grey'"
                  size="small"
                  label
                  :prepend-icon="payrollStatusIcon(record.status)"
                >
                  {{ record.status }}
                </VChip>
              </div>
            </template>
            <template #subtitle>
              <div class="text-medium-emphasis">
                {{ record.unit_code || record.unit_id }}
              </div>
            </template>
          </VCardItem>
          <VDivider />
          <VCardText class="invoice-body flex-grow-1">
            <div class="d-flex justify-space-between mb-4">
              <div>
                <div class="text-caption text-medium-emphasis d-flex align-center gap-1">
                  <VIcon
                    icon="ri-calendar-line"
                    size="14"
                  />
                  Period
                </div>
                <div class="font-weight-medium">
                  {{ record.payroll_period_start }} – {{ record.payroll_period_end }}
                </div>
              </div>
              <div class="text-end">
                <div class="text-caption text-medium-emphasis d-flex align-center justify-end gap-1">
                  <VIcon
                    icon="ri-calendar-check-line"
                    size="14"
                  />
                  Work days
                </div>
                <div class="font-weight-medium">
                  {{ record.total_work_days }}
                </div>
              </div>
            </div>

            <div class="invoice-grid">
              <div class="invoice-cell">
                <span class="text-caption text-success d-flex align-center gap-1">
                  <VIcon
                    icon="ri-time-line"
                    size="14"
                  />
                  Regular
                </span>
                <span class="font-weight-medium">{{ formatPayrollHours(record.total_regular_hours) }} h</span>
                <span class="text-caption text-medium-emphasis">{{ record.regular_slots }} slots</span>
              </div>
              <div class="invoice-cell">
                <span class="text-caption text-info d-flex align-center gap-1">
                  <VIcon
                    icon="ri-flashlight-line"
                    size="14"
                  />
                  Overtime
                </span>
                <span class="font-weight-medium">{{ formatPayrollHours(record.total_overtime_hours) }} h</span>
                <span class="text-caption text-medium-emphasis">{{ record.ot_slots }} slots</span>
              </div>
              <div class="invoice-cell">
                <span class="text-caption text-medium-emphasis d-flex align-center gap-1">
                  <VIcon
                    icon="ri-price-tag-3-line"
                    size="14"
                  />
                  Rate
                </span>
                <span class="font-weight-medium">{{ formatPayrollCurrency(record.hourly_rate_snapshot) }}/hr</span>
                <span class="text-caption text-medium-emphasis">OT ×{{ record.ot_multiplier_snapshot ?? 1.5 }}</span>
              </div>
            </div>

            <VDivider class="my-3" />

            <div class="invoice-line">
              <span>Base salary</span>
              <span class="font-weight-medium">{{ formatPayrollCurrency(record.base_salary) }}</span>
            </div>
            <div class="invoice-line">
              <span>Overtime pay</span>
              <span class="font-weight-medium">{{ formatPayrollCurrency(record.overtime_pay) }}</span>
            </div>
            <div class="invoice-line">
              <span>Holiday pay</span>
              <span class="font-weight-medium">{{ formatPayrollCurrency(record.holiday_pay) }}</span>
            </div>
            <div class="invoice-adj-row">
              <VTextField
                v-model="record.adjustment_1_remark"
                class="invoice-remark"
                label="Adjustment 1"
                density="compact"
                variant="outlined"
                hide-details
                :readonly="!canEditPayrollAdjustments(record)"
                :disabled="!canEditPayrollAdjustments(record)"
                @update:model-value="onRemarkChange(record)"
              />
              <VTextField
                :model-value="adjDisplayValue(record, 'adjustment_1')"
                class="invoice-adj-amount"
                density="compact"
                variant="underlined"
                hide-details
                inputmode="decimal"
                :readonly="!canEditPayrollAdjustments(record)"
                :disabled="!canEditPayrollAdjustments(record)"
                @focus="onAdjFocus(record, 'adjustment_1')"
                @blur="onAdjBlur(record, 'adjustment_1')"
                @update:model-value="(v) => onAdjInput(record, 'adjustment_1', v)"
              />
            </div>
            <div class="invoice-line total">
              <span>Gross pay</span>
              <span class="font-weight-bold">{{ formatPayrollCurrency(record.gross_pay) }}</span>
            </div>
            <div class="invoice-adj-row">
              <VTextField
                v-model="record.adjustment_2_remark"
                class="invoice-remark"
                label="Adjustment 2"
                density="compact"
                variant="outlined"
                hide-details
                :readonly="!canEditPayrollAdjustments(record)"
                :disabled="!canEditPayrollAdjustments(record)"
                @update:model-value="onRemarkChange(record)"
              />
              <VTextField
                :model-value="adjDisplayValue(record, 'adjustment_2')"
                class="invoice-adj-amount"
                density="compact"
                variant="underlined"
                hide-details
                inputmode="decimal"
                :readonly="!canEditPayrollAdjustments(record)"
                :disabled="!canEditPayrollAdjustments(record)"
                @focus="onAdjFocus(record, 'adjustment_2')"
                @blur="onAdjBlur(record, 'adjustment_2')"
                @update:model-value="(v) => onAdjInput(record, 'adjustment_2', v)"
              />
            </div>
            <div class="invoice-line grand">
              <span class="d-flex align-center gap-1">
                <VIcon
                  icon="ri-wallet-3-line"
                  size="18"
                  class="text-primary"
                />
                Net pay
              </span>
              <span class="text-h6 font-weight-bold text-primary">{{ formatPayrollCurrency(record.net_pay) }}</span>
            </div>
          </VCardText>
          <VDivider />
          <VCardActions class="justify-end">
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
              variant="text"
              prepend-icon="ri-eye-line"
              @click="emit('detail', record)"
            >
              Details
            </VBtn>
            <VBtn
              v-if="canDelete"
              icon
              size="small"
              variant="text"
              color="error"
              @click.stop="emit('delete', record)"
            >
              <VIcon>ri-delete-bin-line</VIcon>
            </VBtn>
          </VCardActions>
        </VCard>
      </VCol>
    </VRow>

    <VCard
      v-if="!loading && visibleSlips.length === 0"
      variant="outlined"
      class="text-center py-10 mt-4"
    >
      <VIcon
        icon="ri-file-paper-2-line"
        size="40"
        class="mb-2 text-medium-emphasis"
      />
      <div class="text-subtitle-1 font-weight-medium mb-1">
        {{ slips.length === 0
          ? `No slips for ${monthLabel}`
          : 'No slips match these filters' }}
      </div>
      <div class="text-body-2 text-medium-emphasis mb-4">
        {{ slips.length === 0
          ? 'Generate payroll from attendance summaries, then edit and approve here.'
          : 'Clear search or switch filter to see more slips.' }}
      </div>
      <VBtn
        v-if="slips.length === 0"
        color="primary"
        prepend-icon="ri-magic-line"
        @click="emit('generate')"
      >
        Generate payroll
      </VBtn>
    </VCard>
  </div>
</template>

<style scoped lang="scss">
.review-search {
  inline-size: 220px;
}

.review-filter-chip {
  cursor: pointer;
}

.payroll-invoice {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.invoice-header {
  padding-block: 16px;
}

.invoice-body {
  padding-block: 16px;
}

.invoice-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.invoice-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.invoice-line {
  display: flex;
  justify-content: space-between;
  padding-block: 4px;
}

.invoice-adj-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding-block: 6px;
}

.invoice-remark {
  flex: 1 1 auto;
  min-inline-size: 0;
}

.invoice-adj-amount {
  flex: 1 0 112px;
  max-inline-size: 140px;
}

.invoice-adj-amount :deep(input) {
  text-align: end;
}

.invoice-line.total {
  border-top: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
  margin-top: 4px;
  padding-top: 8px;
}

.invoice-line.grand {
  margin-top: 4px;
}
</style>
