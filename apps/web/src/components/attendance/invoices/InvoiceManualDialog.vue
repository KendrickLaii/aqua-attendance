<script setup lang="ts">
import {
  type ManualInvoiceLine,
  type TuitionInvoice,
  createManualTuitionInvoice,
  getNextInvoiceNo,
  updateTuitionInvoice,
} from '@/api/attendance/tuitionInvoices'
import { type LocationItem } from '@/api/attendance/locations'
import {
  type CourseEnrollment,
  type CourseSku,
  type EnrollmentPurchase,
  listAllCourseEnrollments,
  listCourseSkus,
} from '@/api/attendance/courses'
import { type Unit, getUnit, listAllUnits, listUnits } from '@/api/attendance/units'
import { resolvePrintLogoUrl } from '@/api/attendance/uploads'
import AttendanceConfirmDialog from '@/components/attendance/AttendanceConfirmDialog.vue'
import HelpBubble from '@/components/attendance/HelpBubble.vue'
import InvoicePrintVersionDialog from '@/components/attendance/invoices/InvoicePrintVersionDialog.vue'
import { useBranding } from '@/composables/useBranding'
import { formatApiError } from '@/utils/formatApiDetail'
import { MANUAL_CREDIT_HINT } from '@/utils/billingStaffCopy'
import {
  DEFAULT_INVOICE_CURRENCY,
  INVOICE_CURRENCIES,
  creditLinesFromInvoice,
  defaultCreditFee,
  formatInvoiceMoney,
  invoicePrintHeaderFromLocation,
  invoiceStudentLabel,
  isCreditInvoice,
  periodFromMonthLabels,
} from '@/utils/invoiceDisplay'
import {
  type TuitionInvoicePrintVersion,
  invoiceMonthLabel,
  openTuitionInvoicePrintPlaceholder,
  printTuitionInvoice,
  tuitionInvoicePrintData,
} from '@/utils/printTuitionInvoice'
import { debitNoteTeamCopy } from '@/utils/printTuitionDebitNote'
import {
  type InvoiceJobOption,
  deleteInvoiceJob,
  listInvoiceJobs,
} from '@/api/attendance/invoiceJobs'

const props = defineProps<{
  modelValue: boolean
  defaultLocationId: string | null
  locationOptions: { value: string; title: string }[]
  locations: LocationItem[]
  defaultMonthLabel: string
  editingInvoice?: TuitionInvoice | null
  creditFromInvoice?: TuitionInvoice | null
  creditMode?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  created: []
}>()

interface ManualInvoiceRow {
  key: number
  month: string
  course: string
  fee: string
  qty: string
  lineId?: string
  purchaseId?: string
}

let manualRowKey = 0

function nextManualRowKey(): number {
  manualRowKey += 1

  return manualRowKey
}

interface UnbilledPackage {
  purchase: EnrollmentPurchase
  enrollment: CourseEnrollment
  sku: CourseSku | undefined
}

const { brand, t } = useBranding()

const manualMaxRows = computed(() => Math.max(1, brand.value.manualInvoiceMaxLines))

const open = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})

