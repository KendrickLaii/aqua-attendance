<script setup lang="ts">
import { useDisplay } from 'vuetify'
import {
  type GoodsReceipt,
  type GoodsReceiptLinePayload,
  type InventoryDocStatus,
  type InventorySupplier,
  type PurchaseOrder,
  confirmGoodsReceipt,
  createGoodsReceipt,
  deleteGoodsReceipt,
  getGoodsReceipt,
  listGoodsReceipts,
  listPurchaseOrders,
  listSuppliers,
  updateGoodsReceipt,
  voidGoodsReceipt,
} from '@/api/attendance/inventoryPurchasing'
import { type InventoryItem, type InventoryWarehouse, listInventoryItems, listWarehouses } from '@/api/attendance/inventory'
import AttendanceConfirmDialog from '@/components/attendance/AttendanceConfirmDialog.vue'
import AttendancePaginationBar from '@/components/attendance/AttendancePaginationBar.vue'
import InventoryDocChain, { type DocChainStep } from '@/components/attendance/inventory/InventoryDocChain.vue'
import { type InventoryDocAction, type InventoryDocMoreItem } from '@/components/attendance/inventory/InventoryDocActions.vue'
import InventoryEmptyState from '@/components/attendance/inventory/InventoryEmptyState.vue'
import InventoryStatusChip from '@/components/attendance/inventory/InventoryStatusChip.vue'
import { useInventoryLinePicker } from '@/composables/useInventoryLinePicker'
import { formatApiError } from '@/utils/formatApiDetail'
import { formatMoney } from '@/utils/inventoryDisplay'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { useConfirmAction } from '@/composables/useConfirmAction'
import { useDirtyGuard } from '@/composables/useDirtyGuard'
import { useLatestRequest } from '@/composables/useLatestRequest'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()
const toast = useToast()
const display = useDisplay()

const loading = ref(true)
const detailLoading = ref(false)
const saving = ref(false)
const loadError = ref('')
const dialogError = ref('')

useAutoClearAlerts(loadError)

const suppliers = ref<InventorySupplier[]>([])
const warehouses = ref<InventoryWarehouse[]>([])
const items = ref<InventoryItem[]>([])
const openOrders = ref<PurchaseOrder[]>([])

