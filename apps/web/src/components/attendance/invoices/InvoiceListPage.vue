<script setup lang="ts">
import {
  type TuitionInvoice,
  type TuitionInvoiceStatus,
  deleteTuitionInvoice,
  generateTuitionInvoices,
  getNextInvoiceNo,
  listAllTuitionInvoices,
  updateTuitionInvoice,
} from '@/api/attendance/tuitionInvoices'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import { type Unit, listAllUnits } from '@/api/attendance/units'
import InvoiceBillsSection, { type InvoiceSortKey } from '@/components/attendance/invoices/InvoiceBillsSection.vue'
import InvoiceManualDialog from '@/components/attendance/invoices/InvoiceManualDialog.vue'
import StatCards from '@/components/attendance/StatCards.vue'
import { resolvePrintLogoUrl } from '@/api/attendance/uploads'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import {
  GENERATE_CONFIRM,
  INVOICE_CANCEL_GENERATED,
  REMOVE_CANCELLED_INVOICE,
} from '@/utils/billingStaffCopy'
import {
  classPreview,
  filterChargeInvoices,
  filterCreditNoteInvoices,
  formatInvoiceMoney,
  invoiceOpenedBy,
  invoicePrintHeaderFromLocation,
  invoiceStatusColor,
  invoiceStatusFilters,
  invoiceStatusLabel,
  invoiceStudentLabel,
  isChargeInvoice,
  isCreditInvoice,
  locationTitle,
} from '@/utils/invoiceDisplay'
import {
  invoiceMonthLabel,
  openTuitionInvoicePrintPlaceholder,
  printTuitionInvoice,
  tuitionInvoicePrintData,
} from '@/utils/printTuitionInvoice'
import { type CancellableTableSort, type SortValue, compareSortValues, cycleSort } from '@/utils/tableSort'

const props = withDefaults(defineProps<{
  variant?: 'invoice' | 'credit'
}>(), {
  variant: 'invoice',
})

const isCreditPage = computed(() => props.variant === 'credit')

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

const invoices = ref<TuitionInvoice[]>([])
const loading = ref(true)
const generating = ref(false)
const loadError = ref('')
const generateError = ref('')
const generateSuccess = ref('')
const expandedId = ref<string | null>(null)
const statusUpdatingId = ref<string | null>(null)
const pendingStatus = ref<{ invoice: TuitionInvoice; status: 'issued' | 'void' } | null>(null)
const pendingGenerate = ref(false)
const issueNoInput = ref('')
const issueNoEdited = ref(false)
const issueNoError = ref('')
const issueRemark = ref('')
const issueStaff = ref('')
const manualInvoiceOpen = ref(false)
const editingInvoice = ref<TuitionInvoice | null>(null)
const creditFromInvoice = ref<TuitionInvoice | null>(null)
const pendingRemove = ref<TuitionInvoice | null>(null)
const locations = ref<LocationItem[]>([])

const LOCATION_FILTER_KEY = props.variant === 'credit'
  ? 'tuition-credit-note-location'
  : 'tuition-invoice-location'
const pendingPrint = ref<TuitionInvoice | null>(null)
const printPayableTo = ref('')
const printPayeeName = ref('')
const createdCreditNote = ref(false)
const locationId = ref<string | null>(localStorage.getItem(LOCATION_FILTER_KEY))

const searchQuery = ref('')
const statusFilter = ref<'all' | TuitionInvoiceStatus>('all')
const showBillingHelp = ref(false)
const invoiceSort = reactive<CancellableTableSort<InvoiceSortKey>>({ key: null, dir: 1 })

const issueStaffUnits = ref<Unit[]>([])
const issueStaffLoaded = ref(false)

useAutoClearAlerts(loadError)
useAutoClearAlerts(generateError)
useAutoClearAlerts(generateSuccess)

const issueStaffOptions = computed(() => issueStaffUnits.value.map(u => u.full_name))

