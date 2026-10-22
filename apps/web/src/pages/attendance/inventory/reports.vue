<script setup lang="ts">
import { useTheme } from 'vuetify'
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
import { reasonCodeLabel } from '@/api/attendance/inventory'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { useLatestRequest } from '@/composables/useLatestRequest'
import { hexToRgb } from '@core/utils/colorConverter'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()
const route = useRoute()
const router = useRouter()
const vuetifyTheme = useTheme()
const reducedMotion = usePreferredReducedMotion()

const tabs = [
  { key: 'valuation', title: 'Stock Valuation 庫存估值', desc: '這份報表告訴你每個分校現在的貨值多少錢。' },
  { key: 'movements', title: 'Movements 異動彙總', desc: '這份報表告訴你一段時間內入庫、出庫和調整各有多少。' },
  { key: 'purchases', title: 'Purchases 採購', desc: '這份報表告訴你跟每個供應商進了多少貨、退了多少，以及還沒收齊的採購單。' },
  { key: 'sales', title: 'Sales 銷售', desc: '這份報表告訴你開了多少發票、折讓了多少、實際收到多少錢。' },
  { key: 'receivables', title: 'Receivables 應收', desc: '這份報表告訴你哪些發票還沒收齊、欠了多久。' },
  { key: 'writeoffs', title: 'Write-offs 損耗', desc: '這份報表告訴你損毀、遺失、贈送等非銷售出庫的數量和成本。' },
] as const

type TabKey = typeof tabs[number]['key']

const activeTab = ref<TabKey>((route.query.tab as TabKey) || 'valuation')
const loading = ref(false)
const loadError = ref('')
const actionError = ref('')

useAutoClearAlerts(loadError)
useAutoClearAlerts(actionError)

const locations = ref<LocationItem[]>([])
const customers = ref<InventoryCustomer[]>([])
const suppliers = ref<InventorySupplier[]>([])

const locationFilter = ref<string | null>((route.query.location_id as string) || null)
const customerFilter = ref<string | null>((route.query.customer_id as string) || null)
const supplierFilter = ref<string | null>((route.query.supplier_id as string) || null)
const dateFrom = ref((route.query.date_from as string) || '')
const dateTo = ref((route.query.date_to as string) || '')
const asOf = ref((route.query.as_of as string) || '')

const datePreset = ref<'custom' | 'this_month' | 'last_month' | 'this_year'>(
  (route.query.preset as 'custom' | 'this_month' | 'last_month' | 'this_year') || 'custom',
)

const tableSearch = ref('')

const valuation = ref<StockValuationReport | null>(null)
const movements = ref<MovementSummaryReport | null>(null)
const purchases = ref<PurchasesReport | null>(null)
const sales = ref<SalesReport | null>(null)
const receivables = ref<ReceivablesReport | null>(null)
const writeoffs = ref<WriteOffsReport | null>(null)
const reportReq = useLatestRequest()

const tabDesc = computed(() => tabs.find(t => t.key === activeTab.value)?.desc ?? '')

function todayStr(): string {
  return new Date().toISOString().slice(0, 10)
}

function applyPreset(preset: string) {
  const now = new Date()

  if (preset === 'this_month') {
    dateFrom.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
    dateTo.value = todayStr()
  }
  else if (preset === 'last_month') {
    const first = new Date(now.getFullYear(), now.getMonth() - 1, 1)
    const last = new Date(now.getFullYear(), now.getMonth(), 0)

    dateFrom.value = first.toISOString().slice(0, 10)
    dateTo.value = last.toISOString().slice(0, 10)
  }
  else if (preset === 'this_year') {
    dateFrom.value = `${now.getFullYear()}-01-01`
    dateTo.value = todayStr()
  }
}

