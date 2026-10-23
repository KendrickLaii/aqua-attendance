<script setup lang="ts">
import {
  type InventoryInvoice,
  type InventoryInvoicePrintDoc,
  type InventoryInvoiceStatus,
  type InventoryPaymentStatus,
  createInvoice,
  deleteInvoice,
  getInvoice,
  getInvoicePrint,
  issueInvoice,
  listInvoices,
  voidInvoice,
} from '@/api/attendance/inventoryInvoicing'
import {
  type InventoryCustomer,
  type SalesOrder,
  getSalesOrder,
  listCustomers,
  listSalesOrders,
} from '@/api/attendance/inventorySales'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import AttendanceConfirmDialog from '@/components/attendance/AttendanceConfirmDialog.vue'
import AttendancePaginationBar from '@/components/attendance/AttendancePaginationBar.vue'
import InventoryCreateDeliveryDialog from '@/components/attendance/inventory/InventoryCreateDeliveryDialog.vue'
import InventoryDocChain, { type DocChainStep } from '@/components/attendance/inventory/InventoryDocChain.vue'
import InventoryInvoicePrintDialog from '@/components/attendance/inventory/InventoryInvoicePrintDialog.vue'
import InventoryRecordPaymentDialog from '@/components/attendance/inventory/InventoryRecordPaymentDialog.vue'
import { type InventoryDocAction, type InventoryDocMoreItem } from '@/components/attendance/inventory/InventoryDocActions.vue'
import InventoryStatusChip from '@/components/attendance/inventory/InventoryStatusChip.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { useConfirmAction } from '@/composables/useConfirmAction'
import { useDirtyGuard } from '@/composables/useDirtyGuard'
import { useLatestRequest } from '@/composables/useLatestRequest'

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

const customers = ref<InventoryCustomer[]>([])
const locations = ref<LocationItem[]>([])

