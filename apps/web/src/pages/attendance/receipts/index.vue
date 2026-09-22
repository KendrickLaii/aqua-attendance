<script setup lang="ts">
import {
  type TuitionReceipt,
  deleteTuitionReceipt,
  listAllTuitionReceipts,
  voidTuitionReceipt,
} from '@/api/attendance/tuitionReceipts'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import StatCards from '@/components/attendance/StatCards.vue'
import { resolvePrintLogoUrl } from '@/api/attendance/uploads'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import {
  REMOVE_VOIDED_RECEIPT,
  VOID_RECEIPT_HINT,
} from '@/utils/billingStaffCopy'
import { formatInvoiceMoney } from '@/utils/invoiceDisplay'
import {
  type TuitionInvoicePrintHeader,
} from '@/utils/printTuitionInvoice'
import {
  openTuitionReceiptPrintPlaceholder,
  printTuitionReceipt,
  tuitionReceiptPrintData,
} from '@/utils/printTuitionReceipt'

definePage({ meta: {} })

const router = useRouter()
const { ensureAccess } = useAttendanceAdminGate()

const {
  yearMonth,
  parsed: parsedYearMonth,
  monthLabel,
  changeMonth,
  toCurrentMonth,
} = useYearMonth()

const {
  page,
  pageSize,
  pageSizeOptions,
  totalCount,
  totalPages,
  listCaption: pagedListCaption,
  resetPage,
} = usePagedList({ pageSize: 40 })

const receipts = ref<TuitionReceipt[]>([])
const loading = ref(true)
const loadError = ref('')
const actionError = ref('')
const expandedId = ref<string | null>(null)
const voidingId = ref<string | null>(null)
const removingId = ref<string | null>(null)
const pendingVoid = ref<TuitionReceipt | null>(null)
const pendingRemove = ref<TuitionReceipt | null>(null)
const locations = ref<LocationItem[]>([])
const searchQuery = ref('')
const statusFilter = ref<'all' | 'posted' | 'void'>('all')

const LOCATION_FILTER_KEY = 'tuition-receipt-location'
const locationId = ref<string | null>(localStorage.getItem(LOCATION_FILTER_KEY))

useAutoClearAlerts(loadError, actionError)

function studentLabel(receipt: TuitionReceipt): string {
  if (receipt.unit_name)
    return receipt.unit_code ? `${receipt.unit_name} (${receipt.unit_code})` : receipt.unit_name
  return receipt.payer_name || '—'
}

function locationName(id: string): string {
  const location = locations.value.find(item => item.id === id)
  return location ? (location.name_zh || location.name_en) : ''
}

const postedReceipts = computed(() => receipts.value.filter(row => row.status === 'posted'))
const voidReceipts = computed(() => receipts.value.filter(row => row.status === 'void'))
const postedTotal = computed(() => postedReceipts.value.reduce((sum, row) => sum + Number(row.amount), 0))

const filteredReceipts = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return receipts.value.filter(receipt => {
    if (statusFilter.value !== 'all' && receipt.status !== statusFilter.value)
      return false
    if (!query)
      return true
    const haystack = [
      receipt.payer_name,
      receipt.unit_name,
      receipt.unit_code,
      receipt.receipt_no,
      receipt.paid_by,
      receipt.description,
      ...receipt.invoices.map(row => row.invoice_no),
    ].join(' ').toLowerCase()
    return haystack.includes(query)
  })
})

const pagedReceipts = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredReceipts.value.slice(start, start + pageSize.value)
})

const allMonths = computed(() => !parsedYearMonth.value)
const locationOptions = computed(() =>
  locations.value
    .filter(location => location.is_active)
    .map(location => ({
      value: location.id,
      title: location.name_zh || location.name_en,
    })),
)
const locationSelectItems = computed(() => [
  { value: 'all', title: 'All locations' },
  ...locationOptions.value,
])
const locationFilter = computed({
  get: () => locationId.value ?? 'all',
  set: (value: string | null) => {
    locationId.value = !value || value === 'all' ? null : value
  },
})
const locationLabel = computed(() => {
  if (!locationId.value)
    return 'All locations'
  return locationOptions.value.find(item => item.value === locationId.value)?.title ?? 'All locations'
})
const scopeLabel = computed(() => {
  const month = parsedYearMonth.value ? monthLabel.value : 'All months'
  return `${month} · ${locationLabel.value}`
})

