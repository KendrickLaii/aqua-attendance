<script setup lang="ts">
import {
  type ManualInvoiceLine,
  createManualTuitionInvoice,
  getNextInvoiceNo,
} from '@/api/attendance/tuitionInvoices'
import { type LocationItem } from '@/api/attendance/locations'
import {
  type CourseEnrollment,
  type CourseSku,
  type EnrollmentPurchase,
  listAllCourseEnrollments,
  listCourseSkus,
} from '@/api/attendance/courses'
import { type Unit, listAllUnits, listUnits } from '@/api/attendance/units'
import { resolvePrintLogoUrl } from '@/api/attendance/uploads'
import { formatApiError } from '@/utils/formatApiDetail'
import {
  formatInvoiceMoney,
  invoicePrintHeaderFromLocation,
} from '@/utils/invoiceDisplay'
import {
  invoiceMonthLabel,
  openTuitionInvoicePrintPlaceholder,
  printTuitionInvoice,
  tuitionInvoicePrintData,
} from '@/utils/printTuitionInvoice'

const props = defineProps<{
  modelValue: boolean
  defaultLocationId: string | null
  locationOptions: { value: string; title: string }[]
  locations: LocationItem[]
  defaultMonthLabel: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  created: []
}>()

interface ManualInvoiceRow {
  month: string
  course: string
  fee: string
  qty: string
  purchaseId?: string
}

interface UnbilledPackage {
  purchase: EnrollmentPurchase
  enrollment: CourseEnrollment
  sku: CourseSku | undefined
}

const MANUAL_MAX_ROWS = 5
const open = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})

const manualError = ref('')
const manualPrinting = ref(false)
const manualNoEdited = ref(false)
const manualLocationId = ref<string | null>(null)
const manualForm = ref<{
  invoiceNo: string
  date: string
  studentName: string
  staff: string
  remark: string
  rows: ManualInvoiceRow[]
}>({
  invoiceNo: '',
  date: '',
  studentName: '',
  staff: '',
  remark: '',
  rows: [],
})

const manualStudent = ref<Unit | string | null>(null)
const manualStudentSearch = ref('')
const manualStudentOptions = ref<Unit[]>([])
const manualStudentLoading = ref(false)
let manualStudentRequestId = 0
const manualSkus = ref<CourseSku[]>([])
const manualSkusLoaded = ref(false)
const manualStaffUnits = ref<Unit[]>([])
const manualStaffLoaded = ref(false)
const manualUnbilledPackages = ref<UnbilledPackage[]>([])
const manualRemovedPackages = ref<UnbilledPackage[]>([])

const staffName = (id: string | null | undefined) =>
  manualStaffUnits.value.find(u => u.id === id)?.full_name ?? ''

const manualStaffOptions = computed(() => manualStaffUnits.value.map(u => u.full_name))

function suggestManualStaff(staffId: string | null | undefined) {
  if (!(manualForm.value.staff ?? '').trim())
    manualForm.value.staff = staffName(staffId)
}

function blankManualRow(): ManualInvoiceRow {
  return {
    month: props.defaultMonthLabel,
    course: '',
    fee: '',
    qty: '',
  }
}

function isBlankManualRow(row: ManualInvoiceRow): boolean {
  return !row.purchaseId && !row.course.trim() && !row.fee.trim() && !row.qty.trim()
}

const manualCanAddRow = computed(
  () => manualForm.value.rows.length < MANUAL_MAX_ROWS
    || manualForm.value.rows.some(isBlankManualRow),
)

function pushManualRow(row: ManualInvoiceRow): boolean {
  const blankIdx = manualForm.value.rows.findIndex(isBlankManualRow)
  if (blankIdx !== -1) {
    manualForm.value.rows[blankIdx] = row

    return true
  }
  if (manualForm.value.rows.length >= MANUAL_MAX_ROWS)
    return false
  manualForm.value.rows.push(row)

  return true
}

async function loadManualStudents(search?: string) {
  const requestId = ++manualStudentRequestId

  manualStudentLoading.value = true
  try {
    const students = await listUnits({
      unit_type: 'student',
      is_active: true,
      search: search || undefined,
      page_size: 20,
    })

    if (requestId === manualStudentRequestId)
      manualStudentOptions.value = students.filter(u => u.status === 'active')
  }
  catch (e) {
    if (requestId === manualStudentRequestId)
      manualError.value = formatApiError(e, 'Could not load students. Search by name, or type a walk-in name.')
  }
  finally {
    if (requestId === manualStudentRequestId)
      manualStudentLoading.value = false
  }
}