const scopedInvoices = computed(() =>
  isCreditPage.value
    ? invoices.value.filter(isCreditInvoice)
    : invoices.value.filter(isChargeInvoice),
)

const statusTotals = computed(() => {
  const totals = {
    draft: { count: 0, amount: 0 },
    issued: { count: 0, amount: 0 },
    paid: { count: 0, amount: 0 },
    void: { count: 0, amount: 0 },
  }

  for (const invoice of scopedInvoices.value) {
    const bucket = totals[invoice.status]
    if (!bucket)
      continue
    bucket.count += 1
    bucket.amount += Number(invoice.total)
  }

  return totals
})

const collectibleTotal = computed(
  () => statusTotals.value.draft.amount + statusTotals.value.issued.amount,
)

const refundTotal = computed(
  () => statusTotals.value.draft.amount + statusTotals.value.issued.amount + statusTotals.value.paid.amount,
)

const statusCounts = computed<Record<string, number>>(() => ({
  all: scopedInvoices.value.length,
  draft: statusTotals.value.draft.count,
  issued: statusTotals.value.issued.count,
  paid: statusTotals.value.paid.count,
  void: statusTotals.value.void.count,
}))

const filteredInvoices = computed(() => {
  const opts = {
    status: statusFilter.value,
    query: searchQuery.value,
  }

  return isCreditPage.value
    ? filterCreditNoteInvoices(invoices.value, opts)
    : filterChargeInvoices(invoices.value, opts)
})

function invoiceSortValue(invoice: TuitionInvoice, key: InvoiceSortKey): SortValue {
  if (key === 'student')
    return invoiceStudentLabel(invoice)
  if (key === 'no')
    return invoice.invoice_no
  if (key === 'staff')
    return invoiceOpenedBy(invoice) || null
  if (key === 'classes')
    return classPreview(invoice)
  if (key === 'status')
    return invoiceStatusLabel[invoice.status] ?? invoice.status

  return Number(invoice.total)
}

const sortedInvoices = computed(() => {
  const key = invoiceSort.key
  if (!key)
    return filteredInvoices.value

  return [...filteredInvoices.value].sort(
    (a, b) => compareSortValues(invoiceSortValue(a, key), invoiceSortValue(b, key)) * invoiceSort.dir,
  )
})

const pagedInvoices = computed(() => {
  const start = (page.value - 1) * pageSize.value

  return sortedInvoices.value.slice(start, start + pageSize.value)
})

function onInvoiceSort(key: InvoiceSortKey) {
  cycleSort(invoiceSort, key)
  resetPage()
  expandedId.value = null
}

const billsCaption = computed(() =>
  pagedListCaption(pagedInvoices.value.length, isCreditPage.value ? 'credit note' : 'bill'),
)

const allMonths = computed(() => !parsedYearMonth.value)
const allLocations = computed(() => !locationId.value)

