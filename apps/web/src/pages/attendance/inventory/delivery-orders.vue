<script setup lang="ts">
import {
  type DeliveryOrder,
  type DeliveryOrderStatus,
  confirmDeliveryOrder,
  deleteDeliveryOrder,
  getDeliveryOrder,
  listDeliveryOrders,
  voidDeliveryOrder,
} from '@/api/attendance/inventorySales'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import AttendanceConfirmDialog from '@/components/attendance/AttendanceConfirmDialog.vue'
import InventoryCreateDeliveryDialog from '@/components/attendance/inventory/InventoryCreateDeliveryDialog.vue'
import AttendancePaginationBar from '@/components/attendance/AttendancePaginationBar.vue'
import InventoryDocChain, { type DocChainStep } from '@/components/attendance/inventory/InventoryDocChain.vue'
import { type InventoryDocAction, type InventoryDocMoreItem } from '@/components/attendance/inventory/InventoryDocActions.vue'
import InventoryStatusChip from '@/components/attendance/inventory/InventoryStatusChip.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { useConfirmAction } from '@/composables/useConfirmAction'
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

const locations = ref<LocationItem[]>([])

const deliveries = ref<DeliveryOrder[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const route = useRoute()
const listReq = useLatestRequest()
const confirm = useConfirmAction()

const statusFilter = ref<DeliveryOrderStatus | null>(
  (route.query.status as DeliveryOrderStatus | undefined) ?? null,
)

const locationFilter = ref<string | null>(null)

const selected = ref<DeliveryOrder | null>(null)

const statusOptions = [
  { value: 'draft' as const, title: 'Draft' },
  { value: 'confirmed' as const, title: 'Confirmed' },
  { value: 'void' as const, title: 'Void' },
]

const locationOptions = computed(() =>
  locations.value.map(l => ({
    value: l.id,
    title: [l.name_en, l.name_zh].filter(Boolean).join(' · '),
  })),
)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const isDraft = computed(() => selected.value?.status === 'draft')

const chainSteps = computed<DocChainStep[]>(() => {
  const dor = selected.value
  if (!dor)
    return []

  return [
    { label: `SO ${dor.so_no_ref ?? ''}`.trim(), state: 'done', to: '/attendance/inventory/sales-orders' },
    { label: `Invoice ${dor.invoice_no ?? ''}`.trim(), state: 'done', to: '/attendance/inventory/invoices' },
    { label: `DO ${dor.do_no}`, state: dor.status === 'void' ? 'void' : 'current', hint: dor.status },
    { label: 'Receipt', state: 'todo', to: '/attendance/inventory/receipts' },
  ]
})

const docPrimary = computed<InventoryDocAction | null>(() => {
  const dor = selected.value
  if (!dor)
    return null
  if (dor.status === 'draft')
    return { label: 'Confirm Delivery', tooltip: '確認已送貨,不影響庫存', onClick: askConfirm }

  return null
})

const docMore = computed<InventoryDocMoreItem[]>(() => {
  const items: InventoryDocMoreItem[] = []

  if (isDraft.value)
    items.push({ label: 'Delete draft', sub: '刪除草稿,不能復原', icon: 'ri-delete-bin-line', danger: true, onClick: askDelete })
  if (selected.value?.status === 'confirmed')
    items.push({ label: 'Void delivery order', sub: '作廢出貨單,只會扣回已送數量,不影響庫存', icon: 'ri-close-circle-line', danger: true, onClick: askVoid })

  return items
})

const createOpen = ref(false)

async function onDeliveryCreated(dor: DeliveryOrder) {
  actionSuccess.value = `Created delivery order ${dor.do_no}.`
  await loadDeliveries()
  await selectDelivery(dor)
}

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  loading.value = true
  try {
    locations.value = await listLocations({ is_active: true })
    await loadDeliveries()
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Failed to load delivery orders.')
  }
  finally {
    loading.value = false
  }
})

async function loadDeliveries() {
  loadError.value = ''

  const token = listReq.next()
  try {
    const result = await listDeliveryOrders({
      status: statusFilter.value ?? undefined,
      location_id: locationFilter.value ?? undefined,
      page: page.value,
      page_size: pageSize.value,
    })

    if (!listReq.isLatest(token))
      return
    deliveries.value = result.items
    total.value = result.total
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Failed to load delivery orders.')
  }
}