const manualError = ref('')
const manualPrinting = ref(false)
const manualNoEdited = ref(false)
const manualLocationId = ref<string | null>(null)
const manualPeriodEdited = ref(false)
const manualForm = ref<{
  invoiceNo: string
  date: string
  period: string
  studentName: string
  staff: string
  currency: string
  topRemark: string
  remark: string
  payableTo: string
  payeeName: string
  rows: ManualInvoiceRow[]
}>({
  invoiceNo: '',
  date: '',
  period: '',
  studentName: '',
  staff: '',
  currency: DEFAULT_INVOICE_CURRENCY,
  topRemark: '',
  remark: '',
  payableTo: '',
  payeeName: '',
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
const lockedUnitId = ref<string | null>(null)
const manualTutorUnitId = ref<string | null>(null)
const hydratingForm = ref(false)

// Resolve the typed/picked Tutor name to a staff unit so the invoice stores
// tutor_unit_id; free text that matches no staff leaves it null.
watch(() => manualForm.value.staff, name => {
  if (hydratingForm.value)
    return
  const trimmed = (name ?? '').trim()

  manualTutorUnitId.value = manualStaffUnits.value.find(u => u.full_name === trimmed)?.id ?? null
})

const isDebitNote = computed(() => brand.value.invoicePrintTemplate === 'debit-note')
const jobs = ref<InvoiceJobOption[]>([])
const jobSearches = reactive<Record<number, string>>({})
const jobNames = computed(() => jobs.value.map(job => job.name))
const jobToDelete = ref<InvoiceJobOption | null>(null)
const deletingJob = ref(false)

const currencyItems = INVOICE_CURRENCIES.map(item => ({
  title: `${item.code} (${item.symbol})`,
  value: item.code,
}))

const isEdit = computed(() => Boolean(props.editingInvoice))
const isCredit = computed(() =>
  Boolean(props.creditFromInvoice && !props.editingInvoice)
  || Boolean(props.creditMode && !props.editingInvoice)
  || Boolean(props.editingInvoice && isCreditInvoice(props.editingInvoice)),
)
const studentLocked = computed(() => isEdit.value || Boolean(props.creditFromInvoice))

// Credit notes count in the month of their date; generated bills keep their month.
const showPeriod = computed(() =>
  !isCredit.value && (!props.editingInvoice || props.editingInvoice.kind === 'manual'),
)

const topRowCols = computed(() => {
  if (isDebitNote.value) {
    return showPeriod.value
      ? { invoiceNo: 3, date: 2, period: 2, location: 3, currency: 2 }
      : { invoiceNo: 3, date: 3, period: 0, location: 3, currency: 3 }
  }

  return showPeriod.value
    ? { invoiceNo: 3, date: 3, period: 3, location: 3, currency: 0 }
    : { invoiceNo: 4, date: 4, period: 0, location: 4, currency: 0 }
})

const linePeriod = computed(() =>
  periodFromMonthLabels(manualForm.value.rows.map(row => row.month))
  || (manualForm.value.date ?? '').slice(0, 7),
)

watch(linePeriod, value => {
  if (!manualPeriodEdited.value)
    manualForm.value.period = value
})

const staffName = (id: string | null | undefined) =>
  manualStaffUnits.value.find(u => u.id === id)?.full_name ?? ''

const manualStaffOptions = computed(() => manualStaffUnits.value.map(u => u.full_name))

function suggestManualStaff(staffId: string | null | undefined) {
  if (!(manualForm.value.staff ?? '').trim())
    manualForm.value.staff = staffName(staffId)
}

async function loadJobs() {
  if (!isDebitNote.value || !manualLocationId.value)
    return
  try {
    jobs.value = await listInvoiceJobs(manualLocationId.value)
  }
  catch (e) {
    manualError.value = formatApiError(e, 'Could not load jobs.')
  }
}

function savedJob(name: string) {
  return jobs.value.find(job => job.name.toLowerCase() === name.trim().toLowerCase())
}

function settleJob(row: ManualInvoiceRow) {
  const existing = savedJob(row.month)
  if (existing)
    row.month = existing.name
}

function onJobValue(idx: number, value: unknown) {
  const row = manualForm.value.rows[idx]
  if (!row)
    return
  row.month = value == null ? '' : String(value)
  nextTick(() => {
    jobSearches[idx] = ''
  })
}

function commitJob(idx: number, row: ManualInvoiceRow) {
  const typed = (jobSearches[idx] || '').trim()
  if (typed)
    row.month = savedJob(typed)?.name ?? typed
  jobSearches[idx] = ''
  settleJob(row)
}

function askRemoveJob(name: string) {
  jobToDelete.value = jobs.value.find(item => item.name === name) ?? null
}

async function confirmRemoveJob() {
  const job = jobToDelete.value
  if (!job)
    return
  deletingJob.value = true
  try {
    await deleteInvoiceJob(job.id)
    jobs.value = jobs.value.filter(item => item.id !== job.id)
    jobToDelete.value = null
  }
  catch (e) {
    manualError.value = formatApiError(e, 'Could not delete this job.')
  }
  finally {
    deletingJob.value = false
  }
}

const dragFrom = ref<number | null>(null)

function moveManualRow(from: number, to: number) {
  const rows = manualForm.value.rows
  if (to < 0 || to >= rows.length || from === to)
    return
  const searches = rows.map((_, index) => jobSearches[index] ?? '')
  const [row] = rows.splice(from, 1)
  const [search] = searches.splice(from, 1)

  rows.splice(to, 0, row)
  searches.splice(to, 0, search)
  searches.forEach((value, index) => {
    jobSearches[index] = value
  })
}

function onRowDragStart(index: number, event: DragEvent) {
  dragFrom.value = index
  event.dataTransfer?.setData('text/plain', String(index))
  if (event.dataTransfer)
    event.dataTransfer.effectAllowed = 'move'
}

function onRowDrop(index: number) {
  const from = dragFrom.value

  dragFrom.value = null
  if (from == null)
    return
  moveManualRow(from, index)
}

function blankManualRow(): ManualInvoiceRow {
  return {
    key: nextManualRowKey(),
    month: isDebitNote.value ? '' : props.defaultMonthLabel,
    course: '',
    fee: '',
    qty: '',
  }
}

function isBlankManualRow(row: ManualInvoiceRow): boolean {
  return !row.purchaseId && !row.course.trim() && !row.fee.trim() && !row.qty.trim()
}

function initialManualRows(): ManualInvoiceRow[] {
  const count = Math.min(
    manualMaxRows.value,
    Math.max(1, brand.value.manualInvoiceDefaultLines),
  )

  return Array.from({ length: count }, () => blankManualRow())
}

const manualCanAddRow = computed(
  () => manualForm.value.rows.length < manualMaxRows.value
    || manualForm.value.rows.some(isBlankManualRow),
)

function pushManualRow(row: ManualInvoiceRow): boolean {
  const blankIdx = manualForm.value.rows.findIndex(isBlankManualRow)
  if (blankIdx !== -1) {
    manualForm.value.rows[blankIdx] = row

    return true
  }
  if (manualForm.value.rows.length >= manualMaxRows.value)
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
      manualError.value = formatApiError(e, t('Could not load students. Search by name, or type a walk-in name.'))
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
  if (hydratingForm.value || studentLocked.value)
    return
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

    // Editing: pre-select the Tutor by its stored staff-unit link (the
    // staff_name snapshot may be stale after a rename).
    if (manualTutorUnitId.value) {
      const resolved = staffName(manualTutorUnitId.value)
      if (resolved)
        manualForm.value.staff = resolved
    }
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
    manualError.value = formatApiError(e, t('Could not load unbilled class packages for this student.'))
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
      subtitle: `${k.billing_unit === 'per_session' ? `Per ${t('class')}` : k.billing_unit === 'yearly' ? 'Yearly' : 'Monthly'}${k.price != null ? ` · HK$${Number(k.price).toFixed(2)}` : ''}`,
    })),
)

