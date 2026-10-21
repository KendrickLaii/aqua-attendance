<script setup lang="ts">
import {
  type InventoryAlerts,
  type InventoryDashboard,
  getInventoryAlerts,
  getInventoryDashboard,
  sendInventoryAlerts,
} from '@/api/attendance/inventoryReports'
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
    const [d, a] = await Promise.all([getInventoryDashboard(params), getInventoryAlerts(params)])

    dashboard.value = d
    alerts.value = a
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
