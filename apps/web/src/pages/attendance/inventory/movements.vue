<script setup lang="ts">
import {
  type InventoryItem,
  type InventoryMovement,
  type InventoryMovementTypeOut,
  type InventoryWarehouse,
  listInventoryItems,
  listInventoryMovements,
  listWarehouses,
  reasonCodeLabel,
} from '@/api/attendance/inventory'
import AttendancePaginationBar from '@/components/attendance/AttendancePaginationBar.vue'
import InventoryEmptyState from '@/components/attendance/inventory/InventoryEmptyState.vue'
import { ATTENDANCE_TIMEZONE, formatAttendanceDateTime } from '@/utils/attendanceDisplay'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { useLatestRequest } from '@/composables/useLatestRequest'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const loading = ref(true)
const loadError = ref('')

useAutoClearAlerts(loadError)

const warehouses = ref<InventoryWarehouse[]>([])
const items = ref<InventoryItem[]>([])
const movements = ref<InventoryMovement[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const listReq = useLatestRequest()

function attendanceDateKey(iso: string): string {
  return new Date(iso).toLocaleDateString('en-CA', { timeZone: ATTENDANCE_TIMEZONE })
}

function receivedDateLabel(movement: InventoryMovement): string | null {
  const effective = movement.effective_date
  if (!effective || effective === attendanceDateKey(movement.created_at))
    return null
  const [year, month, day] = effective.split('-')

  return `${day}/${month}/${year}`
}

const itemFilter = ref<string | null>(null)
const warehouseFilter = ref<string | null>(null)
const typeFilter = ref<InventoryMovementTypeOut | null>(null)
const reasonCodeFilter = ref<string | null>(null)
const dateFrom = ref('')
const dateTo = ref('')

const itemById = computed(() => new Map(items.value.map(i => [i.id, i])))
const warehouseById = computed(() => new Map(warehouses.value.map(l => [l.id, l])))

const itemOptions = computed(() =>
  items.value.map(i => ({
    value: i.id,
    title: [i.sku_code, i.name_zh].filter(Boolean).join(' · '),
  })),
)

const warehouseOptions = computed(() =>
  warehouses.value.map(l => ({
    value: l.id,
    title: [l.name_en, l.name_zh].filter(Boolean).join(' · '),
  })),
)

const typeOptions = [
  { value: 'in' as const, title: 'Stock in 入庫' },
  { value: 'out' as const, title: 'Stock out 出庫' },
  { value: 'adjust' as const, title: 'Adjust 調整' },
  { value: 'transfer_in' as const, title: 'Transfer in 調入' },
  { value: 'transfer_out' as const, title: 'Transfer out 調出' },
]

const reasonCodeOptions = [
  { value: 'opening', title: 'Opening 期初' },
  { value: 'damage', title: 'Damage 損毀' },
  { value: 'loss', title: 'Loss 遺失' },
  { value: 'gift', title: 'Gift 贈送' },
  { value: 'sample', title: 'Sample 樣品' },
  { value: 'internal_use', title: 'Internal use 內部使用' },
  { value: 'supplier_return', title: 'Supplier return 退貨' },
  { value: 'sale', title: 'Sale 銷售' },
  { value: 'sales_return', title: 'Sales return 銷售退回' },
  { value: 'other', title: 'Other 其他' },
]

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  loading.value = true
  try {
    const [warehouseList, itemList] = await Promise.all([
      listWarehouses({ is_active: true }),
      listInventoryItems(),
    ])

    warehouses.value = warehouseList
    items.value = itemList
    await loadMovements()
  }
  catch (e) {
    console.error('Failed to load movements', e)
    loadError.value = formatApiError(e, 'Failed to load movements.')
  }
  finally {
    loading.value = false
  }
})

async function loadMovements() {
  loadError.value = ''

  const token = listReq.next()
  try {
    const result = await listInventoryMovements({
      item_id: itemFilter.value ?? undefined,
      warehouse_id: warehouseFilter.value ?? undefined,
      type: typeFilter.value ?? undefined,
      reason_code: reasonCodeFilter.value ?? undefined,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })

    if (!listReq.isLatest(token))
      return
    movements.value = result.items
    total.value = result.total
  }
  catch (e) {
    if (!listReq.isLatest(token))
      return
    loadError.value = formatApiError(e, 'Failed to load movements.')
  }
}

function onFiltersChange() {
  page.value = 1
  loadMovements()
}

function itemLabel(id: string): string {
  const item = itemById.value.get(id)

  return item ? `${item.sku_code} · ${item.name_zh}` : id
}