function onClassPicked(id: string | null) {
  if (!id)
    return

  const pkg = !isCredit.value
    ? manualUnbilledPackages.value.find(p => p.enrollment.sku_id === id)
    : undefined
  if (pkg) {
    addPurchaseLine(pkg)

    return
  }

  const sku = manualSkus.value.find(k => k.id === id)
  if (!sku)
    return

  const row = blankManualRow()

  row.course = sku.name_zh
  row.fee = sku.price != null
    ? (isCredit.value ? defaultCreditFee(sku.price) : String(sku.price))
    : ''
  row.qty = sku.billing_unit === 'per_session' ? '' : '1'

  suggestManualStaff(sku.staff_id)
  pushManualRow(row)
}

async function suggestManualInvoiceNo() {
  try {
    if (!manualLocationId.value)
      return
    const next = await getNextInvoiceNo(
      manualLocationId.value,
      isCredit.value ? 'credit' : 'invoice',
    )

    if (open.value && !manualNoEdited.value)
      manualForm.value.invoiceNo = next
  }
  catch (e) {
    manualError.value = formatApiError(e, 'Could not suggest the next invoice number. Enter it yourself.')
  }
}

watch(manualLocationId, () => {
  if (open.value && !isEdit.value)
    suggestManualInvoiceNo()
  if (open.value)
    loadJobs()
})

function rowsFromInvoice(invoice: TuitionInvoice, negateFee: boolean): ManualInvoiceRow[] {
  if (negateFee) {
    const creditRows = creditLinesFromInvoice(invoice).map(line => ({
      key: nextManualRowKey(),
      month: line.month || props.defaultMonthLabel,
      course: line.course,
      fee: String(line.fee),
      qty: String(line.qty),
    }))

    return creditRows.length ? creditRows : [blankManualRow()]
  }

  const rows = invoice.lines.map(line => ({
    key: nextManualRowKey(),
    month: line.month_label || (isDebitNote.value ? '' : props.defaultMonthLabel),
    course: line.name_zh,
    fee: String(line.unit_price),
    qty: String(line.quantity),
    lineId: line.id,
    purchaseId: line.purchase_id || undefined,
  }))

  return rows.length ? rows : [blankManualRow()]
}