const statCards = computed(() => [
  {
    label: 'Collected',
    value: formatInvoiceMoney(postedTotal.value),
    hint: `${postedReceipts.value.length} posted receipt${postedReceipts.value.length === 1 ? '' : 's'}`,
    icon: 'ri-checkbox-circle-line',
    color: 'success',
  },
  {
    label: 'Receipts',
    value: String(receipts.value.length),
    hint: voidReceipts.value.length ? `${voidReceipts.value.length} voided` : scopeLabel.value,
    icon: 'ri-file-list-3-line',
    color: 'info',
  },
  {
    label: 'Posted',
    value: String(postedReceipts.value.length),
    hint: scopeLabel.value,
    icon: 'ri-receipt-line',
    color: 'primary',
  },
  {
    label: 'Voided',
    value: String(voidReceipts.value.length),
    hint: 'Void first, then Remove to reuse the number',
    icon: 'ri-close-circle-line',
    color: 'warning',
  },
])

async function loadReceipts() {
  loading.value = true
  loadError.value = ''
  try {
    const period = parsedYearMonth.value
      ? { year: parsedYearMonth.value.year, month: parsedYearMonth.value.month }
      : {}
    const result = await listAllTuitionReceipts({
      ...period,
      location_id: locationId.value ?? undefined,
    })
    receipts.value = result.items
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Could not load receipts.')
  }
  finally {
    loading.value = false
  }
}

async function loadLocations() {
  try {
    locations.value = await listLocations({ page_size: 200 })
    if (!locationOptions.value.some(l => l.value === locationId.value))
      locationId.value = null
  }
  catch (e) {
    locations.value = []
    loadError.value = formatApiError(e, 'Could not load locations. Campus filter and print headers may be incomplete.')
  }
}

function headerFromLocation(location: LocationItem): TuitionInvoicePrintHeader {
  const details = (location.details ?? {}) as Record<string, unknown>
  return {
    nameEn: location.name_en,
    nameZh: location.name_zh ?? '',
    regNo: typeof details.school_reg_no === 'string' ? details.school_reg_no : '',
    address: location.address ?? '',
    phone: location.phone ?? '',
  }
}

async function printReceipt(receipt: TuitionReceipt) {
  try {
    const printWindow = openTuitionReceiptPrintPlaceholder()
    const location = locations.value.find(item => item.id === receipt.location_id)
    printTuitionReceipt(printWindow, tuitionReceiptPrintData(receipt, {
      logoUrl: await resolvePrintLogoUrl(location?.icon_url || location?.main_photo_url || ''),
      header: location ? headerFromLocation(location) : undefined,
    }))
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Could not open print window.')
  }
}

async function confirmRemoveVoided() {
  const receipt = pendingRemove.value
  if (!receipt)
    return
  removingId.value = receipt.id
  actionError.value = ''
  try {
    await deleteTuitionReceipt(receipt.id)
    receipts.value = receipts.value.filter(row => row.id !== receipt.id)
    pendingRemove.value = null
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Could not remove this voided receipt.')
  }
  finally {
    removingId.value = null
  }
}

async function confirmVoid() {
  const receipt = pendingVoid.value
  if (!receipt)
    return
  voidingId.value = receipt.id
  actionError.value = ''
  try {
    const updated = await voidTuitionReceipt(receipt.id)
    const idx = receipts.value.findIndex(row => row.id === receipt.id)
    if (idx !== -1)
      receipts.value[idx] = updated
    pendingVoid.value = null
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Could not void receipt.')
  }
  finally {
    voidingId.value = null
  }
}

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

function showAllMonths() {
  if (yearMonth.value)
    yearMonth.value = ''
}

watch(locationId, id => {
  if (id)
    localStorage.setItem(LOCATION_FILTER_KEY, id)
  else
    localStorage.removeItem(LOCATION_FILTER_KEY)
  resetPage()
  expandedId.value = null
  loadReceipts()
})

watch(yearMonth, () => {
  resetPage()
  loadReceipts()
})

watch(filteredReceipts, list => {
  totalCount.value = list.length
  if (page.value > totalPages.value)
    page.value = totalPages.value
}, { immediate: true })

watch([searchQuery, statusFilter], () => {
  resetPage()
  expandedId.value = null
})

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  await loadLocations()
  if (!yearMonth.value)
    toCurrentMonth()
  else
    await loadReceipts()
})
</script>