function onFiltersChange() {
  page.value = 1
  loadDeliveries()
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

async function selectDelivery(do_: DeliveryOrder) {
  detailLoading.value = true
  try {
    selected.value = await getDeliveryOrder(do_.id)
    await scrollToDetail()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to load delivery order.')
  }
  finally {
    detailLoading.value = false
  }
}

function askConfirm() {
  if (!selected.value)
    return
  confirm.ask(
    `Confirm ${selected.value.do_no}?`,
    '確認這批貨已經送出 — 只更新送貨數量，不影響庫存。',
    { label: 'Confirm', tone: 'info', details: ['發票品項的已送數量增加', '庫存在發票開立時已扣減，這裡不再扣'] },
    performConfirm,
  )
}

async function performConfirm() {
  if (!selected.value)
    return
  actionError.value = ''
  saving.value = true
  try {
    selected.value = await confirmDeliveryOrder(selected.value.id)
    actionSuccess.value = `Confirmed ${selected.value.do_no}.`
    await loadDeliveries()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to confirm.')
  }
  finally {
    saving.value = false
  }
}

function askVoid() {
  const dor = selected.value
  if (!dor)
    return
  const qty = dor.lines.reduce((s, l) => s + l.qty, 0)

  confirm.ask(
    `Void ${dor.do_no}?`,
    `作廢 ${dor.do_no} 會把這 ${qty} 件標記為未送貨，庫存不變。`,
    { label: 'Void', details: ['發票品項的已送數量減少', '庫存不變', '不能復原'] },
    performVoid,
  )
}

async function performVoid() {
  if (!selected.value)
    return
  actionError.value = ''
  saving.value = true
  try {
    selected.value = await voidDeliveryOrder(selected.value.id)
    actionSuccess.value = `Voided ${selected.value.do_no}.`
    await loadDeliveries()
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
    `Delete draft ${selected.value.do_no}?`,
    '草稿出貨單會永久刪除。',
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
    const no = selected.value.do_no

    await deleteDeliveryOrder(selected.value.id)
    actionSuccess.value = `Deleted draft ${no}.`
    selected.value = null
    await loadDeliveries()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to delete.')
  }
  finally {
    saving.value = false
  }
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
          Delivery Orders 送貨單
        </div>
        <div class="text-body-2 text-medium-emphasis">
          這一頁管理出貨單：只記錄實際送貨，庫存在發票開立時已扣減。
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
              @click="loadDeliveries"
            />
          </template>
        </VTooltip>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          class="ms-2"
          @click="createOpen = true"
        >
          New Delivery Order
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

    <VAlert
      type="info"
      variant="tonal"
      density="compact"
      class="mb-4"
    >
      出貨單由已開立的發票產生 — 按右上「New Delivery Order」選一張發票，或在發票頁按 Create Delivery Order。
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
              v-for="dor in deliveries"
              :key="dor.id"
              :active="selected?.id === dor.id"
              @click="selectDelivery(dor)"
            >
              <VListItemTitle>{{ dor.do_no }}</VListItemTitle>
              <VListItemSubtitle>
                {{ dor.customer_name || '—' }} · {{ dor.delivery_date }}
                <template v-if="dor.so_no_ref">
                  · {{ dor.so_no_ref }}
                </template>
              </VListItemSubtitle>
              <template #append>
                <InventoryStatusChip :status="dor.status" />
              </template>
            </VListItem>
            <VListItem v-if="deliveries.length === 0 && !loading">
              <VListItemTitle class="text-medium-emphasis">
                還沒有出貨單 — 先在發票開立貨品，再按「New Delivery Order」建立。
              </VListItemTitle>
            </VListItem>
          </VList>
          <AttendancePaginationBar
            v-model:page="page"
            v-model:page-size="pageSize"
            :total-pages="totalPages"
            :caption="`Page ${page} of ${totalPages} · ${total} deliver${total === 1 ? 'y' : 'ies'}`"
            @change="loadDeliveries"
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
            <span>{{ selected.do_no }}</span>
            <InventoryStatusChip :status="selected.status" />
            <VSpacer />
            <InventoryDocActions
              :primary="docPrimary"
              :more="docMore"
              :loading="saving"
            />
          </VCardTitle>
          <VCardSubtitle>
            {{ selected.customer_name || '—' }} · {{ selected.location_name || '—' }} ·
            {{ selected.delivery_date }}
            <template v-if="selected.invoice_no">
              · Invoice
              <RouterLink :to="`/attendance/inventory/invoices?doc=${selected.invoice_id}`">
                {{ selected.invoice_no }}
              </RouterLink>
            </template>
            <template v-else-if="selected.so_no_ref">
              · SO {{ selected.so_no_ref }}
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
                  </tr>
                </tbody>
              </VTable>
            </div>
          </VCardText>
        </VCard>
        <VCard v-else>
          <VCardText class="text-center text-medium-emphasis py-12">
            從上面的列表選一張出貨單，或按下面的按鈕建立新的。
            <div class="mt-3">
              <VBtn
                color="primary"
                prepend-icon="ri-add-line"
                @click="createOpen = true"
              >
                New Delivery Order
              </VBtn>
            </div>
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <InventoryCreateDeliveryDialog
      v-model="createOpen"
      :invoice="null"
      @created="onDeliveryCreated"
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
  </VContainer>
</template>
