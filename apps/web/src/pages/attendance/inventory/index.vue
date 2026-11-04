<script setup lang="ts">
import {
  type InventoryItem,
  type InventoryStock,
  type InventoryWarehouse,
  exportInventoryStocksCSV,
  importOpeningStockCSV,
  listInventoryItems,
  listInventoryStocks,
  listWarehouses,
} from '@/api/attendance/inventory'
import InventoryEmptyState from '@/components/attendance/inventory/InventoryEmptyState.vue'
import InventoryMovementDialog from '@/components/attendance/inventory/InventoryMovementDialog.vue'
import InventoryTransferDialog from '@/components/attendance/inventory/InventoryTransferDialog.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { useLatestRequest } from '@/composables/useLatestRequest'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()
const toast = useToast()

const loading = ref(true)
const loadError = ref('')

useAutoClearAlerts(loadError)

const warehouses = ref<InventoryWarehouse[]>([])
const items = ref<InventoryItem[]>([])
const stocks = ref<InventoryStock[]>([])

const selectedWarehouseId = ref<string | null>(null)
const search = ref('')
const movementDialogOpen = ref(false)
const movementInitialType = ref<'in' | 'out' | 'adjust'>('in')
const transferDialogOpen = ref(false)

watch(movementDialogOpen, open => {
  if (!open)
    movementInitialType.value = 'in'
})

const openingStockInput = ref<HTMLInputElement | null>(null)
const importing = ref(false)
const stockReq = useLatestRequest()

const itemById = computed(() => new Map(items.value.map(i => [i.id, i])))

const rows = computed(() => {
  const term = search.value.trim().toLowerCase()

  return stocks.value
    .map(stock => {
      const item = itemById.value.get(stock.item_id)
      if (!item)
        return null
      if (
        term
        && ![item.sku_code, item.name_zh, item.name_en ?? '', item.barcode ?? '']
          .some(v => v.toLowerCase().includes(term))
      )
        return null

      return { stock, item, isLow: stock.quantity <= item.reorder_level }
    })
    .filter((r): r is NonNullable<typeof r> => r !== null)
    .sort((a, b) => a.item.sku_code.localeCompare(b.item.sku_code, undefined, { numeric: true }))
})

const statCards = computed(() => {
  const totalUnits = stocks.value.reduce((sum, s) => sum + s.quantity, 0)

  const lowCount = stocks.value.filter(
    s => s.quantity <= (itemById.value.get(s.item_id)?.reorder_level ?? -1),
  ).length

  return [
    { label: 'Tracked items', value: String(new Set(stocks.value.map(s => s.item_id)).size), icon: 'ri-archive-line', color: 'primary' },
    { label: 'Units on hand', value: String(totalUnits), icon: 'ri-stack-line', color: 'info' },
    { label: 'Low-stock items', value: String(lowCount), icon: 'ri-error-warning-line', color: lowCount > 0 ? 'error' : 'success' },
  ]
})

const route = useRoute()
const router = useRouter()

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  await loadAll()

  const action = route.query.action
  if (action === 'movement' || action === 'transfer') {
    if (action === 'movement') {
      movementInitialType.value = route.query.type === 'out' ? 'out' : 'in'
      movementDialogOpen.value = true
    }
    else {
      transferDialogOpen.value = true
    }
    const rest = { ...route.query }

    delete rest.action
    delete rest.type
    router.replace({ query: rest })
  }
})

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    const [warehouseList, itemList] = await Promise.all([
      listWarehouses({ is_active: true }),
      listInventoryItems(),
    ])

    warehouses.value = [...warehouseList].sort((a, b) =>
      (a.name_en || a.name_zh).localeCompare(b.name_en || b.name_zh),
    )
    items.value = itemList
    if (!selectedWarehouseId.value && warehouseList.length > 0)
      selectedWarehouseId.value = warehouseList[0].id
    await loadStocks()
  }
  catch (e) {
    console.error('Failed to load inventory', e)
    loadError.value = formatApiError(e, 'Failed to load inventory.')
  }
  finally {
    loading.value = false
  }
}

async function loadStocks() {
  const token = stockReq.next()

  const result = selectedWarehouseId.value
    ? await listInventoryStocks({ warehouse_id: selectedWarehouseId.value })
    : await listInventoryStocks()

  if (!stockReq.isLatest(token))
    return
  stocks.value = result
}

watch(selectedWarehouseId, async () => {
  try {
    await loadStocks()
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Failed to load stock.')
  }
})

async function exportStocks() {
  try {
    const blob = await exportInventoryStocksCSV(
      selectedWarehouseId.value ? { warehouse_id: selectedWarehouseId.value } : undefined,
    )

    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')

    link.href = url
    link.download = 'inventory_stocks.csv'
    link.click()
    URL.revokeObjectURL(url)
  }
  catch (e) {
    toast.show(formatApiError(e, 'Export failed.'), 'error', 6000)
  }
}

function pickOpeningStockFile() {
  openingStockInput.value?.click()
}

