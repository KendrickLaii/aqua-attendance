<script setup lang="ts">
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
  voidGoodsReceipt,
} from '@/api/attendance/inventoryPurchasing'
import { type InventoryItem, listInventoryItems } from '@/api/attendance/inventory'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import AttendancePaginationBar from '@/components/attendance/AttendancePaginationBar.vue'
import InventoryStatusChip from '@/components/attendance/inventory/InventoryStatusChip.vue'
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

const suppliers = ref<InventorySupplier[]>([])
const locations = ref<LocationItem[]>([])
const items = ref<InventoryItem[]>([])
const openOrders = ref<PurchaseOrder[]>([])

const receipts = ref<GoodsReceipt[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref<InventoryDocStatus | null>(null)
const locationFilter = ref<string | null>(null)

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

const createDialogOpen = ref(false)

const createForm = reactive({
  po_id: null as string | null,
  supplier_id: null as string | null,
  location_id: null as string | null,
  receipt_date: new Date().toISOString().slice(0, 10),
  notes: '',
  allow_over_receipt: false,
})

const manualLines = ref<GoodsReceiptLinePayload[]>([])

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  loading.value = true
  try {
    const [supplierResult, locationList, itemList, poList] = await Promise.all([
      listSuppliers({ is_active: true, page_size: 200 }),
      listLocations({ is_active: true }),
      listInventoryItems(),
      fetchAllOpenOrders(),
    ])

    suppliers.value = supplierResult.items
    locations.value = locationList
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
  try {
    const result = await listGoodsReceipts({
      status: statusFilter.value ?? undefined,
      location_id: locationFilter.value ?? undefined,
      page: page.value,
      page_size: pageSize.value,
    })

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

async function selectReceipt(grn: GoodsReceipt) {
  detailLoading.value = true
  try {
    selected.value = await getGoodsReceipt(grn.id)
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to load goods receipt.')
  }
  finally {
    detailLoading.value = false
  }
}

function openCreate() {
  createForm.po_id = null
  createForm.supplier_id = null
  createForm.location_id = null
  createForm.receipt_date = new Date().toISOString().slice(0, 10)
  createForm.notes = ''
  createForm.allow_over_receipt = false
  manualLines.value = []
  createDialogOpen.value = true
}

const createFromPo = computed(() => !!createForm.po_id)

function addManualLine() {
  manualLines.value.push({ item_id: '', qty: 1, unit_cost: 0 })
}

function removeManualLine(index: number) {
  manualLines.value.splice(index, 1)
}

async function submitCreate() {
  actionError.value = ''
  saving.value = true
  try {
    const po = createForm.po_id ? poById.value.get(createForm.po_id) : null
    const supplierId = po ? po.supplier_id : createForm.supplier_id
    const locationId = po ? po.location_id : createForm.location_id

    if (!supplierId || !locationId) {
      actionError.value = 'Supplier and location are required.'

      return
    }

    const payload = {
      supplier_id: supplierId,
      location_id: locationId,
      receipt_date: createForm.receipt_date,
      notes: createForm.notes || null,
      allow_over_receipt: createForm.allow_over_receipt,
      po_id: createForm.po_id,
      lines: createFromPo.value
        ? []
        : manualLines.value.filter(l => l.item_id && l.qty > 0),
    }

    const grn = await createGoodsReceipt(payload)

    actionSuccess.value = `Created goods receipt ${grn.grn_no}.`
    createDialogOpen.value = false
    await loadReceipts()
    await selectReceipt(grn)
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to create goods receipt.')
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
    selected.value = await confirmGoodsReceipt(selected.value.id)
    actionSuccess.value = `Confirmed ${selected.value.grn_no}.`
    await loadReceipts()
    openOrders.value = await fetchAllOpenOrders()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to confirm.')
  }
  finally {
    saving.value = false
  }
}

async function doVoid() {
  if (!selected.value)
    return
  actionError.value = ''
  saving.value = true
  try {
    selected.value = await voidGoodsReceipt(selected.value.id)
    actionSuccess.value = `Voided ${selected.value.grn_no}.`
    await loadReceipts()
    openOrders.value = await fetchAllOpenOrders()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to void.')
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
    const no = selected.value.grn_no

    await deleteGoodsReceipt(selected.value.id)
    actionSuccess.value = `Deleted draft ${no}.`
    selected.value = null
    await loadReceipts()
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
          Goods Receipts 收貨單
        </div>
      </VCol>
      <VCol cols="auto">
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="loading"
          @click="loadReceipts"
        >
          Refresh
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          class="ms-2"
          @click="openCreate"
        >
          New receipt
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
              :items="locations.map(l => ({ value: l.id, title: l.name_en || l.name_zh || l.id }))"
              label="Location"
              density="comfortable"
              hide-details
              clearable
              @update:model-value="onFiltersChange"
            />
          </VCardText>
          <VList density="compact">
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
            <VListItem v-if="receipts.length === 0 && !loading">
              <VListItemTitle class="text-medium-emphasis">
                No goods receipts yet.
              </VListItemTitle>
            </VListItem>
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
            <span>{{ selected.grn_no }}</span>
            <InventoryStatusChip :status="selected.status" />
            <VSpacer />
            <template v-if="isDraft">
              <VBtn
                color="primary"
                size="small"
                :loading="saving"
                @click="doConfirm"
              >
                Confirm
              </VBtn>
              <VBtn
                variant="text"
                color="error"
                size="small"
                :loading="saving"
                @click="doDelete"
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
              @click="doVoid"
            >
              Void
            </VBtn>
          </VCardTitle>
          <VCardSubtitle>
            {{ selected.supplier_name || '—' }} · {{ selected.location_name || '—' }} ·
            {{ selected.receipt_date }}
            <template v-if="selected.po_no">
              · PO {{ selected.po_no }}
            </template>
          </VCardSubtitle>
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
                <td class="text-end">
                  {{ line.qty }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(line.unit_cost) }}
                </td>
                <td class="text-end font-weight-medium">
                  {{ fmtMoney(line.qty * line.unit_cost) }}
                </td>
              </tr>
            </tbody>
          </VTable>
        </VCard>
        <VCard v-else>
          <VCardText class="text-center text-medium-emphasis py-12">
            Select a goods receipt or create a new one.
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <VDialog
      v-model="createDialogOpen"
      max-width="640"
    >
      <VCard title="New goods receipt">
        <VCardText>
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
              label="Supplier"
              density="comfortable"
              class="mb-3"
            />
            <VSelect
              v-model="createForm.location_id"
              :items="locations.map(l => ({ value: l.id, title: l.name_en || l.name_zh || l.id }))"
              label="Location"
              density="comfortable"
              class="mb-3"
            />
          </template>
          <VTextField
            v-model="createForm.receipt_date"
            label="Receipt date"
            type="date"
            density="comfortable"
            class="mb-3"
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
            class="mb-3"
          />

          <template v-if="!createFromPo">
            <VDivider class="my-3" />
            <div
              v-for="(line, index) in manualLines"
              :key="index"
              class="d-flex gap-3 mb-2 align-center"
            >
              <VAutocomplete
                v-model="line.item_id"
                :items="items.map(i => ({ value: i.id, title: [i.sku_code, i.name_zh].filter(Boolean).join(' · ') }))"
                label="Item"
                density="compact"
                hide-details
                variant="outlined"
                style="flex: 3"
              />
              <VTextField
                v-model.number="line.qty"
                label="Qty"
                type="number"
                min="1"
                density="compact"
                hide-details
                variant="outlined"
                style="flex: 1"
              />
              <VTextField
                v-model.number="line.unit_cost"
                label="Unit cost"
                type="number"
                min="0"
                step="0.01"
                density="compact"
                hide-details
                variant="outlined"
                style="flex: 1"
              />
              <VBtn
                icon="ri-close-line"
                variant="text"
                size="x-small"
                color="error"
                @click="removeManualLine(index)"
              />
            </div>
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
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="createDialogOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :loading="saving"
            :disabled="!createFromPo && manualLines.every(l => !l.item_id)"
            @click="submitCreate"
          >
            Create
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>
