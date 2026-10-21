<script setup lang="ts">
import {
  type InventoryCreditNote,
  type InventoryCreditNotePrintDoc,
  type InventoryCreditNoteStatus,
  type InventoryInvoice,
  confirmCreditNote,
  createCreditNote,
  deleteCreditNote,
  getCreditNote,
  getCreditNotePrint,
  getInvoice,
  listCreditNotes,
  listInvoices,
  voidCreditNote,
} from '@/api/attendance/inventoryInvoicing'
import { type InventoryCustomer, listCustomers } from '@/api/attendance/inventorySales'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import AttendanceConfirmDialog from '@/components/attendance/AttendanceConfirmDialog.vue'
import AttendancePaginationBar from '@/components/attendance/AttendancePaginationBar.vue'
import InventoryCreditNotePrintDialog from '@/components/attendance/inventory/InventoryCreditNotePrintDialog.vue'
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
const saving = ref(false)
const loadError = ref('')
const actionError = ref('')
const actionSuccess = ref('')

useAutoClearAlerts(loadError)
useAutoClearAlerts(actionError)
useAutoClearAlerts(actionSuccess)

const customers = ref<InventoryCustomer[]>([])
const locations = ref<LocationItem[]>([])

const notes = ref<InventoryCreditNote[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const statusFilter = ref<InventoryCreditNoteStatus | null>(null)
const locationFilter = ref<string | null>(null)
const search = ref('')

const listReq = useLatestRequest()
const confirm = useConfirmAction()
const dirty = useDirtyGuard('Discard the credit note being edited?')

const selected = ref<InventoryCreditNote | null>(null)

const statusOptions = [
  { value: 'draft' as const, title: 'Draft' },
  { value: 'confirmed' as const, title: 'Confirmed' },
  { value: 'void' as const, title: 'Void' },
]

const printOpen = ref(false)
const printDoc = ref<InventoryCreditNotePrintDoc | null>(null)

// create dialog
const createOpen = ref(false)
const issuedInvoices = ref<InventoryInvoice[]>([])
const createInvoiceId = ref<string | null>(null)
const createInvoice = ref<InventoryInvoice | null>(null)
const createReason = ref('')
const createDate = ref('')
const createLines = ref<{ invoice_line_id: string; label: string; max_qty: number; qty: number; restock: boolean }[]>([])

let suppressDirty = false
watch([createReason, createDate, createLines], () => {
  if (!suppressDirty && createOpen.value)
    dirty.dirty.value = true
}, { deep: true })

function createLineError(line: { qty: number; max_qty: number }): string {
  if (!Number.isInteger(line.qty) || line.qty < 0)
    return 'Qty must be a whole number ≥ 0'
  if (line.qty > line.max_qty)
    return `Qty cannot exceed ${line.max_qty}`

  return ''
}

const createLineErrors = computed(() => createLines.value.map(createLineError))

const createInvalid = computed(() =>
  !createInvoiceId.value
  || !createReason.value
  || !createLines.value.some(l => l.qty > 0)
  || createLineErrors.value.some(Boolean),
)

function closeCreate() {
  if (dirty.confirmDiscard())
    createOpen.value = false
}

const chainSteps = computed<DocChainStep[]>(() => {
  const scn = selected.value
  if (!scn)
    return []

  return [
    { label: `Invoice ${scn.invoice_no}`, state: 'done', to: '/attendance/inventory/invoices' },
    { label: `CN ${scn.scn_no}`, state: scn.status === 'void' ? 'void' : 'current', hint: scn.status },
    { label: 'Restock', state: scn.status === 'confirmed' ? 'done' : 'todo' },
  ]
})

const headers = [
  { title: 'CN No', key: 'scn_no' },
  { title: 'Invoice', key: 'invoice_no' },
  { title: 'Customer', key: 'customer_name' },
  { title: 'Date', key: 'credit_date' },
  { title: 'Total', key: 'total', align: 'end' as const },
  { title: 'Status', key: 'status' },
]

async function load() {
  loading.value = true
  loadError.value = ''

  const token = listReq.next()
  try {
    const res = await listCreditNotes({
      location_id: locationFilter.value || undefined,
      status: statusFilter.value || undefined,
      search: search.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })

    if (!listReq.isLatest(token))
      return
    notes.value = res.items
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

async function openDetail(scn: InventoryCreditNote) {
  try {
    selected.value = await getCreditNote(scn.id)
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Operation failed.')
  }
}

function onRowClick(_e: Event, row: { item: InventoryCreditNote }) {
  openDetail(row.item)
}

async function openCreate() {
  suppressDirty = true
  createInvoiceId.value = null
  createInvoice.value = null
  createReason.value = ''
  createDate.value = ''
  createLines.value = []
  createOpen.value = true
  dirty.markClean()
  nextTick(() => {
    suppressDirty = false
  })
  try {
    const res = await listInvoices({ status: 'issued', page_size: 200 })

    issuedInvoices.value = res.items
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Operation failed.')
  }
}

async function onPickInvoice() {
  if (!createInvoiceId.value) {
    createInvoice.value = null
    createLines.value = []

    return
  }
  try {
    const inv = await getInvoice(createInvoiceId.value)

    createInvoice.value = inv
    createLines.value = inv.lines.map(l => ({
      invoice_line_id: l.id,
      label: `${l.sku_code} · ${l.name_zh}`,
      max_qty: l.qty - l.credited_qty,
      qty: 0,
      restock: true,
    }))
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Operation failed.')
  }
}

async function submitCreate() {
  if (createInvalid.value) {
    actionError.value = 'Please fix the highlighted fields before creating.'

    return
  }

  const lines = createLines.value
    .filter(l => l.qty > 0)
    .map(l => ({ invoice_line_id: l.invoice_line_id, qty: l.qty, restock: l.restock }))

  saving.value = true
  actionError.value = ''
  try {
    const scn = await createCreditNote({
      invoice_id: createInvoiceId.value ?? '',
      credit_date: createDate.value || null,
      reason: createReason.value,
      lines,
    })

    createOpen.value = false
    dirty.markClean()
    actionSuccess.value = `Credit note ${scn.scn_no} created`
    await load()
    selected.value = scn
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Operation failed.')
  }
  finally {
    saving.value = false
  }
}

function askConfirm() {
  const scn = selected.value
  if (!scn)
    return
  const restocking = scn.lines.filter(l => l.restock).reduce((s, l) => s + l.qty, 0)

  confirm.ask(
    `Confirm ${scn.scn_no}?`,
    `Confirming credits ${fmtMoney(scn.total)} against invoice ${scn.invoice_no}${restocking ? ` and returns ${restocking} item${restocking === 1 ? '' : 's'} to stock` : ''}.`,
    { label: 'Confirm', color: 'primary' },
    performConfirm,
  )
}

async function performConfirm() {
  if (!selected.value)
    return
  saving.value = true
  actionError.value = ''
  try {
    selected.value = await confirmCreditNote(selected.value.id)
    actionSuccess.value = `Credit note ${selected.value.scn_no} confirmed`
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
  const scn = selected.value
  if (!scn)
    return
  confirm.ask(
    `Void ${scn.scn_no}?`,
    `Voiding reverses the ${fmtMoney(scn.total)} credit (and any restock) on invoice ${scn.invoice_no}. This cannot be undone.`,
    { label: 'Void' },
    performVoid,
  )
}

async function performVoid() {
  if (!selected.value)
    return
  saving.value = true
  actionError.value = ''
  try {
    selected.value = await voidCreditNote(selected.value.id)
    actionSuccess.value = 'Credit note voided'
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
    `Delete draft ${selected.value.scn_no}?`,
    'The draft credit note will be permanently deleted.',
    { label: 'Delete' },
    performDelete,
  )
}

async function performDelete() {
  if (!selected.value)
    return
  saving.value = true
  actionError.value = ''
  try {
    await deleteCreditNote(selected.value.id)
    actionSuccess.value = 'Draft credit note deleted'
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

async function onPrint() {
  if (!selected.value)
    return
  try {
    printDoc.value = await getCreditNotePrint(selected.value.id)
    printOpen.value = true
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Operation failed.')
  }
}

function fmtMoney(value: number | null | undefined): string {
  return (value ?? 0).toFixed(2)
}

watch([statusFilter, locationFilter], () => {
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
})
</script>

<template>
  <div>
    <VCard>
      <VCardTitle class="d-flex align-center flex-wrap gap-2">
        <span>Credit Notes 貸項單</span>
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
          v-model="locationFilter"
          :items="locations.map(l => ({ value: l.id, title: l.name_en || l.name_zh || l.code }))"
          density="compact"
          label="Location"
          clearable
          hide-details
          style="max-width: 160px"
        />
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          @click="openCreate"
        >
          New Credit Note
        </VBtn>
      </VCardTitle>
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
          :items="notes"
          :loading="loading"
          density="compact"
          no-data-text="No credit notes yet — create one from an issued invoice."
          @click:row="onRowClick"
        >
          <template #item.scn_no="{ item }">
            <span class="font-weight-medium">{{ item.scn_no }}</span>
          </template>
          <template #item.total="{ item }">
            <span class="tabular-nums">{{ fmtMoney(item.total) }}</span>
          </template>
          <template #item.status="{ item }">
            <InventoryStatusChip :status="item.status" />
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
      max-width="720"
      @update:model-value="v => { if (!v) selected = null }"
    >
      <VCard v-if="selected">
        <VCardTitle class="d-flex align-center">
          <span>{{ selected.scn_no }}</span>
          <VSpacer />
          <InventoryStatusChip :status="selected.status" />
        </VCardTitle>
        <VCardText>
          <InventoryDocChain
            :steps="chainSteps"
            class="mb-3"
          />
          <div class="mb-2 text-body-2">
            <strong>Customer:</strong> {{ selected.customer_name }} ·
            <strong>Invoice:</strong> {{ selected.invoice_no }} ·
            <strong>Date:</strong> {{ selected.credit_date }}
          </div>
          <div class="mb-3 text-body-2">
            <strong>Reason:</strong> {{ selected.reason }}
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
                    Unit amount
                  </th>
                  <th class="text-end">
                    Amount
                  </th>
                  <th class="text-center">
                    Restock
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
                    {{ fmtMoney(line.unit_amount) }}
                  </td>
                  <td class="text-end tabular-nums">
                    {{ fmtMoney(line.amount) }}
                  </td>
                  <td class="text-center">
                    {{ line.restock ? 'Yes' : 'No' }}
                  </td>
                </tr>
              </tbody>
            </VTable>
          </div>
          <div class="text-end mt-3 font-weight-bold">
            Total: {{ fmtMoney(selected.total) }}
          </div>
        </VCardText>
        <VCardActions>
          <VBtn
            v-if="selected.status === 'draft'"
            color="primary"
            prepend-icon="ri-arrow-right-line"
            :loading="saving"
            @click="askConfirm"
          >
            Next: Confirm
          </VBtn>
          <VBtn
            v-if="selected.status === 'confirmed'"
            variant="tonal"
            :loading="saving"
            @click="askVoid"
          >
            Void
          </VBtn>
          <VBtn
            v-if="selected.status === 'draft'"
            color="error"
            variant="tonal"
            :loading="saving"
            @click="askDelete"
          >
            Delete
          </VBtn>
          <VSpacer />
          <VBtn
            variant="text"
            prepend-icon="ri-printer-line"
            @click="onPrint"
          >
            Print
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog
      v-model="createOpen"
      max-width="720"
    >
      <VCard>
        <VCardTitle>New Credit Note</VCardTitle>
        <VCardText>
          <VSelect
            v-model="createInvoiceId"
            :items="issuedInvoices.map(i => ({ value: i.id, title: `${i.invoice_no} · ${i.buyer_name} · ${fmtMoney(i.total)}` }))"
            label="Issued invoice *"
            :error="!createInvoiceId"
            @update:model-value="onPickInvoice"
          />
          <VTextField
            v-model="createReason"
            label="Reason *"
            class="mt-3"
            :error="!createReason"
          />
          <VTextField
            v-model="createDate"
            type="date"
            label="Credit date"
            class="mt-3"
          />
          <div
            v-if="createLines.length"
            class="overflow-x-auto mt-3"
          >
            <VTable density="compact">
              <thead>
                <tr>
                  <th>Item</th>
                  <th class="text-end">
                    Credited max
                  </th>
                  <th style="width: 120px">
                    Qty
                  </th>
                  <th class="text-center">
                    Restock
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(line, i) in createLines"
                  :key="line.invoice_line_id"
                >
                  <td>{{ line.label }}</td>
                  <td class="text-end tabular-nums">
                    {{ line.max_qty }}
                  </td>
                  <td>
                    <VTextField
                      v-model.number="line.qty"
                      type="number"
                      density="compact"
                      hide-details="auto"
                      :min="0"
                      :max="line.max_qty"
                      step="1"
                      :error="!!createLineErrors[i]"
                      :error-messages="createLineErrors[i]"
                    />
                  </td>
                  <td class="text-center">
                    <VCheckbox
                      v-model="line.restock"
                      hide-details
                      density="compact"
                    />
                  </td>
                </tr>
              </tbody>
            </VTable>
          </div>
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
            :disabled="createInvalid"
            :loading="saving"
            @click="submitCreate"
          >
            Create
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <InventoryCreditNotePrintDialog
      v-model="printOpen"
      :doc="printDoc"
    />

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
  </div>
</template>
