<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'
import {
  type InventoryAlerts,
  type InventoryDashboard,
  getInventoryAlerts,
  getInventoryDashboard,
  sendInventoryAlerts,
} from '@/api/attendance/inventoryReports'
import { listSalesOrders } from '@/api/attendance/inventorySales'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const loading = ref(true)
const saving = ref(false)
const loadError = ref('')
const actionError = ref('')
const actionSuccess = ref('')

useAutoClearAlerts(loadError)
useAutoClearAlerts(actionError)
useAutoClearAlerts(actionSuccess)

const locations = ref<LocationItem[]>([])
const locationFilter = ref<string | null>(null)
const dashboard = ref<InventoryDashboard | null>(null)
const alerts = ref<InventoryAlerts | null>(null)

const draftSoCount = ref(0)
const awaitingInvoiceCount = ref(0)

const locParam = () => locationFilter.value ? { location_id: locationFilter.value } : {}

const moneyFmt = new Intl.NumberFormat('en-HK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function fmtMoney(value: number | null | undefined): string {
  return moneyFmt.format(value ?? 0)
}

interface KpiCard {
  zh: string
  en: string
  value: string
  caption: string
  captionColor?: string
  to: RouteLocationRaw
  icon: string
}

const kpiGroups = computed<{ title: string; cards: KpiCard[] }[]>(() => {
  const d = dashboard.value
  if (!d)
    return []

  return [
    {
      title: '庫存 Stock',
      cards: [
        {
          zh: '追蹤品項',
          en: 'Tracked items',
          value: String(d.tracked_items),
          caption: '有在記庫存的品項數',
          to: '/attendance/inventory/items',
          icon: 'ri-archive-line',
        },
        {
          zh: '低庫存',
          en: 'Low stock',
          value: String(d.low_stock_count),
          caption: d.low_stock_count > 0 ? '有品項低於安全庫存，可能要補貨' : '沒有品項低於安全庫存',
          captionColor: d.low_stock_count > 0 ? 'error' : undefined,
          to: '/attendance/inventory',
          icon: 'ri-error-warning-line',
        },
        {
          zh: '庫存總值',
          en: 'Stock value',
          value: `$${fmtMoney(d.stock_value)}`,
          caption: '以平均成本估算',
          to: { path: '/attendance/inventory/reports', query: { tab: 'valuation' } },
          icon: 'ri-money-dollar-circle-line',
        },
      ],
    },
    {
      title: '進貨 Buying',
      cards: [
        {
          zh: '未完成採購單',
          en: 'Open POs',
          value: String(d.open_purchase_orders),
          caption: d.overdue_purchase_orders > 0 ? `逾期 ${d.overdue_purchase_orders} 張` : '沒有逾期',
          captionColor: d.overdue_purchase_orders > 0 ? 'warning' : undefined,
          to: { path: '/attendance/inventory/purchase-orders', query: { status: 'ordered' } },
          icon: 'ri-shopping-cart-line',
        },
      ],
    },
    {
      title: '銷售 Selling',
      cards: [
        {
          zh: '待開票銷售單',
          en: 'To invoice',
          value: String(d.open_sales_orders),
          caption: `還有 ${d.uninvoiced_qty} 件未開票`,
          to: { path: '/attendance/inventory/sales-orders', query: { status: 'confirmed' } },
          icon: 'ri-file-list-3-line',
        },
        {
          zh: '已開票未送貨',
          en: 'To deliver',
          value: String(d.undelivered_invoice_count),
          caption: `還有 ${d.undelivered_qty} 件未送`,
          to: { path: '/attendance/inventory/invoices', query: { status: 'issued' } },
          icon: 'ri-truck-line',
        },
        {
          zh: '未收款發票',
          en: 'Unpaid',
          value: `$${fmtMoney(d.receivable_balance)}`,
          caption: `${d.unpaid_invoice_count} 張未收齊`,
          to: { path: '/attendance/inventory/invoices', query: { payment_status: 'unpaid' } },
          icon: 'ri-bill-line',
        },
        {
          zh: '逾期應收',
          en: 'Overdue',
          value: `$${fmtMoney(d.overdue_receivable_balance)}`,
          caption: d.overdue_receivable_balance > 0 ? '超過 30 天未收，建議跟進' : '沒有逾期款項',
          captionColor: d.overdue_receivable_balance > 0 ? 'error' : undefined,
          to: { path: '/attendance/inventory/reports', query: { tab: 'receivables' } },
          icon: 'ri-alarm-warning-line',
        },
      ],
    },
  ]
})

