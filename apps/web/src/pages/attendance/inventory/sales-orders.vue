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
import AttendanceConfirmDialog from '@/components/attendance/AttendanceConfirmDialog.vue'
import AttendancePaginationBar from '@/components/attendance/AttendancePaginationBar.vue'
import InventoryDocChain, { type DocChainStep } from '@/components/attendance/inventory/InventoryDocChain.vue'
import { type InventoryDocAction, type InventoryDocMoreItem } from '@/components/attendance/inventory/InventoryDocActions.vue'
import InventoryStatusChip from '@/components/attendance/inventory/InventoryStatusChip.vue'
import ProformaPrintDialog from '@/components/attendance/inventory/ProformaPrintDialog.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { useConfirmAction } from '@/composables/useConfirmAction'
import { useDirtyGuard } from '@/composables/useDirtyGuard'
import { useLatestRequest } from '@/composables/useLatestRequest'

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

const route = useRoute()
const router = useRouter()
const listReq = useLatestRequest()
const confirm = useConfirmAction()
const dirty = useDirtyGuard('You have unsaved edits on this sales order. Discard them?')

const customerFilter = ref<string | null>(null)
const locationFilter = ref<string | null>(null)

const statusFilter = ref<SalesOrderStatus | null>(
  (route.query.status as SalesOrderStatus | undefined) ?? null,
)

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
const isEditable = computed(() => !selected.value || selected.value.status === 'draft')

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

let suppressDirty = false
watch([editForm, editLines], () => {
  if (!suppressDirty)
    dirty.dirty.value = true
}, { deep: true })

const isEditorDirty = computed(() => dirty.dirty.value)

const showErrors = ref(false)

interface LineErr { field: 'item' | 'qty' | 'price' | 'discount'; msg: string }

function lineError(line: EditLine): LineErr | null {
  if (!line.item_id)
    return { field: 'item', msg: '請選擇品項' }
  if (!Number.isInteger(line.qty) || line.qty <= 0)
    return { field: 'qty', msg: '數量要是大於 0 的整數' }
  if (line.unit_price == null || line.unit_price < 0)
    return { field: 'price', msg: '單價不能是負數' }
  if (line.discount_amount < 0 || line.discount_amount > line.qty * line.unit_price)
    return { field: 'discount', msg: '折扣要在 0 到該行小計之間' }

  return null
}

const lineErrors = computed(() => editLines.value.map(lineError))

const formInvalid = computed(() =>
  isEditable.value
  && (!editForm.customer_id
    || !editForm.location_id
    || !editForm.order_date
    || editLines.value.length === 0
    || lineErrors.value.some(Boolean)
    || (editForm.discount_amount ?? 0) < 0
    || (editForm.discount_amount ?? 0) > linesSubtotal.value),
)

const chainSteps = computed<DocChainStep[]>(() => {
  const so = selected.value
  if (!so)
    return []

  const steps: DocChainStep[] = [
    { label: `SO ${so.so_no}`, state: so.status === 'cancelled' ? 'void' : 'current', hint: so.status },
    {
      label: 'Delivery',
      state: so.status === 'fulfilled' ? 'done' : 'todo',
      to: '/attendance/inventory/delivery-orders',
    },
    { label: 'Invoice', state: 'todo', to: '/attendance/inventory/invoices' },
    { label: 'Receipt', state: 'todo', to: '/attendance/inventory/receipts' },
  ]

  return steps
})

const docPrimary = computed<InventoryDocAction | null>(() => {
  if (isEditable.value && (!selected.value || dirty.dirty.value))
    return { label: 'Save', tooltip: '儲存這張銷售單的內容', onClick: saveOrder }
  if (selected.value?.status === 'draft')
    return { label: 'Confirm', tooltip: '確認訂單並保留庫存', onClick: askConfirm }
  if (selected.value && canShip.value)
    return { label: 'Create Delivery Order', tooltip: '建立出貨單,出貨確認後才扣庫存', onClick: createDelivery }

  return null
})

const docSecondary = computed<InventoryDocAction | null>(() => {
  if (dirty.dirty.value)
    return null
  if ((isDraft.value && selected.value) || canQuickFulfill.value)
    return { label: 'Quick Fulfill & Invoice', tooltip: '一次完成出貨和開票', onClick: openQuickFulfill }

  return null
})