function warehouseLabel(id: string): string {
  const location = warehouseById.value.get(id)

  return location ? (location.name_en || location.name_zh || id) : id
}

function typeLabel(type: string): string {
  return typeOptions.find(t => t.value === type)?.title ?? type
}
</script>

<template>
  <VContainer>
    <VRow
      class="mb-2"
      align="center"
    >
      <VCol>
        <div class="text-h5 font-weight-medium">
          Stock Movements 異動流水
        </div>
        <div class="text-body-2 text-medium-emphasis">
          這一頁列出所有入庫、出庫、調整和倉庫之間調撥的紀錄。
        </div>
      </VCol>
      <VCol cols="auto">
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="loading"
          @click="loadMovements"
        >
          Refresh
        </VBtn>
      </VCol>
    </VRow>

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

    <VCard>
      <VCardText class="d-flex flex-wrap gap-3 align-center">
        <VAutocomplete
          v-model="itemFilter"
          :items="itemOptions"
          label="Item"
          density="comfortable"
          style="max-width: 260px"
          hide-details
          clearable
          @update:model-value="onFiltersChange"
        />
        <VSelect
          v-model="warehouseFilter"
          :items="warehouseOptions"
          label="Warehouse 倉庫"
          density="comfortable"
          style="max-width: 240px"
          hide-details
          clearable
          @update:model-value="onFiltersChange"
        />
        <VSelect
          v-model="typeFilter"
          :items="typeOptions"
          label="Type"
          density="comfortable"
          style="max-width: 200px"
          hide-details
          clearable
          @update:model-value="onFiltersChange"
        />
        <VSelect
          v-model="reasonCodeFilter"
          :items="reasonCodeOptions"
          label="Reason code"
          density="comfortable"
          style="max-width: 200px"
          hide-details
          clearable
          @update:model-value="onFiltersChange"
        />
        <VTextField
          v-model="dateFrom"
          label="From"
          type="date"
          density="comfortable"
          style="max-width: 170px"
          hide-details
          @update:model-value="onFiltersChange"
        />
        <VTextField
          v-model="dateTo"
          label="To"
          type="date"
          density="comfortable"
          style="max-width: 170px"
          hide-details
          @update:model-value="onFiltersChange"
        />
      </VCardText>
      <div class="overflow-x-auto">
        <VTable>
          <thead>
            <tr>
              <th>Time</th>
              <th>Item</th>
              <th>Warehouse</th>
              <th>Type</th>
              <th class="text-end">
                Delta
              </th>
              <th class="text-end">
                Balance after
              </th>
              <th>Reason</th>
              <th>Reference</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="movement in movements"
              :key="movement.id"
            >
              <td>
                {{ formatAttendanceDateTime(movement.created_at) }}
                <VTooltip
                  v-if="receivedDateLabel(movement)"
                  text="實際收貨日期；上面係入系統時間"
                  location="bottom"
                >
                  <template #activator="{ props }">
                    <div
                      v-bind="props"
                      class="text-caption text-medium-emphasis"
                    >
                      Received {{ receivedDateLabel(movement) }}
                    </div>
                  </template>
                </VTooltip>
              </td>
              <td>{{ itemLabel(movement.item_id) }}</td>
              <td>{{ warehouseLabel(movement.warehouse_id) }}</td>
              <td>
                <VChip
                  :color="movement.type === 'in' ? 'success' : movement.type === 'out' ? 'error' : 'info'"
                  size="small"
                  variant="tonal"
                >
                  {{ typeLabel(movement.type) }}
                </VChip>
              </td>
              <td class="text-end tabular-nums">
                {{ movement.quantity_delta > 0 ? `+${movement.quantity_delta}` : movement.quantity_delta }}
              </td>
              <td class="text-end font-weight-medium tabular-nums">
                {{ movement.balance_after }}
              </td>
              <td>{{ reasonCodeLabel(movement.reason_code) }}</td>
              <td>{{ movement.reason || '—' }}</td>
              <td>{{ movement.reference || '—' }}</td>
            </tr>
            <tr v-if="movements.length === 0 && !loading">
              <td colspan="9">
                <InventoryEmptyState
                  icon="ri-arrow-left-right-line"
                  text="No movements match these filters. Record stock on the Stock Overview page."
                />
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <AttendancePaginationBar
        v-model:page="page"
        v-model:page-size="pageSize"
        :total-pages="totalPages"
        :caption="`Page ${page} of ${totalPages} · ${total} movement${total === 1 ? '' : 's'}`"
        @change="loadMovements"
      />
    </VCard>
  </VContainer>
</template>
