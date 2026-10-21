<script setup lang="ts">
import {
  type MovementSummaryReport,
  type PurchasesReport,
  type ReceivablesReport,
  type SalesReport,
  type StockValuationReport,
  type WriteOffsReport,
  exportReportCSV,
  getMovementsSummary,
  getPurchasesReport,
  getReceivablesReport,
  getSalesReport,
  getStockValuation,
  getWriteOffsReport,
} from '@/api/attendance/inventoryReports'
import { type InventoryCustomer, listCustomers } from '@/api/attendance/inventorySales'
import { type InventorySupplier, listSuppliers } from '@/api/attendance/inventoryPurchasing'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const tabs = [
  { key: 'valuation', title: 'Stock Valuation 庫存估值' },
  { key: 'movements', title: 'Movements 異動彙總' },
  { key: 'purchases', title: 'Purchases 採購' },
  { key: 'sales', title: 'Sales 銷售' },
  { key: 'receivables', title: 'Receivables 應收' },
  { key: 'writeoffs', title: 'Write-offs 損耗' },
] as const

type TabKey = typeof tabs[number]['key']

const activeTab = ref<TabKey>('valuation')
const loading = ref(false)
const loadError = ref('')
const actionError = ref('')

useAutoClearAlerts(loadError)
useAutoClearAlerts(actionError)

const locations = ref<LocationItem[]>([])
const customers = ref<InventoryCustomer[]>([])
const suppliers = ref<InventorySupplier[]>([])

const locationFilter = ref<string | null>(null)
const customerFilter = ref<string | null>(null)
const supplierFilter = ref<string | null>(null)
const dateFrom = ref('')
const dateTo = ref('')
const asOf = ref('')

const valuation = ref<StockValuationReport | null>(null)
const movements = ref<MovementSummaryReport | null>(null)
const purchases = ref<PurchasesReport | null>(null)
const sales = ref<SalesReport | null>(null)
const receivables = ref<ReceivablesReport | null>(null)
const writeoffs = ref<WriteOffsReport | null>(null)

function params() {
  return {
    location_id: locationFilter.value || undefined,
    customer_id: customerFilter.value || undefined,
    supplier_id: supplierFilter.value || undefined,
    date_from: dateFrom.value || undefined,
    date_to: dateTo.value || undefined,
    as_of: asOf.value || undefined,
  }
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const p = params()
    if (activeTab.value === 'valuation')
      valuation.value = await getStockValuation(p)
    else if (activeTab.value === 'movements')
      movements.value = await getMovementsSummary(p)
    else if (activeTab.value === 'purchases')
      purchases.value = await getPurchasesReport(p)
    else if (activeTab.value === 'sales')
      sales.value = await getSalesReport(p)
    else if (activeTab.value === 'receivables')
      receivables.value = await getReceivablesReport(p)
    else if (activeTab.value === 'writeoffs')
      writeoffs.value = await getWriteOffsReport(p)
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Failed to load report.')
  }
  finally {
    loading.value = false
  }
}

const csvPaths: Record<TabKey, string> = {
  valuation: 'stock-valuation',
  movements: 'movements-summary',
  purchases: 'purchases',
  sales: 'sales',
  receivables: 'receivables',
  writeoffs: 'write-offs',
}