const docMore = computed<InventoryDocMoreItem[]>(() => {
  const menu: InventoryDocMoreItem[] = []

  if (selected.value && !isDraft.value && selected.value.status !== 'cancelled')
    menu.push({ label: 'Proforma', sub: '列印形式發票', icon: 'ri-printer-line', onClick: openProforma })
  if (isDraft.value && selected.value)
    menu.push({ label: 'Delete draft', sub: '刪除草稿,不能復原', icon: 'ri-delete-bin-line', danger: true, onClick: askDelete })
  if (selected.value && !isDraft.value && selected.value.status !== 'fulfilled' && selected.value.status !== 'cancelled')
    menu.push({ label: 'Cancel order', sub: '取消銷售單,釋放保留的庫存', icon: 'ri-close-circle-line', danger: true, onClick: askCancel })

  return menu
})

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

    if (route.query.action === 'new') {
      newOrder()

      const rest = { ...route.query }

      delete rest.action
      router.replace({ query: rest })
    }
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

  const token = listReq.next()
  try {
    const result = await listSalesOrders({
      customer_id: customerFilter.value ?? undefined,
      location_id: locationFilter.value ?? undefined,
      status: statusFilter.value ?? undefined,
      page: page.value,
      page_size: pageSize.value,
    })

    if (!listReq.isLatest(token))
      return
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

const detailAnchor = ref<{ $el: HTMLElement } | null>(null)
const reducedMotion = usePreferredReducedMotion()

async function scrollToDetail() {
  await nextTick()
  detailAnchor.value?.$el.scrollIntoView({
    behavior: reducedMotion.value === 'reduce' ? 'auto' : 'smooth',
    block: 'start',
  })
}

async function selectOrder(so: SalesOrder) {
  if (selected.value?.id !== so.id && isEditorDirty.value && !(await dirty.confirmDiscard()))
    return
  detailLoading.value = true
  try {
    const detail = await getSalesOrder(so.id)

    selected.value = detail
    resetEditor(detail)
    await refreshStocks()
    await scrollToDetail()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to load sales order.')
  }
  finally {
    detailLoading.value = false
  }
}

function resetEditor(so: SalesOrder | null) {
  showErrors.value = false
  if (!so)
    return
  suppressDirty = true
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
  dirty.markClean()
  nextTick(() => {
    suppressDirty = false
  })
}

async function newOrder() {
  if (!(await dirty.confirmDiscard()))
    return
  suppressDirty = true
  showErrors.value = false
  selected.value = null
  editForm.customer_id = null
  editForm.location_id = null
  editForm.order_date = new Date().toISOString().slice(0, 10)
  editForm.discount_amount = 0
  editForm.notes = ''
  editLines.value = []
  addLine()
  dirty.markClean()
  nextTick(() => {
    suppressDirty = false
  })
  await scrollToDetail()
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
  if (formInvalid.value) {
    showErrors.value = true
    actionError.value = '請檢查紅色標示的欄位，修正後再儲存。'
    await nextTick()
    document.querySelector<HTMLElement>('.v-input--error input, .v-input--error textarea')?.focus()

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
      customer_id: editForm.customer_id ?? '',
      location_id: editForm.location_id ?? '',
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

function askConfirm() {
  if (!selected.value)
    return
  confirm.ask(
    `Confirm ${selected.value.so_no}?`,
    '確認後會為每個品項保留庫存，請確定訂單內容正確。',
    { label: 'Confirm', tone: 'info', details: ['每個品項的可用庫存會被保留', '之後可建立出貨單出貨'] },
    performConfirm,
  )
}

async function performConfirm() {
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

function askCancel() {
  if (!selected.value)
    return
  confirm.ask(
    `Cancel ${selected.value.so_no}?`,
    '取消後會釋放所有保留的庫存，此操作不能復原。',
    { label: 'Cancel order', details: ['已保留的庫存會全部釋放', '不能復原'] },
    performCancel,
  )
}

async function performCancel() {
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

function askDelete() {
  if (!selected.value)
    return
  confirm.ask(
    `Delete draft ${selected.value.so_no}?`,
    '草稿銷售單和所有品項會永久刪除。',
    { label: 'Delete', details: ['不能復原'] },
    performDelete,
  )
}

async function performDelete() {
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
        <div class="text-body-2 text-medium-emphasis">
          這一頁管理銷售單：記錄客戶要買什麼，之後出貨和開票。
        </div>
      </VCol>
      <VCol cols="auto">
        <VTooltip
          text="重新整理"
          location="bottom"
        >
          <template #activator="{ props }">
            <VBtn
              v-bind="props"
              icon="ri-refresh-line"
              variant="tonal"
              color="primary"
              :loading="loading"
              aria-label="重新整理"
              @click="loadOrders"
            />
          </template>
        </VTooltip>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          class="ms-2"
          @click="newOrder"
        >
          New Sales Order
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
      <VCol cols="12">
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
          <VList
            density="compact"
            style="max-height: 360px; overflow-y: auto"
          >
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
                No sales orders yet — click "New order" to start a sale.
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
        ref="detailAnchor"
        cols="12"
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
            <InventoryDocActions
              :primary="docPrimary"
              :secondary="docSecondary"
              :more="docMore"
              :loading="saving"
            />
          </VCardTitle>
          <VCardText>
            <InventoryDocChain
              v-if="selected"
              :steps="chainSteps"
              class="mb-4"
            />
            <VRow dense>
              <VCol
                cols="12"
                md="6"
              >
                <VSelect
                  v-model="editForm.customer_id"
                  :items="customerOptions"
                  label="Customer *"
                  density="comfortable"
                  :readonly="!isEditable"
                  :error="showErrors && !editForm.customer_id"
                  @blur="showErrors = true"
                />
              </VCol>
              <VCol
                cols="12"
                md="6"
              >
                <VSelect
                  v-model="editForm.location_id"
                  :items="locationOptions"
                  label="Location *"
                  density="comfortable"
                  :readonly="!isEditable"
                  :error="showErrors && !editForm.location_id"
                  @update:model-value="refreshStocks"
                  @blur="showErrors = true"
                />
              </VCol>
              <VCol
                cols="12"
                md="6"
              >
                <VTextField
                  v-model="editForm.order_date"
                  label="Order date *"
                  type="date"
                  density="comfortable"
                  :readonly="!isEditable"
                  :error="showErrors && !editForm.order_date"
                  @blur="showErrors = true"
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
                  :readonly="!isEditable"
                />
              </VCol>
            </VRow>

            <VTable
              density="compact"
              class="inv-line-table"
            >
              <thead>
                <tr>
                  <th class="inv-col-item">
                    Item
                  </th>
                  <th class="inv-col-qty text-end">
                    Qty
                  </th>
                  <th class="inv-col-price text-end">
                    Unit price
                  </th>
                  <th class="inv-col-discount text-end">
                    Discount
                  </th>
                  <th class="inv-col-amount">
                    Amount
                  </th>
                  <th
                    v-if="isEditable"
                    class="inv-col-remove"
                  />
                </tr>
              </thead>
              <tbody>
                <template
                  v-for="(line, index) in editLines"
                  :key="index"
                >
                  <tr>
                    <td>
                      <VAutocomplete
                        v-if="isEditable"
                        v-model="line.item_id"
                        :items="itemOptions"
                        density="compact"
                        hide-details
                        variant="outlined"
                        placeholder="Search item…"
                        :error="showErrors && lineErrors[index]?.field === 'item'"
                        @update:model-value="onItemPicked(line)"
                        @blur="showErrors = true"
                      />
                      <template v-else>
                        {{ itemById.get(line.item_id || '')?.sku_code }} ·
                        {{ itemById.get(line.item_id || '')?.name_zh }}
                      </template>
                    </td>
                    <td class="text-end">
                      <VTextField
                        v-if="isEditable"
                        v-model.number="line.qty"
                        type="number"
                        min="1"
                        step="1"
                        density="compact"
                        hide-details
                        variant="outlined"
                        class="inv-num-input"
                        :error="showErrors && lineErrors[index]?.field === 'qty'"
                        @blur="showErrors = true"
                      />
                      <template v-else>
                        {{ line.qty }}
                      </template>
                    </td>
                    <td class="text-end">
                      <VTextField
                        v-if="isEditable"
                        v-model.number="line.unit_price"
                        type="number"
                        min="0"
                        step="0.01"
                        density="compact"
                        hide-details
                        variant="outlined"
                        class="inv-num-input"
                        :error="showErrors && lineErrors[index]?.field === 'price'"
                        @blur="showErrors = true"
                      />
                      <template v-else>
                        {{ fmtMoney(line.unit_price) }}
                      </template>
                    </td>
                    <td class="text-end">
                      <VTextField
                        v-if="isEditable"
                        v-model.number="line.discount_amount"
                        type="number"
                        min="0"
                        step="0.01"
                        density="compact"
                        hide-details
                        variant="outlined"
                        class="inv-num-input"
                        :error="showErrors && lineErrors[index]?.field === 'discount'"
                        @blur="showErrors = true"
                      />
                      <template v-else>
                        {{ fmtMoney(line.discount_amount) }}
                      </template>
                    </td>
                    <td class="inv-col-amount font-weight-medium">
                      {{ fmtMoney(Math.max(0, (line.qty || 0) * (line.unit_price || 0) - (line.discount_amount || 0))) }}
                    </td>
                    <td
                      v-if="isEditable"
                      class="inv-col-remove"
                    >
                      <VBtn
                        icon="ri-close-line"
                        variant="text"
                        size="x-small"
                        color="error"
                        aria-label="Remove line"
                        @click="removeLine(index)"
                      />
                    </td>
                  </tr>
                  <tr
                    v-if="showErrors && lineErrors[index]"
                    class="inv-line-error"
                  >
                    <td
                      :colspan="isEditable ? 6 : 5"
                      class="text-caption text-error"
                    >
                      {{ lineErrors[index]!.msg }}
                    </td>
                  </tr>
                </template>
              </tbody>
            </VTable>

            <div
              v-if="isEditable"
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
                  :readonly="!isEditable"
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
            從上面的列表選一張銷售單，或按下面的按鈕建立新的。
            <div class="mt-3">
              <VBtn
                color="primary"
                prepend-icon="ri-add-line"
                @click="newOrder"
              >
                New Sales Order
              </VBtn>
            </div>
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

    <AttendanceConfirmDialog
      v-model="confirm.open.value"
      :title="confirm.title.value"
      :confirm-label="confirm.label.value"
      :confirm-color="confirm.color.value"
      :tone="confirm.tone.value"
      :details="confirm.details.value"
      :loading="confirm.loading.value"
      @confirm="confirm.run"
    >
      {{ confirm.message.value }}
    </AttendanceConfirmDialog>
  </VContainer>
</template>
