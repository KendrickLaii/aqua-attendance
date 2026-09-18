<script setup lang="ts">
import {
  createTuitionReceipt,
  listOpenInvoices,
} from '@/api/attendance/tuitionReceipts'
import { type TuitionInvoice } from '@/api/attendance/tuitionInvoices'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import { type Unit, listUnits } from '@/api/attendance/units'
import { requiredValidator } from '@core/utils/validators'
import { formatApiError } from '@/utils/formatApiDetail'
import { resolveMediaUrl } from '@/utils/mediaUrl'
import {
  type TuitionInvoicePrintHeader,
} from '@/utils/printTuitionInvoice'
import {
  openTuitionReceiptPrintPlaceholder,
  printTuitionReceipt,
  tuitionReceiptPrintData,
} from '@/utils/printTuitionReceipt'

definePage({ meta: {} })

const route = useRoute()
const router = useRouter()
const { ensureAccess } = useAttendanceAdminGate()

const LOCATION_FILTER_KEY = 'tuition-receipt-location'

interface AdjustmentRow {
  key: number
  month: string
  course: string
  amount: number | null
}

const locations = ref<LocationItem[]>([])
const paidBy = ref('')
const amount = ref(0)
const adjustments = ref<AdjustmentRow[]>([])
let adjustmentKey = 0
let amountDirty = false
const description = ref('')
const saving = ref(false)
const loadError = ref('')
const formError = ref('')
const openInvoices = ref<TuitionInvoice[]>([])
const selectedIds = ref<string[]>([])
const loadingInvoices = ref(false)
const student = ref<Unit | null>(null)
const studentSearch = ref('')
const studentOptions = ref<Unit[]>([])
const studentLoading = ref(false)
const walkInName = ref('')
const seedInvoiceId = typeof route.query.invoice_id === 'string' ? route.query.invoice_id : null
const lockedFromInvoice = Boolean(seedInvoiceId)
let studentRequestId = 0
const locationId = ref<string | null>(
  typeof route.query.location_id === 'string'
    ? route.query.location_id
    : localStorage.getItem(LOCATION_FILTER_KEY),
)
const receiptDate = ref(new Date().toLocaleDateString('en-CA'))

const locationOptions = computed(() =>
  locations.value
    .filter(location => location.is_active)
    .map(location => ({
      value: location.id,
      title: location.name_zh || location.name_en,
    })),
)

const selectedInvoices = computed(() =>
  openInvoices.value.filter(invoice => selectedIds.value.includes(invoice.id)),
)
const invoiceTotal = computed(() =>
  selectedInvoices.value.reduce((sum, invoice) => sum + Number(invoice.total), 0),
)
const adjustmentTotal = computed(() =>
  adjustments.value.reduce((sum, row) => sum + Number(row.amount || 0), 0),
)
const expectedAmount = computed(() =>
  Math.round((invoiceTotal.value + adjustmentTotal.value) * 100) / 100,
)
const amountFits = computed(() =>
  Math.round(Number(amount.value) * 100) / 100 === expectedAmount.value,
)
const paidByOk = computed(() => Boolean(paidBy.value.trim()))
const lockedStudentLabel = computed(() => {
  const first = openInvoices.value.find(row => row.id === seedInvoiceId) ?? openInvoices.value[0]
  if (first)
    return studentLabel(first)
  return walkInName.value || '—'
})