<template>
  <VContainer>
    <div>
    <VRow class="mb-4">
      <VCol cols="12" md>
        <h4 class="text-h4 mb-1">
          Receipts
        </h4>
        <div class="text-body-2 text-medium-emphasis">
          {{ scopeLabel }}
        </div>
      </VCol>
      <VCol
        cols="12"
        md="auto"
        class="d-flex flex-wrap align-center gap-2 justify-md-end"
      >
        <VBtn
          icon
          variant="tonal"
          size="small"
          aria-label="Previous month"
          :disabled="allMonths"
          @click="changeMonth(-1)"
        >
          <VIcon aria-hidden="true">
            ri-arrow-left-s-line
          </VIcon>
        </VBtn>
        <VTextField
          v-model="yearMonth"
          label="Month"
          type="month"
          density="compact"
          hide-details
          autocomplete="off"
          style="max-width: 180px;"
        />
        <VBtn
          icon
          variant="tonal"
          size="small"
          aria-label="Next month"
          :disabled="allMonths"
          @click="changeMonth(1)"
        >
          <VIcon aria-hidden="true">
            ri-arrow-right-s-line
          </VIcon>
        </VBtn>
        <VBtn
          :variant="allMonths ? 'flat' : 'tonal'"
          :color="allMonths ? 'primary' : undefined"
          :prepend-icon="allMonths ? 'ri-check-line' : 'ri-calendar-line'"
          @click="showAllMonths"
        >
          All months
        </VBtn>
      </VCol>
    </VRow>

    <VCard class="mb-4">
      <VCardText class="pa-4">
        <div class="d-flex flex-wrap gap-2 mb-4">
          <VBtn
            color="primary"
            prepend-icon="ri-add-line"
            @click="router.push('/attendance/receipts/new')"
          >
            New receipt
          </VBtn>
          <VSpacer />
          <VBtn
            variant="tonal"
            color="primary"
            prepend-icon="ri-refresh-line"
            :loading="loading"
            @click="loadReceipts"
          >
            Refresh
          </VBtn>
        </div>
        <div class="d-flex flex-wrap gap-3">
          <VSelect
            v-model="locationFilter"
            :items="locationSelectItems"
            item-title="title"
            item-value="value"
            label="Location"
            prepend-inner-icon="ri-building-line"
            density="compact"
            hide-details
            style="max-width: 260px;"
          />
          <VTextField
            v-model="searchQuery"
            label="Search"
            placeholder="Student, receipt no., paid by…"
            prepend-inner-icon="ri-search-line"
            density="compact"
            hide-details
            clearable
            autocomplete="off"
            style="min-width: 240px; flex: 1;"
          />
        </div>
        <VChipGroup
          v-model="statusFilter"
          mandatory
          selected-class="text-primary"
          class="mt-3"
        >
          <VChip value="all" size="small" variant="outlined" filter>
            All ({{ receipts.length }})
          </VChip>
          <VChip value="posted" size="small" variant="outlined" filter color="success">
            Posted ({{ postedReceipts.length }})
          </VChip>
          <VChip value="void" size="small" variant="outlined" filter color="warning">
            Void ({{ voidReceipts.length }})
          </VChip>
        </VChipGroup>
      </VCardText>
    </VCard>

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

    <StatCards
      v-if="!loading"
      :cards="statCards"
    />

    <VCard>
      <VCardItem>
        <VCardTitle>
          Receipts
          <span class="text-caption text-medium-emphasis font-weight-regular ms-2">
            {{ pagedListCaption(pagedReceipts.length, 'receipt') }}
          </span>
        </VCardTitle>
      </VCardItem>
      <VCardText>
        <div
          v-if="loading"
          class="text-center py-10"
        >
          <VProgressCircular
            indeterminate
            color="primary"
          />
        </div>
        <VTable
          v-else
          density="compact"
          hover
        >
          <thead>
            <tr>
              <th>Student</th>
              <th>No.</th>
              <th>Date</th>
              <th>Paid by</th>
              <th>Status</th>
              <th class="text-end">
                Amount
              </th>
              <th class="text-end">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            <template
              v-for="receipt in pagedReceipts"
              :key="receipt.id"
            >
              <tr
                style="cursor: pointer;"
                @click="toggleExpand(receipt.id)"
              >
                <td>
                  <div>{{ studentLabel(receipt) }}</div>
                  <div
                    v-if="!locationId && locationName(receipt.location_id)"
                    class="text-caption text-medium-emphasis"
                  >
                    {{ locationName(receipt.location_id) }}
                  </div>
                </td>
                <td>{{ receipt.receipt_no }}</td>
                <td>{{ receipt.receipt_date }}</td>
                <td>{{ receipt.paid_by }}</td>
                <td>
                  <VChip
                    size="x-small"
                    label
                    :color="receipt.status === 'posted' ? 'success' : 'warning'"
                  >
                    {{ receipt.status }}
                  </VChip>
                </td>
                <td class="text-end tabular-nums">
                  {{ formatInvoiceMoney(Number(receipt.amount)) }}
                </td>
                <td
                  class="text-end"
                  @click.stop
                >
                  <VBtn
                    icon="ri-printer-line"
                    size="x-small"
                    variant="text"
                    title="Print"
                    :disabled="receipt.status === 'void'"
                    @click="printReceipt(receipt)"
                  />
                  <VBtn
                    v-if="receipt.status === 'posted'"
                    icon="ri-close-circle-line"
                    size="x-small"
                    variant="text"
                    color="error"
                    title="Void receipt"
                    :loading="voidingId === receipt.id"
                    @click="pendingVoid = receipt"
                  />
                  <VBtn
                    v-if="receipt.status === 'void'"
                    icon="ri-delete-bin-line"
                    size="x-small"
                    variant="text"
                    color="error"
                    title="Remove voided receipt"
                    :loading="removingId === receipt.id"
                    @click="pendingRemove = receipt"
                  />
                </td>
              </tr>
              <tr v-if="expandedId === receipt.id">
                <td colspan="7">
                  <div
                    v-if="receipt.description"
                    class="text-body-2 mb-2"
                  >
                    <span class="text-caption text-medium-emphasis">Description</span>
                    <div>{{ receipt.description }}</div>
                  </div>
                  <div class="text-caption text-medium-emphasis mb-2">
                    Settled invoices
                  </div>
                  <div
                    v-if="receipt.adjustments?.length"
                    class="mt-3"
                  >
                    <div class="text-caption text-medium-emphasis mb-2">
                      Adjustments
                    </div>
                    <div
                      v-for="(row, index) in receipt.adjustments"
                      :key="`${receipt.id}-adj-${index}`"
                      class="d-flex justify-space-between py-1"
                    >
                      <span>{{ [row.month, row.course].filter(Boolean).join(' · ') }}</span>
                      <span>{{ formatInvoiceMoney(Number(row.amount)) }}</span>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
            <tr v-if="!pagedReceipts.length">
              <td
                colspan="7"
                class="text-center text-medium-emphasis py-8"
              >
                No receipts in this scope.
              </td>
            </tr>
          </tbody>
        </VTable>
        <AttendancePaginationBar
          v-if="!loading && filteredReceipts.length > 0"
          v-model:page="page"
          v-model:page-size="pageSize"
          :total-pages="totalPages"
          :page-size-options="pageSizeOptions"
        />
      </VCardText>
    </VCard>

    <AttendanceConfirmDialog
      :model-value="pendingVoid != null"
      title="Void this receipt?"
      confirm-label="Void receipt"
      confirm-color="error"
      :loading="voidingId === pendingVoid?.id"
      :error="actionError"
      @update:model-value="value => { if (!value) pendingVoid = null }"
      @confirm="confirmVoid"
      @cancel="pendingVoid = null"
      @clear-error="actionError = ''"
    >
      <p class="text-body-2 mb-0">
        <strong>{{ pendingVoid?.receipt_no }}</strong>
        {{ VOID_RECEIPT_HINT }}
      </p>
    </AttendanceConfirmDialog>

    <AttendanceConfirmDialog
      :model-value="pendingRemove != null"
      title="Remove this voided receipt?"
      confirm-label="Remove"
      confirm-color="error"
      :loading="removingId === pendingRemove?.id"
      :error="actionError"
      @update:model-value="value => { if (!value) pendingRemove = null }"
      @confirm="confirmRemoveVoided"
      @cancel="pendingRemove = null"
      @clear-error="actionError = ''"
    >
      <p class="text-body-2 mb-0">
        <strong>{{ pendingRemove?.receipt_no }}</strong>
        {{ REMOVE_VOIDED_RECEIPT }}
      </p>
    </AttendanceConfirmDialog>
  </div>
  </VContainer>
</template>