const locationOptions = computed(() =>
  locations.value
    .filter(location => location.is_active)
    .map(location => ({
      value: location.id,
      title: locationTitle(location),
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

const defaultManualMonthLabel = computed(() => {
  const parsed = parsedYearMonth.value
  if (!parsed)
    return ''

  return invoiceMonthLabel(`${parsed.year}-${String(parsed.month).padStart(2, '0')}-01`)
})

const statCards = computed(() => isCreditPage.value
  ? [
      {
        label: 'Credits',
        value: formatInvoiceMoney(refundTotal.value),
        hint: `${statusTotals.value.issued.count} issued · ${statusTotals.value.paid.count} paid`,
        icon: 'ri-refund-2-line',
        color: 'secondary',
      },
      {
        label: 'Issued',
        value: formatInvoiceMoney(statusTotals.value.issued.amount),
        hint: `${statusTotals.value.issued.count} credit note${statusTotals.value.issued.count === 1 ? '' : 's'}`,
        icon: 'ri-file-check-line',
        color: 'info',
      },
      {
        label: 'Drafts',
        value: String(statusTotals.value.draft.count),
        hint: formatInvoiceMoney(statusTotals.value.draft.amount),
        icon: 'ri-draft-line',
        color: 'warning',
      },
      {
        label: 'Credit notes',
        value: String(scopedInvoices.value.length),
        hint: statusTotals.value.void.count
          ? `${statusTotals.value.void.count} cancelled`
          : scopeLabel.value,
        icon: 'ri-file-list-3-line',
        color: 'info',
      },
    ]
  : [
      {
        label: 'To collect',
        value: formatInvoiceMoney(collectibleTotal.value),
        hint: `${statusTotals.value.draft.count} draft · ${statusTotals.value.issued.count} issued`,
        icon: 'ri-wallet-3-line',
        color: 'primary',
      },
      {
        label: 'Paid',
        value: formatInvoiceMoney(statusTotals.value.paid.amount),
        hint: parsedYearMonth.value
          ? `${statusTotals.value.paid.count} paid this month`
          : `${statusTotals.value.paid.count} paid`,
        icon: 'ri-checkbox-circle-line',
        color: 'success',
      },
      {
        label: 'Drafts',
        value: String(statusTotals.value.draft.count),
        hint: formatInvoiceMoney(statusTotals.value.draft.amount),
        icon: 'ri-draft-line',
        color: 'warning',
      },
      {
        label: 'Bills',
        value: String(scopedInvoices.value.length),
        hint: statusTotals.value.void.count
          ? `${statusTotals.value.void.count} cancelled — not in to collect`
          : scopeLabel.value,
        icon: 'ri-file-list-3-line',
        color: 'info',
      },
    ])

async function loadInvoices() {
  loading.value = true
  loadError.value = ''
  try {
    const period = parsedYearMonth.value
      ? { year: parsedYearMonth.value.year, month: parsedYearMonth.value.month }
      : {}

    const result = await listAllTuitionInvoices({
      ...period,
      location_id: locationId.value ?? undefined,
    })

    invoices.value = result.items
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Could not load invoices.')
  }
  finally {
    loading.value = false
  }
}

function askGenerate() {
  if (!parsedYearMonth.value)
    return
  pendingGenerate.value = true
}

async function confirmGenerate() {
  await generate()
  pendingGenerate.value = false
}

async function generate() {
  if (!parsedYearMonth.value)
    return

  generating.value = true
  generateError.value = ''
  generateSuccess.value = ''
  try {
    const result = await generateTuitionInvoices(
      parsedYearMonth.value.year,
      parsedYearMonth.value.month,
      locationId.value,
    )

    const leftover = result.leftover_unbilled ?? 0
    generateSuccess.value = `Created ${result.created}, updated ${result.updated}, skipped ${result.skipped}, deleted ${result.deleted ?? 0}.`
    if (leftover > 0) {
      const samples = (result.leftover_purchases ?? [])
        .slice(0, 3)
        .map(p => `${p.unit_code || p.unit_name || 'student'} ${p.purchased_at}`)
        .join(', ')
      generateSuccess.value += ` ${leftover} older unbilled session package${leftover === 1 ? '' : 's'} skipped — generate that month first${samples ? ` (${samples})` : ''}.`
    }
    await loadInvoices()
  }
  catch (e) {
    generateError.value = formatApiError(e, 'Could not generate invoices.')
  }
  finally {
    generating.value = false
  }
}

async function setStatus(
  invoice: TuitionInvoice,
  status: 'issued' | 'void',
  invoiceNo?: string,
  notes?: string | null,
  issuerName?: string,
): Promise<TuitionInvoice | null> {
  statusUpdatingId.value = invoice.id
  generateError.value = ''
  try {
    const updated = await updateTuitionInvoice(invoice.id, {
      status,
      ...(status === 'issued' ? { invoice_no: invoiceNo ?? null } : {}),
      ...(notes !== undefined ? { notes } : {}),
      ...(issuerName !== undefined ? { staff_name: issuerName || null } : {}),
    })

    const idx = invoices.value.findIndex(row => row.id === invoice.id)
    if (idx !== -1)
      invoices.value[idx] = updated
    pendingStatus.value = null

    return updated
  }
  catch (e) {
    generateError.value = formatApiError(e, 'Could not update invoice.')

    return null
  }
  finally {
    statusUpdatingId.value = null
  }
}

async function loadIssueStaff() {
  if (issueStaffLoaded.value)
    return
  try {
    issueStaffUnits.value = await listAllUnits({ unit_type: 'staff' })
    issueStaffLoaded.value = true
  }
  catch (e) {
    issueStaffUnits.value = []
    generateError.value = formatApiError(e, 'Could not load staff names. Type who opened this bill.')
  }
}

async function suggestIssueNo() {
  try {
    const locId = pendingStatus.value?.invoice.location_id ?? locationId.value
    if (!locId)
      return
    const next = await getNextInvoiceNo(locId, isCreditPage.value ? 'credit' : 'invoice')
    if (pendingStatus.value?.status === 'issued' && !issueNoInput.value.trim())
      issueNoInput.value = next
  }
  catch (e) {
    issueNoError.value = formatApiError(e, 'Could not suggest the next invoice number. Enter it yourself.')
  }
}

function goMarkPaid(invoice: TuitionInvoice) {
  router.push({
    path: '/attendance/receipts/new',
    query: {
      invoice_id: invoice.id,
      location_id: invoice.location_id,
      ...(invoice.unit_id ? { unit_id: invoice.unit_id } : {}),
    },
  })
}

function openManualInvoice() {
  editingInvoice.value = null
  creditFromInvoice.value = null
  manualInvoiceOpen.value = true
}

function openEditInvoice(invoice: TuitionInvoice) {
  creditFromInvoice.value = null
  editingInvoice.value = invoice
  manualInvoiceOpen.value = true
}

function openCreditNote(invoice: TuitionInvoice) {
  editingInvoice.value = null
  creditFromInvoice.value = invoice
  createdCreditNote.value = true
  manualInvoiceOpen.value = true
}

function onManualCreated() {
  const openedCredit = createdCreditNote.value || isCreditPage.value
  createdCreditNote.value = false
  closeManualInvoice()
  loadInvoices()
  if (openedCredit && !isCreditPage.value)
    router.push('/attendance/credit-notes')
}

function closeManualInvoice() {
  manualInvoiceOpen.value = false
  editingInvoice.value = null
  creditFromInvoice.value = null
}

async function confirmRemoveCancelled() {
  const invoice = pendingRemove.value
  if (!invoice)
    return
  statusUpdatingId.value = invoice.id
  generateError.value = ''
  try {
    await deleteTuitionInvoice(invoice.id)
    invoices.value = invoices.value.filter(row => row.id !== invoice.id)
    pendingRemove.value = null
  }
  catch (e) {
    generateError.value = formatApiError(e, 'Could not remove this cancelled bill.')
  }
  finally {
    statusUpdatingId.value = null
  }
}

function askStatus(invoice: TuitionInvoice, status: 'issued' | 'void') {
  issueNoInput.value = status === 'issued' ? (invoice.invoice_no ?? '') : ''
  issueNoEdited.value = status === 'issued' && invoice.invoice_no != null
  issueNoError.value = ''
  issueRemark.value = invoice.notes ?? ''
  issueStaff.value = invoice.staff_name ?? ''
  pendingStatus.value = { invoice, status }
  if (status === 'issued') {
    loadIssueStaff()
    if (!invoice.invoice_no)
      suggestIssueNo()
  }
}

function locationName(id: string): string {
  const location = locations.value.find(item => item.id === id)

  return location ? locationTitle(location) : ''
}

async function printOptionsFor(
  invoice: TuitionInvoice,
  names?: { payableTo?: string; payeeName?: string },
) {
  const location = locations.value.find(l => l.id === invoice.location_id)

  return {
    logoUrl: await resolvePrintLogoUrl(location?.icon_url || location?.main_photo_url || ''),
    header: location ? invoicePrintHeaderFromLocation(location) : undefined,
    payableTo: names?.payableTo,
    payeeName: names?.payeeName,
  }
}

watch(locationId, id => {
  if (id)
    localStorage.setItem(LOCATION_FILTER_KEY, id)
  else
    localStorage.removeItem(LOCATION_FILTER_KEY)
  resetPage()
  expandedId.value = null
  loadInvoices()
})

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

async function printWithNames(
  invoice: TuitionInvoice,
  names?: { payableTo?: string; payeeName?: string },
) {
  const printWindow = openTuitionInvoicePrintPlaceholder()

  await printTuitionInvoice(
    printWindow,
    tuitionInvoicePrintData(invoice, await printOptionsFor(invoice, names)),
  )
}

function printInvoice(invoice: TuitionInvoice) {
  if (isCreditPage.value || isCreditInvoice(invoice)) {
    pendingPrint.value = invoice
    printPayableTo.value = invoice.payable_to_name ?? ''
    printPayeeName.value = invoice.payee_name ?? ''

    return
  }

  printWithNames(invoice).catch(e => {
    generateError.value = formatApiError(e, 'Could not open print window.')
  })
}

async function confirmPrintCredit() {
  const invoice = pendingPrint.value
  if (!invoice)
    return

  const payableTo = printPayableTo.value.trim()
  const payeeName = printPayeeName.value.trim()

  try {
    const namesChanged = payableTo !== (invoice.payable_to_name ?? '')
      || payeeName !== (invoice.payee_name ?? '')
    if (namesChanged)
      await updateTuitionInvoice(invoice.id, {
        payable_to_name: payableTo || null,
        payee_name: payeeName || null,
      })

    await printWithNames(invoice, { payableTo, payeeName })
    pendingPrint.value = null
    if (namesChanged)
      await loadInvoices()
  }
  catch (e) {
    generateError.value = formatApiError(e, 'Could not open print window.')
  }
}

async function confirmPendingStatus() {
  const pending = pendingStatus.value
  if (!pending)
    return

  const invoiceNo = issueNoEdited.value ? issueNoInput.value.trim() : ''

  let printWindow: Window | null = null
  if (pending.status === 'issued') {
    try {
      printWindow = openTuitionInvoicePrintPlaceholder()
    }
    catch (e) {
      generateError.value = formatApiError(e, 'Could not open print window.')

      return
    }
  }

  const remark = (issueRemark.value ?? '').trim()

  const updated = await setStatus(
    pending.invoice,
    pending.status,
    invoiceNo || undefined,
    pending.status === 'issued' ? remark || null : undefined,
    pending.status === 'issued' ? issueStaff.value.trim() : undefined,
  )

  if (!updated) {
    printWindow?.close()

    return
  }
  if (printWindow) {
    await printTuitionInvoice(
      printWindow,
      tuitionInvoicePrintData(updated, await printOptionsFor(updated)),
    )
  }
}

const statusConfirmTitle = computed(() => {
  const status = pendingStatus.value?.status
  if (status === 'issued')
    return 'Issue this bill?'
  if (status === 'void')
    return 'Cancel this bill?'

  return 'Update invoice?'
})

const statusConfirmLabel = computed(() => {
  const status = pendingStatus.value?.status
  if (status === 'issued')
    return 'Issue bill'
  if (status === 'void')
    return 'Cancel bill'

  return 'Confirm'
})

const statusConfirmCancelLabel = computed(() =>
  pendingStatus.value?.status === 'void' ? 'Keep bill' : 'Cancel',
)

const statusConfirmColor = computed(() => pendingStatus.value?.status === 'void' ? 'error' : 'primary')

const statusConfirmMaxWidth = computed(() =>
  pendingStatus.value?.status === 'issued' ? 520 : 420,
)

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

function onInvoiceRowKeydown(event: KeyboardEvent, invoiceId: string) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    toggleExpand(invoiceId)
  }
}

const hasActiveFilters = computed(
  () => Boolean(searchQuery.value.trim()) || statusFilter.value !== 'all',
)

function clearFilters() {
  searchQuery.value = ''
  statusFilter.value = 'all'
}

watch(filteredInvoices, list => {
  totalCount.value = list.length
  if (page.value > totalPages.value)
    page.value = totalPages.value
}, { immediate: true })

watch([searchQuery, statusFilter], () => {
  resetPage()
  expandedId.value = null
})

watch(page, () => {
  expandedId.value = null
})

function showAllMonths() {
  if (yearMonth.value)
    yearMonth.value = ''
}

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  loadLocations()
  if (!yearMonth.value)
    toCurrentMonth()
  else
    await loadInvoices()
})

