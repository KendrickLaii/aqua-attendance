<script setup lang="ts">
import {
  type InventoryReceipt,
  type InventoryReceiptPrintDoc,
  type InventoryReceiptStatus,
  RECEIPT_PAID_BY_OPTIONS,
  getReceiptPrint,
  listReceipts,
  voidReceipt,
} from '@/api/attendance/inventoryInvoicing'
import { type InventoryCustomer, listCustomers } from '@/api/attendance/inventorySales'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import AttendancePaginationBar from '@/components/attendance/AttendancePaginationBar.vue'
import InventoryReceiptPrintDialog from '@/components/attendance/inventory/InventoryReceiptPrintDialog.vue'
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

const receipts = ref<InventoryReceipt[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const statusFilter = ref<InventoryReceiptStatus | null>(null)
const customerFilter = ref<string | null>(null)
const locationFilter = ref<string | null>(null)
const search = ref('')

const printOpen = ref(false)
const printDoc = ref<InventoryReceiptPrintDoc | null>(null)

const statusOptions = [
  { value: 'posted' as const, title: 'Posted' },
  { value: 'void' as const, title: 'Void' },
]

const headers = [
  { title: 'Receipt No', key: 'receipt_no' },
  { title: 'Invoice', key: 'invoice_no' },
  { title: 'Customer', key: 'customer_name' },
  { title: 'Date', key: 'receipt_date' },
  { title: 'Amount', key: 'amount' },
  { title: 'Paid by', key: 'paid_by' },
  { title: 'Reference', key: 'reference_no' },
  { title: 'Status', key: 'status' },
  { title: '', key: 'actions', sortable: false },
]

function paidByLabel(value: string): string {
  return RECEIPT_PAID_BY_OPTIONS.find(o => o.value === value)?.label ?? value
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await listReceipts({
      customer_id: customerFilter.value || undefined,
      location_id: locationFilter.value || undefined,
      status: statusFilter.value || undefined,
      search: search.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })

    receipts.value = res.items
    total.value = res.total
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Operation failed.')
  }
  finally {
    loading.value = false
  }
}

async function onVoid(rc: InventoryReceipt) {
  saving.value = true
  actionError.value = ''
  try {
    await voidReceipt(rc.id)
    actionSuccess.value = `Receipt ${rc.receipt_no} voided`
    await load()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Operation failed.')
  }
  finally {
    saving.value = false
  }
}

async function onPrint(rc: InventoryReceipt) {
  try {
    printDoc.value = await getReceiptPrint(rc.id)
    printOpen.value = true
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Operation failed.')
  }
}

function fmtMoney(value: number | null | undefined): string {
  return (value ?? 0).toFixed(2)
}

watch([statusFilter, customerFilter, locationFilter], () => {
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
        <span>Receipts 庫存收據</span>
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
          v-model="locationFilter"
          :items="locations.map(l => ({ value: l.id, title: l.name_en || l.name_zh || l.code }))"
          density="compact"
          label="Location"
          clearable
          hide-details
          style="max-width: 160px"
        />
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
          :items="receipts"
          :loading="loading"
          density="compact"
        >
          <template #item.receipt_no="{ item }">
            <span class="font-weight-medium">{{ item.receipt_no }}</span>
          </template>
          <template #item.amount="{ item }">
            {{ fmtMoney(item.amount) }}
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
              @click="onPrint(item)"
            />
            <VBtn
              v-if="item.status === 'posted'"
              variant="text"
              size="small"
              color="error"
              :loading="saving"
              @click="onVoid(item)"
            >
              Void
            </VBtn>
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

    <InventoryReceiptPrintDialog
      v-model="printOpen"
      :doc="printDoc"
    />
  </div>
</template>