async function onOpeningStockFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]

  input.value = ''
  if (!file)
    return
  importing.value = true
  try {
    const result = await importOpeningStockCSV(file)
    if (result.errors.length)
      toast.show(result.errors.map(e => `Row ${e.row}: ${e.error}`).join(' '), 'error', 6000)
    else
      toast.show(`Opening stock imported: ${result.created} created, ${result.skipped} skipped`)
    await loadStocks()
  }
  catch (e) {
    toast.show(formatApiError(e, 'Opening stock import failed.'), 'error', 6000)
  }
  finally {
    importing.value = false
  }
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
          Inventory 庫存管理
        </div>
        <div class="text-body-2 text-medium-emphasis">
          這一頁顯示各倉庫每個品項的現有數量；紅色代表低於安全庫存。
        </div>
      </VCol>
      <VCol
        cols="auto"
        class="d-flex gap-2"
      >
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="loading"
          @click="loadAll"
        >
          Refresh
        </VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-download-line"
          @click="exportStocks"
        >
          Export CSV
        </VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-upload-line"
          :loading="importing"
          @click="pickOpeningStockFile"
        >
          Import Opening Stock
        </VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-swap-line"
          :disabled="!selectedWarehouseId"
          @click="transferDialogOpen = true"
        >
          Transfer
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          :disabled="!selectedWarehouseId"
          @click="movementDialogOpen = true"
        >
          Record Movement
        </VBtn>
        <input
          ref="openingStockInput"
          type="file"
          accept=".csv,text/csv"
          class="d-none"
          @change="onOpeningStockFile"
        >
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

    <VRow v-if="loading">
      <VCol
        cols="12"
        class="text-center py-12"
      >
        <VProgressCircular
          indeterminate
          color="primary"
          size="48"
        />
      </VCol>
    </VRow>

    <template v-else-if="warehouses.length === 0">
      <InventoryEmptyState
        icon="ri-building-2-line"
        text="No warehouses yet. Add a warehouse before recording stock."
        action-label="Warehouses"
        @action="router.push('/attendance/inventory/warehouses')"
      />
    </template>

    <template v-else>
      <StatCards :cards="statCards" />

      <VCard>
        <VCardText class="d-flex flex-wrap gap-3 align-center">
          <VSelect
            v-model="selectedWarehouseId"
            :items="warehouses.map(l => ({ value: l.id, title: [l.name_en, l.name_zh].filter(Boolean).join(' · ') }))"
            label="Warehouse 倉庫"
            density="comfortable"
            style="max-width: 280px"
            hide-details
          />
          <VTextField
            v-model="search"
            label="Search item"
            prepend-inner-icon="ri-search-line"
            density="comfortable"
            style="max-width: 320px"
            hide-details
            clearable
          />
        </VCardText>
        <div class="overflow-x-auto">
          <VTable>
            <thead>
              <tr>
                <th>SKU</th>
                <th>Item</th>
                <th>Unit</th>
                <th class="text-end">
                  On hand
                </th>
                <th class="text-end">
                  Reserved
                </th>
                <th class="text-end">
                  Available
                </th>
                <th class="text-end">
                  Reorder level
                </th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in rows"
                :key="row.stock.id"
                :class="row.isLow ? 'text-error' : undefined"
              >
                <td>{{ row.item.sku_code }}</td>
                <td>{{ [row.item.name_zh, row.item.name_en].filter(Boolean).join(' · ') }}</td>
                <td>{{ row.item.unit_of_measure || '—' }}</td>
                <td class="text-end font-weight-medium tabular-nums">
                  {{ row.stock.quantity }}
                </td>
                <td class="text-end tabular-nums">
                  {{ row.stock.reserved }}
                </td>
                <td class="text-end tabular-nums">
                  {{ row.stock.available }}
                </td>
                <td class="text-end tabular-nums">
                  {{ row.item.reorder_level }}
                </td>
                <td>
                  <VChip
                    :color="row.isLow ? 'error' : 'success'"
                    size="small"
                    variant="tonal"
                  >
                    {{ row.isLow ? 'Low stock' : 'OK' }}
                  </VChip>
                </td>
              </tr>
              <tr v-if="rows.length === 0">
                <td colspan="8">
                  <InventoryEmptyState
                    icon="ri-stack-line"
                    :text="search ? 'No items match your search.' : 'No stock records for this warehouse yet.'"
                    :action-label="search ? undefined : 'Record Movement'"
                    @action="movementDialogOpen = true"
                  />
                </td>
              </tr>
            </tbody>
          </VTable>
        </div>
      </VCard>
    </template>

    <InventoryMovementDialog
      v-model="movementDialogOpen"
      :warehouse-id="selectedWarehouseId"
      :items="items"
      :initial-type="movementInitialType"
      @saved="loadStocks"
    />
    <InventoryTransferDialog
      v-model="transferDialogOpen"
      :warehouses="warehouses"
      :items="items"
      :from-warehouse-id="selectedWarehouseId"
      @saved="loadStocks"
    />
  </VContainer>
</template>
