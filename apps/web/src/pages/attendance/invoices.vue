<script setup lang="ts">
import {
  type ManualInvoiceLine,
  type TuitionInvoice,
  type TuitionInvoiceLine,
  type TuitionInvoiceStatus,
  createManualTuitionInvoice,
  generateTuitionInvoices,
  getNextInvoiceNo,
  listAllTuitionInvoices,
  updateTuitionInvoice,
} from '@/api/attendance/tuitionInvoices'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import {
  type CourseEnrollment,
  type CourseSku,
  type EnrollmentPurchase,
  listAllCourseEnrollments,
  listCourseSkus,
} from '@/api/attendance/courses'
import { type Unit, listUnits } from '@/api/attendance/units'
import StatCards from '@/components/attendance/StatCards.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import {
  type TuitionInvoicePrintHeader,
  invoiceMonthLabel,
  openTuitionInvoicePrintPlaceholder,
  printTuitionInvoice,
  tuitionInvoicePrintData,
} from '@/utils/printTuitionInvoice'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const {
  yearMonth,
  parsed: parsedYearMonth,
  monthLabel,
  changeMonth,
  toCurrentMonth,
} = useYearMonth()

const invoices = ref<TuitionInvoice[]>([])
const loading = ref(true)
const generating = ref(false)
const loadError = ref('')
const generateError = ref('')
const generateSuccess = ref('')
const expandedId = ref<string | null>(null)
const statusUpdatingId = ref<string | null>(null)
const pendingStatus = ref<{ invoice: TuitionInvoice; status: 'issued' | 'paid' | 'void' } | null>(null)
const pendingGenerate = ref(false)
const issueNoInput = ref('')
const issueNoEdited = ref(false)
const issueNoError = ref('')
const issueRemark = ref('')
const issueStaff = ref('')
const manualInvoiceOpen = ref(false)
const locations = ref<LocationItem[]>([])

const LOCATION_FILTER_KEY = 'tuition-invoice-location'
const locationId = ref<string | null>(localStorage.getItem(LOCATION_FILTER_KEY))
const manualLocationId = ref<string | null>(locationId.value)

interface ManualInvoiceRow {
  month: string
  course: string
  fee: string
  qty: string
  purchaseId?: string
}