const invoices = ref<InventoryInvoice[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const route = useRoute()
const router = useRouter()
const listReq = useLatestRequest()
const confirm = useConfirmAction()
const dirty = useDirtyGuard('Discard the new invoice form?')

const statusFilter = ref<InventoryInvoiceStatus | null>(null)

const paymentFilter = ref<InventoryPaymentStatus | null>(
  (route.query.payment_status as InventoryPaymentStatus | undefined) ?? null,
)

const customerFilter = ref<string | null>(null)
const locationFilter = ref<string | null>(null)
const search = ref('')

const selected = ref<InventoryInvoice | null>(null)

const statusOptions = [
  { value: 'draft' as const, title: 'Draft' },
  { value: 'issued' as const, title: 'Issued' },
  { value: 'void' as const, title: 'Void' },
]

const paymentStatusOptions = [
  { value: 'unpaid' as const, title: 'Unpaid' },
  { value: 'partial' as const, title: 'Partial' },
  { value: 'paid' as const, title: 'Paid' },
  { value: 'void' as const, title: 'Void' },
]

const printOpen = ref(false)
const printDoc = ref<InventoryInvoicePrintDoc | null>(null)

// record payment dialog
const payOpen = ref(false)

// create delivery order dialog (issued invoice → record physical delivery)
const doOpen = ref(false)

// create invoice dialog (from a confirmed/partial SO)
const createOpen = ref(false)
const createSoId = ref<string | null>(null)
const createSo = ref<SalesOrder | null>(null)
const createNotes = ref('')
const createLines = ref<{ so_line_id: string; label: string; remaining: number; qty: number }[]>([])
const createDiscount = ref<number | null>(null)
const soOptions = ref<SalesOrder[]>([])
const soLoading = ref(false)
let soSearchTimer: ReturnType<typeof setTimeout> | undefined

watch([createSoId, createNotes, createLines, createDiscount], () => {
  if (createOpen.value && (createSoId.value || createNotes.value))
    dirty.dirty.value = true
})

watch(createSoId, async id => {
  createSo.value = null
  createLines.value = []
  if (!id)
    return
  soLoading.value = true
  try {
    const so = await getSalesOrder(id)

    createSo.value = so
    createLines.value = so.lines
      .map(l => ({
        so_line_id: l.id,
        label: [l.sku_code, l.name_zh].filter(Boolean).join(' · ') || l.item_id,
        remaining: Math.max(0, l.qty - l.invoiced_qty),
        qty: Math.max(0, l.qty - l.invoiced_qty),
      }))
      .filter(l => l.remaining > 0)
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Operation failed.')
  }
  finally {
    soLoading.value = false
  }
})

const createValid = computed(() =>
  !!createSo.value
  && createLines.value.length > 0
  && createLines.value.some(l => l.qty > 0)
  && createLines.value.every(l => Number.isInteger(l.qty) && l.qty >= 0 && l.qty <= l.remaining),
)

const headers = [
  { title: 'Invoice No', key: 'invoice_no' },
  { title: 'Customer', key: 'customer_name' },
  { title: 'SO', key: 'so_no' },
  { title: 'Date', key: 'issue_date' },
  { title: 'Total', key: 'total', align: 'end' as const },
  { title: 'Balance', key: 'balance', align: 'end' as const },
  { title: 'Status', key: 'status' },
  { title: 'Payment', key: 'payment_status' },
]

const chainSteps = computed<DocChainStep[]>(() => {
  const inv = selected.value
  if (!inv)
    return []

  return [
    { label: `SO ${inv.so_no}`, state: 'done', to: '/attendance/inventory/sales-orders' },
    { label: inv.invoice_no || 'Invoice (draft)', state: inv.status === 'void' ? 'void' : 'current', hint: inv.status },
    {
      label: 'Delivery',
      state: inv.delivery_orders.length ? 'done' : 'todo',
      to: '/attendance/inventory/delivery-orders',
    },
    { label: 'Receipt', state: inv.payment_status === 'paid' ? 'done' : 'todo', to: '/attendance/inventory/receipts' },
  ]
})

const toDeliverQty = computed(() =>
  (selected.value?.lines ?? []).reduce(
    (s, l) => s + Math.max(0, l.qty - l.credited_qty - l.delivered_qty), 0,
  ),
)

const docPrimary = computed<InventoryDocAction | null>(() => {
  const inv = selected.value
  if (!inv)
    return null
  if (inv.status === 'draft')
    return { label: 'Issue', tooltip: '開立發票,庫存會正式扣減', onClick: askIssue }
  if (inv.status === 'issued' && inv.balance > 0)
    return { label: 'Record Payment', tooltip: '記錄客戶付款，產生一張收據', onClick: openPay }

  return null
})

const docSecondary = computed<InventoryDocAction | null>(() => {
  const inv = selected.value
  if (inv?.status === 'issued' && toDeliverQty.value > 0)
    return { label: 'Create Delivery Order', tooltip: '建立出貨單記錄送貨,不影響庫存', onClick: () => { doOpen.value = true } }

  return null
})

const docMore = computed<InventoryDocMoreItem[]>(() => {
  const inv = selected.value
  const items: InventoryDocMoreItem[] = []

  if (!inv)
    return items
  if (inv.invoice_no)
    items.push({ label: 'Print', sub: '列印發票', icon: 'ri-printer-line', onClick: onPrint })
  if (inv.status === 'issued')
    items.push({ label: 'Create Credit Note', sub: '為這張發票開折讓單', icon: 'ri-refund-2-line', onClick: () => router.push({ path: '/attendance/inventory/credit-notes', query: { invoice_id: inv.id } }) })
  if (inv.status === 'draft')
    items.push({ label: 'Delete draft', sub: '刪除草稿,不能復原', icon: 'ri-delete-bin-line', danger: true, onClick: askDelete })
  if (inv.status === 'issued')
    items.push({ label: 'Void invoice', sub: '作廢發票,需先作廢相關收據/折讓單/出貨單', icon: 'ri-close-circle-line', danger: true, onClick: askVoid })

  return items
})

async function load() {
  loading.value = true
  loadError.value = ''

  const token = listReq.next()
  try {
    const res = await listInvoices({
      customer_id: customerFilter.value || undefined,
      location_id: locationFilter.value || undefined,
      status: statusFilter.value || undefined,
      payment_status: paymentFilter.value || undefined,
      search: search.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })

    if (!listReq.isLatest(token))
      return
    invoices.value = res.items
    total.value = res.total
  }
  catch (e) {
    if (!listReq.isLatest(token))
      return
    loadError.value = formatApiError(e, 'Operation failed.')
  }
  finally {
    if (listReq.isLatest(token))
      loading.value = false
  }
}

function onRowClick(_e: Event, row: { item: InventoryInvoice }) {
  selected.value = row.item
}

function openCreate(soId?: string) {
  createSoId.value = soId ?? null
  createNotes.value = ''
  createDiscount.value = null
  dirty.markClean()
  createOpen.value = true
  loadSos('')
}

async function loadSos(term: string) {
  soLoading.value = true
  try {
    const [confirmed, partial] = await Promise.all([
      listSalesOrders({ status: 'confirmed', page_size: 50 }),
      listSalesOrders({ status: 'partial', page_size: 50 }),
    ])

    const needle = (term || '').toLowerCase()

    soOptions.value = [...confirmed.items, ...partial.items]
      .filter(so => !needle || so.so_no.toLowerCase().includes(needle) || (so.buyer_name || '').toLowerCase().includes(needle))
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Operation failed.')
  }
  finally {
    soLoading.value = false
  }
}

function onSoSearch(term: string) {
  clearTimeout(soSearchTimer)
  soSearchTimer = setTimeout(() => loadSos(term), 300)
}

async function closeCreate() {
  if (await dirty.confirmDiscard())
    createOpen.value = false
}

async function submitCreate() {
  if (!createValid.value || !createSo.value)
    return
  saving.value = true
  actionError.value = ''
  try {
    const inv = await createInvoice({
      so_id: createSo.value.id,
      notes: createNotes.value || null,
      discount_amount: createDiscount.value ?? undefined,
      lines: createLines.value
        .filter(l => l.qty > 0)
        .map(l => ({ so_line_id: l.so_line_id, qty: l.qty })),
    })

    dirty.markClean()
    createOpen.value = false
    actionSuccess.value = `Invoice draft created for ${inv.so_no}`
    await load()
    selected.value = inv
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Operation failed.')
  }
  finally {
    saving.value = false
  }
}

function askIssue() {
  if (!selected.value)
    return
  confirm.ask(
    `Issue ${selected.value.invoice_no || 'draft invoice'}?`,
    `開立後會編配發票號碼、庫存正式扣減，向客戶收取 ${fmtMoney(selected.value.total)}。`,
    { label: 'Issue', tone: 'info', details: ['庫存會正式扣減', '開始計算應收款項', '只能透過作廢取消'] },
    performIssue,
  )
}

async function performIssue() {
  if (!selected.value)
    return
  saving.value = true
  actionError.value = ''
  try {
    selected.value = await issueInvoice(selected.value.id)
    actionSuccess.value = `Invoice ${selected.value.invoice_no} issued`
    await load()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Operation failed.')
  }
  finally {
    saving.value = false
  }
}

function askVoid() {
  if (!selected.value)
    return
  confirm.ask(
    `Void ${selected.value.invoice_no}?`,
    '作廢會取消這張發票，扣減過的庫存會加回去。',
    { label: 'Void', details: ['庫存會加回去並重新保留給銷售單', '必須先作廢相關收據、折讓單和出貨單', '不能復原'] },
    performVoid,
  )
}

async function performVoid() {
  if (!selected.value)
    return
  saving.value = true
  actionError.value = ''
  try {
    selected.value = await voidInvoice(selected.value.id)
    actionSuccess.value = 'Invoice voided'
    await load()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Operation failed.')
  }
  finally {
    saving.value = false
  }
}

function askDelete() {
  if (!selected.value)
    return
  confirm.ask(
    'Delete draft invoice?',
    '草稿發票會永久刪除。',
    { label: 'Delete', details: ['不能復原'] },
    performDelete,
  )
}

async function performDelete() {
  if (!selected.value)
    return
  saving.value = true
  actionError.value = ''
  try {
    await deleteInvoice(selected.value.id)
    actionSuccess.value = 'Draft invoice deleted'
    selected.value = null
    await load()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Operation failed.')
  }
  finally {
    saving.value = false
  }
}

function openPay() {
  if (!selected.value)
    return
  payOpen.value = true
}

async function onPaymentSaved() {
  actionSuccess.value = 'Receipt posted'
  if (selected.value)
    selected.value = await getInvoice(selected.value.id)
  await load()
}

async function onDeliveryCreated() {
  actionSuccess.value = 'Delivery order created'
  if (selected.value)
    selected.value = await getInvoice(selected.value.id)
  await load()
}

async function onPrint() {
  if (!selected.value)
    return
  try {
    printDoc.value = await getInvoicePrint(selected.value.id)
    printOpen.value = true
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Operation failed.')
  }
}

function fmtMoney(value: number | null | undefined): string {
  return (value ?? 0).toFixed(2)
}

watch([statusFilter, paymentFilter, customerFilter, locationFilter], () => {
  page.value = 1
  load()
})

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  try {
    const [custs, locs] = await Promise.all([
      listCustomers({ is_active: true, page_size: 200 }),
      listLocations(),
    ])

    customers.value = custs.items
    locations.value = locs
  }
  catch {
    // filters still work without dropdown data
  }
  await load()

  // deep links: ?doc=<invoice_id> opens the invoice, ?so_id=<id> opens New Invoice prefilled
  if (route.query.doc) {
    try {
      selected.value = await getInvoice(String(route.query.doc))
    }
    catch { /* ignore */ }
  }
  else if (route.query.so_id) {
    openCreate(String(route.query.so_id))
  }
})
</script>

