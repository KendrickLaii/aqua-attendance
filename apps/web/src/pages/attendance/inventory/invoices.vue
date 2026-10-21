<script setup lang="ts">
import {
  type InventoryInvoice,
  type InventoryInvoicePrintDoc,
  type InventoryInvoiceStatus,
  type InventoryPaymentStatus,
  type InventoryReceiptPaidBy,
  RECEIPT_PAID_BY_OPTIONS,
  createInvoice,
  createReceipt,
  deleteInvoice,
  getInvoice,
  getInvoicePrint,
  issueInvoice,
  listInvoices,
  voidInvoice,
} from '@/api/attendance/inventoryInvoicing'
import {
  type InventoryCustomer,
  listCustomers,
} from '@/api/attendance/inventorySales'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import AttendancePaginationBar from '@/components/attendance/AttendancePaginationBar.vue'
import InventoryInvoicePrintDialog from '@/components/attendance/inventory/InventoryInvoicePrintDialog.vue'
import InventoryStatusChip from '@/components/attendance/inventory/InventoryStatusChip.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

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
const statusFilter = ref<InventoryInvoiceStatus | null>(null)
const paymentFilter = ref<InventoryPaymentStatus | null>(null)
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
const payAmount = ref<number | null>(null)
const payMethod = ref<InventoryReceiptPaidBy>('cash')
const payReference = ref('')
const payDate = ref('')

// create invoice dialog (from a DO id — usually reached via delivery-orders page)
const createOpen = ref(false)
const createDoId = ref('')
const createNotes = ref('')

const headers = [
  { title: 'Invoice No', key: 'invoice_no' },
  { title: 'Customer', key: 'customer_name' },
  { title: 'DO', key: 'do_no' },
  { title: 'Date', key: 'issue_date' },
  { title: 'Total', key: 'total' },
  { title: 'Balance', key: 'balance' },
  { title: 'Status', key: 'status' },
  { title: 'Payment', key: 'payment_status' },
]

async function load() {
  loading.value = true
  loadError.value = ''
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

    invoices.value = res.items
    total.value = res.total
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Operation failed.')
  }
  finally {
    loading.value = false
  }
}

function onRowClick(_e: Event, row: { item: InventoryInvoice }) {
  selected.value = row.item
}

function openCreate() {
  createDoId.value = ''
  createNotes.value = ''
  createOpen.value = true
}