interface NextStep {
  title: string
  count: number
  detail: string
  to: RouteLocationRaw
  color: string
}

const nextSteps = computed<NextStep[]>(() => {
  const d = dashboard.value
  if (!d)
    return []
  const steps: NextStep[] = []

  if (d.overdue_receivable_balance > 0)
    steps.push({ title: '跟進逾期發票', count: d.unpaid_invoice_count, detail: `逾期 ${fmtMoney(d.overdue_receivable_balance)}，聯絡客戶收款`, to: { path: '/attendance/inventory/invoices', query: { payment_status: 'unpaid' } }, color: 'error' })
  if (d.overdue_purchase_orders > 0)
    steps.push({ title: '追問逾期採購單', count: d.overdue_purchase_orders, detail: '預計到貨日已過，聯絡供應商', to: { path: '/attendance/inventory/purchase-orders', query: { status: 'ordered' } }, color: 'warning' })
  if (d.low_stock_count > 0)
    steps.push({ title: '補低庫存的貨', count: d.low_stock_count, detail: '有品項低於安全庫存，去建採購單', to: { path: '/attendance/inventory/purchase-orders', query: { action: 'new' } }, color: 'error' })
  if (awaitingInvoiceCount.value > 0)
    steps.push({ title: '開發票給已確認的訂單', count: awaitingInvoiceCount.value, detail: `還有 ${d.uninvoiced_qty} 件已確認未開票`, to: { path: '/attendance/inventory/sales-orders', query: { status: 'confirmed' } }, color: 'primary' })
  if (d.undelivered_invoice_count > 0)
    steps.push({ title: '已開票但還沒送貨', count: d.undelivered_invoice_count, detail: `還有 ${d.undelivered_qty} 件貨未送，去建出貨單`, to: { path: '/attendance/inventory/invoices', query: { status: 'issued' } }, color: 'warning' })
  if (draftSoCount.value > 0)
    steps.push({ title: '確認銷售單草稿', count: draftSoCount.value, detail: '草稿確認後才會保留庫存', to: { path: '/attendance/inventory/sales-orders', query: { status: 'draft' } }, color: 'primary' })

  return steps
})

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const params = locationFilter.value ? { location_id: locationFilter.value } : undefined

    const [d, a, draftSos, confirmedSos, partialSos] = await Promise.all([
      getInventoryDashboard(params),
      getInventoryAlerts(params),
      listSalesOrders({ status: 'draft', page_size: 1, ...locParam() }),
      listSalesOrders({ status: 'confirmed', page_size: 1, ...locParam() }),
      listSalesOrders({ status: 'partial', page_size: 1, ...locParam() }),
    ])

    dashboard.value = d
    alerts.value = a
    draftSoCount.value = draftSos.total
    awaitingInvoiceCount.value = confirmedSos.total + partialSos.total
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Failed to load dashboard.')
  }
  finally {
    loading.value = false
  }
}

async function sendNow() {
  saving.value = true
  actionError.value = ''
  try {
    const params = locationFilter.value ? { location_id: locationFilter.value } : undefined
    const result = await sendInventoryAlerts(params)

    actionSuccess.value = `已送出 ${result.created} 則通知（略過 ${result.skipped} 則重複的）。`
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to send notifications.')
  }
  finally {
    saving.value = false
  }
}

const alertCount = computed(() => {
  const a = alerts.value
  if (!a)
    return 0

  return a.low_stock.length + a.overdue_purchase_orders.length
    + a.overdue_invoices.length + a.expiring_proformas.length
})

interface AlertRow { id: string; label: string; detail: string; to: string }
interface AlertGroup { key: string; title: string; count: number; items: AlertRow[] }

