<script setup lang="ts">
import {
  type InventoryCustomer,
  type ProformaDoc,
  type SalesOrder,
  type SalesOrderLinePayload,
  type SalesOrderStatus,
  cancelSalesOrder,
  confirmSalesOrder,
  createDeliveryOrder,
  createSalesOrder,
  deleteSalesOrder,
  getProforma,
  getSalesOrder,
  issueProforma,
  listCustomers,
  listSalesOrders,
  updateSalesOrder,
} from '@/api/attendance/inventorySales'
import {
  type InventoryItem,
  type InventoryStock,
  listInventoryItems,
  listInventoryStocks,
} from '@/api/attendance/inventory'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import {
  type InventoryReceiptPaidBy,
  RECEIPT_PAID_BY_OPTIONS,
  quickFulfill,
} from '@/api/attendance/inventoryInvoicing'
import AttendancePaginationBar from '@/components/attendance/AttendancePaginationBar.vue'
import InventoryStatusChip from '@/components/attendance/inventory/InventoryStatusChip.vue'
import ProformaPrintDialog from '@/components/attendance/inventory/ProformaPrintDialog.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const loading = ref(true)
const detailLoading = ref(false)
const saving = ref(false)
const loadError = ref('')
const actionError = ref('')
const actionSuccess = ref('')

useAutoClearAlerts(loadError)
useAutoClearAlerts(actionError)
useAutoClearAlerts(actionSuccess)

const customers = ref<InventoryCustomer[]>([])
const locations = ref<LocationItem[]>([])
const items = ref<InventoryItem[]>([])
const stocks = ref<InventoryStock[]>([])

const orders = ref<SalesOrder[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const customerFilter = ref<string | null>(null)
const locationFilter = ref<string | null>(null)
const statusFilter = ref<SalesOrderStatus | null>(null)

const selected = ref<SalesOrder | null>(null)

const statusOptions = [
  { value: 'draft' as const, title: 'Draft' },
  { value: 'confirmed' as const, title: 'Confirmed' },
  { value: 'partial' as const, title: 'Partial' },
  { value: 'fulfilled' as const, title: 'Fulfilled' },
  { value: 'cancelled' as const, title: 'Cancelled' },
]

const customerOptions = computed(() =>
  customers.value.map(c => ({ value: c.id, title: `${c.code} · ${c.name_zh}` })),
)

const locationOptions = computed(() =>
  locations.value.map(l => ({
    value: l.id,
    title: [l.name_en, l.name_zh].filter(Boolean).join(' · '),
  })),
)

const itemById = computed(() => new Map(items.value.map(i => [i.id, i])))

const stockByItem = computed(() => {
  const map = new Map<string, InventoryStock>()

  for (const s of stocks.value)
    map.set(s.item_id, s)

  return map
})

const itemOptions = computed(() =>
  items.value.map(i => {
    const stock = stockByItem.value.get(i.id)
    const avail = stock ? ` (avail ${stock.available})` : ''

    return {
      value: i.id,
      title: `${[i.sku_code, i.name_zh].filter(Boolean).join(' · ')}${avail}`,
    }
  }),
)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const isDraft = computed(() => selected.value?.status === 'draft')

const canShip = computed(() =>
  !!selected.value && ['confirmed', 'partial'].includes(selected.value.status),
)

const canQuickFulfill = computed(() =>
  !!selected.value && ['draft', 'confirmed', 'partial'].includes(selected.value.status),
)

interface EditLine {
  item_id: string | null
  qty: number
  unit_price: number
  discount_amount: number
}

const editLines = ref<EditLine[]>([])

const editForm = reactive({
  customer_id: null as string | null,
  location_id: null as string | null,
  order_date: '',
  discount_amount: 0,
  notes: '',
})

const linesSubtotal = computed(() =>
  editLines.value.reduce(
    (sum, l) => sum + Math.max(0, (l.qty || 0) * (l.unit_price || 0) - (l.discount_amount || 0)),
    0,
  ),
)

const editTotal = computed(() => Math.max(0, linesSubtotal.value - (editForm.discount_amount || 0)))

const proformaOpen = ref(false)
const proformaDoc = ref<ProformaDoc | null>(null)

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  loading.value = true
  try {
    const [customerResult, locationList, itemList] = await Promise.all([
      listCustomers({ is_active: true, page_size: 200 }),
      listLocations({ is_active: true }),
      listInventoryItems(),
    ])

    customers.value = customerResult.items
    locations.value = locationList
    items.value = itemList
    await loadOrders()
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Failed to load sales orders.')
  }
  finally {
    loading.value = false
  }
})

