<script setup lang="ts">
import {
  type GoodsReceipt,
  type InventoryDocStatus,
  type InventorySupplier,
  type PurchaseReturn,
  type PurchaseReturnLinePayload,
  confirmPurchaseReturn,
  createPurchaseReturn,
  deletePurchaseReturn,
  getPurchaseReturn,
  listGoodsReceipts,
  listPurchaseReturns,
  listSuppliers,
  voidPurchaseReturn,
} from '@/api/attendance/inventoryPurchasing'
import { type InventoryItem, listInventoryItems } from '@/api/attendance/inventory'
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
const confirmedGrns = ref<GoodsReceipt[]>([])

const returns = ref<PurchaseReturn[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const listReq = useLatestRequest()
const confirm = useConfirmAction()
const dirty = useDirtyGuard('Discard the purchase return being drafted?')

const statusFilter = ref<InventoryDocStatus | null>(null)
const locationFilter = ref<string | null>(null)

const selected = ref<PurchaseReturn | null>(null)

const statusOptions = [
  { value: 'draft' as const, title: 'Draft' },
  { value: 'confirmed' as const, title: 'Confirmed' },
  { value: 'void' as const, title: 'Void' },
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

const grnOptions = computed(() =>
  confirmedGrns.value.map(g => ({
    value: g.id,
    title: `${g.grn_no} · ${g.supplier_name ?? ''} · ${g.receipt_date}`,
  })),
)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const isDraft = computed(() => selected.value?.status === 'draft')

const docPrimary = computed<InventoryDocAction | null>(() =>
  isDraft.value
    ? { label: 'Confirm Return', tooltip: '確認退貨,庫存會正式扣減', onClick: askConfirm }
    : null,
)

const docMore = computed<InventoryDocMoreItem[]>(() => {
  const menu: InventoryDocMoreItem[] = []

  if (isDraft.value)
    menu.push({ label: 'Delete draft', sub: '刪除草稿,不能復原', icon: 'ri-delete-bin-line', danger: true, onClick: askDelete })
  if (selected.value?.status === 'confirmed')
    menu.push({ label: 'Void return', sub: '作廢退貨單,庫存會加回去', icon: 'ri-close-circle-line', danger: true, onClick: askVoid })

  return menu
})

const createDialogOpen = ref(false)

const createForm = reactive({
  supplier_id: null as string | null,
  location_id: null as string | null,
  grn_id: null as string | null,
  return_date: new Date().toISOString().slice(0, 10),
  notes: '',
})

const createLines = ref<PurchaseReturnLinePayload[]>([])

let suppressDirty = false
watch([createForm, createLines], () => {
  if (!suppressDirty && createDialogOpen.value)
    dirty.dirty.value = true
}, { deep: true })

const showErrors = ref(false)

interface LineErr { field: 'item' | 'qty' | 'cost'; msg: string }

function createLineError(line: PurchaseReturnLinePayload): LineErr | null {
  if (!line.item_id)
    return { field: 'item', msg: '請選擇品項' }
  if (!Number.isInteger(line.qty) || line.qty <= 0)
    return { field: 'qty', msg: '數量要是大於 0 的整數' }
  if (line.unit_cost == null || line.unit_cost < 0)
    return { field: 'cost', msg: '單價不能是負數' }

  return null
}

const createLineErrors = computed(() => createLines.value.map(createLineError))

const createInvalid = computed(() =>
  !createForm.supplier_id
  || !createForm.location_id
  || !createForm.return_date
  || createLines.value.length === 0
  || createLineErrors.value.some(Boolean),
)

async function closeCreate() {
  if (await dirty.confirmDiscard())
    createDialogOpen.value = false
}

const chainSteps = computed<DocChainStep[]>(() => {
  const prt = selected.value
  if (!prt)
    return []

  return [
    { label: prt.grn_no ? `GRN ${prt.grn_no}` : 'GRN', state: 'done', to: '/attendance/inventory/goods-receipts' },
    { label: `PRT ${prt.prt_no}`, state: prt.status === 'void' ? 'void' : 'current', hint: prt.status },
    { label: 'Stock', state: prt.status === 'confirmed' ? 'done' : 'todo', to: '/attendance/inventory' },
  ]
})

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  loading.value = true
  try {
    const [supplierResult, locationList, itemList, grnList] = await Promise.all([
      listSuppliers({ is_active: true, page_size: 200 }),
      listLocations({ is_active: true }),
      listInventoryItems(),
      listGoodsReceipts({ status: 'confirmed', page_size: 200 }),
    ])

    suppliers.value = supplierResult.items
    locations.value = locationList
    items.value = itemList
    confirmedGrns.value = grnList.items
    await loadReturns()
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Failed to load purchase returns.')
  }
  finally {
    loading.value = false
  }
})

