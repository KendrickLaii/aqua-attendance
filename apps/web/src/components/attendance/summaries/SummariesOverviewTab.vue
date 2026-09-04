<script setup lang="ts">
import type { SummaryOverviewItem, SummaryOverviewStats } from '@/api/attendance/summaries'
import { formatHours, typeColor, typeLabel } from '@/utils/summaryDisplay'

const props = defineProps<{
  items: SummaryOverviewItem[]
  stats: SummaryOverviewStats | null
  loading: boolean
  monthLabel: string
  search: string
  caption: string
  page: number
  pageSize: number
  pageSizeOptions: number[]
  totalPages: number
}>()

const emit = defineEmits<{
  'update:search': [value: string]
  'detail': [item: SummaryOverviewItem]
  'pageChange': [value: number]
  'pageSizeChange': [value: number]
}>()

const searchModel = computed({
  get: () => props.search,
  set: (value: string) => emit('update:search', value ?? ''),
})

const statCards = computed(() => {
  const stats = props.stats
  const people = stats?.people ?? 0
  const days = stats?.days_present ?? 0
  const complete = stats?.days_complete ?? 0
  const regular = Number.isFinite(stats?.total_regular_hours) ? Number(stats?.total_regular_hours) : 0
  const overtime = Number.isFinite(stats?.total_overtime_hours) ? Number(stats?.total_overtime_hours) : 0
  const completionRate = days > 0 ? `${Math.round((complete / days) * 100)}%` : '-'

  return [
    {
      label: 'People',
      value: String(people),
      hint: 'filtered month total',
      icon: 'ri-group-line',
      color: 'primary',
    },
    {
      label: 'Records',
      value: String(days),
      hint: 'filtered month · daily rows',
      icon: 'ri-calendar-line',
      color: 'secondary',
    },
    {
      label: 'Complete rate',
      value: completionRate,
      hint: `${complete}/${days} complete · month`,
      icon: 'ri-checkbox-circle-line',
      color: 'success',
    },
    {
      label: 'Total hours',
      value: formatHours(regular + overtime),
      hint: `${formatHours(regular)} regular + ${formatHours(overtime)} OT · month`,
      icon: 'ri-time-line',
      color: 'info',
    },
  ]
})
</script>

<template>
  <div>
    <StatCards :cards="statCards" />

    <VCard>
      <VCardTitle class="d-flex flex-wrap align-center justify-space-between gap-2">
        <span>Monthly overview</span>
        <div class="d-flex flex-wrap align-center gap-2">
          <VTextField
            v-model="searchModel"
            placeholder="Search name / code"
            prepend-inner-icon="ri-search-line"
            density="compact"
            hide-details
            clearable
            class="search-field"
          />
          <span class="text-caption text-medium-emphasis">
            {{ caption || monthLabel }}
          </span>
        </div>
      </VCardTitle>
      <div class="summaries-table-scroll">
        <VTable
          class="summaries-table"
          density="compact"
          hover
        >
          <thead>
            <tr>
              <th>
                Unit
              </th>
              <th>
                Type
              </th>
              <th class="text-end">
                <span
                  class="th-label"
                  title="Days present"
                >
                  <VIcon
                    icon="ri-calendar-line"
                    size="14"
                  />
                  Days
                </span>
              </th>
              <th class="text-end">
                <span
                  class="th-label"
                  title="Complete days"
                >
                  <VIcon
                    icon="ri-checkbox-circle-line"
                    size="14"
                  />
                  Complete
                </span>
              </th>
              <th class="text-end">
                <span
                  class="th-label"
                  title="Incomplete days"
                >
                  <VIcon
                    icon="ri-error-warning-line"
                    size="14"
                  />
                  Incomplete
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
              <th class="col-actions" />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in items"
              :key="item.unit_id"
              class="summary-row"
              @click="emit('detail', item)"
            >
              <td>
                <div class="font-weight-medium">
                  {{ item.unit_name || '—' }}
                </div>
                <div class="text-caption text-medium-emphasis">
                  {{ item.unit_code || item.unit_id }}
                </div>
              </td>
              <td>
                <VChip
                  :color="typeColor(item.unit_type)"
                  size="small"
                  label
                  :prepend-icon="item.unit_type === 'staff' ? 'ri-user-line' : 'ri-graduation-cap-line'"
                >
                  {{ typeLabel(item.unit_type) }}
                </VChip>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric"
                  title="Days present"
                >
                  <VIcon
                    icon="ri-calendar-line"
                    size="14"
                    class="text-medium-emphasis"
                  />
                  {{ item.days_present }}
                </span>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric"
                  title="Complete days"
                >
                  <VIcon
                    icon="ri-checkbox-circle-line"
                    size="14"
                    class="text-success"
                  />
                  {{ item.days_complete }}
                </span>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric"
                  title="Incomplete days"
                >
                  <VIcon
                    icon="ri-error-warning-line"
                    size="14"
                    class="text-warning"
                  />
                  {{ item.days_incomplete }}
                </span>
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
                  {{ formatHours(item.total_regular_hours) }}
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
                  {{ item.total_regular_slots }}
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
                  {{ formatHours(item.total_overtime_hours) }}
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
                  {{ item.total_ot_slots }}
                </span>
              </td>
              <td class="col-actions">
                <VBtn
                  variant="text"
                  size="small"
                  prepend-icon="ri-calendar-schedule-line"
                  @click.stop="emit('detail', item)"
                >
                  View days
                </VBtn>
              </td>
            </tr>
            <tr v-if="items.length === 0 && !loading">
              <td
                colspan="10"
                class="text-center text-medium-emphasis py-6"
              >
                No summaries found for {{ monthLabel }}. Click Generate to build them from attendance events.
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <div class="d-flex align-center justify-space-between pa-3">
        <div class="d-flex align-center gap-2">
          <span class="text-caption text-medium-emphasis">{{ caption }}</span>
          <VSelect
            :model-value="pageSize"
            :items="pageSizeOptions"
            density="compact"
            variant="plain"
            hide-details
            style="max-width: 80px;"
            @update:model-value="emit('pageSizeChange', $event)"
          />
          <span class="text-caption text-medium-emphasis">per page</span>
        </div>
        <VPagination
          :model-value="page"
          :length="totalPages"
          :total-visible="5"
          density="compact"
          size="small"
          @update:model-value="emit('pageChange', $event)"
        />
      </div>
    </VCard>
  </div>
</template>

<style scoped lang="scss">
.search-field {
  inline-size: 220px;
}

.summaries-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.summaries-table :deep(th),
.summaries-table :deep(td) {
  white-space: nowrap;
}

.summaries-table :deep(.col-actions) {
  width: 1%;
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

.summary-row {
  cursor: pointer;
}
</style>