const manualStudentDebounce = useDebounceFn(() => loadManualStudents(manualStudentSearch.value.trim()), 300)

watch(manualStudentSearch, value => {
  if (!open.value)
    return
  if (value.trim())
    manualStudentDebounce()
  else
    loadManualStudents()
})

watch(manualStudent, picked => {
  manualRemovedPackages.value = []
  manualForm.value.rows = manualForm.value.rows.filter(row => !row.purchaseId)
  if (picked && typeof picked !== 'string') {
    manualForm.value.studentName = picked.full_name
    loadManualUnbilledPackages(picked.id)
  }
  else if (typeof picked === 'string') {
    manualForm.value.studentName = picked
    manualUnbilledPackages.value = []
  }
  else {
    manualForm.value.studentName = ''
    manualUnbilledPackages.value = []
  }
})

async function loadManualStaff() {
  if (manualStaffLoaded.value)
    return
  try {
    manualStaffUnits.value = await listAllUnits({ unit_type: 'staff' })
    manualStaffLoaded.value = true
  }
  catch (e) {
    manualStaffUnits.value = []
    manualError.value = formatApiError(e, 'Could not load staff names. Type who opened this bill.')
  }
}

async function loadManualSkus() {
  if (manualSkusLoaded.value)
    return
  try {
    manualSkus.value = await listCourseSkus()
    manualSkusLoaded.value = true
  }
  catch (e) {
    manualError.value = formatApiError(e, 'Could not load classes. You can still type class names on each line.')
  }
}

async function loadManualUnbilledPackages(unitId: string) {
  try {
    await loadManualSkus()
    await loadManualStaff()

    const enrollments = await listAllCourseEnrollments({ unit_id: unitId })

    manualUnbilledPackages.value = enrollments.flatMap(enrollment =>
      enrollment.purchases
        .filter(p => p.billed_invoice_line_id === null)
        .map(purchase => ({
          purchase,
          enrollment,
          sku: manualSkus.value.find(k => k.id === enrollment.sku_id),
        })),
    )
  }
  catch (e) {
    manualUnbilledPackages.value = []
    manualError.value = formatApiError(e, 'Could not load unbilled class packages for this student.')
  }
}

function addPurchaseLine(pkg: UnbilledPackage) {
  const row = blankManualRow()

  row.month = invoiceMonthLabel(`${pkg.purchase.purchased_at.slice(0, 7)}-01`)
  row.course = pkg.sku?.name_zh ?? 'Sessions'
  row.fee = pkg.purchase.unit_price != null ? String(pkg.purchase.unit_price) : ''
  row.qty = String(pkg.purchase.purchased_quantity)
  row.purchaseId = pkg.purchase.id

  suggestManualStaff(pkg.sku?.staff_id)

  if (!pushManualRow(row))
    return

  manualUnbilledPackages.value = manualUnbilledPackages.value.filter(
    x => x.purchase.id !== pkg.purchase.id,
  )
  manualRemovedPackages.value.push(pkg)
}

function removeManualRow(idx: number) {
  const [removed] = manualForm.value.rows.splice(idx, 1)
  if (!removed?.purchaseId)
    return

  const restoredIdx = manualRemovedPackages.value.findIndex(p => p.purchase.id === removed.purchaseId)
  if (restoredIdx !== -1)
    manualUnbilledPackages.value.push(...manualRemovedPackages.value.splice(restoredIdx, 1))
}

const manualClassOptions = computed(() =>
  manualSkus.value
    .filter(k => k.is_active)
    .slice()
    .sort((a, b) => {
      const byCode = a.code.localeCompare(b.code, undefined, { numeric: true, sensitivity: 'base' })
      if (byCode !== 0)
        return byCode

      return a.name_zh.localeCompare(b.name_zh, undefined, { numeric: true, sensitivity: 'base' })
    })
    .map(k => ({
      ...k,
      title: `${k.code} · ${k.name_zh}`,
      subtitle: `${k.billing_unit === 'per_session' ? 'Per class' : 'Monthly'}${k.price != null ? ` · HK$${Number(k.price).toFixed(2)}` : ''}`,
    })),
)