const manualForm = ref<{ invoiceNo: string; date: string; studentName: string; staff: string; remark: string; rows: ManualInvoiceRow[] }>({
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

const staffName = (id: string | null | undefined) =>
  manualStaffUnits.value.find(u => u.id === id)?.full_name ?? ''

const manualStaffOptions = computed(() => manualStaffUnits.value.map(u => u.full_name))

// Invoice-level staff (who opened the invoice / gets commission). Picking a
// class or package offers its teacher as the default, but never overwrites.
function suggestManualStaff(staffId: string | null | undefined) {
  if (!(manualForm.value.staff ?? '').trim())
    manualForm.value.staff = staffName(staffId)
}

interface UnbilledPackage {
  purchase: EnrollmentPurchase
  enrollment: CourseEnrollment
  sku: CourseSku | undefined
}

const manualUnbilledPackages = ref<UnbilledPackage[]>([])

// Packages already pulled into a row — kept so removing that row restores the chip.
const manualRemovedPackages = ref<UnbilledPackage[]>([])
const MANUAL_MAX_ROWS = 5
const manualNoEdited = ref(false)
const manualPrinting = ref(false)

// Separate from generateError: the manual dialog covers the page-level alert,
// so its errors must render inside the dialog.
const manualError = ref('')

const searchQuery = ref('')
const statusFilter = ref<'all' | TuitionInvoiceStatus>('all')

useAutoClearAlerts(loadError)
useAutoClearAlerts(generateError)

const statusColor: Record<string, string> = {
  draft: 'warning',
  issued: 'info',
  paid: 'success',
  void: 'grey',
}

const statusLabel: Record<string, string> = {
  draft: '草稿',
  issued: '已出單',
  paid: '已收訖',
  void: '已作廢',
}

const statusFilters: { title: string; value: 'all' | TuitionInvoiceStatus }[] = [
  { title: '全部', value: 'all' },
  { title: '草稿', value: 'draft' },
  { title: '已出單', value: 'issued' },
  { title: '已收訖', value: 'paid' },
  { title: '已作廢', value: 'void' },
]

function formatMoney(value: number): string {
  return `HK$${Number(value).toLocaleString('en-HK', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function billingLabel(unit: string): string {
  if (unit === 'per_session')
    return '堂費'
  if (unit === 'manual')
    return '手動'

  return '月費'
}

function formatQty(line: TuitionInvoiceLine): string {
  const qty = Number(line.quantity)
  const whole = Number.isInteger(qty) ? String(qty) : qty.toFixed(2)
  if (line.billing_unit === 'per_session')
    return `${whole} ${qty === 1 ? 'session' : 'sessions'}`

  // Free-form manual lines have no unit — 1 could be a month, an item, a fee.
  if (line.billing_unit === 'manual')
    return whole

  return qty === 1 ? '1 month' : `${whole} months`
}

function lineFormula(line: TuitionInvoiceLine): string {
  return `${formatQty(line)} × ${formatMoney(Number(line.unit_price))}`
}

function classNames(invoice: TuitionInvoice): string[] {
  return invoice.lines.map(line => line.name_zh || line.sku_code)
}

function classPreview(invoice: TuitionInvoice): string {
  const names = classNames(invoice)
  if (names.length === 0)
    return 'No lines'
  if (names.length <= 2)
    return names.join(' · ')

  return `${names.slice(0, 2).join(' · ')} +${names.length - 2}`
}

const statusTotals = computed(() => {
  const totals = {
    draft: { count: 0, amount: 0 },
    issued: { count: 0, amount: 0 },
    paid: { count: 0, amount: 0 },
    void: { count: 0, amount: 0 },
  }

  for (const invoice of invoices.value) {
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

const statusCounts = computed<Record<string, number>>(() => ({
  all: invoices.value.length,
  draft: statusTotals.value.draft.count,
  issued: statusTotals.value.issued.count,
  paid: statusTotals.value.paid.count,
  void: statusTotals.value.void.count,
}))

const filteredInvoices = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()

  return invoices.value.filter(invoice => {
    if (statusFilter.value !== 'all' && invoice.status !== statusFilter.value)
      return false
    if (!query)
      return true

    const haystack = [
      invoice.unit_name,
      invoice.unit_code,
      invoice.manual_student_name,
      invoice.invoice_no,
      invoice.notes,
      ...invoice.lines.flatMap(line => [line.sku_code, line.name_zh]),
    ].join(' ').toLowerCase()

    return haystack.includes(query)
  })
})

const statCards = computed(() => [
  {
    label: 'To collect',
    value: formatMoney(collectibleTotal.value),
    hint: `${statusTotals.value.draft.count} draft · ${statusTotals.value.issued.count} issued`,
    icon: 'ri-wallet-3-line',
    color: 'primary',
  },
  {
    label: 'Paid',
    value: formatMoney(statusTotals.value.paid.amount),
    hint: `${statusTotals.value.paid.count} paid this month`,
    icon: 'ri-checkbox-circle-line',
    color: 'success',
  },
  {
    label: 'Drafts',
    value: String(statusTotals.value.draft.count),
    hint: formatMoney(statusTotals.value.draft.amount),
    icon: 'ri-draft-line',
    color: 'warning',
  },
  {
    label: 'Bills',
    value: String(invoices.value.length),
    hint: statusTotals.value.void.count ? `${statusTotals.value.void.count} void excluded from collect` : monthLabel.value,
    icon: 'ri-file-list-3-line',
    color: 'info',
  },
])

async function loadInvoices() {
  if (!parsedYearMonth.value)
    return

  loading.value = true
  loadError.value = ''
  try {
    const result = await listAllTuitionInvoices({
      year: parsedYearMonth.value.year,
      month: parsedYearMonth.value.month,
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
    )

    generateSuccess.value = `Created ${result.created}, updated ${result.updated}, skipped ${result.skipped}, deleted ${result.deleted ?? 0}.`
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
  status: 'issued' | 'paid' | 'void',
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

async function suggestIssueNo() {
  try {
    const locId = pendingStatus.value?.invoice.location_id ?? locationId.value
    if (!locId)
      return
    const next = await getNextInvoiceNo(locId)
    if (pendingStatus.value?.status === 'issued' && !issueNoInput.value.trim())
      issueNoInput.value = String(next)
  }
  catch {
    // leave empty — the field stays editable
  }
}

function askStatus(invoice: TuitionInvoice, status: 'issued' | 'paid' | 'void') {
  issueNoInput.value = status === 'issued' ? (invoice.invoice_no ?? '') : ''
  issueNoEdited.value = status === 'issued' && invoice.invoice_no != null
  issueNoError.value = ''
  issueRemark.value = invoice.notes ?? ''
  issueStaff.value = invoice.staff_name ?? ''
  pendingStatus.value = { invoice, status }
  if (status === 'issued') {
    loadManualStaff()
    if (!invoice.invoice_no)
      suggestIssueNo()
  }
}

const locationOptions = computed(() =>
  locations.value
    .filter(location => location.is_active)
    .map(location => ({
      value: location.id,
      title: location.name_zh || location.name_en,
    })),
)

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

function printOptionsFor(invoice: TuitionInvoice) {
  const location = locations.value.find(l => l.id === invoice.location_id)

  return {
    logoUrl: location?.icon_url || location?.main_photo_url || '',
    header: location ? headerFromLocation(location) : undefined,
  }
}

watch(locationId, id => {
  if (id)
    localStorage.setItem(LOCATION_FILTER_KEY, id)
  else
    localStorage.removeItem(LOCATION_FILTER_KEY)
  loadInvoices()
})

async function loadLocations() {
  try {
    // Load all locations (including inactive) so printed invoices can look
    // up the campus they were issued under; only active ones are selectable.
    locations.value = await listLocations({ page_size: 200 })
    if (!locationOptions.value.some(l => l.value === locationId.value))
      locationId.value = null
  }
  catch {
    locations.value = []
  }
}

function printInvoice(invoice: TuitionInvoice) {
  try {
    const printWindow = openTuitionInvoicePrintPlaceholder()

    printTuitionInvoice(
      printWindow,
      tuitionInvoicePrintData(invoice, printOptionsFor(invoice)),
    )
  }
  catch (e) {
    generateError.value = formatApiError(e, 'Could not open print window.')
  }
}

async function confirmPendingStatus() {
  const pending = pendingStatus.value
  if (!pending)
    return

  // Only send a number the user actually typed — otherwise the server
  // allocates the next sequential one atomically.
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
    pending.status === 'paid' ? undefined : remark || null,
    pending.status === 'issued' ? issueStaff.value.trim() : undefined,
  )

  if (!updated) {
    printWindow?.close()

    return
  }
  if (printWindow) {
    printTuitionInvoice(
      printWindow,
      tuitionInvoicePrintData(updated, printOptionsFor(updated)),
    )
  }
}

function blankManualRow(): ManualInvoiceRow {
  const parsed = parsedYearMonth.value

  return {
    month: parsed
      ? invoiceMonthLabel(`${parsed.year}-${String(parsed.month).padStart(2, '0')}-01`)
      : '',
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
  // Fill the first untouched row instead of appending below empty rows.
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
    console.error('Failed to load students for manual invoice', e)
  }
  finally {
    if (requestId === manualStudentRequestId)
      manualStudentLoading.value = false
  }
}

const manualStudentDebounce = useDebounceFn(() => loadManualStudents(manualStudentSearch.value.trim()), 300)

watch(manualStudentSearch, value => {
  if (!manualInvoiceOpen.value)
    return
  if (value.trim())
    manualStudentDebounce()
  else
    loadManualStudents()
})

watch(manualStudent, picked => {
  manualRemovedPackages.value = []

  // Package rows belong to the previously picked student — drop them so a
  // stale purchaseId can't be billed on the wrong student's invoice.
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
    manualStaffUnits.value = await listUnits({ unit_type: 'staff', page_size: 200 })
    manualStaffLoaded.value = true
  }
  catch {
    manualStaffUnits.value = []
  }
}

async function loadManualUnbilledPackages(unitId: string) {
  try {
    await loadManualSkus()
    await loadManualStaff()

    // No status filter — an unbilled package stays billable even if the
    // enrollment was cancelled (the student still owes for what they bought).
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
  catch {
    manualUnbilledPackages.value = []
  }
}

function addPurchaseLine(pkg: UnbilledPackage) {
  const row = blankManualRow()

  // Same label format as every other row ("Sept-26"), not the raw ISO month.
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

  // Put the package chip back so it can be re-added or billed later.
  const restoredIdx = manualRemovedPackages.value.findIndex(p => p.purchase.id === removed.purchaseId)
  if (restoredIdx !== -1)
    manualUnbilledPackages.value.push(...manualRemovedPackages.value.splice(restoredIdx, 1))
}

async function loadManualSkus() {
  if (manualSkusLoaded.value)
    return
  try {
    manualSkus.value = await listCourseSkus()
    manualSkusLoaded.value = true
  }
  catch (e) {
    console.error('Failed to load classes for manual invoice', e)
  }
}

const manualClassOptions = computed(() =>
  manualSkus.value
    .filter(k => k.is_active)
    .map(k => ({
      ...k,
      title: `${k.code} · ${k.name_zh}`,
      subtitle: `${k.billing_unit === 'per_session' ? '堂費' : '月費'}${k.price != null ? ` · HK$${Number(k.price).toFixed(2)}` : ''}`,
    })),
)

// Stateless picker — model stays null so the selected class never sticks in
// the field; the pick just adds a line.
function onClassPicked(id: string | null) {
  if (!id)
    return

  // If this student has an unbilled package for that class, bill the package
  // itself — a free line would leave the purchase unbilled and billable again.
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

    // Only overwrite a number the user has not typed — numbers are per campus,
    // so the preview must follow the selected location.
    if (manualInvoiceOpen.value && !manualNoEdited.value)
      manualForm.value.invoiceNo = String(next)
  }
  catch {
    // leave empty — the field stays editable
  }
}

watch(manualLocationId, () => {
  if (manualInvoiceOpen.value)
    suggestManualInvoiceNo()
})

function openManualInvoice() {
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
  manualLocationId.value = locationId.value
  manualInvoiceOpen.value = true
  loadManualStudents()
  loadManualSkus()
  loadManualStaff()
  suggestManualInvoiceNo()
}

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

    // A row the user touched but left incomplete/invalid must not be dropped
    // silently — name the problem instead of a generic "add a line" message.
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

    // Open the print window synchronously — after an await the browser may
    // treat window.open as a pop-up and block it.
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
        tuitionInvoicePrintData(created, printOptionsFor(created)),
      )
      manualInvoiceOpen.value = false
      await loadInvoices()
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

const statusConfirmTitle = computed(() => {
  const status = pendingStatus.value?.status
  if (status === 'issued')
    return '出單 Issue this invoice?'
  if (status === 'paid')
    return '收訖 Mark this invoice paid?'
  if (status === 'void')
    return '作廢 Void this invoice?'

  return 'Update invoice?'
})

const statusConfirmLabel = computed(() => {
  const status = pendingStatus.value?.status
  if (status === 'issued')
    return '出單 Issue'
  if (status === 'paid')
    return '收訖 Paid'
  if (status === 'void')
    return '作廢 Void'

  return 'Confirm'
})

const statusConfirmColor = computed(() => pendingStatus.value?.status === 'void' ? 'error' : 'primary')

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

function clearFilters() {
  searchQuery.value = ''
  statusFilter.value = 'all'
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
        <div class="text-h5 font-weight-medium">
          Tuition invoices
        </div>
        <div class="text-body-2 text-medium-emphasis">
          {{ monthLabel }}
          <span v-if="invoices.length">
            · {{ invoices.length }} bill{{ invoices.length === 1 ? '' : 's' }}
            · {{ formatMoney(collectibleTotal) }} to collect
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
          @click="changeMonth(-1)"
        >
          <VIcon>ri-arrow-left-s-line</VIcon>
        </VBtn>
        <VTextField
          v-model="yearMonth"
          label="Month"
          type="month"
          density="compact"
          hide-details
          style="max-width: 180px;"
        />
        <VBtn
          icon
          variant="tonal"
          size="small"
          @click="changeMonth(1)"
        >
          <VIcon>ri-arrow-right-s-line</VIcon>
        </VBtn>
      </VCol>
    </VRow>

    <div class="d-flex flex-wrap align-center justify-space-between gap-3 mb-4">
      <div class="d-flex flex-wrap align-center gap-2">
        <VBtn
          color="primary"
          prepend-icon="ri-magic-line"
          :loading="generating"
          :disabled="!parsedYearMonth"
          @click="askGenerate"
        >
          Generate
        </VBtn>
        <VBtn
          variant="tonal"
          prepend-icon="ri-printer-line"
          @click="openManualInvoice"
        >
          Manual invoice
        </VBtn>
      </div>
      <VSelect
        v-model="locationId"
        :items="locationOptions"
        label="Location"
        density="compact"
        hide-details
        clearable
        style="max-width: 200px; min-width: 160px;"
      />
    </div>

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
      v-if="generateError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
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
      @click:close="generateSuccess = ''"
    >
      {{ generateSuccess }}
    </VAlert>

    <StatCards
      v-if="!loading"
      :cards="statCards"
    />

    <div class="d-flex flex-wrap align-center justify-space-between gap-3 mb-4">
      <VChipGroup
        v-model="statusFilter"
        mandatory
        selected-class="text-primary"
      >
        <VChip
          v-for="chip in statusFilters"
          :key="chip.value"
          :value="chip.value"
          size="small"
          variant="outlined"
          filter
        >
          {{ chip.title }} ({{ statusCounts[chip.value] ?? 0 }})
        </VChip>
      </VChipGroup>
      <div class="d-flex flex-wrap align-center gap-2">
        <VTextField
          v-model="searchQuery"
          label="Search"
          placeholder="Student, code, invoice no., class, or remark"
          prepend-inner-icon="ri-search-line"
          density="compact"
          hide-details
          clearable
          style="min-width: 260px;"
        />
        <VBtn
          icon
          variant="tonal"
          size="small"
          :loading="loading"
          title="Refresh"
          @click="loadInvoices"
        >
          <VIcon>ri-refresh-line</VIcon>
        </VBtn>
      </div>
    </div>

    <VCard>
      <VCardItem>
        <VCardTitle>Bills</VCardTitle>
        <VCardSubtitle>
          One bill per student for this calendar month. Click a row for line items.
          <span v-if="filteredInvoices.length !== invoices.length">
            · Showing {{ filteredInvoices.length }} of {{ invoices.length }}
          </span>
        </VCardSubtitle>
      </VCardItem>
      <VCardText>
        <VExpansionPanels
          variant="accordion"
          class="mb-4"
        >
          <VExpansionPanel title="How Generate bills this month">
            <VExpansionPanelText>
              <ul class="text-body-2 ps-4 mb-0">
                <li>One draft per student whose enrollments overlap this month.</li>
                <li>月費: flat SKU price once per month, even if they miss days.</li>
                <li>堂費: each session package bought (recorded on enrollment) is billed once, never monthly. Not based on attendance.</li>
                <li>私補 / variable-rate classes: leave the class price empty. Enrollment records how many sessions were bought; set the price when you bill it with <strong>Manual invoice</strong>.</li>
                <li>Packages with no price yet are skipped by Generate — they wait for a manual invoice.</li>
                <li>Inactive classes and monthly classes with no price are skipped. Issued / paid bills are not overwritten.</li>
                <li>留意: the Location filter shows invoices under the campus they were issued for.</li>
              </ul>
            </VExpansionPanelText>
          </VExpansionPanel>
        </VExpansionPanels>

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
              <th>編號</th>
              <th>Classes</th>
              <th>Period</th>
              <th>Status</th>
              <th class="text-end">
                Total
              </th>
              <th>備註</th>
              <th
                class="text-no-wrap"
                style="width: 1%;"
              />
            </tr>
          </thead>
          <tbody>
            <template
              v-for="invoice in filteredInvoices"
              :key="invoice.id"
            >
              <tr
                style="cursor: pointer;"
                @click="toggleExpand(invoice.id)"
              >
                <td>
                  {{ invoice.unit_name ?? invoice.manual_student_name ?? '—' }}
                  <div class="text-caption text-medium-emphasis">
                    {{ invoice.unit_code }}
                    <VChip
                      v-if="invoice.kind === 'manual'"
                      size="x-small"
                      color="info"
                      class="ms-1"
                    >
                      manual
                    </VChip>
                  </div>
                </td>
                <td class="text-caption text-no-wrap">
                  {{ invoice.invoice_no ?? '—' }}
                </td>
                <td>
                  <div>{{ classPreview(invoice) }}</div>
                  <div class="text-caption text-medium-emphasis">
                    {{ invoice.lines.length }} line{{ invoice.lines.length === 1 ? '' : 's' }}
                    <VIcon
                      size="14"
                      class="ms-1"
                    >
                      {{ expandedId === invoice.id ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line' }}
                    </VIcon>
                  </div>
                </td>
                <td class="text-caption text-medium-emphasis text-no-wrap">
                  {{ invoice.period_start }} – {{ invoice.period_end }}
                </td>
                <td>
                  <VChip
                    size="x-small"
                    :color="statusColor[invoice.status] ?? 'grey'"
                  >
                    {{ statusLabel[invoice.status] ?? invoice.status }}
                  </VChip>
                </td>
                <td class="text-end font-weight-medium text-no-wrap">
                  {{ formatMoney(Number(invoice.total)) }}
                </td>
                <td
                  class="text-caption text-medium-emphasis"
                  style="max-width: 220px;"
                >
                  <span
                    v-if="invoice.notes"
                    class="d-inline-block text-truncate align-middle"
                    style="max-width: 200px;"
                    :title="invoice.notes"
                  >{{ invoice.notes }}</span>
                  <span
                    v-else
                    class="text-disabled"
                  >—</span>
                </td>
                <td
                  class="text-end text-no-wrap"
                  @click.stop
                >
                  <VBtn
                    v-if="invoice.status !== 'void'"
                    icon="ri-printer-line"
                    size="x-small"
                    variant="text"
                    title="列印 Print / reprint"
                    @click="printInvoice(invoice)"
                  />
                  <VBtn
                    v-if="invoice.status === 'draft'"
                    size="x-small"
                    variant="text"
                    color="primary"
                    prepend-icon="ri-file-check-line"
                    title="出單 — assign invoice no. and print"
                    :loading="statusUpdatingId === invoice.id"
                    @click="askStatus(invoice, 'issued')"
                  >
                    出單
                  </VBtn>
                  <VBtn
                    v-if="invoice.status === 'issued'"
                    size="x-small"
                    variant="text"
                    color="success"
                    prepend-icon="ri-money-dollar-circle-line"
                    title="收訖 — payment received"
                    :loading="statusUpdatingId === invoice.id"
                    @click="askStatus(invoice, 'paid')"
                  >
                    收訖
                  </VBtn>
                  <VBtn
                    v-if="invoice.status === 'draft' || invoice.status === 'issued'"
                    size="x-small"
                    variant="text"
                    color="error"
                    prepend-icon="ri-close-circle-line"
                    title="作廢 — cancel this invoice"
                    :loading="statusUpdatingId === invoice.id"
                    @click="askStatus(invoice, 'void')"
                  >
                    作廢
                  </VBtn>
                </td>
              </tr>
              <tr v-if="expandedId === invoice.id">
                <td colspan="8">
                  <div class="text-caption text-medium-emphasis mb-2">
                    {{ invoice.kind === 'manual'
                      ? 'Manual invoice — lines were typed when it was issued.'
                      : 'Snapshot of SKU price at Generate. Changing the class later does not rewrite issued or paid bills.' }}
                  </div>
                  <div class="text-caption mb-2 d-flex flex-wrap gap-3">
                    <span v-if="invoice.staff_name">開單人: {{ invoice.staff_name }}</span>
                    <span v-if="invoice.notes">備註: {{ invoice.notes }}</span>
                  </div>
                  <VTable density="compact">
                    <thead>
                      <tr>
                        <th>Class</th>
                        <th>How billed</th>
                        <th>Calculation</th>
                        <th class="text-end">
                          Amount
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="line in invoice.lines"
                        :key="line.id"
                      >
                        <td>
                          {{ line.name_zh }}
                          <div class="text-caption text-medium-emphasis">
                            {{ line.sku_code }}
                            <span v-if="line.staff_name"> · {{ line.staff_name }}</span>
                          </div>
                        </td>
                        <td>
                          <VChip
                            size="x-small"
                            variant="tonal"
                          >
                            {{ billingLabel(line.billing_unit) }}
                          </VChip>
                        </td>
                        <td class="text-medium-emphasis">
                          {{ lineFormula(line) }}
                        </td>
                        <td class="text-end font-weight-medium text-no-wrap">
                          {{ formatMoney(Number(line.amount)) }}
                        </td>
                      </tr>
                      <tr v-if="invoice.lines.length === 0">
                        <td
                          colspan="4"
                          class="text-medium-emphasis"
                        >
                          No chargeable classes this month.
                        </td>
                      </tr>
                    </tbody>
                  </VTable>
                </td>
              </tr>
            </template>
            <tr v-if="!loading && filteredInvoices.length === 0">
              <td
                colspan="8"
                class="text-center text-medium-emphasis py-8"
              >
                <template v-if="invoices.length === 0">
                  No bills this month. Enroll students with billed dates (and sessions purchased for 堂費 classes), then Generate.
                </template>
                <template v-else>
                  No bills match this search or status.
                  <div class="mt-2">
                    <VBtn
                      size="small"
                      variant="text"
                      @click="clearFilters"
                    >
                      Clear filters
                    </VBtn>
                  </div>
                </template>
              </td>
            </tr>
          </tbody>
        </VTable>
      </VCardText>
    </VCard>

    <AttendanceConfirmDialog
      :model-value="pendingStatus != null"
      :title="statusConfirmTitle"
      :confirm-label="statusConfirmLabel"
      :confirm-color="statusConfirmColor"
      :loading="statusUpdatingId === pendingStatus?.invoice.id"
      :error="generateError"
      @update:model-value="value => { if (!value) pendingStatus = null }"
      @confirm="confirmPendingStatus"
      @cancel="pendingStatus = null"
      @clear-error="generateError = ''"
    >
      <template v-if="pendingStatus?.status === 'issued'">
        <div class="mb-3">
          Issuing locks {{ pendingStatus.invoice.unit_name ?? pendingStatus.invoice.unit_code }}
          at {{ formatMoney(Number(pendingStatus.invoice.total)) }}. Generate will no longer change this month.
        </div>
        <VTextField
          v-model="issueNoInput"
          label="Invoice no. (編號)"
          density="compact"
          hint="Auto-generated — change only if you need a different number."
          persistent-hint
          :error-messages="issueNoError"
          autofocus
          @update:model-value="issueNoEdited = true; issueNoError = ''"
        />
        <VCombobox
          v-model="issueStaff"
          :items="manualStaffOptions"
          label="開單人 Staff"
          density="compact"
          class="mt-2"
          hint="Who issued this invoice — for commission; not printed."
          persistent-hint
          clearable
        />
        <VTextField
          v-model="issueRemark"
          label="Remark (備註)"
          density="compact"
          class="mt-2"
          placeholder="Optional — printed on the invoice"
          clearable
        />
        <div class="text-caption text-medium-emphasis">
          The printed invoice opens in a new window after issuing.
        </div>
      </template>
      <template v-else-if="pendingStatus?.status === 'paid'">
        Mark {{ pendingStatus.invoice.unit_name ?? pendingStatus.invoice.unit_code }}
        ({{ formatMoney(Number(pendingStatus.invoice.total)) }}) as paid?
      </template>
      <template v-else-if="pendingStatus?.status === 'void'">
        {{ pendingStatus.invoice.unit_name ?? pendingStatus.invoice.manual_student_name ?? pendingStatus.invoice.unit_code }}
        will be marked void. The invoice number is not reused.
        <template v-if="pendingStatus.invoice.kind === 'manual'">
          Any session package billed on it becomes unbilled again, so you can re-issue it.
        </template>
        <template v-else>
          Generate will restore it to draft if the student is still enrolled this month, with a new number.
        </template>
        <VTextField
          v-model="issueRemark"
          label="Remark (備註)"
          density="compact"
          class="mt-3"
          placeholder="Optional — e.g. why it was voided"
          clearable
        />
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
      Replaces drafts, skips issued and paid, deletes leftover drafts, and may restore void bills if the student is still enrolled.
    </AttendanceConfirmDialog>

    <VDialog
      v-model="manualInvoiceOpen"
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
            Creates an issued invoice saved for reprint / payment tracking — for ad-hoc sales and 私補 session packages not billed through Generate.
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
                label="編號 Invoice no."
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
                label="日期 Date"
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
                label="中心 Location (logo)"
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
                label="學生姓名 Student"
                placeholder="Search student name or code — or type any name"
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
                label="開單人 Staff"
                placeholder="Who issued this — for commission"
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
                Unbilled session packages — click to add a line (marks the package as billed):
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
                · {{ pkg.purchase.purchased_quantity }} 堂
                <template v-if="pkg.purchase.unit_price != null">
                  × HK${{ Number(pkg.purchase.unit_price).toFixed(2) }}
                </template>
                <template v-else>
                  · 價錢待定
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
                <th>月份</th>
                <th>課程</th>
                <th style="width: 110px;">
                  單價
                </th>
                <th style="width: 90px;">
                  數量
                </th>
                <th
                  class="text-end"
                  style="width: 110px;"
                >
                  總額
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
                    placeholder="Sept-26"
                  />
                </td>
                <td>
                  <div class="d-flex align-center">
                    <VTextField
                      v-model="row.course"
                      density="compact"
                      hide-details
                      placeholder="功課輔導班"
                    />
                    <VChip
                      v-if="row.purchaseId"
                      size="x-small"
                      color="primary"
                      variant="tonal"
                      class="ms-1 flex-shrink-0"
                    >
                      堂費
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
                  {{ manualRowAmount(row) == null ? '—' : formatMoney(manualRowAmount(row)!) }}
                </td>
                <td class="text-end">
                  <VBtn
                    icon="ri-close-line"
                    size="x-small"
                    variant="text"
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
              label="Add a class line"
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
              Total: {{ formatMoney(manualTotal) }}
            </div>
          </div>
          <VTextField
            v-model="manualForm.remark"
            label="備註 Remark"
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
            @click="manualInvoiceOpen = false"
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
  </VContainer>
</template>

<style scoped>
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
