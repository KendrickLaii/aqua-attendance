<script setup lang="ts">
import {
  type InventorySupplier,
  type PurchaseOrder,
  type PurchaseOrderLinePayload,
  type PurchaseOrderStatus,
  cancelPurchaseOrder,
  createGoodsReceipt,
  createPurchaseOrder,
  deletePurchaseOrder,
  getPurchaseOrder,
  listPurchaseOrders,
  listSuppliers,
  orderPurchaseOrder,
  updatePurchaseOrder,
} from '@/api/attendance/inventoryPurchasing'
import {
  type InventoryItem,
  listInventoryItems,
} from '@/api/attendance/inventory'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import AttendanceConfirmDialog from '@/components/attendance/AttendanceConfirmDialog.vue'
import AttendancePaginationBar from '@/components/attendance/AttendancePaginationBar.vue'
import InventoryDocChain, { type DocChainStep } from '@/components/attendance/inventory/InventoryDocChain.vue'
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
const detailLoading = ref(false)
const saving = ref(false)
const loadError = ref('')
const actionError = ref('')
const actionSuccess = ref('')

useAutoClearAlerts(loadError)
useAutoClearAlerts(actionError)
useAutoClearAlerts(actionSuccess)

const suppliers = ref<InventorySupplier[]>([])
const locations = ref<LocationItem[]>([])
const items = ref<InventoryItem[]>([])

const orders = ref<PurchaseOrder[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const route = useRoute()
const router = useRouter()
const listReq = useLatestRequest()
const confirm = useConfirmAction()
const dirty = useDirtyGuard('You have unsaved edits on this purchase order. Discard them?')

const supplierFilter = ref<string | null>(null)
const locationFilter = ref<string | null>(null)

const statusFilter = ref<PurchaseOrderStatus | null>(
  (route.query.status as PurchaseOrderStatus | undefined) ?? null,
)

const selected = ref<PurchaseOrder | null>(null)

const statusOptions = [
  { value: 'draft' as const, title: 'Draft' },
  { value: 'ordered' as const, title: 'Ordered' },
  { value: 'partial' as const, title: 'Partial' },
  { value: 'received' as const, title: 'Received' },
  { value: 'cancelled' as const, title: 'Cancelled' },
]

const supplierOptions = computed(() =>
  suppliers.value.map(s => ({ value: s.id, title: `${s.code} · ${s.name_zh}` })),
)

const locationOptions = computed(() =>
  locations.value.map(l => ({
    value: l.id,
    title: [l.name_en, l.name_zh].filter(Boolean).join(' · '),
  })),
)

const itemOptions = computed(() =>
  items.value.map(i => ({
    value: i.id,
    title: [i.sku_code, i.name_zh].filter(Boolean).join(' · '),
  })),
)

const itemById = computed(() => new Map(items.value.map(i => [i.id, i])))

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const isDraft = computed(() => selected.value?.status === 'draft')
const isEditable = computed(() => !selected.value || selected.value.status === 'draft')

interface EditLine {
  item_id: string | null
  ordered_qty: number
  unit_cost: number
  discount_amount: number
}

const editLines = ref<EditLine[]>([])

const editForm = reactive({
  supplier_id: null as string | null,
  location_id: null as string | null,
  order_date: '',
  expected_date: '',
  discount_amount: 0,
  notes: '',
})

const linesSubtotal = computed(() =>
  editLines.value.reduce(
    (sum, l) => sum + Math.max(0, (l.ordered_qty || 0) * (l.unit_cost || 0) - (l.discount_amount || 0)),
    0,
  ),
)

const editTotal = computed(() => Math.max(0, linesSubtotal.value - (editForm.discount_amount || 0)))

let suppressDirty = false
watch([editForm, editLines], () => {
  if (!suppressDirty)
    dirty.dirty.value = true
}, { deep: true })

const showErrors = ref(false)

interface LineErr { field: 'item' | 'qty' | 'cost' | 'discount'; msg: string }

function lineError(line: EditLine): LineErr | null {
  if (!line.item_id)
    return { field: 'item', msg: '請選擇品項' }
  if (!Number.isInteger(line.ordered_qty) || line.ordered_qty <= 0)
    return { field: 'qty', msg: '數量要是大於 0 的整數' }
  if (line.unit_cost == null || line.unit_cost < 0)
    return { field: 'cost', msg: '單價不能是負數' }
  if (line.discount_amount < 0 || line.discount_amount > line.ordered_qty * line.unit_cost)
    return { field: 'discount', msg: '折扣要在 0 到該行小計之間' }

  return null
}

const lineErrors = computed(() => editLines.value.map(lineError))

const formInvalid = computed(() =>
  isEditable.value
  && (!editForm.supplier_id
    || !editForm.location_id
    || !editForm.order_date
    || editLines.value.length === 0
    || lineErrors.value.some(Boolean)
    || (editForm.discount_amount ?? 0) < 0
    || (editForm.discount_amount ?? 0) > linesSubtotal.value),
)

const chainSteps = computed<DocChainStep[]>(() => {
  const po = selected.value
  if (!po)
    return []

  return [
    { label: `PO ${po.po_no}`, state: po.status === 'cancelled' ? 'void' : 'current', hint: po.status },
    {
      label: 'Goods receipt',
      state: po.status === 'received' ? 'done' : 'todo',
      to: '/attendance/inventory/goods-receipts',
    },
    { label: 'Stock', state: po.status === 'received' ? 'done' : 'todo', to: '/attendance/inventory' },
  ]
})

const docPrimary = computed<InventoryDocAction | null>(() => {
  if (isEditable.value && (!selected.value || dirty.dirty.value))
    return { label: 'Save', tooltip: '儲存這張採購單的內容', onClick: saveOrder }
  if (selected.value?.status === 'draft')
    return { label: 'Order', tooltip: '正式下單給供應商,等貨到再收貨', onClick: askOrder }
  if (selected.value && ['ordered', 'partial'].includes(selected.value.status))
    return { label: 'Receive Goods', tooltip: '建立收貨單,確認後庫存才會增加', onClick: receiveGoods }

  return null
})

const docMore = computed<InventoryDocMoreItem[]>(() => {
  const menu: InventoryDocMoreItem[] = []

  if (isDraft.value && selected.value)
    menu.push({ label: 'Delete draft', sub: '刪除草稿,不能復原', icon: 'ri-delete-bin-line', danger: true, onClick: askDelete })
  if (selected.value && ['ordered', 'partial'].includes(selected.value.status))
    menu.push({ label: 'Cancel order', sub: '取消採購單,不再收貨', icon: 'ri-close-circle-line', danger: true, onClick: askCancel })

  return menu
})

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  loading.value = true
  try {
    const [supplierResult, locationList, itemList] = await Promise.all([
      listSuppliers({ is_active: true, page_size: 200 }),
      listLocations({ is_active: true }),
      listInventoryItems(),
    ])

    suppliers.value = supplierResult.items
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
    loadError.value = formatApiError(e, 'Failed to load purchase orders.')
  }
  finally {
    loading.value = false
  }
})