const receipts = ref<GoodsReceipt[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const listReq = useLatestRequest()
const confirm = useConfirmAction()
const dirty = useDirtyGuard('Discard the goods receipt being drafted?')

const statusFilter = ref<InventoryDocStatus | null>(null)
const warehouseFilter = ref<string | null>(null)

const selected = ref<GoodsReceipt | null>(null)

const statusOptions = [
  { value: 'draft' as const, title: 'Draft' },
  { value: 'confirmed' as const, title: 'Confirmed' },
  { value: 'void' as const, title: 'Void' },
]

const poOptions = computed(() =>
  openOrders.value.map(po => ({
    value: po.id,
    title: `${po.po_no} · ${po.supplier_name ?? ''}`,
  })),
)

const poById = computed(() => new Map(openOrders.value.map(p => [p.id, p])))

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const isDraft = computed(() => selected.value?.status === 'draft')

const docPrimary = computed<InventoryDocAction | null>(() =>
  isDraft.value
    ? { label: 'Confirm Receipt', tooltip: '確認收貨,庫存會正式增加', onClick: askConfirm }
    : null,
)

const docMore = computed<InventoryDocMoreItem[]>(() => {
  const menu: InventoryDocMoreItem[] = []

  if (isDraft.value)
    menu.push({ label: 'Edit date & notes', sub: '改收貨日期同備註', icon: 'ri-edit-line', onClick: openEdit })
  if (isDraft.value)
    menu.push({ label: 'Delete draft', sub: '刪除草稿,不能復原', icon: 'ri-delete-bin-line', danger: true, onClick: askDelete })
  if (selected.value?.status === 'confirmed')
    menu.push({ label: 'Void receipt', sub: '作廢收貨單,庫存會扣回去;日期錯咗可以作廢再開過', icon: 'ri-close-circle-line', danger: true, onClick: askVoid })

  return menu
})

const chainSteps = computed<DocChainStep[]>(() => {
  const grn = selected.value
  if (!grn)
    return []

  return [
    { label: grn.po_no ? `PO ${grn.po_no}` : 'PO', state: 'done', to: '/attendance/inventory/purchase-orders' },
    { label: `GRN ${grn.grn_no}`, state: grn.status === 'void' ? 'void' : 'current', hint: grn.status },
    { label: 'Stock', state: grn.status === 'confirmed' ? 'done' : 'todo', to: '/attendance/inventory' },
  ]
})

const editDialogOpen = ref(false)
const editShowErrors = ref(false)
const editError = ref('')
const editForm = reactive({ receipt_date: '', notes: '' })

const createDialogOpen = ref(false)
const confirmAllowOverReceipt = ref(false)

const createForm = reactive({
  po_id: null as string | null,
  supplier_id: null as string | null,
  warehouse_id: null as string | null,
  receipt_date: new Date().toISOString().slice(0, 10),
  notes: '',
  allow_over_receipt: false,
})

const manualLines = ref<GoodsReceiptLinePayload[]>([])

let suppressDirty = false
watch([createForm, manualLines], () => {
  if (!suppressDirty && createDialogOpen.value)
    dirty.dirty.value = true
}, { deep: true })

const showErrors = ref(false)

interface LineErr { field: 'item' | 'qty' | 'cost'; msg: string }

function manualLineError(line: GoodsReceiptLinePayload): LineErr | null {
  if (!line.item_id)
    return { field: 'item', msg: '請選擇品項' }
  if (!Number.isInteger(line.qty) || line.qty <= 0)
    return { field: 'qty', msg: '數量要是大於 0 的整數' }
  if (line.unit_cost == null || line.unit_cost < 0)
    return { field: 'cost', msg: '單價不能是負數' }

  return null
}

const manualLineErrors = computed(() => manualLines.value.map(manualLineError))
const createFromPo = computed(() => !!createForm.po_id)

const createInvalid = computed(() =>
  createFromPo.value
    ? !createForm.receipt_date
    : (!createForm.supplier_id
      || !createForm.warehouse_id
      || !createForm.receipt_date
      || manualLines.value.length === 0
      || manualLineErrors.value.some(Boolean)),
)

async function closeCreate() {
  if (await dirty.confirmDiscard())
    createDialogOpen.value = false
}

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  loading.value = true
  try {
    const [supplierResult, warehouseList, itemList, poList] = await Promise.all([
      listSuppliers({ is_active: true, page_size: 200 }),
      listWarehouses({ is_active: true }),
      listInventoryItems(),
      fetchAllOpenOrders(),
    ])

    suppliers.value = supplierResult.items
    warehouses.value = warehouseList
    items.value = itemList
    openOrders.value = poList
    await loadReceipts()
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Failed to load goods receipts.')
  }
  finally {
    loading.value = false
  }
})

async function fetchAllOpenOrders(): Promise<PurchaseOrder[]> {
  const ordered = await listPurchaseOrders({ status: 'ordered', page_size: 200 })
  const partial = await listPurchaseOrders({ status: 'partial', page_size: 200 })

  return [...ordered.items, ...partial.items]
}

async function loadReceipts() {
  loadError.value = ''

  const token = listReq.next()
  try {
    const result = await listGoodsReceipts({
      status: statusFilter.value ?? undefined,
      warehouse_id: warehouseFilter.value ?? undefined,
      page: page.value,
      page_size: pageSize.value,
    })

    if (!listReq.isLatest(token))
      return
    receipts.value = result.items
    total.value = result.total
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Failed to load goods receipts.')
  }
}