async function exportCsv() {
  actionError.value = ''
  try {
    const blob = await exportReportCSV(csvPaths[activeTab.value], params())
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')

    link.href = url
    link.download = `${csvPaths[activeTab.value]}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Export failed.')
  }
}

function fmtMoney(value: number | null | undefined): string {
  return (value ?? 0).toFixed(2)
}

function reasonsText(reasons: Record<string, number>): string {
  return Object.entries(reasons).map(([k, v]) => `${k}:${v}`).join('; ')
}

watch(activeTab, () => {
  load()
})

watch([locationFilter, customerFilter, supplierFilter, dateFrom, dateTo, asOf], load)

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  try {
    const [locs, custs, sups] = await Promise.all([
      listLocations(),
      listCustomers({ is_active: true, page_size: 200 }),
      listSuppliers({ is_active: true, page_size: 200 }),
    ])

    locations.value = locs
    customers.value = custs.items
    suppliers.value = sups.items
  }
  catch {
    // filters still work without dropdown data
  }
  await load()
})
</script>

<template>
  <div>
    <VCard>
      <VCardTitle class="d-flex align-center flex-wrap gap-2">
        <span>Inventory Reports 庫存報表</span>
        <VSpacer />
        <VSelect
          v-model="locationFilter"
          :items="locations.map(l => ({ value: l.id, title: l.name_en || l.name_zh || l.code }))"
          density="compact"
          label="Location"
          clearable
          hide-details
          style="max-width: 180px"
        />
        <VSelect
          v-if="activeTab === 'sales' || activeTab === 'receivables'"
          v-model="customerFilter"
          :items="customers.map(c => ({ value: c.id, title: c.name_zh }))"
          density="compact"
          label="Customer"
          clearable
          hide-details
          style="max-width: 180px"
        />
        <VSelect
          v-if="activeTab === 'purchases'"
          v-model="supplierFilter"
          :items="suppliers.map(s => ({ value: s.id, title: s.name_zh }))"
          density="compact"
          label="Supplier"
          clearable
          hide-details
          style="max-width: 180px"
        />
        <template v-if="activeTab !== 'valuation'">
          <VTextField
            v-if="activeTab !== 'receivables'"
            v-model="dateFrom"
            type="date"
            density="compact"
            label="From"
            hide-details
            style="max-width: 150px"
          />
          <VTextField
            v-if="activeTab !== 'receivables'"
            v-model="dateTo"
            type="date"
            density="compact"
            label="To"
            hide-details
            style="max-width: 150px"
          />
          <VTextField
            v-if="activeTab === 'receivables'"
            v-model="asOf"
            type="date"
            density="compact"
            label="As of"
            hide-details
            style="max-width: 150px"
          />
        </template>
        <VBtn
          variant="tonal"
          prepend-icon="ri-file-download-line"
          @click="exportCsv"
        >
          Export CSV
        </VBtn>
      </VCardTitle>
      <VCardText>
        <VAlert
          v-if="loadError"
          type="error"
          variant="tonal"
          class="mb-4"
        >
          {{ loadError }}
        </VAlert>
        <VAlert
          v-if="actionError"
          type="error"
          variant="tonal"
          class="mb-4"
        >
          {{ actionError }}
        </VAlert>

        <VTabs
          v-model="activeTab"
          class="mb-4"
        >
          <VTab
            v-for="t in tabs"
            :key="t.key"
            :value="t.key"
          >
            {{ t.title }}
          </VTab>
        </VTabs>

        <VProgressLinear
          v-if="loading"
          indeterminate
          class="mb-2"
        />

        <!-- Stock valuation -->
        <template v-if="activeTab === 'valuation' && valuation">
          <VTable density="compact">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Item</th>
                <th>Location</th>
                <th class="text-end">
                  Qty
                </th>
                <th class="text-end">
                  Reserved
                </th>
                <th class="text-end">
                  Available
                </th>
                <th class="text-end">
                  Avg cost
                </th>
                <th class="text-end">
                  Value
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="r in valuation.rows"
                :key="`${r.item_id}-${r.location_id}`"
              >
                <td>{{ r.sku_code }}</td>
                <td>{{ r.name_zh }}</td>
                <td>{{ r.location_name || r.location_id }}</td>
                <td class="text-end">
                  {{ r.quantity }}
                </td>
                <td class="text-end">
                  {{ r.reserved }}
                </td>
                <td class="text-end">
                  {{ r.available }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(r.avg_cost) }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(r.value) }}
                </td>
              </tr>
            </tbody>
          </VTable>
          <div class="mt-3 text-body-2">
            <div
              v-for="lt in valuation.location_totals"
              :key="lt.location_id"
            >
              {{ lt.location_name || lt.location_id }}: {{ fmtMoney(lt.value) }}
            </div>
            <div class="font-weight-bold">
              Grand total: {{ fmtMoney(valuation.grand_total) }}
            </div>
          </div>
        </template>

        <!-- Movements summary -->
        <template v-if="activeTab === 'movements' && movements">
          <VTable density="compact">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Item</th>
                <th class="text-end">
                  In
                </th>
                <th class="text-end">
                  Out
                </th>
                <th class="text-end">
                  Adjust
                </th>
                <th class="text-end">
                  Trf in
                </th>
                <th class="text-end">
                  Trf out
                </th>
                <th class="text-end">
                  Net
                </th>
                <th>Reasons</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="r in movements.rows"
                :key="r.item_id"
              >
                <td>{{ r.sku_code }}</td>
                <td>{{ r.name_zh }}</td>
                <td class="text-end">
                  {{ r.qty_in }}
                </td>
                <td class="text-end">
                  {{ r.qty_out }}
                </td>
                <td class="text-end">
                  {{ r.qty_adjust }}
                </td>
                <td class="text-end">
                  {{ r.qty_transfer_in }}
                </td>
                <td class="text-end">
                  {{ r.qty_transfer_out }}
                </td>
                <td class="text-end">
                  {{ r.net_change }}
                </td>
                <td class="text-caption">
                  {{ reasonsText(r.reasons) }}
                </td>
              </tr>
            </tbody>
          </VTable>
          <div class="mt-3 text-body-2 font-weight-bold">
            Net change: {{ movements.totals.net_change }}
          </div>
        </template>

        <!-- Purchases -->
        <template v-if="activeTab === 'purchases' && purchases">
          <VTable density="compact">
            <thead>
              <tr>
                <th>Supplier</th>
                <th>SKU</th>
                <th>Item</th>
                <th class="text-end">
                  Qty in
                </th>
                <th class="text-end">
                  Value in
                </th>
                <th class="text-end">
                  Qty ret
                </th>
                <th class="text-end">
                  Value ret
                </th>
                <th class="text-end">
                  Net qty
                </th>
                <th class="text-end">
                  Net value
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="r in purchases.rows"
                :key="`${r.supplier_id}-${r.item_id}`"
              >
                <td>{{ r.supplier_name }}</td>
                <td>{{ r.sku_code }}</td>
                <td>{{ r.name_zh }}</td>
                <td class="text-end">
                  {{ r.qty_received }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(r.value_received) }}
                </td>
                <td class="text-end">
                  {{ r.qty_returned }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(r.value_returned) }}
                </td>
                <td class="text-end">
                  {{ r.net_qty }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(r.net_value) }}
                </td>
              </tr>
            </tbody>
          </VTable>
          <div class="mt-3 text-body-2 font-weight-bold">
            Net purchases: {{ fmtMoney(purchases.totals.net_value) }}
          </div>
          <template v-if="purchases.open_orders.length">
            <div class="text-subtitle-2 mt-4 mb-2">
              Open purchase orders
            </div>
            <VTable density="compact">
              <thead>
                <tr>
                  <th>PO</th>
                  <th>Supplier</th>
                  <th>Expected</th>
                  <th class="text-end">
                    Outstanding qty
                  </th>
                  <th class="text-end">
                    Outstanding value
                  </th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="o in purchases.open_orders"
                  :key="o.po_id"
                >
                  <td>{{ o.po_no }}</td>
                  <td>{{ o.supplier_name }}</td>
                  <td>
                    {{ o.expected_date || '—' }}
                    <VChip
                      v-if="o.overdue"
                      size="x-small"
                      color="error"
                      class="ms-1"
                    >
                      Overdue
                    </VChip>
                  </td>
                  <td class="text-end">
                    {{ o.outstanding_qty }}
                  </td>
                  <td class="text-end">
                    {{ fmtMoney(o.outstanding_value) }}
                  </td>
                  <td>{{ o.status }}</td>
                </tr>
              </tbody>
            </VTable>
          </template>
        </template>

        <!-- Sales -->
        <template v-if="activeTab === 'sales' && sales">
          <VTable density="compact">
            <thead>
              <tr>
                <th>Date</th>
                <th>Customer</th>
                <th>SKU</th>
                <th>Item</th>
                <th class="text-end">
                  Invoices
                </th>
                <th class="text-end">
                  Qty
                </th>
                <th class="text-end">
                  Amount
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(r, i) in sales.rows"
                :key="i"
              >
                <td>{{ r.date }}</td>
                <td>{{ r.customer_name }}</td>
                <td>{{ r.sku_code }}</td>
                <td>{{ r.name_zh }}</td>
                <td class="text-end">
                  {{ r.invoice_count }}
                </td>
                <td class="text-end">
                  {{ r.qty }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(r.amount) }}
                </td>
              </tr>
            </tbody>
          </VTable>
          <div class="mt-3 text-body-2">
            Invoiced: {{ fmtMoney(sales.totals.invoiced) }} ·
            Credited: {{ fmtMoney(sales.totals.credited) }} ·
            <span class="font-weight-bold">Net sales: {{ fmtMoney(sales.totals.net_sales) }}</span> ·
            Payments: {{ fmtMoney(sales.totals.payments) }}
          </div>
        </template>

        <!-- Receivables -->
        <template v-if="activeTab === 'receivables' && receivables">
          <VTable density="compact">
            <thead>
              <tr>
                <th>Invoice</th>
                <th>Customer</th>
                <th>Issue date</th>
                <th class="text-end">
                  Total
                </th>
                <th class="text-end">
                  Paid
                </th>
                <th class="text-end">
                  Credited
                </th>
                <th class="text-end">
                  Balance
                </th>
                <th class="text-end">
                  Days
                </th>
                <th>Bucket</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="r in receivables.rows"
                :key="r.invoice_id"
              >
                <td>{{ r.invoice_no }}</td>
                <td>{{ r.customer_name }}</td>
                <td>{{ r.issue_date || '—' }}</td>
                <td class="text-end">
                  {{ fmtMoney(r.total) }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(r.paid) }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(r.credited) }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(r.balance) }}
                </td>
                <td class="text-end">
                  {{ r.days_outstanding }}
                </td>
                <td>{{ r.bucket }}</td>
              </tr>
            </tbody>
          </VTable>
          <div class="mt-3 text-body-2">
            <div
              v-for="ct in receivables.customer_totals"
              :key="ct.customer_id"
            >
              {{ ct.customer_name }}: {{ fmtMoney(ct.balance) }} ({{ ct.count }} invoice{{ ct.count === 1 ? '' : 's' }})
            </div>
            <div class="mt-1">
              <span
                v-for="(v, k) in receivables.buckets"
                :key="k"
                class="me-4"
              >{{ k }}: {{ fmtMoney(v) }}</span>
            </div>
            <div class="font-weight-bold mt-1">
              Grand total: {{ fmtMoney(receivables.grand_total) }}
            </div>
          </div>
        </template>

        <!-- Write-offs -->
        <template v-if="activeTab === 'writeoffs' && writeoffs">
          <VTable density="compact">
            <thead>
              <tr>
                <th>Reason</th>
                <th>SKU</th>
                <th>Item</th>
                <th class="text-end">
                  Qty
                </th>
                <th class="text-end">
                  Cost
                </th>
                <th class="text-end">
                  Cost missing
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(r, i) in writeoffs.rows"
                :key="i"
              >
                <td>{{ r.reason_code }}</td>
                <td>{{ r.sku_code }}</td>
                <td>{{ r.name_zh }}</td>
                <td class="text-end">
                  {{ r.qty }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(r.cost) }}
                </td>
                <td class="text-end">
                  {{ r.cost_missing }}
                </td>
              </tr>
            </tbody>
          </VTable>
          <div class="mt-3 text-body-2 font-weight-bold">
            Total: {{ writeoffs.totals.qty }} units · {{ fmtMoney(writeoffs.totals.cost) }}
          </div>
        </template>
      </VCardText>
    </VCard>
  </div>
</template>