function onClassPicked(id: string | null) {
  if (!id)
    return

  const pkg = manualUnbilledPackages.value.find(p => p.enrollment.sku_id === id)
  if (pkg) {
    addPurchaseLine(pkg)

    return
  }

  const sku = manualSkus.value.find(k => k.id === id)
  if (!sku)
    return

  const row = blankManualRow()

  row.course = sku.name_zh
  row.fee = sku.price != null ? String(sku.price) : ''
  row.qty = sku.billing_unit === 'per_session' ? '' : '1'

  suggestManualStaff(sku.staff_id)
  pushManualRow(row)
}

async function suggestManualInvoiceNo() {
  try {
    if (!manualLocationId.value)
      return
    const next = await getNextInvoiceNo(manualLocationId.value)

    if (open.value && !manualNoEdited.value)
      manualForm.value.invoiceNo = String(next)
  }
  catch (e) {
    manualError.value = formatApiError(e, 'Could not suggest the next invoice number. Enter it yourself.')
  }
}

watch(manualLocationId, () => {
  if (open.value)
    suggestManualInvoiceNo()
})

function resetForm() {
  manualError.value = ''
  manualForm.value = {
    invoiceNo: '',
    date: new Date().toLocaleDateString('en-CA'),
    studentName: '',
    staff: '',
    remark: '',
    rows: [blankManualRow()],
  }
  manualStudent.value = null
  manualStudentSearch.value = ''
  manualUnbilledPackages.value = []
  manualRemovedPackages.value = []
  manualNoEdited.value = false
  manualLocationId.value = props.defaultLocationId
}

watch(open, value => {
  if (!value)
    return
  resetForm()
  loadManualStudents()
  loadManualSkus()
  loadManualStaff()
  suggestManualInvoiceNo()
})

function manualNumber(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed)
    return null
  const parsed = Number(trimmed)

  return Number.isNaN(parsed) ? null : parsed
}

function manualRowAmount(row: ManualInvoiceRow): number | null {
  const fee = manualNumber(row.fee)
  const qty = manualNumber(row.qty)
  if (fee == null || qty == null)
    return null

  return fee * qty
}

const manualTotal = computed(
  () => manualForm.value.rows.reduce((sum, row) => sum + (manualRowAmount(row) ?? 0), 0),
)

async function printOptionsFor(invoice: { location_id: string }) {
  const location = props.locations.find(l => l.id === invoice.location_id)

  return {
    logoUrl: await resolvePrintLogoUrl(location?.icon_url || location?.main_photo_url || ''),
    header: location ? invoicePrintHeaderFromLocation(location) : undefined,
  }
}

async function printManualInvoice() {
  manualPrinting.value = true
  manualError.value = ''
  try {
    if (manualForm.value.rows.some(row => row.purchaseId && manualNumber(row.fee) == null)) {
      manualError.value = 'Session package lines need a fee — enter the price to charge.'
      manualPrinting.value = false

      return
    }

    const validLines = manualForm.value.rows
      .map(row => ({
        month: row.month.trim(),
        course: row.course.trim(),
        fee: manualNumber(row.fee),
        qty: manualNumber(row.qty),
        staff_name: (manualForm.value.staff ?? '').trim() || null,
        purchase_id: row.purchaseId || undefined,
      }))
      .filter(row => row.course && row.fee != null && row.fee >= 0 && row.qty != null && row.qty > 0)

    const touchedRows = manualForm.value.rows.filter(
      row => row.purchaseId || row.course.trim() || row.fee.trim() || row.qty.trim(),
    ).length

    if (validLines.length < touchedRows) {
      manualError.value = 'Each filled line needs a course, a fee (0 or more) and a quantity above 0 — fix or remove it.'
      manualPrinting.value = false

      return
    }

    if (validLines.length === 0) {
      manualError.value = 'Add at least one line with course, fee and quantity.'
      manualPrinting.value = false

      return
    }

    const unitId = manualStudent.value && typeof manualStudent.value !== 'string'
      ? manualStudent.value.id
      : undefined

    if (!unitId && !(manualForm.value.studentName ?? '').trim()) {
      manualError.value = 'Pick a student, or type a name for a walk-in invoice.'
      manualPrinting.value = false

      return
    }

    if (!manualLocationId.value) {
      manualError.value = 'Please select a location for the manual invoice.'
      manualPrinting.value = false

      return
    }

    let printWindow: Window | null = null
    try {
      printWindow = openTuitionInvoicePrintPlaceholder()
    }
    catch (e) {
      manualError.value = formatApiError(e, 'Could not open print window.')
      manualPrinting.value = false

      return
    }

    try {
      const created = await createManualTuitionInvoice({
        date: manualForm.value.date,
        location_id: manualLocationId.value,
        unit_id: unitId,
        manual_student_name: unitId ? null : ((manualForm.value.studentName ?? '').trim() || null),
        staff_name: (manualForm.value.staff ?? '').trim() || null,
        invoice_no: manualNoEdited.value ? (manualForm.value.invoiceNo ?? '').trim() || undefined : undefined,
        notes: (manualForm.value.remark ?? '').trim() || null,
        lines: validLines as ManualInvoiceLine[],
      })

      printTuitionInvoice(
        printWindow,
        tuitionInvoicePrintData(created, await printOptionsFor(created)),
      )
      open.value = false
      emit('created')
    }
    catch (e) {
      printWindow.close()
      throw e
    }
  }
  catch (e) {
    manualError.value = formatApiError(e, 'Could not create or print manual invoice.')
  }
  finally {
    manualPrinting.value = false
  }
}
</script>