const alertGroups = computed<AlertGroup[]>(() => {
  const a = alerts.value
  if (!a)
    return []

  return [
    {
      key: 'low_stock',
      title: '低庫存',
      count: a.low_stock.length,
      items: a.low_stock.map(x => ({
        id: `${x.item_id}-${x.location_id}`,
        label: `${x.sku_code} ${x.name_zh}`,
        detail: `剩 ${x.quantity}（安全庫存 ${x.reorder_level}）`,
        to: '/attendance/inventory',
      })),
    },
    {
      key: 'overdue_po',
      title: '逾期採購單',
      count: a.overdue_purchase_orders.length,
      items: a.overdue_purchase_orders.map(x => ({
        id: x.id,
        label: x.po_no,
        detail: `預計 ${x.expected_date || '—'} 到貨（${x.status}）`,
        to: '/attendance/inventory/purchase-orders',
      })),
    },
    {
      key: 'overdue_invoice',
      title: '逾期發票',
      count: a.overdue_invoices.length,
      items: a.overdue_invoices.map(x => ({
        id: x.id,
        label: x.invoice_no,
        detail: `${x.buyer_name} · 未收 $${fmtMoney(x.balance)} · ${x.issue_date || ''}`,
        to: '/attendance/inventory/invoices',
      })),
    },
    {
      key: 'expiring_pf',
      title: '過期形式發票',
      count: a.expiring_proformas.length,
      items: a.expiring_proformas.map(x => ({
        id: x.id,
        label: x.pf_no,
        detail: `${x.so_no} · 有效至 ${x.pf_valid_until || '—'}`,
        to: '/attendance/inventory/sales-orders',
      })),
    },
  ].filter(g => g.count > 0)
})

const expandedGroups = ref<Record<string, boolean>>({})

function groupItems(g: AlertGroup) {
  return expandedGroups.value[g.key] ? g.items : g.items.slice(0, 5)
}

const quickActions = [
  { label: 'New Purchase Order', icon: 'ri-shopping-cart-line', to: { path: '/attendance/inventory/purchase-orders', query: { action: 'new' } } },
  { label: 'New Sales Order', icon: 'ri-store-2-line', to: { path: '/attendance/inventory/sales-orders', query: { action: 'new' } } },
  { label: 'Record Stock Out', icon: 'ri-logout-box-line', to: { path: '/attendance/inventory', query: { action: 'movement', type: 'out' } } },
  { label: 'Start Stocktake', icon: 'ri-survey-line', to: { path: '/attendance/inventory/stocktakes', query: { action: 'new' } } },
]

watch(locationFilter, load)

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  try {
    locations.value = await listLocations()
  }
  catch {
    // optional
  }
  await load()
})
</script>