watch(datePreset, p => {
  if (p !== 'custom')
    applyPreset(p)
})

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

  const token = reportReq.next()
  const tab = activeTab.value
  try {
    const p = params()

    const result = tab === 'valuation'
      ? await getStockValuation(p)
      : tab === 'movements'
        ? await getMovementsSummary(p)
        : tab === 'purchases'
          ? await getPurchasesReport(p)
          : tab === 'sales'
            ? await getSalesReport(p)
            : tab === 'receivables'
              ? await getReceivablesReport(p)
              : await getWriteOffsReport(p)

    if (!reportReq.isLatest(token))
      return
    if (tab === 'valuation')
      valuation.value = result as StockValuationReport
    else if (tab === 'movements')
      movements.value = result as MovementSummaryReport
    else if (tab === 'purchases')
      purchases.value = result as PurchasesReport
    else if (tab === 'sales')
      sales.value = result as SalesReport
    else if (tab === 'receivables')
      receivables.value = result as ReceivablesReport
    else
      writeoffs.value = result as WriteOffsReport
  }
  catch (e) {
    if (!reportReq.isLatest(token))
      return
    loadError.value = formatApiError(e, 'Failed to load report.')
  }
  finally {
    if (reportReq.isLatest(token))
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

const moneyFmt = new Intl.NumberFormat('en-HK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function fmtMoney(value: number | null | undefined): string {
  return moneyFmt.format(value ?? 0)
}

function reasonsText(reasons: Record<string, number>): string {
  return Object.entries(reasons).map(([k, v]) => `${reasonCodeLabel(k)}: ${v}`).join('; ')
}

// ---- KPI cards ----
interface Kpi { label: string; value: string }

const kpis = computed<Kpi[]>(() => {
  if (activeTab.value === 'valuation' && valuation.value) {
    const rows = valuation.value.rows

    return [
      { label: '品項數', value: String(rows.length) },
      { label: '總數量', value: String(rows.reduce((s, r) => s + r.quantity, 0)) },
      { label: '總價值', value: `$${fmtMoney(valuation.value.grand_total)}` },
    ]
  }
  if (activeTab.value === 'movements' && movements.value) {
    const rows = movements.value.rows

    return [
      { label: '入庫量', value: String(rows.reduce((s, r) => s + r.qty_in, 0)) },
      { label: '出庫量', value: String(rows.reduce((s, r) => s + r.qty_out, 0)) },
      { label: '調整', value: String(rows.reduce((s, r) => s + r.qty_adjust, 0)) },
      { label: '淨變動', value: String(movements.value.totals.net_change) },
    ]
  }
  if (activeTab.value === 'purchases' && purchases.value) {
    const overdue = purchases.value.open_orders.filter(o => o.overdue).length

    return [
      { label: '收貨金額', value: `$${fmtMoney(purchases.value.rows.reduce((s, r) => s + r.value_received, 0))}` },
      { label: '退貨金額', value: `$${fmtMoney(purchases.value.rows.reduce((s, r) => s + r.value_returned, 0))}` },
      { label: '未收齊採購單', value: `${purchases.value.open_orders.length}（逾期 ${overdue}）` },
    ]
  }
  if (activeTab.value === 'sales' && sales.value) {
    const t = sales.value.totals

    return [
      { label: '開票金額', value: `$${fmtMoney(t.invoiced)}` },
      { label: '折讓金額', value: `$${fmtMoney(t.credited)}` },
      { label: '已收', value: `$${fmtMoney(t.payments)}` },
      { label: '未收', value: `$${fmtMoney(Math.max(0, (t.net_sales ?? 0) - (t.payments ?? 0)))}` },
    ]
  }
  if (activeTab.value === 'receivables' && receivables.value) {
    const overdue = Object.entries(receivables.value.buckets)
      .filter(([k]) => k !== '0-30')
      .reduce((s, [, v]) => s + v, 0)

    return [
      { label: '總應收', value: `$${fmtMoney(receivables.value.grand_total)}` },
      { label: '逾期（超過 30 天）', value: `$${fmtMoney(overdue)}` },
      { label: '客戶數', value: String(receivables.value.customer_totals.length) },
    ]
  }
  if (activeTab.value === 'writeoffs' && writeoffs.value) {
    return [
      { label: '總數量', value: String(writeoffs.value.totals.qty) },
      { label: '總成本', value: `$${fmtMoney(writeoffs.value.totals.cost)}` },
    ]
  }

  return []
})

// ---- Charts ----
const themeColors = computed(() => vuetifyTheme.current.value.colors)
const themeVars = computed(() => vuetifyTheme.current.value.variables)

const baseChart = computed(() => ({
  chart: {
    toolbar: { show: false },
    parentHeightOffset: 0,
    animations: { enabled: reducedMotion.value !== 'reduce' },
  },
  dataLabels: { enabled: false },
  grid: { padding: { left: 4, right: 4 } },
  xaxis: {
    labels: {
      style: { colors: `rgba(${hexToRgb(themeColors.value['on-surface'])},${themeVars.value['medium-emphasis-opacity']})` },
    },
  },
  legend: {
    fontSize: '13px',
    labels: { colors: `rgba(${hexToRgb(themeColors.value['on-surface'])},${themeVars.value['medium-emphasis-opacity']})` },
    markers: { radius: 12 },
  },
}))

const valuationChart = computed(() => {
  if (!valuation.value)
    return null
  const top = [...valuation.value.rows].sort((a, b) => b.value - a.value).slice(0, 10)

  return {
    options: {
      ...baseChart.value,
      colors: [themeColors.value.primary],
      plotOptions: { bar: { horizontal: true, borderRadius: 4, barHeight: '60%' } },
      xaxis: { ...baseChart.value.xaxis, categories: top.map(r => r.sku_code) },
      tooltip: { y: { formatter: (v: number) => `$${fmtMoney(v)}` } },
    },
    series: [{ name: '價值', data: top.map(r => r.value) }],
  }
})

const movementsChart = computed(() => {
  if (!movements.value)
    return null
  const rows = movements.value.rows
  const cats = ['入庫', '出庫', '調整', '分校轉入', '分校轉出']

  const data = [
    rows.reduce((s, r) => s + r.qty_in, 0),
    rows.reduce((s, r) => s + r.qty_out, 0),
    rows.reduce((s, r) => s + r.qty_adjust, 0),
    rows.reduce((s, r) => s + r.qty_transfer_in, 0),
    rows.reduce((s, r) => s + r.qty_transfer_out, 0),
  ]

  return {
    options: {
      ...baseChart.value,
      colors: [themeColors.value.success, themeColors.value.error, themeColors.value.warning, themeColors.value.info, themeColors.value.secondary],
      plotOptions: { bar: { borderRadius: 4, columnWidth: '45%', distributed: true } },
      xaxis: { ...baseChart.value.xaxis, categories: cats },
      legend: { ...baseChart.value.legend, show: false },
    },
    series: [{ name: '數量', data }],
  }
})

const purchasesChart = computed(() => {
  if (!purchases.value)
    return null
  const bySupplier = new Map<string, number>()

  for (const r of purchases.value.rows)
    bySupplier.set(r.supplier_name ?? '—', (bySupplier.get(r.supplier_name ?? '—') ?? 0) + r.net_value)
  const entries = [...bySupplier.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10)

  return {
    options: {
      ...baseChart.value,
      colors: [themeColors.value.primary],
      plotOptions: { bar: { borderRadius: 4, columnWidth: '45%' } },
      xaxis: { ...baseChart.value.xaxis, categories: entries.map(e => e[0]) },
      tooltip: { y: { formatter: (v: number) => `$${fmtMoney(v)}` } },
    },
    series: [{ name: '淨採購額', data: entries.map(e => e[1]) }],
  }
})

const salesChart = computed(() => {
  if (!sales.value)
    return null
  const t = sales.value.totals

  return {
    options: {
      ...baseChart.value,
      colors: [themeColors.value.primary, themeColors.value.warning, themeColors.value.success],
      plotOptions: { bar: { borderRadius: 4, columnWidth: '40%', distributed: true } },
      xaxis: { ...baseChart.value.xaxis, categories: ['開票', '折讓', '已收'] },
      legend: { ...baseChart.value.legend, show: false },
      tooltip: { y: { formatter: (v: number) => `$${fmtMoney(v)}` } },
    },
    series: [{ name: '金額', data: [t.invoiced ?? 0, t.credited ?? 0, t.payments ?? 0] }],
  }
})

const receivablesChart = computed(() => {
  if (!receivables.value)
    return null
  const labels = Object.keys(receivables.value.buckets)
  const data = labels.map(k => receivables.value!.buckets[k])

  return {
    options: {
      ...baseChart.value,
      labels: labels.map(k => `${k} 天`),
      colors: [themeColors.value.success, themeColors.value.warning, themeColors.value.error, themeColors.value.secondary],
      stroke: { width: 1, colors: [themeColors.value.surface] },
    },
    series: data,
  }
})

const writeoffsChart = computed(() => {
  if (!writeoffs.value)
    return null
  const byReason = new Map<string, number>()

  for (const r of writeoffs.value.rows)
    byReason.set(reasonCodeLabel(r.reason_code), (byReason.get(reasonCodeLabel(r.reason_code)) ?? 0) + r.cost)

  return {
    options: {
      ...baseChart.value,
      labels: [...byReason.keys()],
      colors: [themeColors.value.error, themeColors.value.warning, themeColors.value.info, themeColors.value.secondary, themeColors.value.primary],
      stroke: { width: 1, colors: [themeColors.value.surface] },
      tooltip: { y: { formatter: (v: number) => `$${fmtMoney(v)}` } },
    },
    series: [...byReason.values()],
  }
})

const chartsByTab = {
  valuation: valuationChart,
  movements: movementsChart,
  purchases: purchasesChart,
  sales: salesChart,
  receivables: receivablesChart,
  writeoffs: writeoffsChart,
} as const

const currentChart = computed(() => chartsByTab[activeTab.value]?.value ?? null)

const chartType = computed(() =>
  activeTab.value === 'receivables' || activeTab.value === 'writeoffs' ? 'donut' : 'bar',
)

// ---- VDataTable headers ----
const headersValuation = [
  { title: 'SKU', key: 'sku_code' },
  { title: 'Item', key: 'name_zh' },
  { title: 'Location', key: 'location_name' },
  { title: 'Qty', key: 'quantity', align: 'end' as const },
  { title: 'Reserved', key: 'reserved', align: 'end' as const },
  { title: 'Available', key: 'available', align: 'end' as const },
  { title: 'Avg cost', key: 'avg_cost', align: 'end' as const },
  { title: 'Value', key: 'value', align: 'end' as const },
]

const headersMovements = [
  { title: 'SKU', key: 'sku_code' },
  { title: 'Item', key: 'name_zh' },
  { title: 'In', key: 'qty_in', align: 'end' as const },
  { title: 'Out', key: 'qty_out', align: 'end' as const },
  { title: 'Adjust', key: 'qty_adjust', align: 'end' as const },
  { title: 'Trf in', key: 'qty_transfer_in', align: 'end' as const },
  { title: 'Trf out', key: 'qty_transfer_out', align: 'end' as const },
  { title: 'Net', key: 'net_change', align: 'end' as const },
  { title: 'Reasons', key: 'reasons', sortable: false },
]

const headersPurchases = [
  { title: 'Supplier', key: 'supplier_name' },
  { title: 'SKU', key: 'sku_code' },
  { title: 'Item', key: 'name_zh' },
  { title: 'Qty in', key: 'qty_received', align: 'end' as const },
  { title: 'Value in', key: 'value_received', align: 'end' as const },
  { title: 'Qty ret', key: 'qty_returned', align: 'end' as const },
  { title: 'Value ret', key: 'value_returned', align: 'end' as const },
  { title: 'Net qty', key: 'net_qty', align: 'end' as const },
  { title: 'Net value', key: 'net_value', align: 'end' as const },
]

const headersSales = [
  { title: 'Date', key: 'date' },
  { title: 'Customer', key: 'customer_name' },
  { title: 'SKU', key: 'sku_code' },
  { title: 'Item', key: 'name_zh' },
  { title: 'Invoices', key: 'invoice_count', align: 'end' as const },
  { title: 'Qty', key: 'qty', align: 'end' as const },
  { title: 'Amount', key: 'amount', align: 'end' as const },
]

const headersReceivables = [
  { title: 'Invoice', key: 'invoice_no' },
  { title: 'Customer', key: 'customer_name' },
  { title: 'Issue date', key: 'issue_date' },
  { title: 'Total', key: 'total', align: 'end' as const },
  { title: 'Paid', key: 'paid', align: 'end' as const },
  { title: 'Credited', key: 'credited', align: 'end' as const },
  { title: 'Balance', key: 'balance', align: 'end' as const },
  { title: 'Days', key: 'days_outstanding', align: 'end' as const },
  { title: 'Bucket', key: 'bucket' },
]

const headersWriteoffs = [
  { title: 'Reason', key: 'reason_code' },
  { title: 'SKU', key: 'sku_code' },
  { title: 'Item', key: 'name_zh' },
  { title: 'Qty', key: 'qty', align: 'end' as const },
  { title: 'Cost', key: 'cost', align: 'end' as const },
  { title: 'Cost missing', key: 'cost_missing', align: 'end' as const },
]

const emptyText = computed(() => `${tabDesc.value.split('。')[0]} — 目前沒有符合條件的資料，試試調整日期或篩選。`)

// Single watcher: several ref changes in one tick trigger load() only once.
watch(
  [activeTab, locationFilter, customerFilter, supplierFilter, dateFrom, dateTo, asOf],
  () => {
    tableSearch.value = ''
    load()

    const query: Record<string, string> = { tab: activeTab.value }

    if (locationFilter.value)
      query.location_id = locationFilter.value
    if (customerFilter.value)
      query.customer_id = customerFilter.value
    if (supplierFilter.value)
      query.supplier_id = supplierFilter.value
    if (dateFrom.value)
      query.date_from = dateFrom.value
    if (dateTo.value)
      query.date_to = dateTo.value
    if (asOf.value)
      query.as_of = asOf.value
    if (datePreset.value !== 'custom')
      query.preset = datePreset.value
    router.replace({ query })
  },
)

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
        <template v-if="activeTab === 'movements' || activeTab === 'purchases' || activeTab === 'sales' || activeTab === 'writeoffs'">
          <VChipGroup
            v-model="datePreset"
            mandatory
            selected-class="text-primary"
            style="flex-shrink: 0"
          >
            <VChip
              value="this_month"
              size="small"
              variant="outlined"
              filter
            >
              本月
            </VChip>
            <VChip
              value="last_month"
              size="small"
              variant="outlined"
              filter
            >
              上月
            </VChip>
            <VChip
              value="this_year"
              size="small"
              variant="outlined"
              filter
            >
              今年
            </VChip>
            <VChip
              value="custom"
              size="small"
              variant="outlined"
              filter
            >
              自訂
            </VChip>
          </VChipGroup>
          <VTextField
            v-model="dateFrom"
            type="date"
            density="compact"
            label="From"
            hide-details
            style="max-width: 150px"
            @update:model-value="datePreset = 'custom'"
          />
          <VTextField
            v-model="dateTo"
            type="date"
            density="compact"
            label="To"
            hide-details
            style="max-width: 150px"
            @update:model-value="datePreset = 'custom'"
          />
        </template>
        <VTextField
          v-if="activeTab === 'receivables'"
          v-model="asOf"
          type="date"
          density="compact"
          label="As of"
          hide-details
          style="max-width: 150px"
        />
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
          class="mb-1"
        >
          <VTab
            v-for="t in tabs"
            :key="t.key"
            :value="t.key"
          >
            {{ t.title }}
          </VTab>
        </VTabs>
        <div class="text-body-2 text-medium-emphasis mb-4">
          {{ tabDesc }}
        </div>

        <VProgressLinear
          v-if="loading"
          indeterminate
          class="mb-2"
        />

        <VRow
          v-if="kpis.length"
          class="mb-4"
          dense
        >
          <VCol
            v-for="k in kpis"
            :key="k.label"
            cols="6"
            md="3"
          >
            <VCard
              variant="tonal"
              color="primary"
            >
              <VCardText class="py-3">
                <div class="text-caption">
                  {{ k.label }}
                </div>
                <div class="text-h6 tabular-nums">
                  {{ k.value }}
                </div>
              </VCardText>
            </VCard>
          </VCol>
        </VRow>

        <VCard
          v-if="currentChart && (currentChart.series.length || 0) > 0"
          variant="outlined"
          class="mb-4"
        >
          <VCardText>
            <VueApexCharts
              :type="chartType"
              height="280"
              :options="currentChart.options"
              :series="currentChart.series"
            />
          </VCardText>
        </VCard>

        <VTextField
          v-model="tableSearch"
          density="compact"
          label="篩選表格內容"
          prepend-inner-icon="ri-search-line"
          hide-details
          clearable
          class="mb-3"
          style="max-width: 280px"
        />

        <!-- Stock valuation -->
        <template v-if="activeTab === 'valuation'">
          <VDataTable
            v-if="valuation"
            :headers="headersValuation"
            :items="valuation.rows"
            :search="tableSearch"
            :loading="loading"
            density="compact"
            items-per-page="25"
            :no-data-text="emptyText"
          >
            <template #item.quantity="{ item }">
              <span class="tabular-nums">{{ item.quantity }}</span>
            </template>
            <template #item.reserved="{ item }">
              <span class="tabular-nums">{{ item.reserved }}</span>
            </template>
            <template #item.available="{ item }">
              <span class="tabular-nums">{{ item.available }}</span>
            </template>
            <template #item.avg_cost="{ item }">
              <span class="tabular-nums">{{ fmtMoney(item.avg_cost) }}</span>
            </template>
            <template #item.value="{ item }">
              <span class="tabular-nums">{{ fmtMoney(item.value) }}</span>
            </template>
          </VDataTable>
          <div
            v-if="valuation"
            class="mt-3 text-body-2"
          >
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
        <template v-if="activeTab === 'movements'">
          <VDataTable
            v-if="movements"
            :headers="headersMovements"
            :items="movements.rows"
            :search="tableSearch"
            :loading="loading"
            density="compact"
            items-per-page="25"
            :no-data-text="emptyText"
          >
            <template #item.reasons="{ item }">
              <span class="text-caption">{{ reasonsText(item.reasons) }}</span>
            </template>
          </VDataTable>
          <div
            v-if="movements"
            class="mt-3 text-body-2 font-weight-bold"
          >
            Net change: {{ movements.totals.net_change }}
          </div>
        </template>

        <!-- Purchases -->
        <template v-if="activeTab === 'purchases'">
          <VDataTable
            v-if="purchases"
            :headers="headersPurchases"
            :items="purchases.rows"
            :search="tableSearch"
            :loading="loading"
            density="compact"
            items-per-page="25"
            :no-data-text="emptyText"
          >
            <template #item.value_received="{ item }">
              <span class="tabular-nums">{{ fmtMoney(item.value_received) }}</span>
            </template>
            <template #item.value_returned="{ item }">
              <span class="tabular-nums">{{ fmtMoney(item.value_returned) }}</span>
            </template>
            <template #item.net_value="{ item }">
              <span class="tabular-nums">{{ fmtMoney(item.net_value) }}</span>
            </template>
          </VDataTable>
          <div
            v-if="purchases"
            class="mt-3 text-body-2 font-weight-bold"
          >
            Net purchases: {{ fmtMoney(purchases.totals.net_value) }}
          </div>
          <template v-if="purchases?.open_orders.length">
            <div class="text-subtitle-2 mt-4 mb-2">
              Open purchase orders
            </div>
            <VDataTable
              :headers="[
                { title: 'PO', key: 'po_no' },
                { title: 'Supplier', key: 'supplier_name' },
                { title: 'Expected', key: 'expected_date' },
                { title: 'Outstanding qty', key: 'outstanding_qty', align: 'end' as const },
                { title: 'Outstanding value', key: 'outstanding_value', align: 'end' as const },
                { title: 'Status', key: 'status' },
              ]"
              :items="purchases.open_orders"
              density="compact"
              items-per-page="10"
            >
              <template #item.expected_date="{ item }">
                {{ item.expected_date || '—' }}
                <VChip
                  v-if="item.overdue"
                  size="x-small"
                  color="error"
                  class="ms-1"
                >
                  Overdue
                </VChip>
              </template>
              <template #item.outstanding_value="{ item }">
                <span class="tabular-nums">{{ fmtMoney(item.outstanding_value) }}</span>
              </template>
            </VDataTable>
          </template>
        </template>

        <!-- Sales -->
        <template v-if="activeTab === 'sales'">
          <VDataTable
            v-if="sales"
            :headers="headersSales"
            :items="sales.rows"
            :search="tableSearch"
            :loading="loading"
            density="compact"
            items-per-page="25"
            :no-data-text="emptyText"
          >
            <template #item.amount="{ item }">
              <span class="tabular-nums">{{ fmtMoney(item.amount) }}</span>
            </template>
          </VDataTable>
          <div
            v-if="sales"
            class="mt-3 text-body-2"
          >
            Invoiced: {{ fmtMoney(sales.totals.invoiced) }} ·
            Header discounts: -{{ fmtMoney(sales.totals.header_discounts) }} ·
            Credited: {{ fmtMoney(sales.totals.credited) }} ·
            <span class="font-weight-bold">Net sales: {{ fmtMoney(sales.totals.net_sales) }}</span> ·
            Payments: {{ fmtMoney(sales.totals.payments) }}
          </div>
        </template>

        <!-- Receivables -->
        <template v-if="activeTab === 'receivables'">
          <VDataTable
            v-if="receivables"
            :headers="headersReceivables"
            :items="receivables.rows"
            :search="tableSearch"
            :loading="loading"
            density="compact"
            items-per-page="25"
            :no-data-text="emptyText"
          >
            <template #item.issue_date="{ item }">
              {{ item.issue_date || '—' }}
            </template>
            <template #item.total="{ item }">
              <span class="tabular-nums">{{ fmtMoney(item.total) }}</span>
            </template>
            <template #item.paid="{ item }">
              <span class="tabular-nums">{{ fmtMoney(item.paid) }}</span>
            </template>
            <template #item.credited="{ item }">
              <span class="tabular-nums">{{ fmtMoney(item.credited) }}</span>
            </template>
            <template #item.balance="{ item }">
              <span class="tabular-nums">{{ fmtMoney(item.balance) }}</span>
            </template>
          </VDataTable>
          <div
            v-if="receivables"
            class="mt-3 text-body-2"
          >
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
        <template v-if="activeTab === 'writeoffs'">
          <VDataTable
            v-if="writeoffs"
            :headers="headersWriteoffs"
            :items="writeoffs.rows"
            :search="tableSearch"
            :loading="loading"
            density="compact"
            items-per-page="25"
            :no-data-text="emptyText"
          >
            <template #item.reason_code="{ item }">
              {{ reasonCodeLabel(item.reason_code) }}
            </template>
            <template #item.cost="{ item }">
              <span class="tabular-nums">{{ fmtMoney(item.cost) }}</span>
            </template>
          </VDataTable>
          <div
            v-if="writeoffs"
            class="mt-3 text-body-2 font-weight-bold"
          >
            Total: {{ writeoffs.totals.qty }} units · {{ fmtMoney(writeoffs.totals.cost) }}
          </div>
        </template>
      </VCardText>
    </VCard>
  </div>
</template>

<style scoped>
.v-table :deep(.v-table__wrapper) {
  overflow-x: auto;
}
</style>