async function submitCreate() {
  if (!createDoId.value)
    return
  saving.value = true
  actionError.value = ''
  try {
    const inv = await createInvoice({ do_id: createDoId.value, notes: createNotes.value || null })

    createOpen.value = false
    actionSuccess.value = `Invoice draft created for DO ${inv.do_no}`
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

async function onIssue() {
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

async function onVoid() {
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

async function onDelete() {
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
  payAmount.value = selected.value.balance
  payMethod.value = 'cash'
  payReference.value = ''
  payDate.value = ''
  payOpen.value = true
}

async function submitPay() {
  if (!selected.value || !payAmount.value)
    return
  saving.value = true
  actionError.value = ''
  try {
    await createReceipt({
      invoice_id: selected.value.id,
      amount: payAmount.value,
      paid_by: payMethod.value,
      reference_no: payReference.value || null,
      receipt_date: payDate.value || null,
    })
    payOpen.value = false
    actionSuccess.value = 'Receipt posted'
    selected.value = await getInvoice(selected.value.id)
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
})
</script>

<template>
  <div>
    <VCard>
      <VCardTitle class="d-flex align-center flex-wrap gap-2">
        <span>Invoices 庫存發票</span>
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
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          @click="openCreate"
        >
          New Invoice
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
          :items="invoices"
          :loading="loading"
          density="compact"
          @click:row="onRowClick"
        >
          <template #item.invoice_no="{ item }">
            <span class="font-weight-medium">{{ item.invoice_no || '(draft)' }}</span>
          </template>
          <template #item.total="{ item }">
            {{ fmtMoney(item.total) }}
          </template>
          <template #item.balance="{ item }">
            {{ fmtMoney(item.balance) }}
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
          <div class="mb-2 text-body-2">
            <strong>Customer:</strong> {{ selected.buyer_name }} ·
            <strong>SO:</strong> {{ selected.so_no }} ·
            <strong>DO:</strong> {{ selected.do_no }}
          </div>
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
                  Discount
                </th>
                <th class="text-end">
                  Amount
                </th>
                <th class="text-end">
                  Credited
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="line in selected.lines"
                :key="line.id"
              >
                <td>{{ [line.sku_code, line.name_zh].filter(Boolean).join(' · ') }}</td>
                <td class="text-end">
                  {{ line.qty }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(line.unit_price) }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(line.discount_amount) }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(line.amount) }}
                </td>
                <td class="text-end">
                  {{ line.credited_qty }}
                </td>
              </tr>
            </tbody>
          </VTable>
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

          <div
            v-if="selected.receipts.length"
            class="mt-4"
          >
            <div class="text-subtitle-2 mb-1">
              Receipts
            </div>
            <div
              v-for="r in selected.receipts"
              :key="r.id"
              class="text-body-2"
            >
              {{ r.receipt_no }} · {{ fmtMoney(r.amount) }} · {{ r.paid_by }} · {{ r.status }}
            </div>
          </div>
          <div
            v-if="selected.credit_notes.length"
            class="mt-4"
          >
            <div class="text-subtitle-2 mb-1">
              Credit Notes
            </div>
            <div
              v-for="s in selected.credit_notes"
              :key="s.id"
              class="text-body-2"
            >
              {{ s.scn_no }} · {{ fmtMoney(s.total) }} · {{ s.status }}
            </div>
          </div>
        </VCardText>
        <VCardActions>
          <VBtn
            v-if="selected.status === 'draft'"
            color="primary"
            :loading="saving"
            @click="onIssue"
          >
            Issue
          </VBtn>
          <VBtn
            v-if="selected.status === 'issued' && selected.balance > 0"
            color="success"
            variant="tonal"
            @click="openPay"
          >
            Record Payment
          </VBtn>
          <VBtn
            v-if="selected.status === 'issued'"
            variant="tonal"
            :loading="saving"
            @click="onVoid"
          >
            Void
          </VBtn>
          <VBtn
            v-if="selected.status === 'draft'"
            color="error"
            variant="tonal"
            :loading="saving"
            @click="onDelete"
          >
            Delete
          </VBtn>
          <VSpacer />
          <VBtn
            v-if="selected.invoice_no"
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
      max-width="440"
    >
      <VCard>
        <VCardTitle>New Invoice from Delivery Order</VCardTitle>
        <VCardText>
          <VTextField
            v-model="createDoId"
            label="Delivery Order ID"
            hint="Paste a confirmed DO id (or use Create Invoice on the Delivery Orders page)"
            persistent-hint
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
            @click="createOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :disabled="!createDoId"
            :loading="saving"
            @click="submitCreate"
          >
            Create
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog
      v-model="payOpen"
      max-width="440"
    >
      <VCard>
        <VCardTitle>Record Payment</VCardTitle>
        <VCardText>
          <VTextField
            v-model.number="payAmount"
            type="number"
            label="Amount"
            :hint="`Balance ${fmtMoney(selected?.balance)}`"
            persistent-hint
          />
          <VSelect
            v-model="payMethod"
            :items="RECEIPT_PAID_BY_OPTIONS"
            label="Paid by"
            class="mt-3"
          />
          <VTextField
            v-model="payReference"
            label="Reference no."
            class="mt-3"
          />
          <VTextField
            v-model="payDate"
            type="date"
            label="Receipt date"
            class="mt-3"
          />
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="payOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :disabled="!payAmount"
            :loading="saving"
            @click="submitPay"
          >
            Post Receipt
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <InventoryInvoicePrintDialog
      v-model="printOpen"
      :doc="printDoc"
    />
  </div>
</template>