<template>
  <div>
    <VCard class="mb-4">
      <VCardText>
        <div class="d-flex flex-wrap gap-3 align-center">
          <div>
            <div class="text-h5 font-weight-medium">
              庫存儀表板 Dashboard
            </div>
            <div class="text-body-2 text-medium-emphasis">
              這一頁顯示需要注意的事：低庫存、待開票/待送貨和未收款的發票。
            </div>
          </div>
          <VSpacer />
          <VSelect
            v-model="locationFilter"
            :items="locations.map(l => ({ value: l.id, title: l.name_en || l.name_zh || l.code }))"
            label="Location"
            density="comfortable"
            style="max-width: 280px"
            hide-details
            clearable
          />
        </div>
        <div class="d-flex flex-wrap gap-2 mt-3">
          <VBtn
            v-for="qa in quickActions"
            :key="qa.label"
            :to="qa.to"
            :prepend-icon="qa.icon"
            variant="tonal"
            color="primary"
            size="small"
          >
            {{ qa.label }}
          </VBtn>
        </div>
      </VCardText>
    </VCard>

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
    <VAlert
      v-if="actionSuccess"
      type="success"
      variant="tonal"
      class="mb-4"
    >
      {{ actionSuccess }}
    </VAlert>

    <VProgressCircular
      v-if="loading"
      indeterminate
      color="primary"
      size="48"
    />

    <template v-else-if="dashboard">
      <div
        v-for="group in kpiGroups"
        :key="group.title"
      >
        <div class="text-subtitle-2 text-medium-emphasis mt-4 mb-2">
          {{ group.title }}
        </div>
        <VRow dense>
          <VCol
            v-for="card in group.cards"
            :key="card.en"
            cols="12"
            sm="6"
            md="4"
            lg="3"
          >
            <VCard
              :to="card.to"
              link
              class="h-100"
            >
              <VCardText>
                <div class="d-flex align-center gap-2 mb-1">
                  <VIcon
                    :icon="card.icon"
                    size="18"
                    class="text-medium-emphasis"
                  />
                  <span class="text-body-2 font-weight-medium">{{ card.zh }}</span>
                  <span class="text-caption text-medium-emphasis">{{ card.en }}</span>
                </div>
                <div class="text-h5 tabular-nums">
                  {{ card.value }}
                </div>
                <div
                  class="text-caption mt-1"
                  :class="card.captionColor ? `text-${card.captionColor}` : 'text-medium-emphasis'"
                >
                  {{ card.caption }}
                </div>
              </VCardText>
            </VCard>
          </VCol>
        </VRow>
      </div>

      <VCard class="mt-4">
        <VCardTitle>本月 This month</VCardTitle>
        <VCardText>
          <VRow dense>
            <VCol
              cols="12"
              md="6"
            >
              <div class="text-subtitle-2 mb-2">
                銷售 Sales
              </div>
              <div class="text-body-2">
                開票 <span class="tabular-nums font-weight-medium">{{ fmtMoney(dashboard.month_invoiced) }}</span>
                · 折讓 <span class="tabular-nums font-weight-medium text-error">-{{ fmtMoney(dashboard.month_credited) }}</span>
                · 淨額 <span class="tabular-nums font-weight-bold">{{ fmtMoney(dashboard.month_sales) }}</span>
              </div>
            </VCol>
            <VCol
              cols="12"
              md="6"
            >
              <div class="text-subtitle-2 mb-2">
                進貨 Purchases
              </div>
              <div class="text-body-2">
                收貨 <span class="tabular-nums font-weight-medium">{{ fmtMoney(dashboard.month_purchases_gross) }}</span>
                · 退貨 <span class="tabular-nums font-weight-medium text-error">-{{ fmtMoney(dashboard.month_purchase_returns) }}</span>
                · 淨額 <span class="tabular-nums font-weight-bold">{{ fmtMoney(dashboard.month_purchases) }}</span>
              </div>
            </VCol>
          </VRow>
        </VCardText>
      </VCard>

      <VCard class="mt-4">
        <VCardTitle>下一步 What to do next</VCardTitle>
        <VCardText v-if="nextSteps.length">
          <VRow dense>
            <VCol
              v-for="step in nextSteps"
              :key="step.title"
              cols="12"
              sm="6"
              md="4"
            >
              <VCard
                :to="step.to"
                variant="tonal"
                :color="step.color"
                link
                class="h-100"
              >
                <VCardText class="d-flex align-center gap-3">
                  <VAvatar
                    :color="step.color"
                    size="40"
                  >
                    {{ step.count }}
                  </VAvatar>
                  <div class="min-w-0">
                    <div class="font-weight-medium">
                      {{ step.title }}
                    </div>
                    <div class="text-caption">
                      {{ step.detail }}
                    </div>
                  </div>
                  <VSpacer />
                  <VIcon icon="ri-arrow-right-line" />
                </VCardText>
              </VCard>
            </VCol>
          </VRow>
        </VCardText>
        <VCardText
          v-else
          class="text-medium-emphasis"
        >
          目前沒有待辦事項。
        </VCardText>
      </VCard>

      <VCard class="mt-4">
        <VCardTitle class="d-flex align-center">
          <span>警示 Alerts ({{ alertCount }})</span>
          <VSpacer />
          <VTooltip
            text="把這些警示發到所有管理員的通知鈴鐺"
            location="bottom"
          >
            <template #activator="{ props }">
              <VBtn
                v-bind="props"
                color="primary"
                variant="tonal"
                prepend-icon="ri-notification-3-line"
                :loading="saving"
                @click="sendNow"
              >
                Send notifications now
              </VBtn>
            </template>
          </VTooltip>
        </VCardTitle>
        <VCardText v-if="alerts">
          <VAlert
            v-if="alertCount === 0"
            type="success"
            variant="tonal"
          >
            目前沒有警示。
          </VAlert>

          <div
            v-for="g in alertGroups"
            :key="g.key"
            class="mt-3"
          >
            <div class="d-flex align-center gap-2 mb-1">
              <span class="text-subtitle-2">{{ g.title }}</span>
              <VChip
                size="x-small"
                color="error"
                variant="tonal"
              >
                {{ g.count }}
              </VChip>
            </div>
            <div
              v-for="item in groupItems(g)"
              :key="item.id"
              class="text-body-2"
            >
              <RouterLink :to="item.to">
                {{ item.label }}
              </RouterLink>
              — {{ item.detail }}
            </div>
            <VBtn
              v-if="g.items.length > 5"
              variant="text"
              size="x-small"
              class="mt-1"
              @click="expandedGroups[g.key] = !expandedGroups[g.key]"
            >
              {{ expandedGroups[g.key] ? '收起' : `查看全部 (${g.items.length})` }}
            </VBtn>
          </div>
        </VCardText>
      </VCard>
    </template>
  </div>
</template>