function onFiltersChange() {
  page.value = 1
  loadReceipts()
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

async function selectReceipt(grn: GoodsReceipt) {
  detailLoading.value = true
  try {
    selected.value = await getGoodsReceipt(grn.id)
    await scrollToDetail()
  }
  catch (e) {
    toast.show(formatApiError(e, 'Failed to load goods receipt.'), 'error', 6000)
  }
  finally {
    detailLoading.value = false
  }
}

function openCreate() {
  suppressDirty = true
  showErrors.value = false
  createForm.po_id = null
  createForm.supplier_id = null
  createForm.warehouse_id = null
  createForm.receipt_date = new Date().toISOString().slice(0, 10)
  createForm.notes = ''
  createForm.allow_over_receipt = false
  manualLines.value = []
  dialogError.value = ''
  createDialogOpen.value = true
  dirty.markClean()
  nextTick(() => {
    suppressDirty = false
  })
}

function addManualLine() {
  manualLines.value.push({ item_id: '', qty: 1, unit_cost: 0 })
}

const { onPickItem } = useInventoryLinePicker({
  lines: manualLines,
  itemById: id => items.value.find(i => i.id === id),
  qtyKey: 'qty',
  priceKeys: ['unit_cost'],
})

const manualSubtotal = computed(() =>
  manualLines.value.reduce((s, l) => s + (l.qty || 0) * (l.unit_cost || 0), 0),
)

function removeManualLine(index: number) {
  manualLines.value.splice(index, 1)
}

async function submitCreate() {
  if (createInvalid.value) {
    showErrors.value = true
    dialogError.value = '請檢查紅色標示的欄位，修正後再建立。'
    await nextTick()
    document.querySelector<HTMLElement>('.v-input--error input, .v-input--error textarea')?.focus()

    return
  }
  saving.value = true
  dialogError.value = ''
  try {
    const po = createForm.po_id ? poById.value.get(createForm.po_id) : null
    const supplierId = po ? po.supplier_id : createForm.supplier_id
    const warehouseId = po ? po.warehouse_id : createForm.warehouse_id

    if (!supplierId || !warehouseId) {
      dialogError.value = 'Supplier and location are required.'

      return
    }

    const payload = {
      supplier_id: supplierId,
      warehouse_id: warehouseId,
      receipt_date: createForm.receipt_date,
      notes: createForm.notes || null,
      allow_over_receipt: createForm.allow_over_receipt,
      po_id: createForm.po_id,
      lines: createFromPo.value
        ? []
        : manualLines.value.filter(l => l.item_id && l.qty > 0),
    }

    const grn = await createGoodsReceipt(payload)

    toast.show(`Created goods receipt ${grn.grn_no}.`)
    createDialogOpen.value = false
    dirty.markClean()
    await loadReceipts()
    await selectReceipt(grn)
  }
  catch (e) {
    dialogError.value = formatApiError(e, 'Failed to create goods receipt.')
  }
  finally {
    saving.value = false
  }
}

function openEdit() {
  if (!selected.value)
    return
  editForm.receipt_date = selected.value.receipt_date
  editForm.notes = selected.value.notes ?? ''
  editShowErrors.value = false
  editError.value = ''
  editDialogOpen.value = true
}

async function submitEdit() {
  if (!selected.value)
    return
  if (!editForm.receipt_date) {
    editShowErrors.value = true
    editError.value = '請填收貨日期。'

    return
  }
  saving.value = true
  editError.value = ''
  try {
    selected.value = await updateGoodsReceipt(selected.value.id, {
      receipt_date: editForm.receipt_date,
      notes: editForm.notes || null,
    })
    editDialogOpen.value = false
    toast.show(`Updated ${selected.value.grn_no}.`)
    await loadReceipts()
  }
  catch (e) {
    editError.value = formatApiError(e, 'Failed to update goods receipt.')
  }
  finally {
    saving.value = false
  }
}

function askConfirm() {
  const grn = selected.value
  if (!grn)
    return
  const qty = grn.lines.reduce((s, l) => s + l.qty, 0)

  confirmAllowOverReceipt.value = false
  confirm.ask(
    `Confirm ${grn.grn_no}?`,
    `確認後 ${qty} 件貨會加入庫存並更新平均成本。`,
    { label: 'Confirm', tone: 'info', details: ['庫存數量增加', '品項平均成本更新', '要收超過訂購量才勾「允許超收」'] },
    performConfirm,
  )
}

async function performConfirm() {
  if (!selected.value)
    return
  saving.value = true
  try {
    selected.value = await confirmGoodsReceipt(selected.value.id, confirmAllowOverReceipt.value)
    toast.show(`Confirmed ${selected.value.grn_no}.`)
    await loadReceipts()
    openOrders.value = await fetchAllOpenOrders()
  }
  catch (e) {
    toast.show(formatApiError(e, 'Failed to confirm.'), 'error', 6000)
  }
  finally {
    saving.value = false
  }
}

function askVoid() {
  const grn = selected.value
  if (!grn)
    return
  const qty = grn.lines.reduce((s, l) => s + l.qty, 0)

  confirm.ask(
    `Void ${grn.grn_no}?`,
    `作廢後 ${qty} 件會從庫存扣回。`,
    { label: 'Void', details: ['庫存數量扣回', '如有已確認退貨需先作廢該退貨', '不能復原'] },
    performVoid,
  )
}

async function performVoid() {
  if (!selected.value)
    return
  saving.value = true
  try {
    selected.value = await voidGoodsReceipt(selected.value.id)
    toast.show(`Voided ${selected.value.grn_no}.`)
    await loadReceipts()
    openOrders.value = await fetchAllOpenOrders()
  }
  catch (e) {
    toast.show(formatApiError(e, 'Failed to void.'), 'error', 6000)
  }
  finally {
    saving.value = false
  }
}

function askDelete() {
  if (!selected.value)
    return
  confirm.ask(
    `Delete draft ${selected.value.grn_no}?`,
    '草稿收貨單會永久刪除。',
    { label: 'Delete', details: ['不能復原'] },
    performDelete,
  )
}

async function performDelete() {
  if (!selected.value)
    return
  saving.value = true
  try {
    const no = selected.value.grn_no

    await deleteGoodsReceipt(selected.value.id)
    toast.show(`Deleted draft ${no}.`)
    selected.value = null
    await loadReceipts()
  }
  catch (e) {
    toast.show(formatApiError(e, 'Failed to delete.'), 'error', 6000)
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
          Goods Receipts 收貨單
        </div>
        <div class="text-body-2 text-medium-emphasis">
          這一頁管理收貨單：貨到了在這裡確認，庫存才會增加。
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
              @click="loadReceipts"
            />
          </template>
        </VTooltip>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          class="ms-2"
          @click="openCreate"
        >
          New Goods Receipt
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

    <VRow>
      <VCol cols="12">
        <VCard>
          <VCardText class="d-flex flex-wrap gap-3">
            <VSelect
              v-model="statusFilter"
              :items="statusOptions"
              label="Status"
              density="comfortable"
              hide-details
              clearable
              @update:model-value="onFiltersChange"
            />
            <VSelect
              v-model="warehouseFilter"
              :items="warehouses.map(l => ({ value: l.id, title: l.name_en || l.name_zh || l.id }))"
              label="Warehouse 倉庫"
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
              v-for="grn in receipts"
              :key="grn.id"
              :active="selected?.id === grn.id"
              @click="selectReceipt(grn)"
            >
              <VListItemTitle>{{ grn.grn_no }}</VListItemTitle>
              <VListItemSubtitle>
                {{ grn.supplier_name || '—' }} · {{ grn.receipt_date }}
                <template v-if="grn.po_no">
                  · {{ grn.po_no }}
                </template>
              </VListItemSubtitle>
              <template #append>
                <InventoryStatusChip :status="grn.status" />
              </template>
            </VListItem>
            <InventoryEmptyState
              v-if="receipts.length === 0 && !loading"
              icon="ri-inbox-archive-line"
              text="No goods receipts yet."
              action-label="New Goods Receipt"
              @action="openCreate"
            />
          </VList>
          <AttendancePaginationBar
            v-model:page="page"
            v-model:page-size="pageSize"
            :total-pages="totalPages"
            :caption="`Page ${page} of ${totalPages} · ${total} receipt${total === 1 ? '' : 's'}`"
            @change="loadReceipts"
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
        <VCard v-else-if="selected">
          <VCardTitle class="d-flex align-center gap-3">
            <span>{{ selected.grn_no }}</span>
            <InventoryStatusChip :status="selected.status" />
            <VSpacer />
            <InventoryDocActions
              :primary="docPrimary"
              :more="docMore"
              :loading="saving"
            />
          </VCardTitle>
          <VCardSubtitle>
            {{ selected.supplier_name || '—' }} · {{ selected.warehouse_name || '—' }} ·
            {{ selected.receipt_date }}
            <template v-if="selected.po_no">
              · PO {{ selected.po_no }}
            </template>
          </VCardSubtitle>
          <div
            v-if="selected.notes"
            class="text-body-2 text-medium-emphasis px-4 pt-1"
          >
            Notes: {{ selected.notes }}
          </div>
          <VCardText class="pa-0">
            <InventoryDocChain
              :steps="chainSteps"
              class="px-4 pb-2"
            />
            <div class="overflow-x-auto">
              <VTable>
                <thead>
                  <tr>
                    <th>Item</th>
                    <th class="text-end">
                      Qty
                    </th>
                    <th class="text-end">
                      Unit cost
                    </th>
                    <th class="text-end">
                      Amount
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="line in selected.lines"
                    :key="line.id"
                  >
                    <td>{{ [line.sku_code, line.name_zh].filter(Boolean).join(' · ') || line.item_id }}</td>
                    <td class="text-end tabular-nums">
                      {{ line.qty }}
                    </td>
                    <td class="text-end tabular-nums">
                      {{ formatMoney(line.unit_cost) }}
                    </td>
                    <td class="text-end font-weight-medium tabular-nums">
                      {{ formatMoney(line.qty * line.unit_cost) }}
                    </td>
                  </tr>
                </tbody>
              </VTable>
            </div>
          </VCardText>
        </VCard>
        <VCard v-else>
          <VCardText class="text-center text-medium-emphasis py-12">
            從上面的列表選一張收貨單，或按下面的按鈕建立新的。
            <div class="mt-3">
              <VBtn
                color="primary"
                prepend-icon="ri-add-line"
                @click="openCreate"
              >
                New Goods Receipt
              </VBtn>
            </div>
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <VDialog
      v-model="createDialogOpen"
      max-width="900"
      :fullscreen="display.xs.value"
      scrollable
    >
      <VCard title="New goods receipt">
        <VCardText>
          <VAlert
            v-if="dialogError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            {{ dialogError }}
          </VAlert>
          <div class="text-overline text-medium-emphasis mb-2">
            Document
          </div>
          <VAlert
            type="info"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            Pick an open PO to prefill remaining quantities, or leave it blank and add lines manually.
          </VAlert>
          <VSelect
            v-model="createForm.po_id"
            :items="poOptions"
            label="Purchase order"
            density="comfortable"
            class="mb-3"
            clearable
          />
          <template v-if="!createFromPo">
            <VSelect
              v-model="createForm.supplier_id"
              :items="suppliers.map(s => ({ value: s.id, title: `${s.code} · ${s.name_zh}` }))"
              label="Supplier *"
              density="comfortable"
              class="mb-3"
              :error="showErrors && !createForm.supplier_id"
              @blur="showErrors = true"
            />
            <VSelect
              v-model="createForm.warehouse_id"
              :items="warehouses.map(l => ({ value: l.id, title: l.name_en || l.name_zh || l.id }))"
              label="Warehouse 倉庫 *"
              density="comfortable"
              class="mb-3"
              :error="showErrors && !createForm.warehouse_id"
              @blur="showErrors = true"
            />
          </template>
          <VTextField
            v-model="createForm.receipt_date"
            label="Receipt date *"
            type="date"
            density="comfortable"
            class="mb-3"
            hint="補舊單請填實際收貨日期"
            persistent-hint
            :error="showErrors && !createForm.receipt_date"
            @blur="showErrors = true"
          />
          <VTextField
            v-model="createForm.notes"
            label="Notes"
            density="comfortable"
            class="mb-3"
          />
          <VCheckbox
            v-model="createForm.allow_over_receipt"
            label="Allow over-receipt"
            density="comfortable"
            hide-details
          />

          <template v-if="!createFromPo">
            <div class="text-overline text-medium-emphasis mb-2 mt-4">
              Lines
            </div>
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
                  <th class="text-end">
                    Line total
                  </th>
                  <th class="inv-col-remove" />
                </tr>
              </thead>
              <tbody>
                <template
                  v-for="(line, index) in manualLines"
                  :key="index"
                >
                  <tr>
                    <td>
                      <VAutocomplete
                        v-model="line.item_id"
                        :items="items.map(i => ({ value: i.id, title: [i.sku_code, i.name_zh].filter(Boolean).join(' · ') }))"
                        density="compact"
                        hide-details
                        variant="outlined"
                        placeholder="Search item…"
                        :error="showErrors && manualLineErrors[index]?.field === 'item'"
                        @update:model-value="onPickItem(index)"
                        @blur="showErrors = true"
                      />
                    </td>
                    <td>
                      <VTextField
                        v-model.number="line.qty"
                        type="number"
                        min="1"
                        step="1"
                        density="compact"
                        hide-details
                        variant="outlined"
                        class="inv-num-input"
                        :error="showErrors && manualLineErrors[index]?.field === 'qty'"
                        @blur="showErrors = true"
                      />
                    </td>
                    <td>
                      <VTextField
                        v-model.number="line.unit_cost"
                        type="number"
                        min="0"
                        step="0.01"
                        density="compact"
                        hide-details
                        variant="outlined"
                        class="inv-num-input"
                        :error="showErrors && manualLineErrors[index]?.field === 'cost'"
                        @blur="showErrors = true"
                      />
                    </td>
                    <td class="text-end tabular-nums">
                      {{ formatMoney((line.qty || 0) * (line.unit_cost || 0)) }}
                    </td>
                    <td class="inv-col-remove">
                      <VBtn
                        icon="ri-close-line"
                        variant="text"
                        size="x-small"
                        color="error"
                        aria-label="Remove line"
                        @click="removeManualLine(index)"
                      />
                    </td>
                  </tr>
                  <tr
                    v-if="showErrors && manualLineErrors[index]"
                    class="inv-line-error"
                  >
                    <td
                      colspan="5"
                      class="text-caption text-error"
                    >
                      {{ manualLineErrors[index]!.msg }}
                    </td>
                  </tr>
                </template>
              </tbody>
              <tfoot v-if="manualLines.length">
                <tr>
                  <td
                    colspan="3"
                    class="text-end text-medium-emphasis"
                  >
                    Subtotal
                  </td>
                  <td class="text-end tabular-nums font-weight-bold">
                    {{ formatMoney(manualSubtotal) }}
                  </td>
                  <td />
                </tr>
              </tfoot>
            </VTable>
            <VBtn
              variant="text"
              size="small"
              color="primary"
              prepend-icon="ri-add-line"
              @click="addManualLine"
            >
              Add line
            </VBtn>
          </template>
        </VCardText>
        <VDivider />
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
            :loading="saving"
            @click="submitCreate"
          >
            Create
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

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
      <div>{{ confirm.message.value }}</div>
      <VCheckbox
        v-if="confirm.title.value.startsWith('Confirm')"
        v-model="confirmAllowOverReceipt"
        label="Allow over-receipt (receive more than ordered)"
        density="compact"
        hide-details
        class="mt-2"
      />
    </AttendanceConfirmDialog>

    <VDialog
      v-model="editDialogOpen"
      max-width="480"
      :fullscreen="display.xs.value"
    >
      <VCard title="Edit date & notes">
        <VCardText>
          <VAlert
            v-if="editError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            {{ editError }}
          </VAlert>
          <VTextField
            v-model="editForm.receipt_date"
            label="Receipt date *"
            type="date"
            density="comfortable"
            class="mb-3"
            :error="editShowErrors && !editForm.receipt_date"
            @blur="editShowErrors = true"
          />
          <VTextField
            v-model="editForm.notes"
            label="Notes"
            density="comfortable"
          />
        </VCardText>
        <VDivider />
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="editDialogOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :loading="saving"
            @click="submitEdit"
          >
            Save
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>
