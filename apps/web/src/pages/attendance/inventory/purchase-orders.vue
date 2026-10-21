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

const orders = ref<PurchaseOrder[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const supplierFilter = ref<string | null>(null)
const locationFilter = ref<string | null>(null)
const statusFilter = ref<PurchaseOrderStatus | null>(null)

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
  try {
    const result = await listPurchaseOrders({
      supplier_id: supplierFilter.value ?? undefined,
      location_id: locationFilter.value ?? undefined,
      status: statusFilter.value ?? undefined,
      page: page.value,
      page_size: pageSize.value,
    })

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

async function selectOrder(po: PurchaseOrder) {
  detailLoading.value = true
  try {
    const detail = await getPurchaseOrder(po.id)

    selected.value = detail
    resetEditor(detail)
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to load purchase order.')
  }
  finally {
    detailLoading.value = false
  }
}

function resetEditor(po: PurchaseOrder | null) {
  if (!po) {
    editLines.value = []

    return
  }
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
}

function newOrder() {
  selected.value = null
  editForm.supplier_id = null
  editForm.location_id = null
  editForm.order_date = new Date().toISOString().slice(0, 10)
  editForm.expected_date = ''
  editForm.discount_amount = 0
  editForm.notes = ''
  editLines.value = []
  addLine()
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

  const lines: PurchaseOrderLinePayload[] = editLines.value
    .filter(l => l.item_id && l.ordered_qty > 0)
    .map(l => ({
      item_id: l.item_id as string,
      ordered_qty: l.ordered_qty,
      unit_cost: l.unit_cost,
      discount_amount: l.discount_amount || 0,
    }))

  if (!editForm.supplier_id || !editForm.location_id) {
    actionError.value = 'Supplier and location are required.'

    return
  }

  saving.value = true
  try {
    const payload = {
      supplier_id: editForm.supplier_id,
      location_id: editForm.location_id,
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

async function doOrder() {
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

async function doCancel() {
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

async function doDelete() {
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
          <VList density="compact">
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
                No purchase orders yet.
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
          <VCardTitle class="d-flex align-center gap-3">
            <span>{{ selected ? selected.po_no : 'New purchase order' }}</span>
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
                color="info"
                size="small"
                :loading="saving"
                @click="doOrder"
              >
                Order
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
            <template v-if="selected && ['ordered', 'partial'].includes(selected.status)">
              <VBtn
                color="primary"
                size="small"
                :loading="saving"
                @click="receiveGoods"
              >
                Receive goods
              </VBtn>
              <VBtn
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
                  v-model="editForm.supplier_id"
                  :items="supplierOptions"
                  label="Supplier"
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
                  v-model="editForm.expected_date"
                  label="Expected date"
                  type="date"
                  density="comfortable"
                  :readonly="!isDraft && !!selected"
                />
              </VCol>
              <VCol cols="12">
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
                    Unit cost
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
                      v-model.number="line.ordered_qty"
                      type="number"
                      min="1"
                      density="compact"
                      hide-details
                      variant="outlined"
                    />
                    <template v-else>
                      {{ line.ordered_qty }}
                    </template>
                  </td>
                  <td class="text-end">
                    <VTextField
                      v-if="isDraft"
                      v-model.number="line.unit_cost"
                      type="number"
                      min="0"
                      step="0.01"
                      density="compact"
                      hide-details
                      variant="outlined"
                    />
                    <template v-else>
                      {{ fmtMoney(line.unit_cost) }}
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
                    {{ fmtMoney(Math.max(0, (line.ordered_qty || 0) * (line.unit_cost || 0) - (line.discount_amount || 0))) }}
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
            Select a purchase order or create a new one.
          </VCardText>
        </VCard>
      </VCol>
    </VRow>
  </VContainer>
</template>