function fillFromInvoice(invoice: TuitionInvoice, negateFee: boolean) {
  hydratingForm.value = true
  lockedUnitId.value = invoice.unit_id
  manualTutorUnitId.value = negateFee ? null : invoice.tutor_unit_id
  manualError.value = ''
  manualLocationId.value = invoice.location_id

  // Older manual bills stored the typed date as a one-day period; read their
  // month from the lines instead. Month-range periods were chosen on save.
  const rows = rowsFromInvoice(invoice, negateFee)
  const storedPeriod = invoice.period_start.slice(0, 7)
  const inferredPeriod = periodFromMonthLabels(rows.map(row => row.month))
  const legacyPeriod = invoice.period_start === invoice.period_end
  const period = legacyPeriod ? (inferredPeriod || storedPeriod) : storedPeriod

  manualPeriodEdited.value = !legacyPeriod && period !== inferredPeriod
  manualForm.value = {
    invoiceNo: negateFee ? '' : (invoice.invoice_no ?? ''),
    date: negateFee ? new Date().toLocaleDateString('en-CA') : (invoice.issue_date ?? invoice.period_start),
    period,
    studentName: invoiceStudentLabel(invoice),
    staff: invoice.staff_name ?? '',
    currency: invoice.currency || DEFAULT_INVOICE_CURRENCY,
    topRemark: negateFee ? '' : (invoice.top_notes ?? ''),
    remark: negateFee ? '' : (invoice.notes ?? ''),
    payableTo: negateFee ? '' : (invoice.payable_to_name ?? ''),
    payeeName: negateFee ? '' : (invoice.payee_name ?? ''),
    rows,
  }
  manualStudent.value = invoiceStudentLabel(invoice)
  manualStudentSearch.value = ''
  manualUnbilledPackages.value = []
  manualRemovedPackages.value = []
  manualNoEdited.value = false
  void nextTick().then(() => {
    hydratingForm.value = false
  })
  if (invoice.unit_id && !negateFee)
    loadManualUnbilledPackages(invoice.unit_id)
}

function resetForm() {
  hydratingForm.value = true
  lockedUnitId.value = null
  manualTutorUnitId.value = null
  manualError.value = ''
  manualPeriodEdited.value = false
  manualForm.value = {
    invoiceNo: '',
    date: new Date().toLocaleDateString('en-CA'),
    period: '',
    studentName: '',
    staff: '',
    currency: DEFAULT_INVOICE_CURRENCY,
    topRemark: '',
    remark: '',
    payableTo: '',
    payeeName: '',
    rows: initialManualRows(),
  }
  manualForm.value.period = linePeriod.value
  manualStudent.value = null
  manualStudentSearch.value = ''
  manualUnbilledPackages.value = []
  manualRemovedPackages.value = []
  manualNoEdited.value = false
  manualLocationId.value = props.defaultLocationId
  hydratingForm.value = false
}