function formatMoney(value: number): string {
  return `HK$${Number(value).toLocaleString('en-HK', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function studentLabel(invoice: TuitionInvoice): string {
  if (invoice.unit_name)
    return invoice.unit_code ? `${invoice.unit_name} (${invoice.unit_code})` : invoice.unit_name
  return invoice.manual_student_name || '—'
}

function classPreview(invoice: TuitionInvoice): string {
  return invoice.lines.map(line => line.name_zh || line.sku_code).filter(Boolean).join(' · ')
}

function roundMoney(value: number): number {
  return Math.round(Number(value) * 100) / 100
}

function addAdjustment() {
  adjustments.value.push({
    key: ++adjustmentKey,
    month: '',
    course: '調整',
    amount: 0,
  })
}

function removeAdjustment(key: number) {
  adjustments.value = adjustments.value.filter(row => row.key !== key)
}

function onAmountInput() {
  amountDirty = true
}

const adjustmentPayload = computed(() =>
  adjustments.value
    .filter(row => Number(row.amount) !== 0)
    .map(row => ({
      month: row.month.trim(),
      course: row.course.trim() || '調整',
      fee: null,
      qty: null,
      amount: roundMoney(Number(row.amount)),
    })),
)

watch(expectedAmount, value => {
  if (!amountDirty)
    amount.value = value
}, { immediate: true })

watch([selectedIds, adjustments], () => {
  amountDirty = false
  amount.value = expectedAmount.value
}, { deep: true })

async function loadLocations() {
  locations.value = await listLocations({ page_size: 200 })
  if (locationId.value && !locationOptions.value.some(item => item.value === locationId.value))
    locationId.value = locationOptions.value[0]?.value ?? null
  if (!locationId.value)
    locationId.value = locationOptions.value[0]?.value ?? null
}

async function loadStudents(search?: string) {
  const requestId = ++studentRequestId
  studentLoading.value = true
  try {
    const students = await listUnits({
      unit_type: 'student',
      is_active: true,
      search: search || undefined,
      page_size: 20,
    })
    if (requestId === studentRequestId)
      studentOptions.value = students.filter(unit => unit.status === 'active')
  }
  catch (e) {
    if (requestId === studentRequestId)
      formError.value = formatApiError(e, 'Could not load students.')
  }
  finally {
    if (requestId === studentRequestId)
      studentLoading.value = false
  }
}

const studentDebounce = useDebounceFn(() => loadStudents(studentSearch.value.trim()), 300)

watch(studentSearch, value => {
  if (lockedFromInvoice)
    return
  if (value.trim())
    studentDebounce()
  else
    loadStudents()
})

async function loadOpenInvoices() {
  if (!locationId.value)
    return
  loadingInvoices.value = true
  formError.value = ''
  try {
    if (seedInvoiceId) {
      openInvoices.value = await listOpenInvoices({
        location_id: locationId.value,
        invoice_id: seedInvoiceId,
      })
      const seedFound = openInvoices.value.some(row => row.id === seedInvoiceId)
      selectedIds.value = seedFound ? [seedInvoiceId] : []
      if (!seedFound)
        formError.value = 'This invoice is not issued, so it cannot be paid.'
      const first = openInvoices.value.find(row => row.id === seedInvoiceId) ?? openInvoices.value[0]
      walkInName.value = first?.manual_student_name ?? ''
      if (first?.unit_id && !student.value) {
        student.value = studentOptions.value.find(unit => unit.id === first.unit_id) ?? {
          id: first.unit_id,
          full_name: first.unit_name ?? '',
          code: first.unit_code ?? '',
        } as Unit
      }
      return
    }

    if (!student.value) {
      openInvoices.value = []
      selectedIds.value = []
      return
    }

    openInvoices.value = await listOpenInvoices({
      location_id: locationId.value,
      unit_id: student.value.id,
    })
    selectedIds.value = openInvoices.value.map(row => row.id)
  }
  catch (e) {
    formError.value = formatApiError(e, 'Could not load unpaid invoices.')
    openInvoices.value = []
  }
  finally {
    loadingInvoices.value = false
  }
}

watch([locationId, student], () => {
  if (!lockedFromInvoice)
    loadOpenInvoices()
})

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

async function submit() {
  if (!locationId.value) {
    formError.value = 'Pick a location.'
    return
  }
  if (!paidBy.value?.trim()) {
    formError.value = 'PAID BY is required.'
    return
  }
  if (!selectedIds.value.length) {
    formError.value = 'Select at least one issued invoice.'
    return
  }
  if (!amountFits.value) {
    formError.value = `Amount does not match invoices plus adjustments (expected ${formatMoney(expectedAmount.value)}).`
    return
  }

  let printWindow: Window | null = null
  try {
    printWindow = openTuitionReceiptPrintPlaceholder()
  }
  catch (e) {
    formError.value = formatApiError(e, 'Could not open print window.')
    return
  }

  saving.value = true
  formError.value = ''
  try {
    const first = selectedInvoices.value[0]
    const created = await createTuitionReceipt({
      location_id: locationId.value,
      unit_id: first?.unit_id ?? student.value?.id ?? null,
      payer_name: first?.unit_id ? null : (walkInName.value || first?.manual_student_name || null),
      paid_by: paidBy.value.trim(),
      receipt_date: receiptDate.value,
      invoice_ids: selectedIds.value,
      amount: roundMoney(Number(amount.value)),
      adjustments: adjustmentPayload.value,
      description: description.value.trim() || null,
    })
    const location = locations.value.find(item => item.id === created.location_id)
    printTuitionReceipt(printWindow, tuitionReceiptPrintData(created, {
      logoUrl: resolveMediaUrl(location?.icon_url || location?.main_photo_url || ''),
      header: location ? headerFromLocation(location) : undefined,
    }))
    await router.push('/attendance/receipts')
  }
  catch (e) {
    printWindow.close()
    formError.value = formatApiError(e, 'Could not create receipt.')
  }
  finally {
    saving.value = false
  }
}

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  try {
    await loadLocations()
    if (!lockedFromInvoice)
      await loadStudents()
    await loadOpenInvoices()
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Could not open the receipt form.')
  }
})
</script>

<template>
  <VContainer>
    <div class="d-flex align-center flex-wrap gap-2 mb-4">
      <VBtn
        variant="text"
        prepend-icon="ri-arrow-left-line"
        @click="router.push('/attendance/receipts')"
      >
        Receipts
      </VBtn>
      <h4 class="text-h4 mb-0">
        New receipt
      </h4>
    </div>

    <VAlert
      v-if="loadError"
      type="error"
      variant="tonal"
      class="mb-4"
    >
      {{ loadError }}
    </VAlert>
    <VAlert
      v-if="formError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="formError = ''"
    >
      {{ formError }}
    </VAlert>

    <VCard>
      <VCardText class="pa-4">
        <VRow>
          <VCol
            cols="12"
            md="4"
          >
            <VSelect
              v-model="locationId"
              :items="locationOptions"
              item-title="title"
              item-value="value"
              label="Location"
              density="compact"
              hide-details
              :disabled="lockedFromInvoice"
            />
          </VCol>
          <VCol
            cols="12"
            md="4"
          >
            <VTextField
              v-model="receiptDate"
              label="Receipt date"
              type="date"
              density="compact"
              hide-details
            />
          </VCol>
          <VCol
            cols="12"
            md="4"
          >
            <VTextField
              v-model="paidBy"
              density="compact"
              required
              :rules="[requiredValidator]"
              hide-details="auto"
              autocomplete="off"
            >
              <template #label>
                PAID BY <span class="text-error">*</span>
              </template>
            </VTextField>
          </VCol>
          <VCol
            cols="12"
            md="8"
          >
            <VCombobox
              v-if="!lockedFromInvoice"
              v-model="student"
              v-model:search="studentSearch"
              :items="studentOptions"
              :loading="studentLoading"
              item-title="full_name"
              return-object
              label="Student"
              placeholder="Search student…"
              density="compact"
              hide-details
              clearable
              no-filter
            >
              <template #item="{ props: itemProps, item }">
                <VListItem
                  v-bind="itemProps"
                  :subtitle="item.raw.code"
                />
              </template>
            </VCombobox>
            <VTextField
              v-else
              :model-value="lockedStudentLabel"
              label="Student"
              density="compact"
              hide-details
              disabled
            />
          </VCol>
          <VCol
            cols="12"
            md="4"
          >
            <VTextField
              v-model.number="amount"
              label="Amount"
              type="number"
              step="0.01"
              prefix="HK$"
              density="compact"
              :hide-details="amountFits"
              :error="!amountFits"
              :error-messages="amountFits ? undefined : `Must equal invoices plus adjustments (${formatMoney(expectedAmount)})`"
              @update:model-value="onAmountInput"
            />
          </VCol>
          <VCol cols="12">
            <VTextField
              v-model="description"
              label="Description"
              density="compact"
              hide-details
              autocomplete="off"
            />
          </VCol>
        </VRow>

        <div class="text-subtitle-2 mt-4 mb-2">
          Issued invoices
        </div>
        <div
          v-if="loadingInvoices"
          class="text-center py-6"
        >
          <VProgressCircular
            indeterminate
            color="primary"
          />
        </div>
        <div
          v-else-if="!openInvoices.length"
          class="text-medium-emphasis py-4"
        >
          No issued invoices to collect for this student.
        </div>
        <VTable
          v-else
          density="compact"
        >
          <thead>
            <tr>
              <th style="width: 48px;" />
              <th>Invoice</th>
              <th>Classes</th>
              <th class="text-end">
                Total
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="invoice in openInvoices"
              :key="invoice.id"
            >
              <td>
                <VCheckbox
                  v-model="selectedIds"
                  :value="invoice.id"
                  hide-details
                  density="compact"
                />
              </td>
              <td>
                <div>{{ invoice.invoice_no || '—' }}</div>
                <div class="text-caption text-medium-emphasis">
                  {{ invoice.period_start }}
                </div>
              </td>
              <td>{{ classPreview(invoice) }}</td>
              <td class="text-end tabular-nums">
                {{ formatMoney(Number(invoice.total)) }}
              </td>
            </tr>
          </tbody>
        </VTable>

        <div class="d-flex align-center justify-space-between mt-6 mb-2">
          <div class="text-subtitle-2">
            Adjustments
          </div>
          <VBtn
            size="small"
            variant="tonal"
            prepend-icon="ri-add-line"
            @click="addAdjustment"
          >
            Add adjustment
          </VBtn>
        </div>
        <div
          v-if="!adjustments.length"
          class="text-medium-emphasis mb-2"
        >
          Optional extra lines (discount, surcharge, rounding). Amount must still equal invoices plus these lines.
        </div>
        <VTable
          v-else
          density="compact"
          class="mb-2"
        >
          <thead>
            <tr>
              <th>Month</th>
              <th>Description</th>
              <th class="text-end">
                Amount
              </th>
              <th style="width: 48px;" />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in adjustments"
              :key="row.key"
            >
              <td>
                <VTextField
                  v-model="row.month"
                  density="compact"
                  hide-details
                  placeholder="Sept-26"
                  autocomplete="off"
                />
              </td>
              <td>
                <VTextField
                  v-model="row.course"
                  density="compact"
                  hide-details
                  placeholder="調整"
                  autocomplete="off"
                />
              </td>
              <td>
                <VTextField
                  v-model.number="row.amount"
                  type="number"
                  step="0.01"
                  density="compact"
                  hide-details
                  class="text-end"
                />
              </td>
              <td>
                <VBtn
                  icon="ri-delete-bin-line"
                  size="x-small"
                  variant="text"
                  @click="removeAdjustment(row.key)"
                />
              </td>
            </tr>
          </tbody>
        </VTable>
        <div class="text-caption text-medium-emphasis mb-4">
          Invoices {{ formatMoney(invoiceTotal) }}
          + Adjustments {{ formatMoney(adjustmentTotal) }}
          = {{ formatMoney(expectedAmount) }}
        </div>

        <div class="d-flex justify-end gap-2 mt-6">
          <VBtn
            variant="tonal"
            @click="router.push('/attendance/receipts')"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :loading="saving"
            :disabled="!selectedIds.length || !paidByOk"
            @click="submit"
          >
            Save and print
          </VBtn>
        </div>
      </VCardText>
    </VCard>
  </VContainer>
</template>