<template>
  <VDialog
    v-model="open"
    max-width="960"
    persistent
  >
    <VCard>
      <VCardTitle class="text-h6 py-4">
        Manual invoice
      </VCardTitle>
      <VDivider />
      <VCardText class="pa-4">
        <div class="text-caption text-medium-emphasis mb-3">
          Creates an issued bill you can reprint and track payment for — use this for one-off sales and private-class packages that Generate skips.
        </div>
        <VAlert
          v-if="manualError"
          type="error"
          variant="tonal"
          density="compact"
          class="mb-3"
          closable
          @click:close="manualError = ''"
        >
          {{ manualError }}
        </VAlert>
        <VRow dense>
          <VCol
            cols="12"
            sm="4"
          >
            <VTextField
              v-model="manualForm.invoiceNo"
              label="Invoice no."
              density="compact"
              hint="Auto-generated — editable"
              persistent-hint
              @update:model-value="manualNoEdited = true"
            />
          </VCol>
          <VCol
            cols="12"
            sm="4"
          >
            <VTextField
              v-model="manualForm.date"
              label="Date"
              type="date"
              density="compact"
              hide-details
            />
          </VCol>
          <VCol
            cols="12"
            sm="4"
          >
            <VSelect
              v-model="manualLocationId"
              :items="locationOptions"
              label="Location (logo)"
              density="compact"
              hide-details
              clearable
            />
          </VCol>
          <VCol
            cols="12"
            sm="7"
          >
            <VCombobox
              v-model="manualStudent"
              v-model:search="manualStudentSearch"
              :items="manualStudentOptions"
              :loading="manualStudentLoading"
              item-title="full_name"
              return-object
              label="Student name"
              placeholder="Search student name or code — or type any name…"
              prepend-inner-icon="ri-search-line"
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
          </VCol>
          <VCol
            cols="12"
            sm="5"
          >
            <VCombobox
              v-model="manualForm.staff"
              :items="manualStaffOptions"
              label="Opened by"
              placeholder="Who opened this bill — for commission…"
              prepend-inner-icon="ri-user-star-line"
              density="compact"
              hint="Applies to every line; not printed on the invoice."
              persistent-hint
              clearable
            />
          </VCol>
          <VCol
            v-if="manualUnbilledPackages.length && manualCanAddRow"
            cols="12"
          >
            <div class="text-caption text-medium-emphasis mb-1">
              Unbilled class packages — click to add a line:
            </div>
            <VChip
              v-for="pkg in manualUnbilledPackages"
              :key="pkg.purchase.id"
              color="primary"
              variant="tonal"
              class="me-2 mb-1"
              @click="addPurchaseLine(pkg)"
            >
              <VIcon
                icon="ri-add-line"
                size="14"
                start
              />
              {{ pkg.sku ? `${pkg.sku.code} · ${pkg.sku.name_zh}` : 'Sessions' }}
              · {{ pkg.purchase.purchased_quantity }} {{ pkg.purchase.purchased_quantity === 1 ? 'class' : 'classes' }}
              <template v-if="pkg.purchase.unit_price != null">
                × HK${{ Number(pkg.purchase.unit_price).toFixed(2) }}
              </template>
              <template v-else>
                · price not set
              </template>
              · {{ pkg.purchase.purchased_at }}
            </VChip>
          </VCol>
        </VRow>

        <VTable
          density="compact"
          class="mt-4 no-number-spin"
        >
          <thead>
            <tr>
              <th>Month</th>
              <th>Class</th>
              <th style="width: 110px;">
                Price
              </th>
              <th style="width: 90px;">
                Qty
              </th>
              <th
                class="text-end"
                style="width: 110px;"
              >
                Total
              </th>
              <th style="width: 40px;" />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, idx) in manualForm.rows"
              :key="idx"
            >
              <td>
                <VTextField
                  v-model="row.month"
                  density="compact"
                  hide-details
                  placeholder="Sept-26…"
                />
              </td>
              <td>
                <div class="d-flex align-center">
                  <VTextField
                    v-model="row.course"
                    density="compact"
                    hide-details
                    placeholder="Homework class…"
                  />
                  <VChip
                    v-if="row.purchaseId"
                    size="x-small"
                    color="primary"
                    variant="tonal"
                    class="ms-1 flex-shrink-0"
                  >
                    Per class
                  </VChip>
                </div>
              </td>
              <td>
                <VTextField
                  v-model="row.fee"
                  density="compact"
                  hide-details
                  type="number"
                  min="0"
                />
              </td>
              <td>
                <VTextField
                  v-model="row.qty"
                  density="compact"
                  hide-details
                  type="number"
                  min="0"
                  :disabled="Boolean(row.purchaseId)"
                  :title="row.purchaseId ? 'Bills the whole purchased package' : undefined"
                />
              </td>
              <td class="text-end text-no-wrap">
                {{ manualRowAmount(row) == null ? '—' : formatInvoiceMoney(manualRowAmount(row)!) }}
              </td>
              <td class="text-end">
                <VBtn
                  icon="ri-close-line"
                  size="x-small"
                  variant="text"
                  aria-label="Remove line"
                  :disabled="manualForm.rows.length <= 1"
                  @click="removeManualRow(idx)"
                />
              </td>
            </tr>
          </tbody>
        </VTable>
        <div class="d-flex flex-wrap align-center gap-2 mt-2">
          <VBtn
            size="small"
            variant="text"
            prepend-icon="ri-add-line"
            :disabled="manualForm.rows.length >= MANUAL_MAX_ROWS || manualForm.rows.some(isBlankManualRow)"
            @click="manualForm.rows.push(blankManualRow())"
          >
            Add line
          </VBtn>
          <VAutocomplete
            :model-value="null"
            :items="manualClassOptions"
            item-title="title"
            item-value="id"
            label="Add a class"
            prepend-inner-icon="ri-add-circle-line"
            density="compact"
            hide-details
            clearable
            style="max-width: 320px; min-width: 200px;"
            :disabled="manualClassOptions.length === 0 || !manualCanAddRow"
            @update:model-value="onClassPicked"
          >
            <template #item="{ props: itemProps, item }">
              <VListItem
                v-bind="itemProps"
                :title="item.raw.title"
                :subtitle="item.raw.subtitle"
              />
            </template>
          </VAutocomplete>
          <VSpacer />
          <div class="font-weight-medium">
            Total: {{ formatInvoiceMoney(manualTotal) }}
          </div>
        </div>
        <VTextField
          v-model="manualForm.remark"
          label="Remark"
          density="compact"
          class="mt-3"
          placeholder="Optional — printed on the invoice"
          clearable
        />
      </VCardText>
      <VDivider />
      <DialogFooter>
        <VBtn
          variant="outlined"
          color="primary"
          @click="open = false"
        >
          Cancel
        </VBtn>
        <VBtn
          variant="flat"
          color="primary"
          prepend-icon="ri-printer-line"
          :loading="manualPrinting"
          @click="printManualInvoice"
        >
          Create &amp; print
        </VBtn>
      </DialogFooter>
    </VCard>
  </VDialog>
</template>

<style scoped lang="scss">
.no-number-spin :deep(input[type='number']) {
  appearance: textfield;
  -moz-appearance: textfield;
}

.no-number-spin :deep(input[type='number']::-webkit-outer-spin-button),
.no-number-spin :deep(input[type='number']::-webkit-inner-spin-button) {
  -webkit-appearance: none;
  margin: 0;
}
</style>