watch(open, value => {
  if (!value)
    return
  if (props.editingInvoice)
    fillFromInvoice(props.editingInvoice, false)
  else if (props.creditFromInvoice)
    fillFromInvoice(props.creditFromInvoice, true)
  else
    resetForm()
  loadManualStudents()
  loadManualSkus()
  loadManualStaff()
  loadJobs()
  if (!isEdit.value)
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

const dialogTitle = computed(() => {
  if (isEdit.value)
    return 'Edit invoice'
  if (isCredit.value || manualTotal.value < 0)
    return 'Credit note'

  return 'Manual invoice'
})

async function printOptionsFor(
  invoice: { location_id: string; unit_id?: string | null },
  printVersion?: TuitionInvoicePrintVersion,
) {
  const location = props.locations.find(l => l.id === invoice.location_id)

  const team = location && brand.value.invoicePrintTemplate === 'debit-note'
    ? debitNoteTeamCopy(location)
    : null

  let billTo = ''

  if (brand.value.invoicePrintTemplate === 'debit-note' && invoice.unit_id) {
    try {
      const unit = await getUnit(invoice.unit_id)

      billTo = (unit.address ?? '').trim()
    }
    catch {
      billTo = ''
    }
  }

  return {
    logoUrl: await resolvePrintLogoUrl(location?.icon_url || location?.main_photo_url || ''),
    paymentText: team?.paymentText || undefined,
    billTo: billTo || undefined,
    header: location ? invoicePrintHeaderFromLocation(location) : undefined,
    template: brand.value.invoicePrintTemplate,
    printVersion,
    payableTo: (manualForm.value.payableTo ?? '').trim(),
    payeeName: (manualForm.value.payeeName ?? '').trim(),
  }
}

interface ManualInvoiceDraft {
  lines: ManualInvoiceLine[]
  unitId: string | undefined
  locationId: string
}

const versionDialogOpen = ref(false)
const pendingDraft = ref<ManualInvoiceDraft | null>(null)

function validateManualInvoice(): ManualInvoiceDraft | null {
  if (manualForm.value.rows.some(row => row.purchaseId && (manualNumber(row.fee) ?? 0) < 0)) {
    manualError.value = 'Session package lines cannot have a negative fee.'

    return null
  }

  if (manualForm.value.rows.some(row => row.purchaseId && manualNumber(row.fee) == null)) {
    manualError.value = 'Session package lines need a price. 0 is allowed, but it cannot be left blank.'

    return null
  }

  const validLines = manualForm.value.rows
    .map(row => {
      const fee = manualNumber(row.fee)

      return {
        id: isEdit.value ? row.lineId : undefined,
        month: row.month.trim(),
        course: row.course.trim(),
        fee: fee == null ? null : (isCredit.value ? -Math.abs(fee) : fee),
        qty: manualNumber(row.qty),
        staff_name: (manualForm.value.staff ?? '').trim() || null,
        purchase_id: isCredit.value ? undefined : (row.purchaseId || undefined),
      }
    })
    .filter(row => row.course && row.fee != null && Number.isFinite(row.fee) && row.qty != null && (isDebitNote.value ? row.qty >= 0 : row.qty > 0))

  const touchedRows = manualForm.value.rows.filter(
    row => row.purchaseId || row.course.trim() || row.fee.trim() || row.qty.trim(),
  ).length

  if (validLines.length < touchedRows) {
    manualError.value = isDebitNote.value
      ? 'Each filled line needs a course, a price and a quantity. 0 is allowed. Fix or remove the line. Use a negative price for a credit note.'
      : 'Each filled line needs a course, a price (0 is allowed) and a quantity above 0 — fix or remove it. Use a negative price for a credit note.'

    return null
  }

  if (validLines.length === 0) {
    manualError.value = 'Add at least one line with course, fee and quantity.'

    return null
  }

  const unitId = lockedUnitId.value
    || (manualStudent.value && typeof manualStudent.value !== 'string'
      ? manualStudent.value.id
      : undefined)

  if (!unitId && !(manualForm.value.studentName ?? '').trim()) {
    manualError.value = t('Pick a student, or type a name for a walk-in invoice.')

    return null
  }

  if (!manualLocationId.value) {
    manualError.value = t('Please select a location for the manual invoice.')

    return null
  }

  return {
    lines: validLines as ManualInvoiceLine[],
    unitId,
    locationId: manualLocationId.value,
  }
}

async function saveAndPrintManualInvoice(
  draft: ManualInvoiceDraft,
  printVersion?: TuitionInvoicePrintVersion,
  openedWindow?: Window,
) {
  manualPrinting.value = true
  manualError.value = ''

  let printWindow: Window | null = openedWindow ?? null
  try {
    if (!printWindow && !isEdit.value) {
      try {
        printWindow = openTuitionInvoicePrintPlaceholder()
      }
      catch (e) {
        manualError.value = formatApiError(e, 'Could not open print window.')

        return
      }
    }

    const currency = isDebitNote.value ? manualForm.value.currency : undefined
    const topNotes = isDebitNote.value ? ((manualForm.value.topRemark ?? '').trim() || null) : undefined

    const saved = isEdit.value && props.editingInvoice
      ? await updateTuitionInvoice(props.editingInvoice.id, {
        staff_name: (manualForm.value.staff ?? '').trim() || null,
        tutor_unit_id: manualTutorUnitId.value,
        payable_to_name: (manualForm.value.payableTo ?? '').trim() || null,
        payee_name: (manualForm.value.payeeName ?? '').trim() || null,
        currency,
        top_notes: topNotes,
        notes: (manualForm.value.remark ?? '').trim() || null,
        ...(showPeriod.value && manualForm.value.period ? { period: manualForm.value.period } : {}),
        lines: draft.lines,
      })
      : await createManualTuitionInvoice({
        date: manualForm.value.date,
        period: showPeriod.value ? manualForm.value.period || undefined : undefined,
        location_id: draft.locationId,
        unit_id: draft.unitId,
        manual_student_name: draft.unitId ? null : ((manualForm.value.studentName ?? '').trim() || null),
        staff_name: (manualForm.value.staff ?? '').trim() || null,
        tutor_unit_id: manualTutorUnitId.value,
        payable_to_name: (manualForm.value.payableTo ?? '').trim() || null,
        payee_name: (manualForm.value.payeeName ?? '').trim() || null,
        invoice_no: manualNoEdited.value ? (manualForm.value.invoiceNo ?? '').trim() || undefined : undefined,
        currency,
        top_notes: topNotes,
        notes: (manualForm.value.remark ?? '').trim() || null,
        lines: draft.lines,
      })

    if (!printWindow) {
      try {
        printWindow = openTuitionInvoicePrintPlaceholder()
      }
      catch {
        open.value = false
        emit('created')

        return
      }
    }

    await printTuitionInvoice(
      printWindow,
      tuitionInvoicePrintData(saved, await printOptionsFor(saved, printVersion)),
    )
    open.value = false
    emit('created')
  }
  catch (e) {
    printWindow?.close()
    manualError.value = formatApiError(e, 'Could not create or print manual invoice.')
  }
  finally {
    manualPrinting.value = false
  }
}

async function printManualInvoice() {
  manualError.value = ''

  const draft = validateManualInvoice()
  if (!draft)
    return

  if (isDebitNote.value) {
    pendingDraft.value = draft
    versionDialogOpen.value = true

    return
  }

  await saveAndPrintManualInvoice(draft)
}

// Runs inside the version button's click, so the print window may open here.
function onPrintVersionChosen(version: TuitionInvoicePrintVersion) {
  const draft = pendingDraft.value

  pendingDraft.value = null
  if (!draft)
    return

  let printWindow: Window
  try {
    printWindow = openTuitionInvoicePrintPlaceholder()
  }
  catch (e) {
    manualError.value = formatApiError(e, 'Could not open print window.')

    return
  }

  void saveAndPrintManualInvoice(draft, version, printWindow)
}
</script>

<template>
  <VDialog
    v-model="open"
    :fullscreen="isDebitNote"
    :max-width="isDebitNote ? undefined : 960"
    persistent
  >
    <VCard :class="isDebitNote ? 'invoice-manual-card d-flex flex-column' : undefined">
      <VCardTitle class="text-h6 py-4 d-flex align-center">
        {{ dialogTitle }}
        <HelpBubble :text="MANUAL_CREDIT_HINT" />
      </VCardTitle>
      <VDivider />
      <VCardText :class="isDebitNote ? 'pa-4 invoice-manual-body' : 'pa-4'">
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
            :sm="topRowCols.invoiceNo"
          >
            <VTextField
              v-model="manualForm.invoiceNo"
              :label="isCredit ? 'Credit note no.' : 'Invoice no.'"
              density="compact"
              :hint="isEdit ? 'Kept on Edit' : 'Auto-generated — editable'"
              persistent-hint
              :disabled="isEdit"
              @update:model-value="manualNoEdited = true"
            />
          </VCol>
          <VCol
            cols="12"
            :sm="topRowCols.date"
          >
            <VTextField
              v-model="manualForm.date"
              label="Date"
              type="date"
              density="compact"
              :hint="showPeriod ? 'Printed on the invoice' : 'Printed; counts in this month'"
              persistent-hint
              :disabled="isEdit"
            />
          </VCol>
          <VCol
            v-if="showPeriod"
            cols="12"
            :sm="topRowCols.period"
          >
            <VTextField
              v-model="manualForm.period"
              :label="t('Bill month')"
              type="month"
              density="compact"
              :hint="t('Month this bill counts in')"
              persistent-hint
              autocomplete="off"
              @update:model-value="manualPeriodEdited = true"
            />
          </VCol>
          <VCol
            cols="12"
            :sm="topRowCols.location"
          >
            <VSelect
              v-model="manualLocationId"
              :items="locationOptions"
              :label="t('Location (logo)')"
              density="compact"
              hide-details
              clearable
              :disabled="studentLocked"
            />
          </VCol>
          <VCol
            v-if="isDebitNote"
            cols="12"
            :sm="topRowCols.currency"
          >
            <VSelect
              v-model="manualForm.currency"
              :items="currencyItems"
              label="Currency"
              density="compact"
              hide-details
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
              :label="t('Student name')"
              :placeholder="t('Search student name or code — or type any name…')"
              prepend-inner-icon="ri-search-line"
              density="compact"
              hide-details
              clearable
              no-filter
              :disabled="studentLocked"
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
              :label="t('Tutor')"
              :placeholder="t('Tutor for this bill — for commission…')"
              prepend-inner-icon="ri-user-star-line"
              density="compact"
              hint="Applies to every line; not printed on the invoice."
              persistent-hint
              clearable
            />
          </VCol>
          <VCol
            v-if="isDebitNote"
            cols="12"
          >
            <VTextField
              v-model="manualForm.topRemark"
              label="Remark 1"
              density="compact"
              hide-details
              placeholder="Optional — printed under the title"
              clearable
            />
          </VCol>
          <VCol
            v-if="isCredit"
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="manualForm.payableTo"
              label="Payable to name"
              density="compact"
              hint="Printed on CHEQUE PAYABLE TO"
              persistent-hint
              autocomplete="off"
              @update:model-value="value => { if (!(manualForm.payeeName ?? '').trim()) manualForm.payeeName = value }"
            />
          </VCol>
          <VCol
            v-if="isCredit"
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="manualForm.payeeName"
              label="Name"
              density="compact"
              hint="Printed on NAME. Paid by and Supervisor stay blank."
              persistent-hint
              autocomplete="off"
            />
          </VCol>
          <VCol
            v-if="!isCredit && manualUnbilledPackages.length && manualCanAddRow"
            cols="12"
          >
            <div class="text-caption text-medium-emphasis mb-1">
              Unbilled {{ t('class') }} packages — click to add a line:
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
              · {{ pkg.purchase.purchased_quantity }} {{ pkg.purchase.purchased_quantity === 1 ? t('class') : t('classes') }}
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

        <div :class="isDebitNote ? 'invoice-lines' : undefined">
        <VTable
          density="compact"
          class="no-number-spin"
          :class="isDebitNote ? undefined : 'mt-4'"
        >
          <thead>
            <tr>
              <th
                v-if="isDebitNote"
                style="width: 72px;"
              />
              <th
                :class="isDebitNote ? 'invoice-job-col' : undefined"
                :style="isDebitNote ? undefined : { width: '180px' }"
              >
                {{ isDebitNote ? 'Job' : t('Month') }}
              </th>
              <th>{{ t('Class') }}</th>
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
              :key="row.key"
              @dragover.prevent
              @drop="isDebitNote ? onRowDrop(idx) : undefined"
            >
              <td
                v-if="isDebitNote"
                class="text-no-wrap"
              >
                <VBtn
                  icon="ri-draggable"
                  size="x-small"
                  variant="text"
                  aria-label="Drag to reorder"
                  draggable="true"
                  class="invoice-row-handle"
                  @dragstart="onRowDragStart(idx, $event)"
                  @dragend="dragFrom = null"
                />
                <VBtn
                  icon="ri-arrow-up-line"
                  size="x-small"
                  variant="text"
                  aria-label="Move line up"
                  :disabled="idx === 0"
                  @click="moveManualRow(idx, idx - 1)"
                />
                <VBtn
                  icon="ri-arrow-down-line"
                  size="x-small"
                  variant="text"
                  aria-label="Move line down"
                  :disabled="idx === manualForm.rows.length - 1"
                  @click="moveManualRow(idx, idx + 1)"
                />
              </td>
              <td :class="isDebitNote ? 'invoice-job-col' : undefined">
                <VCombobox
                  v-if="isDebitNote"
                  class="invoice-job"
                  :model-value="row.month"
                  :items="jobNames"
                  :search="jobSearches[idx] ?? ''"
                  :menu="Boolean((jobSearches[idx] || '').trim())"
                  density="compact"
                  hide-details
                  clearable
                  placeholder="Optional"
                  @update:model-value="onJobValue(idx, $event)"
                  @update:search="jobSearches[idx] = $event"
                  @blur="commitJob(idx, row)"
                >
                  <template #item="{ props: itemProps, item }">
                    <VListItem v-bind="itemProps">
                      <template #append>
                        <VBtn
                          icon="ri-close-line"
                          size="x-small"
                          variant="text"
                          aria-label="Delete job"
                          @mousedown.prevent
                          @click.stop="askRemoveJob(String(item.title))"
                        />
                      </template>
                    </VListItem>
                  </template>
                  <template #no-data>
                    <VListItem
                      v-if="(jobSearches[idx] || '').trim()"
                      :title="`Use ${(jobSearches[idx] || '').trim()}`"
                      @mousedown.prevent
                      @click="commitJob(idx, row)"
                    />
                  </template>
                </VCombobox>
                <VTextField
                  v-if="!isDebitNote"
                  v-model="row.month"
                  density="compact"
                  hide-details
                  placeholder="Sept-26…"
                />
              </td>
              <td :class="isDebitNote ? 'invoice-line-item' : undefined">
                <div class="d-flex align-start">
                  <VTextarea
                    v-if="isDebitNote"
                    v-model="row.course"
                    density="compact"
                    hide-details
                    auto-grow
                    rows="1"
                    max-rows="8"
                    maxlength="255"
                    :placeholder="`Homework ${t('class')}…`"
                  />
                  <VTextField
                    v-else
                    v-model="row.course"
                    density="compact"
                    hide-details
                    :placeholder="`Homework ${t('class')}…`"
                  />
                  <VChip
                    v-if="row.purchaseId"
                    size="x-small"
                    color="primary"
                    variant="tonal"
                    class="ms-1 flex-shrink-0"
                  >
                    Per {{ t('class') }}
                  </VChip>
                </div>
              </td>
              <td>
                <VTextField
                  v-model="row.fee"
                  density="compact"
                  hide-details
                  type="number"
                  step="0.01"
                  :placeholder="isCredit ? '-1785' : undefined"
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
                {{ manualRowAmount(row) == null ? '—' : formatInvoiceMoney(manualRowAmount(row)!, manualForm.currency) }}
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
            :disabled="manualForm.rows.length >= manualMaxRows || manualForm.rows.some(isBlankManualRow)"
            @click="manualForm.rows.push(blankManualRow())"
          >
            Add line
          </VBtn>
          <VAutocomplete
            :model-value="null"
            :items="manualClassOptions"
            item-title="title"
            item-value="id"
            :label="t('Add a class')"
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
            {{ manualTotal < 0 ? 'Credit' : 'Total' }}: {{ formatInvoiceMoney(manualTotal, manualForm.currency) }}
          </div>
        </div>
        </div>
        <VTextField
          v-model="manualForm.remark"
          :label="isDebitNote ? 'Remark 2' : 'Remark'"
          density="compact"
          class="mt-3"
          :placeholder="isCredit ? 'Optional — printed on the credit note' : 'Optional — printed on the invoice'"
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
          {{ isEdit ? 'Save & print' : 'Create & print' }}
        </VBtn>
      </DialogFooter>
    </VCard>
  </VDialog>

  <InvoicePrintVersionDialog
    v-model="versionDialogOpen"
    @select="onPrintVersionChosen"
  />

  <AttendanceConfirmDialog
    :model-value="Boolean(jobToDelete)"
    :title="jobToDelete ? `Delete ${jobToDelete.name}?` : 'Delete job?'"
    confirm-label="Delete"
    confirm-color="error"
    :loading="deletingJob"
    @confirm="confirmRemoveJob"
    @cancel="jobToDelete = null"
  >
    This removes it from this {{ t('location') }}'s list. Invoices that already use this job keep the name.
  </AttendanceConfirmDialog>
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

.invoice-row-handle {
  cursor: grab;
}

.invoice-manual-card {
  height: 100%;
  max-height: 100dvh;
  border-radius: 0;
}

.invoice-manual-body {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.invoice-lines {
  flex: 1 1 auto;
  min-height: 16rem;
  margin-top: 16px;
  overflow: auto;
}

.invoice-job-col {
  width: 16rem;
  min-width: 16rem;
}

.invoice-job :deep(input) {
  text-overflow: clip;
}

.invoice-line-item {
  min-width: 28rem;
}

.invoice-line-item :deep(textarea) {
  line-height: 1.4;
}
</style>
