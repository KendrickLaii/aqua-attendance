<script setup lang="ts">
import {
  type InventoryAlerts,
  type InventoryDashboard,
  getInventoryAlerts,
  getInventoryDashboard,
  sendInventoryAlerts,
} from '@/api/attendance/inventoryReports'
import { listInvoices } from '@/api/attendance/inventoryInvoicing'
import { listDeliveryOrders, listSalesOrders } from '@/api/attendance/inventorySales'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import StatCards from '@/components/attendance/StatCards.vue'
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
const awaitingDeliveryCount = ref(0)
const uninvoicedDoCount = ref(0)

const locParam = () => locationFilter.value ? { location_id: locationFilter.value } : {}

interface NextStep {
  title: string
  count: number
  detail: string
  to: string
  color: string
}

const nextSteps = computed<NextStep[]>(() => {
  const d = dashboard.value
  if (!d)
    return []
  const steps: NextStep[] = []

  if (draftSoCount.value > 0)
    steps.push({ title: 'Confirm sales orders', count: draftSoCount.value, detail: 'draft orders waiting to reserve stock', to: '/attendance/inventory/sales-orders?status=draft', color: 'primary' })
  if (awaitingDeliveryCount.value > 0)
    steps.push({ title: 'Ship confirmed orders', count: awaitingDeliveryCount.value, detail: 'confirmed orders awaiting a delivery order', to: '/attendance/inventory/sales-orders?status=confirmed', color: 'primary' })
  if (uninvoicedDoCount.value > 0)
    steps.push({ title: 'Invoice delivered orders', count: uninvoicedDoCount.value, detail: 'delivered goods with no invoice yet', to: '/attendance/inventory/delivery-orders?status=confirmed', color: 'warning' })
  if (d.unpaid_invoice_count > 0)
    steps.push({ title: 'Collect unpaid invoices', count: d.unpaid_invoice_count, detail: `balance ${fmtMoney(d.receivable_balance)}`, to: '/attendance/inventory/invoices?payment_status=unpaid', color: 'error' })
  if (d.overdue_purchase_orders > 0)
    steps.push({ title: 'Chase overdue POs', count: d.overdue_purchase_orders, detail: 'expected delivery date has passed', to: '/attendance/inventory/purchase-orders', color: 'warning' })
  if (d.low_stock_count > 0)
    steps.push({ title: 'Reorder low-stock items', count: d.low_stock_count, detail: 'at or below reorder level', to: '/attendance/inventory', color: 'error' })

  return steps
})

function fmtMoney(value: number | null | undefined): string {
  return (value ?? 0).toFixed(2)
}

