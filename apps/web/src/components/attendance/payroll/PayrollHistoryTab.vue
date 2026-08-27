<script setup lang="ts">
import type { PayrollRecord, PayrollStats } from '@/api/attendance/payroll'
import {
  formatPayrollCurrency,
  formatPayrollHours,
  payrollStatusColorMap,
  payrollStatusIcon,
  payrollStatusOptions,
  safePayrollNumber,
} from '@/utils/payrollDisplay'

const props = defineProps<{
  monthLabel: string
  records: PayrollRecord[]
  stats: PayrollStats | null
  loading: boolean
  refreshing: boolean
  search: string
  filterStatus: string
  unitType: string
  page: number
  pageSize: number
  pageSizeOptions: number[]
  totalCount: number
  totalPages: number
  listCaption: string
  canDelete: boolean
}>()

const emit = defineEmits<{
  'update:search': [value: string]
  'update:filterStatus': [value: string]
  'update:unitType': [value: string]
  'update:page': [value: number]
  'update:pageSize': [value: number]
  refresh: []
  review: []
  generate: []
  detail: [record: PayrollRecord]
  delete: [record: PayrollRecord]
}>()

const searchModel = computed({
  get: () => props.search,
  set: (value: string) => emit('update:search', value ?? ''),
})

const filterStatusModel = computed({
  get: () => props.filterStatus,
  set: (value: string) => emit('update:filterStatus', value ?? ''),
})

const unitTypeModel = computed({
  get: () => props.unitType,
  set: (value: string) => emit('update:unitType', value),
})

const pageModel = computed({
  get: () => props.page,
  set: (value: number) => emit('update:page', value),
})

const pageSizeModel = computed({
  get: () => props.pageSize,
  set: (value: number) => emit('update:pageSize', value),
})

const visibleRecords = computed(() => {
  const q = props.search.trim().toLowerCase()
  if (!q)
    return props.records

  return props.records.filter(r =>
    (r.unit_name || '').toLowerCase().includes(q)
    || (r.unit_code || '').toLowerCase().includes(q),
  )
})

