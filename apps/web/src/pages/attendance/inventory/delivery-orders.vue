<script setup lang="ts">
import {
  type DeliveryOrder,
  type DeliveryOrderStatus,
  type SalesOrder,
  confirmDeliveryOrder,
  deleteDeliveryOrder,
  getDeliveryOrder,
  listDeliveryOrders,
  listSalesOrders,
  voidDeliveryOrder,
} from '@/api/attendance/inventorySales'
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

const locations = ref<LocationItem[]>([])
const openOrders = ref<SalesOrder[]>([])

const deliveries = ref<DeliveryOrder[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref<DeliveryOrderStatus | null>(null)
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

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  loading.value = true
  try {
    const [locationList, confirmed, partial] = await Promise.all([
      listLocations({ is_active: true }),
      listSalesOrders({ status: 'confirmed', page_size: 200 }),
      listSalesOrders({ status: 'partial', page_size: 200 }),
    ])

    locations.value = locationList
    openOrders.value = [...confirmed.items, ...partial.items]
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
  try {
    const result = await listDeliveryOrders({
      status: statusFilter.value ?? undefined,
      location_id: locationFilter.value ?? undefined,
      page: page.value,
      page_size: pageSize.value,
    })

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

async function selectDelivery(do_: DeliveryOrder) {
  detailLoading.value = true
  try {
    selected.value = await getDeliveryOrder(do_.id)
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to load delivery order.')
  }
  finally {
    detailLoading.value = false
  }
}

async function doConfirm() {
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

async function doVoid() {
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

async function doDelete() {
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
      </VCol>
      <VCol cols="auto">
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="loading"
          @click="loadDeliveries"
        >
          Refresh
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
      Delivery orders are created from a confirmed sales order — use the "Create DO" action on the sales order page.
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
                No delivery orders yet.
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
            <span>{{ selected.do_no }}</span>
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
            {{ selected.customer_name || '—' }} · {{ selected.location_name || '—' }} ·
            {{ selected.delivery_date }}
            <template v-if="selected.so_no_ref">
              · SO {{ selected.so_no_ref }}
            </template>
          </VCardSubtitle>
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
                <td class="text-end">
                  {{ line.qty }}
                </td>
              </tr>
            </tbody>
          </VTable>
        </VCard>
        <VCard v-else>
          <VCardText class="text-center text-medium-emphasis py-12">
            Select a delivery order.
          </VCardText>
        </VCard>
      </VCol>
    </VRow>
  </VContainer>
</template>