async function loadOrders() {
  loadError.value = ''
  try {
    const result = await listSalesOrders({
      customer_id: customerFilter.value ?? undefined,
      location_id: locationFilter.value ?? undefined,
      status: statusFilter.value ?? undefined,
      page: page.value,
      page_size: pageSize.value,
    })

    orders.value = result.items
    total.value = result.total
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Failed to load sales orders.')
  }
}

function onFiltersChange() {
  page.value = 1
  loadOrders()
}

async function refreshStocks() {
  if (!editForm.location_id) {
    stocks.value = []

    return
  }
  stocks.value = await listInventoryStocks({ location_id: editForm.location_id })
}

async function selectOrder(so: SalesOrder) {
  detailLoading.value = true
  try {
    const detail = await getSalesOrder(so.id)

    selected.value = detail
    resetEditor(detail)
    await refreshStocks()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to load sales order.')
  }
  finally {
    detailLoading.value = false
  }
}

function resetEditor(so: SalesOrder | null) {
  if (!so)
    return
  editForm.customer_id = so.customer_id
  editForm.location_id = so.location_id
  editForm.order_date = so.order_date
  editForm.discount_amount = so.discount_amount
  editForm.notes = so.notes ?? ''
  editLines.value = so.lines.map(l => ({
    item_id: l.item_id,
    qty: l.qty,
    unit_price: l.unit_price,
    discount_amount: l.discount_amount,
  }))
  if (editLines.value.length === 0)
    addLine()
}

function newOrder() {
  selected.value = null
  editForm.customer_id = null
  editForm.location_id = null
  editForm.order_date = new Date().toISOString().slice(0, 10)
  editForm.discount_amount = 0
  editForm.notes = ''
  editLines.value = []
  addLine()
}

function addLine() {
  editLines.value.push({ item_id: null, qty: 1, unit_price: 0, discount_amount: 0 })
}

function removeLine(index: number) {
  editLines.value.splice(index, 1)
}

function onItemPicked(line: EditLine) {
  const item = line.item_id ? itemById.value.get(line.item_id) : null

  if (item && !line.unit_price)
    line.unit_price = item.sale_price ?? 0
}

async function saveOrder() {
  actionError.value = ''
  actionSuccess.value = ''
  if (!editForm.customer_id || !editForm.location_id) {
    actionError.value = 'Customer and location are required.'

    return
  }

  const lines: SalesOrderLinePayload[] = editLines.value
    .filter(l => l.item_id && l.qty > 0)
    .map(l => ({
      item_id: l.item_id as string,
      qty: l.qty,
      unit_price: l.unit_price,
      discount_amount: l.discount_amount || 0,
    }))

  saving.value = true
  try {
    const payload = {
      customer_id: editForm.customer_id,
      location_id: editForm.location_id,
      order_date: editForm.order_date,
      discount_amount: editForm.discount_amount || 0,
      notes: editForm.notes || null,
      lines,
    }

    const saved = selected.value
      ? await updateSalesOrder(selected.value.id, payload)
      : await createSalesOrder(payload)

    selected.value = saved
    resetEditor(saved)
    actionSuccess.value = `Saved ${saved.so_no}.`
    await loadOrders()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to save sales order.')
  }
  finally {
    saving.value = false
  }
}

async function doConfirm() {
  if (!selected.value)
    return
  actionError.value = ''
  saving.value = true
  try {
    selected.value = await confirmSalesOrder(selected.value.id)
    actionSuccess.value = `${selected.value.so_no} confirmed — stock reserved.`
    await loadOrders()
    await refreshStocks()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to confirm.')
  }
  finally {
    saving.value = false
  }
}

async function doCancel() {
  if (!selected.value)
    return
  actionError.value = ''
  saving.value = true
  try {
    selected.value = await cancelSalesOrder(selected.value.id)
    actionSuccess.value = `${selected.value.so_no} cancelled.`
    await loadOrders()
    await refreshStocks()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to cancel.')
  }
  finally {
    saving.value = false
  }
}