const statCards = computed(() => {
  const stats = props.stats
  const gross = safePayrollNumber(stats?.total_gross_pay ?? 0)
  const net = safePayrollNumber(stats?.total_net_pay ?? 0)
  const approved = stats?.approved ?? 0
  const paid = stats?.paid ?? 0
  const pending = stats?.pending ?? 0

  return [
    {
      label: 'Slips',
      value: String(props.totalCount),
      hint: props.listCaption || 'this month',
      icon: 'ri-file-list-3-line',
      color: 'primary',
    },
    {
      label: 'Gross pay',
      value: formatPayrollCurrency(gross),
      hint: props.monthLabel,
      icon: 'ri-money-dollar-circle-line',
      color: 'info',
    },
    {
      label: 'Net pay',
      value: formatPayrollCurrency(net),
      hint: props.monthLabel,
      icon: 'ri-wallet-3-line',
      color: 'success',
    },
    {
      label: 'Progress',
      value: String(paid),
      hint: `${approved} approved · ${pending} still open`,
      icon: 'ri-checkbox-circle-line',
      color: 'secondary',
    },
  ]
})
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-center justify-space-between gap-3 mb-3">
      <div>
        <div class="text-subtitle-1 font-weight-medium">
          Monthly history
        </div>
        <div class="text-body-2 text-medium-emphasis">
          Lookup slips for {{ monthLabel }}. To change pay or status, open Review.
        </div>
      </div>
      <div class="d-flex flex-wrap align-center gap-2">
        <VBtn
          color="primary"
          variant="tonal"
          prepend-icon="ri-file-paper-2-line"
          @click="emit('review')"
        >
          Review slips
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

    <VRow
      class="mb-3"
      dense
    >
      <VCol
        cols="12"
        sm="6"
        md="3"
      >
        <VTextField
          v-model="searchModel"
          label="Search staff"
          density="compact"
          prepend-inner-icon="ri-search-line"
          clearable
          hide-details
        />
      </VCol>
      <VCol
        cols="12"
        sm="6"
        md="3"
      >
        <VSelect
          v-model="filterStatusModel"
          :items="payrollStatusOptions"
          item-title="title"
          item-value="value"
          label="Status"
          density="compact"
          prepend-inner-icon="ri-filter-3-line"
          hide-details
        />
      </VCol>
      <VCol
        cols="12"
        sm="6"
        md="3"
      >
        <VSelect
          v-model="unitTypeModel"
          :items="[{ title: 'Staff', value: 'staff' }, { title: 'Student', value: 'student' }]"
          item-title="title"
          item-value="value"
          label="Type"
          density="compact"
          prepend-inner-icon="ri-user-line"
          hide-details
        />
      </VCol>
    </VRow>

    <VProgressLinear
      v-if="loading && !refreshing"
      indeterminate
      color="primary"
      class="mb-2"
    />

    <VCard>
      <VCardTitle class="d-flex flex-wrap align-center justify-space-between gap-2">
        <span class="d-flex align-center gap-2">
          <VIcon
            icon="ri-list-check-2"
            size="20"
          />
          {{ monthLabel }} slips
        </span>
        <span class="text-caption text-medium-emphasis">
          {{ listCaption || monthLabel }}
        </span>
      </VCardTitle>
      <div class="payroll-table-scroll">
        <VTable
          class="payroll-table"
          density="compact"
          hover
        >
          <thead>
            <tr>
              <th>Staff</th>
              <th class="text-end">
                Days
              </th>
              <th class="text-end">
                Hours
              </th>
              <th class="text-end">
                Gross
              </th>
              <th class="text-end">
                Net
              </th>
              <th>Status</th>
              <th class="col-actions" />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in visibleRecords"
              :key="r.id"
              class="payroll-row"
              @click="emit('detail', r)"
            >
              <td>
                <div class="d-flex align-center gap-2">
                  <VAvatar
                    color="primary"
                    variant="tonal"
                    size="28"
                    rounded
                  >
                    <VIcon
                      icon="ri-user-line"
                      size="16"
                    />
                  </VAvatar>
                  <div>
                    <div class="font-weight-medium">
                      {{ r.unit_name || '—' }}
                    </div>
                    <div
                      v-if="r.unit_code"
                      class="text-caption text-medium-emphasis"
                    >
                      {{ r.unit_code }}
                    </div>
                  </div>
                </div>
              </td>
              <td class="text-end">
                {{ r.total_work_days }}
              </td>
              <td class="text-end">
                <div class="cell-metric text-success justify-end">
                  <VIcon
                    icon="ri-time-line"
                    size="14"
                  />
                  {{ formatPayrollHours(r.total_regular_hours) }}
                </div>
                <div class="text-caption text-medium-emphasis">
                  OT {{ formatPayrollHours(r.total_overtime_hours) }}
                </div>
              </td>
              <td class="text-end">
                {{ formatPayrollCurrency(r.gross_pay) }}
              </td>
              <td class="text-end font-weight-medium text-primary">
                {{ formatPayrollCurrency(r.net_pay) }}
              </td>
              <td>
                <VChip
                  :color="payrollStatusColorMap[r.status] ?? 'grey'"
                  size="small"
                  label
                  :prepend-icon="payrollStatusIcon(r.status)"
                >
                  {{ r.status }}
                </VChip>
              </td>
              <td class="col-actions">
                <div class="d-flex flex-nowrap align-center">
                  <VBtn
                    size="small"
                    variant="text"
                    prepend-icon="ri-eye-line"
                    @click.stop="emit('detail', r)"
                  >
                    Details
                  </VBtn>
                  <VBtn
                    v-if="canDelete"
                    icon
                    size="small"
                    variant="text"
                    color="error"
                    @click.stop="emit('delete', r)"
                  >
                    <VIcon>ri-delete-bin-line</VIcon>
                  </VBtn>
                </div>
              </td>
            </tr>
            <tr v-if="visibleRecords.length === 0 && !loading">
              <td
                colspan="7"
                class="text-center text-medium-emphasis py-8"
              >
                <div class="mb-2">
                  {{ records.length === 0 ? `No slips for ${monthLabel}.` : 'No slips match this search.' }}
                </div>
                <VBtn
                  v-if="records.length === 0"
                  color="primary"
                  variant="tonal"
                  prepend-icon="ri-magic-line"
                  @click="emit('generate')"
                >
                  Generate payroll
                </VBtn>
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <div class="d-flex align-center justify-space-between pa-3">
        <div class="d-flex align-center gap-2">
          <span class="text-caption text-medium-emphasis">{{ listCaption }}</span>
          <VSelect
            v-model="pageSizeModel"
            :items="pageSizeOptions"
            density="compact"
            variant="plain"
            hide-details
            style="max-width: 80px;"
          />
          <span class="text-caption text-medium-emphasis">per page</span>
        </div>
        <VPagination
          v-model="pageModel"
          :length="totalPages"
          :total-visible="5"
          density="compact"
          size="small"
        />
      </div>
    </VCard>
  </div>
</template>

<style scoped lang="scss">
.payroll-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.payroll-table :deep(th),
.payroll-table :deep(td) {
  white-space: nowrap;
}

.payroll-table :deep(.col-actions) {
  width: 1%;
  white-space: nowrap;
  vertical-align: middle;
}

.payroll-row {
  cursor: pointer;
}

.cell-metric {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.text-end .cell-metric {
  justify-content: flex-end;
}
</style>