const statCards = computed(() => {
  const d = dashboard.value
  if (!d)
    return []

  return [
    { label: 'Tracked items', value: String(d.tracked_items), icon: 'ri-archive-line', color: 'primary' },
    { label: 'Low stock', value: String(d.low_stock_count), icon: 'ri-error-warning-line', color: d.low_stock_count > 0 ? 'error' : 'success' },
    { label: 'Stock value', value: fmtMoney(d.stock_value), icon: 'ri-money-dollar-circle-line', color: 'info' },
    { label: 'Open POs', value: `${d.open_purchase_orders} (${d.overdue_purchase_orders} overdue)`, icon: 'ri-shopping-cart-line', color: d.overdue_purchase_orders > 0 ? 'warning' : 'primary' },
    { label: 'Open SOs', value: `${d.open_sales_orders} · ${d.unshipped_qty} unshipped`, icon: 'ri-truck-line', color: 'primary' },
    { label: 'Unpaid invoices', value: `${d.unpaid_invoice_count} · ${fmtMoney(d.receivable_balance)}`, icon: 'ri-bill-line', color: 'info' },
    { label: 'Overdue receivable', value: fmtMoney(d.overdue_receivable_balance), icon: 'ri-alarm-warning-line', color: d.overdue_receivable_balance > 0 ? 'error' : 'success' },
    { label: 'This month', value: `Sales ${fmtMoney(d.month_sales)} · Purchases ${fmtMoney(d.month_purchases)}`, icon: 'ri-calendar-line', color: 'primary' },
  ]
})

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const params = locationFilter.value ? { location_id: locationFilter.value } : undefined

    const [d, a, draftSos, confirmedSos, partialSos, confirmedDos, invList] = await Promise.all([
      getInventoryDashboard(params),
      getInventoryAlerts(params),
      listSalesOrders({ status: 'draft', page_size: 1, ...locParam() }),
      listSalesOrders({ status: 'confirmed', page_size: 1, ...locParam() }),
      listSalesOrders({ status: 'partial', page_size: 1, ...locParam() }),
      listDeliveryOrders({ status: 'confirmed', page_size: 200, ...locParam() }),
      listInvoices({ page_size: 200, ...locParam() }),
    ])

    dashboard.value = d
    alerts.value = a
    draftSoCount.value = draftSos.total
    awaitingDeliveryCount.value = confirmedSos.total + partialSos.total

    const invoicedDoIds = new Set(
      invList.items.filter(i => i.status !== 'void').map(i => i.do_id),
    )

    uninvoicedDoCount.value = confirmedDos.items.filter(dor => !invoicedDoIds.has(dor.id)).length
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

    actionSuccess.value = `Notifications sent: ${result.created} created, ${result.skipped} skipped.`
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
      <VCardText class="d-flex flex-wrap gap-3 align-center">
        <div class="text-h5 font-weight-medium">
          Inventory Dashboard 庫存儀表板
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

    <template v-else>
      <StatCards :cards="statCards" />

      <VCard
        v-if="nextSteps.length"
        class="mt-4"
      >
        <VCardTitle class="d-flex align-center">
          <span>What to do next 下一步</span>
        </VCardTitle>
        <VCardText>
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
              >
                <VCardText class="d-flex align-center gap-3">
                  <VAvatar
                    :color="step.color"
                    size="40"
                  >
                    {{ step.count }}
                  </VAvatar>
                  <div>
                    <div class="font-weight-medium">
                      {{ step.title }}
                    </div>
                    <div class="text-caption">
                      {{ step.detail }}
                    </div>
                  </div>
                </VCardText>
              </VCard>
            </VCol>
          </VRow>
        </VCardText>
      </VCard>

      <VCard class="mt-4">
        <VCardTitle class="d-flex align-center">
          <span>Alerts 警示 ({{ alertCount }})</span>
          <VSpacer />
          <VBtn
            color="primary"
            variant="tonal"
            prepend-icon="ri-notification-3-line"
            :loading="saving"
            @click="sendNow"
          >
            Send notifications now
          </VBtn>
        </VCardTitle>
        <VCardText v-if="alerts">
          <VAlert
            v-if="alertCount === 0"
            type="success"
            variant="tonal"
          >
            No alerts.
          </VAlert>

          <div v-if="alerts.low_stock.length">
            <div class="text-subtitle-2 mb-1">
              Low stock 低庫存
            </div>
            <div
              v-for="a in alerts.low_stock"
              :key="`${a.item_id}-${a.location_id}`"
              class="text-body-2"
            >
              <RouterLink to="/attendance/inventory">
                {{ a.sku_code }} {{ a.name_zh }}
              </RouterLink>
              — {{ a.quantity }} on hand (reorder level {{ a.reorder_level }})
            </div>
          </div>

          <div
            v-if="alerts.overdue_purchase_orders.length"
            class="mt-4"
          >
            <div class="text-subtitle-2 mb-1">
              Overdue purchase orders 逾期採購單
            </div>
            <div
              v-for="a in alerts.overdue_purchase_orders"
              :key="a.id"
              class="text-body-2"
            >
              <RouterLink to="/attendance/inventory/purchase-orders">
                {{ a.po_no }}
              </RouterLink>
              — expected {{ a.expected_date }} ({{ a.status }})
            </div>
          </div>

          <div
            v-if="alerts.overdue_invoices.length"
            class="mt-4"
          >
            <div class="text-subtitle-2 mb-1">
              Overdue invoices 逾期發票
            </div>
            <div
              v-for="a in alerts.overdue_invoices"
              :key="a.id"
              class="text-body-2"
            >
              <RouterLink to="/attendance/inventory/invoices">
                {{ a.invoice_no }}
              </RouterLink>
              — {{ a.buyer_name }} · balance {{ fmtMoney(a.balance) }} since {{ a.issue_date }}
            </div>
          </div>

          <div
            v-if="alerts.expiring_proformas.length"
            class="mt-4"
          >
            <div class="text-subtitle-2 mb-1">
              Expired proformas 逾期形式發票
            </div>
            <div
              v-for="a in alerts.expiring_proformas"
              :key="a.id"
              class="text-body-2"
            >
              <RouterLink to="/attendance/inventory/sales-orders">
                {{ a.pf_no }}
              </RouterLink>
              — {{ a.so_no }} · valid until {{ a.pf_valid_until }}
            </div>
          </div>
        </VCardText>
      </VCard>
    </template>
  </div>
</template>