async function loadReturns() {
  loadError.value = ''

  const token = listReq.next()
  try {
    const result = await listPurchaseReturns({
      status: statusFilter.value ?? undefined,
      location_id: locationFilter.value ?? undefined,
      page: page.value,
      page_size: pageSize.value,
    })

    if (!listReq.isLatest(token))
      return
    returns.value = result.items
    total.value = result.total
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Failed to load purchase returns.')
  }
}

function onFiltersChange() {
  page.value = 1
  loadReturns()
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

async function selectReturn(prt: PurchaseReturn) {
  detailLoading.value = true
  try {
    selected.value = await getPurchaseReturn(prt.id)
    await scrollToDetail()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to load purchase return.')
  }
  finally {
    detailLoading.value = false
  }
}

function openCreate() {
  suppressDirty = true
  showErrors.value = false
  createForm.supplier_id = null
  createForm.location_id = null
  createForm.grn_id = null
  createForm.return_date = new Date().toISOString().slice(0, 10)
  createForm.notes = ''
  createLines.value = []
  addCreateLine()
  createDialogOpen.value = true
  dirty.markClean()
  nextTick(() => {
    suppressDirty = false
  })
}

function addCreateLine() {
  createLines.value.push({ item_id: '', qty: 1, unit_cost: 0 })
}

function removeCreateLine(index: number) {
  createLines.value.splice(index, 1)
}

async function submitCreate() {
  actionError.value = ''
  if (createInvalid.value) {
    showErrors.value = true
    actionError.value = '請檢查紅色標示的欄位，修正後再建立。'
    await nextTick()
    document.querySelector<HTMLElement>('.v-input--error input, .v-input--error textarea')?.focus()

    return
  }
  saving.value = true
  try {
    const lines = createLines.value.filter(l => l.item_id && l.qty > 0)

    const prt = await createPurchaseReturn({
      supplier_id: createForm.supplier_id ?? '',
      location_id: createForm.location_id ?? '',
      grn_id: createForm.grn_id,
      return_date: createForm.return_date,
      notes: createForm.notes || null,
      lines,
    })

    actionSuccess.value = `Created purchase return ${prt.prt_no}.`
    createDialogOpen.value = false
    dirty.markClean()
    await loadReturns()
    await selectReturn(prt)
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to create purchase return.')
  }
  finally {
    saving.value = false
  }
}

function askConfirm() {
  const prt = selected.value
  if (!prt)
    return
  const qty = prt.lines.reduce((s, l) => s + l.qty, 0)

  confirm.ask(
    `Confirm ${prt.prt_no}?`,
    `確認後 ${qty} 件會從庫存扣減（退給供應商）。`,
    { label: 'Confirm', tone: 'info', details: ['庫存數量減少', '不能復原，只能作廢'] },
    performConfirm,
  )
}

async function performConfirm() {
  if (!selected.value)
    return
  actionError.value = ''
  saving.value = true
  try {
    selected.value = await confirmPurchaseReturn(selected.value.id)
    actionSuccess.value = `Confirmed ${selected.value.prt_no}.`
    await loadReturns()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to confirm.')
  }
  finally {
    saving.value = false
  }
}

function askVoid() {
  const prt = selected.value
  if (!prt)
    return
  const qty = prt.lines.reduce((s, l) => s + l.qty, 0)

  confirm.ask(
    `Void ${prt.prt_no}?`,
    `作廢後 ${qty} 件會加回庫存。`,
    { label: 'Void', details: ['庫存數量加回', '不能復原'] },
    performVoid,
  )
}

async function performVoid() {
  if (!selected.value)
    return
  actionError.value = ''
  saving.value = true
  try {
    selected.value = await voidPurchaseReturn(selected.value.id)
    actionSuccess.value = `Voided ${selected.value.prt_no}.`
    await loadReturns()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to void.')
  }
  finally {
    saving.value = false
  }
}

function askDelete() {
  if (!selected.value)
    return
  confirm.ask(
    `Delete draft ${selected.value.prt_no}?`,
    '草稿退貨單會永久刪除。',
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
    const no = selected.value.prt_no

    await deletePurchaseReturn(selected.value.id)
    actionSuccess.value = `Deleted draft ${no}.`
    selected.value = null
    await loadReturns()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to delete.')
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
          Purchase Returns 採購退貨
        </div>
        <div class="text-body-2 text-medium-emphasis">
          這一頁管理退貨單：把有問題的貨退回給供應商。
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
              @click="loadReturns"
            />
          </template>
        </VTooltip>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          class="ms-2"
          @click="openCreate"
        >
          New Purchase Return
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
              v-model="statusFilter"
              :items="statusOptions"
              label="Status"
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
          </VCardText>
          <VList
            density="compact"
            style="max-height: 360px; overflow-y: auto"
          >
            <VListItem
              v-for="prt in returns"
              :key="prt.id"
              :active="selected?.id === prt.id"
              @click="selectReturn(prt)"
            >
              <VListItemTitle>{{ prt.prt_no }}</VListItemTitle>
              <VListItemSubtitle>
                {{ prt.supplier_name || '—' }} · {{ prt.return_date }}
                <template v-if="prt.grn_no">
                  · {{ prt.grn_no }}
                </template>
              </VListItemSubtitle>
              <template #append>
                <InventoryStatusChip :status="prt.status" />
              </template>
            </VListItem>
            <VListItem v-if="returns.length === 0 && !loading">
              <VListItemTitle class="text-medium-emphasis">
                No purchase returns yet — click "New return" to send goods back to a supplier.
              </VListItemTitle>
            </VListItem>
          </VList>
          <AttendancePaginationBar
            v-model:page="page"
            v-model:page-size="pageSize"
            :total-pages="totalPages"
            :caption="`Page ${page} of ${totalPages} · ${total} return${total === 1 ? '' : 's'}`"
            @change="loadReturns"
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
            <span>{{ selected.prt_no }}</span>
            <InventoryStatusChip :status="selected.status" />
            <VSpacer />
            <InventoryDocActions
              :primary="docPrimary"
              :more="docMore"
              :loading="saving"
            />
          </VCardTitle>
          <VCardSubtitle>
            {{ selected.supplier_name || '—' }} · {{ selected.location_name || '—' }} ·
            {{ selected.return_date }}
            <template v-if="selected.grn_no">
              · against {{ selected.grn_no }}
            </template>
          </VCardSubtitle>
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
                      {{ fmtMoney(line.unit_cost) }}
                    </td>
                    <td class="text-end font-weight-medium tabular-nums">
                      {{ fmtMoney(line.qty * line.unit_cost) }}
                    </td>
                  </tr>
                </tbody>
              </VTable>
            </div>
          </VCardText>
        </VCard>
        <VCard v-else>
          <VCardText class="text-center text-medium-emphasis py-12">
            從上面的列表選一張退貨單，或按下面的按鈕建立新的。
            <div class="mt-3">
              <VBtn
                color="primary"
                prepend-icon="ri-add-line"
                @click="openCreate"
              >
                New Purchase Return
              </VBtn>
            </div>
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <VDialog
      v-model="createDialogOpen"
      max-width="640"
    >
      <VCard title="New purchase return">
        <VCardText>
          <VSelect
            v-model="createForm.supplier_id"
            :items="supplierOptions"
            label="Supplier *"
            density="comfortable"
            class="mb-3"
            :error="showErrors && !createForm.supplier_id"
            @blur="showErrors = true"
          />
          <VSelect
            v-model="createForm.location_id"
            :items="locationOptions"
            label="Location *"
            density="comfortable"
            class="mb-3"
            :error="showErrors && !createForm.location_id"
            @blur="showErrors = true"
          />
          <VSelect
            v-model="createForm.grn_id"
            :items="grnOptions"
            label="Against goods receipt"
            hint="Optional — return qty may not exceed received qty."
            persistent-hint
            density="comfortable"
            class="mb-3"
            clearable
          />
          <VTextField
            v-model="createForm.return_date"
            label="Return date *"
            type="date"
            density="comfortable"
            class="mb-3"
            :error="showErrors && !createForm.return_date"
            @blur="showErrors = true"
          />
          <VTextField
            v-model="createForm.notes"
            label="Notes"
            density="comfortable"
            class="mb-3"
          />

          <VDivider class="my-3" />
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
                <th class="inv-col-remove" />
              </tr>
            </thead>
            <tbody>
              <template
                v-for="(line, index) in createLines"
                :key="index"
              >
                <tr>
                  <td>
                    <VAutocomplete
                      v-model="line.item_id"
                      :items="itemOptions"
                      density="compact"
                      hide-details
                      variant="outlined"
                      placeholder="Search item…"
                      :error="showErrors && createLineErrors[index]?.field === 'item'"
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
                      :error="showErrors && createLineErrors[index]?.field === 'qty'"
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
                      :error="showErrors && createLineErrors[index]?.field === 'cost'"
                      @blur="showErrors = true"
                    />
                  </td>
                  <td class="inv-col-remove">
                    <VBtn
                      icon="ri-close-line"
                      variant="text"
                      size="x-small"
                      color="error"
                      aria-label="Remove line"
                      @click="removeCreateLine(index)"
                    />
                  </td>
                </tr>
                <tr
                  v-if="showErrors && createLineErrors[index]"
                  class="inv-line-error"
                >
                  <td
                    colspan="4"
                    class="text-caption text-error"
                  >
                    {{ createLineErrors[index]!.msg }}
                  </td>
                </tr>
              </template>
            </tbody>
          </VTable>
          <VBtn
            variant="text"
            size="small"
            color="primary"
            prepend-icon="ri-add-line"
            @click="addCreateLine"
          >
            Add line
          </VBtn>
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
      {{ confirm.message.value }}
    </AttendanceConfirmDialog>
  </VContainer>
</template>
