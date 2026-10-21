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
const confirmedGrns = ref<GoodsReceipt[]>([])

const returns = ref<PurchaseReturn[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
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
  try {
    const result = await listPurchaseReturns({
      status: statusFilter.value ?? undefined,
      location_id: locationFilter.value ?? undefined,
      page: page.value,
      page_size: pageSize.value,
    })

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
  createForm.supplier_id = null
  createForm.location_id = null
  createForm.grn_id = null
  createForm.return_date = new Date().toISOString().slice(0, 10)
  createForm.notes = ''
  createLines.value = []
  addCreateLine()
  createDialogOpen.value = true
}

function addCreateLine() {
  createLines.value.push({ item_id: '', qty: 1, unit_cost: 0 })
}

function removeCreateLine(index: number) {
  createLines.value.splice(index, 1)
}

async function submitCreate() {
  actionError.value = ''
  saving.value = true
  try {
    if (!createForm.supplier_id || !createForm.location_id) {
      actionError.value = 'Supplier and location are required.'

      return
    }
    const lines = createLines.value.filter(l => l.item_id && l.qty > 0)

    const prt = await createPurchaseReturn({
      supplier_id: createForm.supplier_id,
      location_id: createForm.location_id,
      grn_id: createForm.grn_id,
      return_date: createForm.return_date,
      notes: createForm.notes || null,
      lines,
    })

    actionSuccess.value = `Created purchase return ${prt.prt_no}.`
    createDialogOpen.value = false
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

async function doConfirm() {
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

async function doVoid() {
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

async function doDelete() {
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
                No purchase returns yet.
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
            {{ selected.return_date }}
            <template v-if="selected.grn_no">
              · against {{ selected.grn_no }}
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
            label="Supplier"
            density="comfortable"
            class="mb-3"
          />
          <VSelect
            v-model="createForm.location_id"
            :items="locationOptions"
            label="Location"
            density="comfortable"
            class="mb-3"
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
            label="Return date"
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

          <VDivider class="my-3" />
          <div
            v-for="(line, index) in createLines"
            :key="index"
            class="d-flex gap-3 mb-2 align-center"
          >
            <VAutocomplete
              v-model="line.item_id"
              :items="itemOptions"
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
            @click="createDialogOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :loading="saving"
            :disabled="!createLines.some(l => l.item_id)"
            @click="submitCreate"
          >
            Create
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>