async function doDelete() {
  if (!selected.value)
    return
  actionError.value = ''
  saving.value = true
  try {
    const no = selected.value.so_no

    await deleteSalesOrder(selected.value.id)
    actionSuccess.value = `Deleted draft ${no}.`
    selected.value = null
    await loadOrders()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to delete.')
  }
  finally {
    saving.value = false
  }
}

async function openProforma() {
  if (!selected.value)
    return
  actionError.value = ''
  saving.value = true
  try {
    selected.value = await issueProforma(selected.value.id)
    proformaDoc.value = await getProforma(selected.value.id)
    proformaOpen.value = true
    await loadOrders()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to issue proforma.')
  }
  finally {
    saving.value = false
  }
}

async function createDelivery() {
  if (!selected.value)
    return
  actionError.value = ''
  saving.value = true
  try {
    const dor = await createDeliveryOrder({
      so_id: selected.value.id,
      delivery_date: new Date().toISOString().slice(0, 10),
    })

    actionSuccess.value = `Created delivery order ${dor.do_no} from ${selected.value.so_no}.`
    await loadOrders()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to create delivery order.')
  }
  finally {
    saving.value = false
  }
}

function fmtMoney(value: number | null | undefined): string {
  return (value ?? 0).toFixed(2)
}

const quickFulfillOpen = ref(false)
const qfWithPay = ref(false)
const qfAmount = ref<number | null>(null)
const qfMethod = ref<InventoryReceiptPaidBy>('cash')
const qfReference = ref('')

function openQuickFulfill() {
  if (!selected.value)
    return
  qfWithPay.value = false
  qfAmount.value = selected.value.total
  qfMethod.value = 'cash'
  qfReference.value = ''
  quickFulfillOpen.value = true
}