async function loadOrders() {
  loadError.value = ''

  const token = listReq.next()
  try {
    const result = await listPurchaseOrders({
      supplier_id: supplierFilter.value ?? undefined,
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
    loadError.value = formatApiError(e, 'Failed to load purchase orders.')
  }
}

function onFiltersChange() {
  page.value = 1
  loadOrders()
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

async function selectOrder(po: PurchaseOrder) {
  if (selected.value?.id !== po.id && dirty.dirty.value && !(await dirty.confirmDiscard()))
    return
  detailLoading.value = true
  try {
    const detail = await getPurchaseOrder(po.id)

    selected.value = detail
    resetEditor(detail)
    await scrollToDetail()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to load purchase order.')
  }
  finally {
    detailLoading.value = false
  }
}

function resetEditor(po: PurchaseOrder | null) {
  showErrors.value = false
  if (!po) {
    editLines.value = []

    return
  }
  suppressDirty = true
  editForm.supplier_id = po.supplier_id
  editForm.location_id = po.location_id
  editForm.order_date = po.order_date
  editForm.expected_date = po.expected_date ?? ''
  editForm.discount_amount = po.discount_amount
  editForm.notes = po.notes ?? ''
  editLines.value = po.lines.map(l => ({
    item_id: l.item_id,
    ordered_qty: l.ordered_qty,
    unit_cost: l.unit_cost,
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
  editForm.supplier_id = null
  editForm.location_id = null
  editForm.order_date = new Date().toISOString().slice(0, 10)
  editForm.expected_date = ''
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
  editLines.value.push({ item_id: null, ordered_qty: 1, unit_cost: 0, discount_amount: 0 })
}

function removeLine(index: number) {
  editLines.value.splice(index, 1)
}

function onItemPicked(line: EditLine) {
  const item = line.item_id ? itemById.value.get(line.item_id) : null

  if (item && !line.unit_cost)
    line.unit_cost = item.cost_price ?? 0
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

  const lines: PurchaseOrderLinePayload[] = editLines.value
    .filter(l => l.item_id && l.ordered_qty > 0)
    .map(l => ({
      item_id: l.item_id as string,
      ordered_qty: l.ordered_qty,
      unit_cost: l.unit_cost,
      discount_amount: l.discount_amount || 0,
    }))

  saving.value = true
  try {
    const payload = {
      supplier_id: editForm.supplier_id ?? '',
      location_id: editForm.location_id ?? '',
      order_date: editForm.order_date,
      expected_date: editForm.expected_date || null,
      discount_amount: editForm.discount_amount || 0,
      notes: editForm.notes || null,
      lines,
    }

    const saved = selected.value
      ? await updatePurchaseOrder(selected.value.id, payload)
      : await createPurchaseOrder(payload)

    selected.value = saved
    resetEditor(saved)
    actionSuccess.value = `Saved ${saved.po_no}.`
    await loadOrders()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to save purchase order.')
  }
  finally {
    saving.value = false
  }
}

function askOrder() {
  if (!selected.value)
    return
  confirm.ask(
    `Order ${selected.value.po_no}?`,
    '標記採購單已下單給供應商。',
    { label: 'Order', tone: 'info', details: ['之後可以建立收貨單收貨', '下單後仍可取消'] },
    performOrder,
  )
}

async function performOrder() {
  if (!selected.value)
    return
  actionError.value = ''
  saving.value = true
  try {
    selected.value = await orderPurchaseOrder(selected.value.id)
    actionSuccess.value = `${selected.value.po_no} ordered.`
    await loadOrders()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to order.')
  }
  finally {
    saving.value = false
  }
}

function askCancel() {
  if (!selected.value)
    return
  confirm.ask(
    `Cancel ${selected.value.po_no}?`,
    '取消後不能再對此採購單收貨，此操作不能復原。',
    { label: 'Cancel order', details: ['不能再建立收貨單', '不能復原'] },
    performCancel,
  )
}

async function performCancel() {
  if (!selected.value)
    return
  actionError.value = ''
  saving.value = true
  try {
    selected.value = await cancelPurchaseOrder(selected.value.id)
    actionSuccess.value = `${selected.value.po_no} cancelled.`
    await loadOrders()
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
    `Delete draft ${selected.value.po_no}?`,
    '草稿採購單和所有品項會永久刪除。',
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
    const no = selected.value.po_no

    await deletePurchaseOrder(selected.value.id)
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

async function receiveGoods() {
  if (!selected.value)
    return
  actionError.value = ''
  saving.value = true
  try {
    const grn = await createGoodsReceipt({
      po_id: selected.value.id,
      supplier_id: selected.value.supplier_id,
      location_id: selected.value.location_id,
      receipt_date: new Date().toISOString().slice(0, 10),
    })

    actionSuccess.value = `Created goods receipt ${grn.grn_no} from ${selected.value.po_no}.`
    selected.value = await getPurchaseOrder(selected.value.id)
    await loadOrders()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to create goods receipt.')
  }
  finally {
    saving.value = false
  }
}

function fmtMoney(value: number | null | undefined): string {
  return (value ?? 0).toFixed(2)
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
          Purchase Orders 採購單
        </div>
        <div class="text-body-2 text-medium-emphasis">
          這一頁管理採購單：向供應商下單進貨。
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
          New Purchase Order
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
              v-model="supplierFilter"
              :items="supplierOptions"
              label="Supplier"
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
              v-for="po in orders"
              :key="po.id"
              :active="selected?.id === po.id"
              @click="selectOrder(po)"
            >
              <VListItemTitle>{{ po.po_no }}</VListItemTitle>
              <VListItemSubtitle>
                {{ po.supplier_name || '—' }} · {{ po.order_date }} · {{ fmtMoney(po.total) }}
              </VListItemSubtitle>
              <template #append>
                <InventoryStatusChip :status="po.status" />
              </template>
            </VListItem>
            <VListItem v-if="orders.length === 0 && !loading">
              <VListItemTitle class="text-medium-emphasis">
                No purchase orders yet — click "New order" to buy stock.
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
          <VCardTitle class="d-flex align-center gap-3">
            <span>{{ selected ? selected.po_no : 'New purchase order' }}</span>
            <InventoryStatusChip
              v-if="selected"
              :status="selected.status"
            />
            <VSpacer />
            <InventoryDocActions
              :primary="docPrimary"
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
                  v-model="editForm.supplier_id"
                  :items="supplierOptions"
                  label="Supplier *"
                  density="comfortable"
                  :readonly="!isEditable"
                  :error="showErrors && !editForm.supplier_id"
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
                  v-model="editForm.expected_date"
                  label="Expected date"
                  type="date"
                  density="comfortable"
                  :readonly="!isEditable"
                />
              </VCol>
              <VCol cols="12">
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
                    Unit cost
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
                        v-model.number="line.ordered_qty"
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
                        {{ line.ordered_qty }}
                      </template>
                    </td>
                    <td class="text-end">
                      <VTextField
                        v-if="isEditable"
                        v-model.number="line.unit_cost"
                        type="number"
                        min="0"
                        step="0.01"
                        density="compact"
                        hide-details
                        variant="outlined"
                        class="inv-num-input"
                        :error="showErrors && lineErrors[index]?.field === 'cost'"
                        @blur="showErrors = true"
                      />
                      <template v-else>
                        {{ fmtMoney(line.unit_cost) }}
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
                      {{ fmtMoney(Math.max(0, (line.ordered_qty || 0) * (line.unit_cost || 0) - (line.discount_amount || 0))) }}
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
            從上面的列表選一張採購單，或按下面的按鈕建立新的。
            <div class="mt-3">
              <VBtn
                color="primary"
                prepend-icon="ri-add-line"
                @click="newOrder"
              >
                New Purchase Order
              </VBtn>
            </div>
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

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
