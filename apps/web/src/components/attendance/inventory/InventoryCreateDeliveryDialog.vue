<script setup lang="ts">
import {
  type DeliveryOrder,
  createDeliveryOrder,
} from '@/api/attendance/inventorySales'
import {
  type InventoryInvoice,
  getInvoice,
  listInvoices,
} from '@/api/attendance/inventoryInvoicing'
import { formatApiError } from '@/utils/formatApiDetail'

const props = defineProps<{

  /**
   * Preselected invoice (invoice detail page). When null the dialog shows an
   * autocomplete of issued invoices to pick from (delivery-orders page).
   */
  invoice: InventoryInvoice | null
}>()

const emit = defineEmits<{
  created: [order: DeliveryOrder]
}>()

const open = defineModel<boolean>({ required: true })

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const deliveryDate = ref(new Date().toISOString().slice(0, 10))

// ---- invoice picker (used when no invoice is preselected) ----
const invoiceSearch = ref('')
const invoiceItems = ref<InventoryInvoice[]>([])
const pickedInvoiceId = ref<string | null>(null)
const detail = ref<InventoryInvoice | null>(null)

const invoiceOptions = computed(() =>
  invoiceItems.value.map(i => ({
    value: i.id,
    title: `${i.invoice_no ?? '—'} · ${i.customer_name ?? i.buyer_name ?? '—'} · ${i.issue_date ?? ''}`,
  })),
)

interface DoLine {
  invoice_line_id: string
  item_id: string
  label: string
  deliverable: number
  qty: number
}

const lines = ref<DoLine[]>([])

function seedLines(inv: InventoryInvoice) {
  lines.value = inv.lines
    .map(l => ({
      invoice_line_id: l.id,
      item_id: l.item_id,
      label: [l.sku_code, l.name_zh].filter(Boolean).join(' · ') || l.item_id,
      deliverable: Math.max(0, l.qty - l.credited_qty - l.delivered_qty),
      qty: Math.max(0, l.qty - l.credited_qty - l.delivered_qty),
    }))
    .filter(l => l.deliverable > 0)
}

let searchTimer: ReturnType<typeof setTimeout> | null = null

watch(invoiceSearch, v => {
  if (searchTimer)
    clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadInvoices(v), 300)
})

watch(pickedInvoiceId, async id => {
  detail.value = null
  lines.value = []
  if (!id)
    return
  loading.value = true
  error.value = ''
  try {
    const inv = await getInvoice(id)

    detail.value = inv
    seedLines(inv)
  }
  catch (e) {
    error.value = formatApiError(e, 'Failed to load invoice.')
  }
  finally {
    loading.value = false
  }
})

async function loadInvoices(search?: string) {
  try {
    const result = await listInvoices({ status: 'issued', search: search || undefined, page_size: 50 })

    invoiceItems.value = result.items
  }
  catch {
    invoiceItems.value = []
  }
}

// ---- deliverable lines ----
const activeInvoice = computed(() => props.invoice ?? detail.value)

watch(open, v => {
  if (!v)
    return
  error.value = ''
  deliveryDate.value = new Date().toISOString().slice(0, 10)
  pickedInvoiceId.value = null
  detail.value = null
  invoiceSearch.value = ''
  if (props.invoice) {
    seedLines(props.invoice)
  }
  else {
    lines.value = []
    loadInvoices()
  }
})

const canCreate = computed(() =>
  !!activeInvoice.value
  && lines.value.length > 0
  && lines.value.some(l => l.qty > 0)
  && lines.value.every(l => l.qty >= 0 && l.qty <= l.deliverable && Number.isInteger(l.qty)),
)

async function doCreate() {
  const inv = activeInvoice.value
  if (!inv || !canCreate.value)
    return
  error.value = ''
  saving.value = true
  try {
    const dor = await createDeliveryOrder({
      invoice_id: inv.id,
      delivery_date: deliveryDate.value,
      lines: lines.value
        .filter(l => l.qty > 0)
        .map(l => ({ invoice_line_id: l.invoice_line_id, item_id: l.item_id, qty: l.qty })),
    })

    open.value = false
    emit('created', dor)
  }
  catch (e) {
    error.value = formatApiError(e, 'Failed to create delivery order.')
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <VDialog
    v-model="open"
    max-width="720"
  >
    <VCard>
      <VCardTitle>New Delivery Order</VCardTitle>
      <VCardText>
        <div class="text-body-2 text-medium-emphasis mb-3">
          出貨單只記錄實際送貨，不影響庫存 — 庫存在發票開立時已扣減。
        </div>
        <VAutocomplete
          v-if="!props.invoice"
          v-model="pickedInvoiceId"
          v-model:search="invoiceSearch"
          :items="invoiceOptions"
          :loading="loading"
          label="Invoice"
          density="comfortable"
          hide-details
          clearable
          no-filter
          class="mb-3"
        >
          <template #message>
            選一張已開立的發票，系統會帶出還沒送貨的品項。
          </template>
        </VAutocomplete>
        <div
          v-if="activeInvoice"
          class="text-body-2 mb-2"
        >
          {{ activeInvoice.invoice_no }} · {{ activeInvoice.customer_name || activeInvoice.buyer_name }}
        </div>
        <VAlert
          v-if="activeInvoice && lines.length === 0 && !loading"
          type="info"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          這張發票沒有還沒送貨的品項。
        </VAlert>
        <VTable
          v-if="lines.length"
          class="inv-line-table mb-2"
        >
          <thead>
            <tr>
              <th>Item</th>
              <th class="text-end">
                可送 Deliverable
              </th>
              <th class="col-qty text-end">
                Qty
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="line in lines"
              :key="line.invoice_line_id"
            >
              <td>{{ line.label }}</td>
              <td class="text-end tabular-nums">
                {{ line.deliverable }}
              </td>
              <td>
                <VTextField
                  v-model.number="line.qty"
                  type="number"
                  min="0"
                  :max="line.deliverable"
                  density="compact"
                  variant="outlined"
                  hide-details
                  class="inv-num-input"
                />
              </td>
            </tr>
          </tbody>
        </VTable>
        <VTextField
          v-model="deliveryDate"
          type="date"
          label="Delivery date"
          density="comfortable"
          hide-details
          class="mt-3"
          style="max-width: 220px"
        />
        <VAlert
          v-if="error"
          type="error"
          variant="tonal"
          density="compact"
          class="mt-3"
        >
          {{ error }}
        </VAlert>
      </VCardText>
      <VCardActions>
        <VSpacer />
        <VBtn
          variant="text"
          @click="open = false"
        >
          Cancel
        </VBtn>
        <VBtn
          color="primary"
          :disabled="!canCreate"
          :loading="saving"
          @click="doCreate"
        >
          Create
        </VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>