<template>
  <div>
    <VCard>
      <VCardTitle class="d-flex align-center flex-wrap gap-2">
        <span>Sales Invoices 銷售發票</span>
        <VSpacer />
        <VTextField
          v-model="search"
          density="compact"
          label="Search"
          prepend-inner-icon="ri-search-line"
          hide-details
          style="max-width: 200px"
          @update:model-value="page = 1; load()"
        />
        <VSelect
          v-model="statusFilter"
          :items="statusOptions"
          density="compact"
          label="Status"
          clearable
          hide-details
          style="max-width: 140px"
        />
        <VSelect
          v-model="paymentFilter"
          :items="paymentStatusOptions"
          density="compact"
          label="Payment"
          clearable
          hide-details
          style="max-width: 140px"
        />
        <VSelect
          v-model="customerFilter"
          :items="customers.map(c => ({ value: c.id, title: c.name_zh }))"
          density="compact"
          label="Customer"
          clearable
          hide-details
          style="max-width: 180px"
        />
        <VSelect
          v-model="locationFilter"
          :items="locations.map(l => ({ value: l.id, title: l.name_en || l.name_zh || l.code }))"
          density="compact"
          label="Location"
          clearable
          hide-details
          style="max-width: 160px"
        />
        <VTooltip
          text="重新整理"
          location="bottom"
        >
          <template #activator="{ props }">
            <VBtn
              v-bind="props"
              icon="ri-refresh-line"
              variant="tonal"
              :loading="loading"
              aria-label="重新整理"
              @click="load"
            />
          </template>
        </VTooltip>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          @click="openCreate"
        >
          New Invoice
        </VBtn>
      </VCardTitle>
      <VCardSubtitle>
        這一頁管理銷售發票：向客戶請款用的單據。由已確認的銷售單建立，開立時扣庫存。
      </VCardSubtitle>
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
        <VAlert
          v-if="actionSuccess"
          type="success"
          variant="tonal"
          class="mb-4"
        >
          {{ actionSuccess }}
        </VAlert>

        <VDataTable
          :headers="headers"
          :items="invoices"
          :loading="loading"
          density="compact"
          no-data-text="還沒有發票 — 按「New Invoice」從已確認的銷售單建立。"
          @click:row="onRowClick"
        >
          <template #item.invoice_no="{ item }">
            <span class="font-weight-medium">{{ item.invoice_no || '(draft)' }}</span>
          </template>
          <template #item.total="{ item }">
            <span class="tabular-nums">{{ fmtMoney(item.total) }}</span>
          </template>
          <template #item.balance="{ item }">
            <span class="tabular-nums">{{ fmtMoney(item.balance) }}</span>
          </template>
          <template #item.status="{ item }">
            <InventoryStatusChip :status="item.status" />
          </template>
          <template #item.payment_status="{ item }">
            <InventoryStatusChip :status="item.payment_status" />
          </template>
        </VDataTable>
        <AttendancePaginationBar
          v-model:page="page"
          v-model:page-size="pageSize"
          :total-pages="totalPages"
          :caption="`Page ${page} of ${totalPages} · ${total} record${total === 1 ? '' : 's'}`"
          @change="load"
        />
      </VCardText>
    </VCard>

    <VDialog
      :model-value="!!selected"
      max-width="760"
      @update:model-value="v => { if (!v) selected = null }"
    >
      <VCard v-if="selected">
        <VCardTitle class="d-flex align-center">
          <span>{{ selected.invoice_no || 'Draft invoice' }}</span>
          <VSpacer />
          <InventoryStatusChip :status="selected.status" />
          <InventoryStatusChip
            :status="selected.payment_status"
            class="ms-2"
          />
        </VCardTitle>
        <VCardText>
          <InventoryDocChain
            :steps="chainSteps"
            class="mb-3"
          />
          <div class="mb-2 text-body-2">
            <strong>Customer:</strong> {{ selected.buyer_name }} ·
            <strong>SO:</strong>
            <RouterLink to="/attendance/inventory/sales-orders">
              {{ selected.so_no }}
            </RouterLink>
          </div>
          <div class="overflow-x-auto">
            <VTable density="compact">
              <thead>
                <tr>
                  <th>Item</th>
                  <th class="text-end">
                    Qty
                  </th>
                  <th class="text-end">
                    Price
                  </th>
                  <th class="text-end">
                    Amount
                  </th>
                  <th class="text-end">
                    Delivered
                  </th>
                  <th class="text-end">
                    Credited
                  </th>
                  <th class="text-end">
                    To deliver
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="line in selected.lines"
                  :key="line.id"
                >
                  <td>{{ [line.sku_code, line.name_zh].filter(Boolean).join(' · ') }}</td>
                  <td class="text-end tabular-nums">
                    {{ line.qty }}
                  </td>
                  <td class="text-end tabular-nums">
                    {{ fmtMoney(line.unit_price) }}
                  </td>
                  <td class="text-end tabular-nums">
                    {{ fmtMoney(line.amount) }}
                  </td>
                  <td class="text-end tabular-nums">
                    {{ line.delivered_qty }}
                  </td>
                  <td class="text-end tabular-nums">
                    {{ line.credited_qty }}
                  </td>
                  <td class="text-end tabular-nums">
                    {{ Math.max(0, line.qty - line.credited_qty - line.delivered_qty) }}
                  </td>
                </tr>
              </tbody>
            </VTable>
          </div>
          <div class="d-flex justify-end mt-3 text-body-2">
            <div>
              <div>Subtotal: {{ fmtMoney(selected.subtotal) }}</div>
              <div>Discount: -{{ fmtMoney(selected.discount_amount) }}</div>
              <div class="font-weight-bold">
                Total: {{ fmtMoney(selected.total) }}
              </div>
              <div>Paid: {{ fmtMoney(selected.paid_total) }}</div>
              <div v-if="selected.credited_total">
                Credited: {{ fmtMoney(selected.credited_total) }}
              </div>
              <div class="font-weight-bold">
                Balance: {{ fmtMoney(selected.balance) }}
              </div>
            </div>
          </div>

          <VDivider class="my-4" />
          <div class="text-subtitle-2 mb-2">
            相關單據 Sub-documents
          </div>
          <div class="mb-3">
            <div class="d-flex align-center mb-1">
              <span class="text-body-2 font-weight-medium">出貨單 Delivery Orders</span>
              <VSpacer />
              <VBtn
                v-if="selected.status === 'issued' && toDeliverQty > 0"
                size="small"
                variant="tonal"
                color="primary"
                @click="doOpen = true"
              >
                Create Delivery Order
              </VBtn>
            </div>
            <div
              v-if="selected.delivery_orders.length"
              class="text-body-2"
            >
              <div
                v-for="d in selected.delivery_orders"
                :key="d.id"
              >
                <RouterLink to="/attendance/inventory/delivery-orders">
                  {{ d.do_no }}
                </RouterLink>
                · {{ d.delivery_date }} · {{ d.status }}
              </div>
            </div>
            <div
              v-else
              class="text-body-2 text-medium-emphasis"
            >
              還沒有出貨單。
            </div>
          </div>
          <div class="mb-3">
            <div class="text-body-2 font-weight-medium mb-1">
              收據 Receipts
            </div>
            <div
              v-if="selected.receipts.length"
              class="text-body-2"
            >
              <div
                v-for="r in selected.receipts"
                :key="r.id"
              >
                <RouterLink to="/attendance/inventory/receipts">
                  {{ r.receipt_no }}
                </RouterLink>
                · {{ fmtMoney(r.amount) }} · {{ r.paid_by }} · {{ r.status }}
              </div>
            </div>
            <div
              v-else
              class="text-body-2 text-medium-emphasis"
            >
              還沒有收據。
            </div>
          </div>
          <div>
            <div class="text-body-2 font-weight-medium mb-1">
              貸項單 Credit Notes
            </div>
            <div
              v-if="selected.credit_notes.length"
              class="text-body-2"
            >
              <div
                v-for="s in selected.credit_notes"
                :key="s.id"
              >
                <RouterLink to="/attendance/inventory/credit-notes">
                  {{ s.scn_no }}
                </RouterLink>
                · {{ fmtMoney(s.total) }} · {{ s.status }}
              </div>
            </div>
            <div
              v-else
              class="text-body-2 text-medium-emphasis"
            >
              沒有折讓單。
            </div>
          </div>
        </VCardText>
        <VCardActions>
          <VSpacer />
          <InventoryDocActions
            :primary="docPrimary"
            :secondary="docSecondary"
            :more="docMore"
            :loading="saving"
          />
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog
      v-model="createOpen"
      max-width="440"
      :persistent="dirty.dirty.value"
    >
      <VCard>
        <VCardTitle>New Invoice from Sales Order</VCardTitle>
        <VCardText>
          <VAutocomplete
            v-model="createSoId"
            :items="soOptions"
            item-value="id"
            :item-props="s => ({ title: `${s.so_no} · ${s.buyer_name ?? ''} · ${s.order_date}`, subtitle: s.status })"
            :loading="soLoading"
            no-filter
            label="銷售單 Sales Order *"
            hint="選一張已確認的銷售單，系統會帶出還沒開票的品項"
            persistent-hint
            @update:search="onSoSearch"
          />
          <VTable
            v-if="createLines.length"
            class="inv-line-table mt-3"
            density="compact"
          >
            <thead>
              <tr>
                <th>Item</th>
                <th class="text-end">
                  未開票 Remaining
                </th>
                <th class="col-qty text-end">
                  Qty
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="line in createLines"
                :key="line.so_line_id"
              >
                <td>{{ line.label }}</td>
                <td class="text-end tabular-nums">
                  {{ line.remaining }}
                </td>
                <td>
                  <VTextField
                    v-model.number="line.qty"
                    type="number"
                    min="0"
                    :max="line.remaining"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="inv-num-input"
                  />
                </td>
              </tr>
            </tbody>
          </VTable>
          <VAlert
            v-else-if="createSoId && !soLoading"
            type="info"
            variant="tonal"
            density="compact"
            class="mt-3"
          >
            這張銷售單已全數開票。
          </VAlert>
          <VTextField
            v-model.number="createDiscount"
            type="number"
            min="0"
            label="Discount (留空按比例)"
            class="mt-3"
          />
          <VTextField
            v-model="createNotes"
            label="Notes"
            class="mt-3"
          />
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="closeCreate"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :disabled="!createValid"
            :loading="saving"
            @click="submitCreate"
          >
            Create
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <InventoryRecordPaymentDialog
      v-model="payOpen"
      :invoice="selected
        ? { id: selected.id, invoice_no: selected.invoice_no ?? '', buyer_name: selected.buyer_name, balance: selected.balance }
        : null"
      @saved="onPaymentSaved"
    />

    <InventoryCreateDeliveryDialog
      v-model="doOpen"
      :invoice="selected"
      @created="onDeliveryCreated"
    />

    <InventoryInvoicePrintDialog
      v-model="printOpen"
      :doc="printDoc"
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
  </div>
</template>
