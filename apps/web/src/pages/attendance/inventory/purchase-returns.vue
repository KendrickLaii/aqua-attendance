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

function createLineError(line: PurchaseReturnLinePayload): string {
  if (!line.item_id)
    return 'Item required'
  if (!Number.isInteger(line.qty) || line.qty <= 0)
    return 'Qty must be a whole number > 0'
  if (line.unit_cost == null || line.unit_cost < 0)
    return 'Cost must be >= 0'

  return ''
}

const createLineErrors = computed(() => createLines.value.map(createLineError))

const createInvalid = computed(() =>
  !createForm.supplier_id
  || !createForm.location_id
  || !createForm.return_date
  || createLines.value.length === 0
  || createLineErrors.value.some(Boolean),
)

function closeCreate() {
  if (dirty.confirmDiscard())
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

async function selectReturn(prt: PurchaseReturn) {
  detailLoading.value = true
  try {
    selected.value = await getPurchaseReturn(prt.id)
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
    actionError.value = 'Please fix the highlighted fields before creating.'

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
    `Confirming removes ${qty} item${qty === 1 ? '' : 's'} from stock as a return to the supplier.`,
    { label: 'Confirm', color: 'primary' },
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
    `Voiding restores ${qty} item${qty === 1 ? '' : 's'} to stock. This cannot be undone.`,
    { label: 'Void' },
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
    'The draft purchase return will be permanently deleted.',
    { label: 'Delete' },
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
      </VCol>
      <VCol cols="auto">
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="loading"
          @click="loadReturns"
        >
          Refresh
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          class="ms-2"
          @click="openCreate"
        >
          New return
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
          <VList density="compact">
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
        <VCard v-else-if="selected">
          <VCardTitle class="d-flex align-center gap-3">
            <span>{{ selected.prt_no }}</span>
            <InventoryStatusChip :status="selected.status" />
            <VSpacer />
            <VBtn
              v-if="isDraft"
              color="primary"
              size="small"
              prepend-icon="ri-arrow-right-line"
              :loading="saving"
              @click="askConfirm"
            >
              Next: Confirm return
            </VBtn>
            <template v-if="isDraft">
              <VBtn
                variant="text"
                color="error"
                size="small"
                :loading="saving"
                @click="askDelete"
              >
                Delete
              </VBtn>
            </template>
            <VBtn
              v-else-if="selected.status === 'confirmed'"
              variant="tonal"
              color="error"
              size="small"
              :loading="saving"
              @click="askVoid"
            >
              Void
            </VBtn>
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
            Select a purchase return or create a new one.
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
            :error="!createForm.supplier_id"
          />
          <VSelect
            v-model="createForm.location_id"
            :items="locationOptions"
            label="Location *"
            density="comfortable"
            class="mb-3"
            :error="!createForm.location_id"
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
            :error="!createForm.return_date"
          />
          <VTextField
            v-model="createForm.notes"
            label="Notes"
            density="comfortable"
            class="mb-3"
          />

          <VDivider class="my-3" />
          <div
            v-for="(line, index) in createLines"
            :key="index"
            class="d-flex gap-3 mb-2 align-center"
          >
            <VAutocomplete
              v-model="line.item_id"
              :items="itemOptions"
              label="Item *"
              density="compact"
              hide-details="auto"
              variant="outlined"
              style="flex: 3"
              :error="!!createLineErrors[index]"
              :error-messages="createLineErrors[index]"
            />
            <VTextField
              v-model.number="line.qty"
              label="Qty *"
              type="number"
              min="1"
              step="1"
              density="compact"
              hide-details="auto"
              variant="outlined"
              style="flex: 1"
              :error="!!createLineErrors[index]"
            />
            <VTextField
              v-model.number="line.unit_cost"
              label="Unit cost *"
              type="number"
              min="0"
              step="0.01"
              density="compact"
              hide-details="auto"
              variant="outlined"
              style="flex: 1"
              :error="!!createLineErrors[index]"
            />
            <VBtn
              icon="ri-close-line"
              variant="text"
              size="x-small"
              color="error"
              aria-label="Remove line"
              @click="removeCreateLine(index)"
            />
          </div>
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
            :disabled="createInvalid"
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
      :loading="confirm.loading.value"
      @confirm="confirm.run"
    >
      {{ confirm.message.value }}
    </AttendanceConfirmDialog>
  </VContainer>
</template>