watch(yearMonth, () => {
  generateSuccess.value = ''
  expandedId.value = null
  resetPage()
  loadInvoices()
})
</script>

<template>
  <VContainer>
    <VRow
      class="mb-2"
      align="center"
    >
      <VCol>
        <div class="text-h5 font-weight-medium invoice-page-title">
          {{ isCreditPage ? 'Credit notes' : 'Tuition invoices' }}
        </div>
        <div class="text-body-2 text-medium-emphasis">
          {{ scopeLabel }}
          <span v-if="scopedInvoices.length">
            · {{ scopedInvoices.length }}
            {{ isCreditPage ? `credit note${scopedInvoices.length === 1 ? '' : 's'}` : `bill${scopedInvoices.length === 1 ? '' : 's'}` }}
            · {{ isCreditPage ? formatInvoiceMoney(refundTotal) : `${formatInvoiceMoney(collectibleTotal)} to collect` }}
          </span>
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
        <div class="invoice-actions">
          <VBtn
            v-if="!isCreditPage"
            color="primary"
            prepend-icon="ri-magic-line"
            :loading="generating"
            :disabled="allMonths"
            :title="allMonths ? 'Pick a month to generate bills' : undefined"
            @click="askGenerate"
          >
            Generate
          </VBtn>
          <VBtn
            variant="tonal"
            prepend-icon="ri-file-add-line"
            @click="openManualInvoice"
          >
            {{ isCreditPage ? 'New credit note' : 'Manual invoice' }}
          </VBtn>
          <VSpacer />
          <VBtn
            variant="tonal"
            color="primary"
            prepend-icon="ri-refresh-line"
            :loading="loading"
            @click="loadInvoices"
          >
            Refresh
          </VBtn>
        </div>

        <div class="invoice-filters">
          <VSelect
            v-model="locationFilter"
            :items="locationSelectItems"
            item-title="title"
            item-value="value"
            label="Location"
            prepend-inner-icon="ri-building-line"
            density="compact"
            hide-details
            autocomplete="off"
            class="invoice-filter-location"
          />
          <VTextField
            v-model="searchQuery"
            label="Search"
            placeholder="Student, staff, invoice no., class…"
            prepend-inner-icon="ri-search-line"
            density="compact"
            hide-details
            clearable
            autocomplete="off"
            spellcheck="false"
            class="invoice-filter-search"
          />
        </div>

        <div class="invoice-status-row">
          <div class="filter-chip-block">
            <span class="text-caption text-medium-emphasis">Status</span>
            <VChipGroup
              v-model="statusFilter"
              mandatory
              selected-class="text-primary"
            >
              <VChip
                v-for="chip in invoiceStatusFilters"
                :key="chip.value"
                :value="chip.value"
                size="small"
                variant="outlined"
                filter
                class="text-no-wrap"
                :color="chip.value === 'all' ? undefined : invoiceStatusColor[chip.value]"
              >
                {{ chip.title }} ({{ statusCounts[chip.value] ?? 0 }})
              </VChip>
            </VChipGroup>
          </div>
          <VBtn
            v-if="hasActiveFilters"
            size="small"
            variant="text"
            prepend-icon="ri-filter-off-line"
            @click="clearFilters"
          >
            Reset
          </VBtn>
        </div>
      </VCardText>
    </VCard>

    <VAlert
      v-if="loadError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      role="alert"
      @click:close="loadError = ''"
    >
      {{ loadError }}
    </VAlert>
    <VAlert
      v-if="generateError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      role="alert"
      @click:close="generateError = ''"
    >
      {{ generateError }}
    </VAlert>
    <VAlert
      v-if="generateSuccess"
      type="success"
      variant="tonal"
      class="mb-4"
      closable
      role="status"
      aria-live="polite"
      @click:close="generateSuccess = ''"
    >
      {{ generateSuccess }}
    </VAlert>

    <StatCards
      v-if="!loading"
      :cards="statCards"
    />

    <InvoiceBillsSection
      v-model:show-billing-help="showBillingHelp"
      :invoices="scopedInvoices"
      :filtered-invoices="filteredInvoices"
      :paged-invoices="pagedInvoices"
      :loading="loading"
      :all-months="allMonths"
      :all-locations="allLocations"
      :bills-caption="billsCaption"
      :expanded-id="expandedId"
      :status-updating-id="statusUpdatingId"
      :location-name="locationName"
      :variant="variant"
      :sort="invoiceSort"
      @sort="onInvoiceSort"
      @toggle-expand="toggleExpand"
      @row-keydown="onInvoiceRowKeydown"
      @print="printInvoice"
      @edit="openEditInvoice"
      @credit="openCreditNote"
      @issue="askStatus($event, 'issued')"
      @pay="goMarkPaid"
      @void="askStatus($event, 'void')"
      @remove="pendingRemove = $event"
      @clear-filters="clearFilters"
    >
      <template #pagination>
        <AttendancePaginationBar
          v-if="!loading && filteredInvoices.length > 0"
          v-model:page="page"
          v-model:page-size="pageSize"
          :total-pages="totalPages"
          :page-size-options="pageSizeOptions"
        />
      </template>
    </InvoiceBillsSection>

    <AttendanceConfirmDialog
      :model-value="pendingStatus != null"
      :title="statusConfirmTitle"
      :confirm-label="statusConfirmLabel"
      :cancel-label="statusConfirmCancelLabel"
      :confirm-color="statusConfirmColor"
      :max-width="statusConfirmMaxWidth"
      :loading="statusUpdatingId === pendingStatus?.invoice.id"
      :error="generateError"
      @update:model-value="value => { if (!value) pendingStatus = null }"
      @confirm="confirmPendingStatus"
      @cancel="pendingStatus = null"
      @clear-error="generateError = ''"
    >
      <template v-if="pendingStatus?.status === 'issued'">
        <p class="text-body-2 mb-4">
          Issuing locks <strong>{{ invoiceStudentLabel(pendingStatus.invoice) }}</strong>
          at <strong>{{ formatInvoiceMoney(Number(pendingStatus.invoice.total)) }}</strong>.
          Generate will not change this bill after that.
        </p>
        <VTextField
          v-model="issueNoInput"
          label="Invoice no."
          density="compact"
          hide-details
          autocomplete="off"
          spellcheck="false"
          autofocus
          @update:model-value="issueNoEdited = true; issueNoError = ''"
        />
        <div class="text-caption text-medium-emphasis mt-1 mb-4">
          Auto-generated — change only if you need a different number.
        </div>
        <VAlert
          v-if="issueNoError"
          type="error"
          variant="text"
          density="compact"
          class="mb-3"
        >
          {{ issueNoError }}
        </VAlert>
        <VCombobox
          v-model="issueStaff"
          :items="issueStaffOptions"
          label="Opened by"
          density="compact"
          hide-details
          autocomplete="off"
          clearable
        />
        <div class="text-caption text-medium-emphasis mt-1 mb-4">
          Who opened this bill — for commission. Not printed.
        </div>
        <VTextField
          v-model="issueRemark"
          label="Remark"
          density="compact"
          hide-details
          placeholder="Optional — printed on the invoice"
          autocomplete="off"
          clearable
        />
        <div class="text-caption text-medium-emphasis mt-1">
          The printed invoice opens in a new window after issuing.
        </div>
      </template>
      <template v-else-if="pendingStatus?.status === 'void'">
        <p class="text-body-2 mb-0">
          <strong>{{ invoiceStudentLabel(pendingStatus.invoice) }}</strong>
          will be cancelled. The invoice number is held until you Remove this cancelled bill.
          <template v-if="pendingStatus.invoice.kind === 'manual'">
            Any class package on it can be billed again.
          </template>
          <template v-else>
            {{ INVOICE_CANCEL_GENERATED }}
          </template>
        </p>
      </template>
    </AttendanceConfirmDialog>

    <AttendanceConfirmDialog
      :model-value="pendingGenerate"
      title="Generate bills for this month?"
      confirm-label="Generate"
      confirm-color="primary"
      :loading="generating"
      @update:model-value="value => { if (!value) pendingGenerate = false }"
      @confirm="confirmGenerate"
      @cancel="pendingGenerate = false"
    >
      Replaces drafts for {{ locationId ? (locationName(locationId) || 'this campus') : 'all campuses' }}. {{ GENERATE_CONFIRM }}
    </AttendanceConfirmDialog>

    <AttendanceConfirmDialog
      :model-value="pendingRemove != null"
      title="Remove this cancelled bill?"
      confirm-label="Remove"
      cancel-label="Keep bill"
      confirm-color="error"
      :loading="statusUpdatingId === pendingRemove?.id"
      :error="generateError"
      @update:model-value="value => { if (!value) pendingRemove = null }"
      @confirm="confirmRemoveCancelled"
      @cancel="pendingRemove = null"
      @clear-error="generateError = ''"
    >
      <p class="text-body-2 mb-0">
        {{ REMOVE_CANCELLED_INVOICE }}
      </p>
    </AttendanceConfirmDialog>

    <AttendanceConfirmDialog
      :model-value="pendingPrint != null"
      title="Print credit note"
      confirm-label="Print"
      confirm-color="primary"
      :max-width="480"
      @update:model-value="value => { if (!value) pendingPrint = null }"
      @confirm="confirmPrintCredit"
      @cancel="pendingPrint = null"
    >
      <p class="text-body-2 mb-4">
        These names print on the refund request. Paid by and Supervisor stay blank so they can be signed after printing.
      </p>
      <VTextField
        v-model="printPayableTo"
        label="Payable to name"
        density="compact"
        class="mb-3"
        autocomplete="off"
        autofocus
        @update:model-value="value => { if (!printPayeeName) printPayeeName = value }"
      />
      <VTextField
        v-model="printPayeeName"
        label="Name"
        density="compact"
        autocomplete="off"
      />
    </AttendanceConfirmDialog>

    <InvoiceManualDialog
      v-model="manualInvoiceOpen"
      :default-location-id="locationId"
      :location-options="locationOptions"
      :locations="locations"
      :default-month-label="defaultManualMonthLabel"
      :editing-invoice="editingInvoice"
      :credit-from-invoice="creditFromInvoice"
      :credit-mode="isCreditPage"
      @update:model-value="value => { if (!value) closeManualInvoice() }"
      @created="onManualCreated"
    />
  </VContainer>
</template>

<style scoped lang="scss">
.invoice-page-title {
  text-wrap: balance;
}

.invoice-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 16px;
}

.invoice-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}

.invoice-filter-location {
  width: 220px;
  max-width: 100%;
}

.invoice-filter-search {
  width: 240px;
  max-width: 100%;
}

.invoice-status-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  align-items: center;
}

.filter-chip-block {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
  align-items: center;
  min-width: 0;
}
</style>
