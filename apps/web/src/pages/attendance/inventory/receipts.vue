<script setup lang="ts">
import { type InventoryWarehouse, listWarehouses } from '@/api/attendance/inventory'

import {
  type InventoryReceipt,
  type InventoryReceiptPrintDoc,
  type InventoryReceiptStatus,
  RECEIPT_PAID_BY_OPTIONS,
  getReceiptPrint,
  listInvoices,
  listReceipts,
  voidReceipt,
} from '@/api/attendance/inventoryInvoicing'
import { type InventoryCustomer, listCustomers } from '@/api/attendance/inventorySales'
import AttendanceConfirmDialog from '@/components/attendance/AttendanceConfirmDialog.vue'
import AttendancePaginationBar from '@/components/attendance/AttendancePaginationBar.vue'
import InventoryReceiptPrintDialog from '@/components/attendance/inventory/InventoryReceiptPrintDialog.vue'
import InventoryRecordPaymentDialog, { type PaymentInvoiceOption } from '@/components/attendance/inventory/InventoryRecordPaymentDialog.vue'
import InventoryEmptyState from '@/components/attendance/inventory/InventoryEmptyState.vue'
import InventoryStatusChip from '@/components/attendance/inventory/InventoryStatusChip.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { formatMoney } from '@/utils/inventoryDisplay'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { useConfirmAction } from '@/composables/useConfirmAction'
import { useLatestRequest } from '@/composables/useLatestRequest'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()
const toast = useToast()

const loading = ref(true)
const saving = ref(false)
const loadError = ref('')

useAutoClearAlerts(loadError)

const customers = ref<InventoryCustomer[]>([])
const warehouses = ref<InventoryWarehouse[]>([])

const receipts = ref<InventoryReceipt[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const statusFilter = ref<InventoryReceiptStatus | null>(null)
const customerFilter = ref<string | null>(null)
const warehouseFilter = ref<string | null>(null)
const search = ref('')

const listReq = useLatestRequest()
const confirm = useConfirmAction()

const printOpen = ref(false)
const printDoc = ref<InventoryReceiptPrintDoc | null>(null)

// record payment dialog
const payOpen = ref(false)
const payInvoiceOptions = ref<PaymentInvoiceOption[]>([])
const payInvoicesLoading = ref(false)

async function openPay() {
  payOpen.value = true
  payInvoicesLoading.value = true
  try {
    const res = await listInvoices({ status: 'issued', page_size: 200 })

    payInvoiceOptions.value = res.items
      .filter(inv => inv.balance > 0)
      .map(inv => ({
        value: inv.id,
        title: `${inv.invoice_no} · ${inv.buyer_name || '—'} · 餘額 ${formatMoney(inv.balance)}`,
        invoice: { id: inv.id, invoice_no: inv.invoice_no ?? '', buyer_name: inv.buyer_name, balance: inv.balance },
      }))
  }
  catch (e) {
    toast.show(formatApiError(e, 'Operation failed.'), 'error', 6000)
  }
  finally {
    payInvoicesLoading.value = false
  }
}

async function onPaymentSaved() {
  await load()
}

const statusOptions = [
  { value: 'posted' as const, title: 'Posted' },
  { value: 'void' as const, title: 'Void' },
]

const headers = [
  { title: 'Receipt No', key: 'receipt_no' },
  { title: 'Invoice', key: 'invoice_no' },
  { title: 'Customer', key: 'customer_name' },
  { title: 'Date', key: 'receipt_date' },
  { title: 'Amount', key: 'amount', align: 'end' as const },
  { title: 'Paid by', key: 'paid_by' },
  { title: 'Reference', key: 'reference_no' },
  { title: 'Status', key: 'status' },
  { title: '', key: 'actions', sortable: false },
]

function paidByLabel(value: string): string {
  return RECEIPT_PAID_BY_OPTIONS.find(o => o.value === value)?.title ?? value
}

async function load() {
  loading.value = true
  loadError.value = ''

  const token = listReq.next()
  try {
    const res = await listReceipts({
      customer_id: customerFilter.value || undefined,
      warehouse_id: warehouseFilter.value || undefined,
      status: statusFilter.value || undefined,
      search: search.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })

    if (!listReq.isLatest(token))
      return
    receipts.value = res.items
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

function askVoid(rc: InventoryReceipt) {
  confirm.ask(
    `Void ${rc.receipt_no}?`,
    `作廢會把 ${formatMoney(rc.amount)} 收款從發票餘額中移除。`,
    { label: 'Void', details: ['發票變回未收齊狀態', '不能復原'] },
    async () => {
      saving.value = true
      try {
        await voidReceipt(rc.id)
        toast.show(`Receipt ${rc.receipt_no} voided`)
        await load()
      }
      catch (e) {
        toast.show(formatApiError(e, 'Operation failed.'), 'error', 6000)
      }
      finally {
        saving.value = false
      }
    },
  )
}

async function onPrint(rc: InventoryReceipt) {
  try {
    printDoc.value = await getReceiptPrint(rc.id)
    printOpen.value = true
  }
  catch (e) {
    toast.show(formatApiError(e, 'Operation failed.'), 'error', 6000)
  }
}

watch([statusFilter, customerFilter, warehouseFilter], () => {
  page.value = 1
  load()
})

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  try {
    const [custs, locs] = await Promise.all([
      listCustomers({ is_active: true, page_size: 200 }),
      listWarehouses(),
    ])

    customers.value = custs.items
    warehouses.value = locs
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
        <span>Sales Receipts 銷售收據</span>
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
          v-model="customerFilter"
          :items="customers.map(c => ({ value: c.id, title: c.name_zh }))"
          density="compact"
          label="Customer"
          clearable
          hide-details
          style="max-width: 180px"
        />
        <VSelect
          v-model="warehouseFilter"
          :items="warehouses.map(l => ({ value: l.id, title: l.name_en || l.name_zh || l.code }))"
          density="compact"
          label="Warehouse 倉庫"
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
          @click="openPay"
        >
          Record Payment
        </VBtn>
      </VCardTitle>
      <VCardSubtitle>
        這一頁管理銷售收據：記錄已收到的款項，按 Record Payment 選一張未收齊的發票。
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

        <VDataTable
          :headers="headers"
          :items="receipts"
          :loading="loading"
          density="compact"
        >
          <template #item.receipt_no="{ item }">
            <span class="font-weight-medium">{{ item.receipt_no }}</span>
          </template>
          <template #item.amount="{ item }">
            <span class="tabular-nums">{{ formatMoney(item.amount) }}</span>
          </template>
          <template #item.paid_by="{ item }">
            {{ paidByLabel(item.paid_by) }}
          </template>
          <template #item.status="{ item }">
            <InventoryStatusChip :status="item.status" />
          </template>
          <template #item.actions="{ item }">
            <VBtn
              variant="text"
              size="small"
              icon="ri-printer-line"
              aria-label="Print receipt"
              @click="onPrint(item)"
            />
            <VBtn
              v-if="item.status === 'posted'"
              variant="text"
              size="small"
              color="error"
              :loading="saving"
              @click="askVoid(item)"
            >
              Void
            </VBtn>
          </template>
          <template #no-data>
            <InventoryEmptyState
              icon="ri-receipt-line"
              text="No receipts yet."
              action-label="Record Payment"
              @action="openPay"
            />
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

    <InventoryRecordPaymentDialog
      v-model="payOpen"
      :invoice-options="payInvoiceOptions"
      :loading="payInvoicesLoading"
      @saved="onPaymentSaved"
    />

    <InventoryReceiptPrintDialog
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