async function doQuickFulfill() {
  if (!selected.value)
    return
  actionError.value = ''
  saving.value = true
  try {
    const result = await quickFulfill(selected.value.id, {
      pay: qfWithPay.value && qfAmount.value
        ? { amount: qfAmount.value, paid_by: qfMethod.value, reference_no: qfReference.value || null }
        : undefined,
    })

    quickFulfillOpen.value = false
    selected.value = result.so
    actionSuccess.value = `Fulfilled ${result.so.so_no}: DO ${result.delivery_order.do_no}, invoice ${result.invoice.invoice_no}${result.receipt ? `, receipt ${result.receipt.receipt_no}` : ''}.`
    await loadOrders()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to quick-fulfill.')
  }
  finally {
    saving.value = false
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
          Sales Orders 銷售單
        </div>
      </VCol>
      <VCol cols="auto">
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="loading"
          @click="loadOrders"
        >
          Refresh
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          class="ms-2"
          @click="newOrder"
        >
          New order
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
    <VAlert
      v-if="actionError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="actionError = ''"
    >
      {{ actionError }}
    </VAlert>
    <VAlert
      v-if="actionSuccess"
      type="success"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="actionSuccess = ''"
    >
      {{ actionSuccess }}
    </VAlert>

    <VRow>
      <VCol
        cols="12"
        md="5"
      >
        <VCard>
          <VCardText class="d-flex flex-wrap gap-3">
            <VSelect
              v-model="customerFilter"
              :items="customerOptions"
              label="Customer"
              density="comfortable"
              hide-details
              clearable
              @update:model-value="onFiltersChange"
            />
            <VSelect
              v-model="locationFilter"
              :items="locationOptions"
              label="Location"
              density="comfortable"
              hide-details
              clearable
              @update:model-value="onFiltersChange"
            />
            <VSelect
              v-model="statusFilter"
              :items="statusOptions"
              label="Status"
              density="comfortable"
              hide-details
              clearable
              @update:model-value="onFiltersChange"
            />
          </VCardText>
          <VList density="compact">
            <VListItem
              v-for="so in orders"
              :key="so.id"
              :active="selected?.id === so.id"
              @click="selectOrder(so)"
            >
              <VListItemTitle>{{ so.so_no }}</VListItemTitle>
              <VListItemSubtitle>
                {{ so.customer_name || '—' }} · {{ so.order_date }} · {{ fmtMoney(so.total) }}
                <template v-if="so.pf_no">
                  · {{ so.pf_no }}
                </template>
              </VListItemSubtitle>
              <template #append>
                <InventoryStatusChip :status="so.status" />
              </template>
            </VListItem>
            <VListItem v-if="orders.length === 0 && !loading">
              <VListItemTitle class="text-medium-emphasis">
                No sales orders yet.
              </VListItemTitle>
            </VListItem>
          </VList>
          <AttendancePaginationBar
            v-model:page="page"
            v-model:page-size="pageSize"
            :total-pages="totalPages"
            :caption="`Page ${page} of ${totalPages} · ${total} order${total === 1 ? '' : 's'}`"
            @change="loadOrders"
          />
        </VCard>
      </VCol>

      <VCol
        cols="12"
        md="7"
      >
        <VCard v-if="detailLoading">
          <VCardText class="text-center py-12">
            <VProgressCircular
              indeterminate
              color="primary"
              size="40"
            />
          </VCardText>
        </VCard>
        <VCard v-else-if="selected || editLines.length">
          <VCardTitle class="d-flex align-center gap-3 flex-wrap">
            <span>{{ selected ? selected.so_no : 'New sales order' }}</span>
            <InventoryStatusChip
              v-if="selected"
              :status="selected.status"
            />
            <VSpacer />
            <template v-if="isDraft">
              <VBtn
                color="primary"
                size="small"
                :loading="saving"
                @click="saveOrder"
              >
                Save
              </VBtn>
              <VBtn
                v-if="selected"
                variant="tonal"
                color="success"
                size="small"
                :loading="saving"
                @click="doConfirm"
              >
                Confirm
              </VBtn>
              <VBtn
                v-if="selected"
                variant="tonal"
                color="success"
                size="small"
                @click="openQuickFulfill"
              >
                Quick Fulfill & Invoice
              </VBtn>
              <VBtn
                v-if="selected"
                variant="text"
                color="error"
                size="small"
                :loading="saving"
                @click="doDelete"
              >
                Delete
              </VBtn>
            </template>
            <template v-if="selected && !isDraft && selected.status !== 'cancelled'">
              <VBtn
                variant="tonal"
                color="info"
                size="small"
                :loading="saving"
                @click="openProforma"
              >
                Proforma
              </VBtn>
              <VBtn
                v-if="canShip"
                color="primary"
                size="small"
                :loading="saving"
                @click="createDelivery"
              >
                Create DO
              </VBtn>
              <VBtn
                v-if="canQuickFulfill"
                variant="tonal"
                color="success"
                size="small"
                @click="openQuickFulfill"
              >
                Quick Fulfill & Invoice
              </VBtn>
              <VBtn
                v-if="selected.status !== 'fulfilled'"
                variant="text"
                color="error"
                size="small"
                :loading="saving"
                @click="doCancel"
              >
                Cancel
              </VBtn>
            </template>
          </VCardTitle>
          <VCardText>
            <VRow dense>
              <VCol
                cols="12"
                md="6"
              >
                <VSelect
                  v-model="editForm.customer_id"
                  :items="customerOptions"
                  label="Customer"
                  density="comfortable"
                  :readonly="!isDraft && !!selected"
                />
              </VCol>
              <VCol
                cols="12"
                md="6"
              >
                <VSelect
                  v-model="editForm.location_id"
                  :items="locationOptions"
                  label="Location"
                  density="comfortable"
                  :readonly="!isDraft && !!selected"
                  @update:model-value="refreshStocks"
                />
              </VCol>
              <VCol
                cols="12"
                md="6"
              >
                <VTextField
                  v-model="editForm.order_date"
                  label="Order date"
                  type="date"
                  density="comfortable"
                  :readonly="!isDraft && !!selected"
                />
              </VCol>
              <VCol
                cols="12"
                md="6"
              >
                <VTextField
                  v-model="editForm.notes"
                  label="Notes"
                  density="comfortable"
                  :readonly="!isDraft && !!selected"
                />
              </VCol>
            </VRow>

            <VTable density="compact">
              <thead>
                <tr>
                  <th>Item</th>
                  <th
                    class="text-end"
                    style="width: 90px"
                  >
                    Qty
                  </th>
                  <th
                    class="text-end"
                    style="width: 110px"
                  >
                    Unit price
                  </th>
                  <th
                    class="text-end"
                    style="width: 110px"
                  >
                    Discount
                  </th>
                  <th class="text-end">
                    Amount
                  </th>
                  <th
                    v-if="isDraft"
                    style="width: 48px"
                  />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(line, index) in editLines"
                  :key="index"
                >
                  <td>
                    <VAutocomplete
                      v-if="isDraft"
                      v-model="line.item_id"
                      :items="itemOptions"
                      density="compact"
                      hide-details
                      variant="outlined"
                      @update:model-value="onItemPicked(line)"
                    />
                    <template v-else>
                      {{ itemById.get(line.item_id || '')?.sku_code }} ·
                      {{ itemById.get(line.item_id || '')?.name_zh }}
                    </template>
                  </td>
                  <td class="text-end">
                    <VTextField
                      v-if="isDraft"
                      v-model.number="line.qty"
                      type="number"
                      min="1"
                      density="compact"
                      hide-details
                      variant="outlined"
                    />
                    <template v-else>
                      {{ line.qty }}
                    </template>
                  </td>
                  <td class="text-end">
                    <VTextField
                      v-if="isDraft"
                      v-model.number="line.unit_price"
                      type="number"
                      min="0"
                      step="0.01"
                      density="compact"
                      hide-details
                      variant="outlined"
                    />
                    <template v-else>
                      {{ fmtMoney(line.unit_price) }}
                    </template>
                  </td>
                  <td class="text-end">
                    <VTextField
                      v-if="isDraft"
                      v-model.number="line.discount_amount"
                      type="number"
                      min="0"
                      step="0.01"
                      density="compact"
                      hide-details
                      variant="outlined"
                    />
                    <template v-else>
                      {{ fmtMoney(line.discount_amount) }}
                    </template>
                  </td>
                  <td class="text-end font-weight-medium">
                    {{ fmtMoney(Math.max(0, (line.qty || 0) * (line.unit_price || 0) - (line.discount_amount || 0))) }}
                  </td>
                  <td v-if="isDraft">
                    <VBtn
                      icon="ri-close-line"
                      variant="text"
                      size="x-small"
                      color="error"
                      @click="removeLine(index)"
                    />
                  </td>
                </tr>
              </tbody>
            </VTable>

            <div
              v-if="isDraft"
              class="mt-2"
            >
              <VBtn
                variant="text"
                size="small"
                color="primary"
                prepend-icon="ri-add-line"
                @click="addLine"
              >
                Add line
              </VBtn>
            </div>

            <VDivider class="my-3" />
            <div class="d-flex justify-end gap-8">
              <div>
                <div class="text-caption text-medium-emphasis">
                  Subtotal
                </div>
                <div class="text-end">
                  {{ fmtMoney(linesSubtotal) }}
                </div>
              </div>
              <div style="width: 140px">
                <VTextField
                  v-model.number="editForm.discount_amount"
                  label="Header discount"
                  type="number"
                  min="0"
                  step="0.01"
                  density="compact"
                  hide-details
                  variant="outlined"
                  :readonly="!isDraft && !!selected"
                />
              </div>
              <div>
                <div class="text-caption text-medium-emphasis">
                  Total
                </div>
                <div class="text-end text-h6">
                  {{ fmtMoney(editTotal) }}
                </div>
              </div>
            </div>
          </VCardText>
        </VCard>
        <VCard v-else>
          <VCardText class="text-center text-medium-emphasis py-12">
            Select a sales order or create a new one.
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <VDialog
      v-model="quickFulfillOpen"
      max-width="440"
    >
      <VCard>
        <VCardTitle>Quick Fulfill & Invoice</VCardTitle>
        <VCardText>
          <div class="text-body-2 mb-3">
            Confirms the order (if draft), ships all remaining quantities, and issues an invoice.
          </div>
          <VCheckbox
            v-model="qfWithPay"
            label="Record a payment receipt"
            density="compact"
            hide-details
          />
          <template v-if="qfWithPay">
            <VTextField
              v-model.number="qfAmount"
              type="number"
              label="Amount"
              class="mt-3"
            />
            <VSelect
              v-model="qfMethod"
              :items="RECEIPT_PAID_BY_OPTIONS"
              label="Paid by"
              class="mt-3"
            />
            <VTextField
              v-model="qfReference"
              label="Reference no."
              class="mt-3"
            />
          </template>
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="quickFulfillOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :loading="saving"
            @click="doQuickFulfill"
          >
            Fulfill
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <ProformaPrintDialog
      v-model="proformaOpen"
      :doc="proformaDoc"
    />
  </VContainer>
</template>
