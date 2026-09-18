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
import { resolveMediaUrl } from '@/utils/mediaUrl'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import {
  type TuitionInvoicePrintHeader,
  invoiceMonthLabel,
  openTuitionInvoicePrintPlaceholder,
  printTuitionInvoice,
  tuitionInvoicePrintData,
} from '@/utils/printTuitionInvoice'

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
const showBillingHelp = ref(false)

useAutoClearAlerts(loadError)
useAutoClearAlerts(generateError)
useAutoClearAlerts(generateSuccess)

const statusColor: Record<string, string> = {
  draft: 'warning',
  issued: 'info',
  paid: 'success',
  void: 'grey',
}

const statusLabel: Record<string, string> = {
  draft: 'Draft',
  issued: 'Issued',
  paid: 'Paid',
  void: 'Cancelled',
}

const statusFilters: { title: string; value: 'all' | TuitionInvoiceStatus }[] = [
  { title: 'All', value: 'all' },
  { title: 'Draft', value: 'draft' },
  { title: 'Issued', value: 'issued' },
  { title: 'Paid', value: 'paid' },
  { title: 'Cancelled', value: 'void' },
]

function formatMoney(value: number): string {
  return `HK$${Number(value).toLocaleString('en-HK', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function billingLabel(unit: string): string {
  if (unit === 'per_session')
    return 'Per class'
  if (unit === 'manual')
    return 'Manual'

  return 'Monthly'
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
  if (names.length === 1)
    return names[0]

  return `${names[0]} +${names.length - 1}`
}

function periodLabel(invoice: TuitionInvoice): string {
  if (invoice.period_start === invoice.period_end)
    return invoice.period_start

  return `${invoice.period_start} – ${invoice.period_end}`
}

function studentLabel(invoice: TuitionInvoice): string {
  return invoice.unit_name ?? invoice.manual_student_name ?? '—'
}

function openedBy(invoice: TuitionInvoice): string {
  return (invoice.staff_name ?? '').trim()
}

function locationName(id: string): string {
  const location = locations.value.find(item => item.id === id)

  return location ? (location.name_zh || location.name_en) : ''
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
      invoice.receipt_no,
      invoice.staff_name,
      invoice.notes,
      ...invoice.lines.flatMap(line => [line.sku_code, line.name_zh, line.staff_name]),
    ].join(' ').toLowerCase()

    return haystack.includes(query)
  })
})

const pagedInvoices = computed(() => {
  const start = (page.value - 1) * pageSize.value

  return filteredInvoices.value.slice(start, start + pageSize.value)
})

const billsCaption = computed(() => pagedListCaption(pagedInvoices.value.length, 'bill'))

const allMonths = computed(() => !parsedYearMonth.value)
const allLocations = computed(() => !locationId.value)

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
    label: 'To collect',
    value: formatMoney(collectibleTotal.value),
    hint: `${statusTotals.value.draft.count} draft · ${statusTotals.value.issued.count} issued`,
    icon: 'ri-wallet-3-line',
    color: 'primary',
  },
  {
    label: 'Paid',
    value: formatMoney(statusTotals.value.paid.amount),
    hint: parsedYearMonth.value
      ? `${statusTotals.value.paid.count} paid this month`
      : `${statusTotals.value.paid.count} paid`,
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

function askStatus(invoice: TuitionInvoice, status: 'issued' | 'void') {
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
    logoUrl: resolveMediaUrl(location?.icon_url || location?.main_photo_url || ''),
    header: location ? headerFromLocation(location) : undefined,
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
    pending.status === 'issued' ? remark || null : undefined,
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
          Tuition invoices
        </div>
        <div class="text-body-2 text-medium-emphasis">
          {{ scopeLabel }}
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
            Manual invoice
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
                v-for="chip in statusFilters"
                :key="chip.value"
                :value="chip.value"
                size="small"
                variant="outlined"
                filter
                class="text-no-wrap"
                :color="chip.value === 'all' ? undefined : statusColor[chip.value]"
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

    <VCard>
      <VCardItem>
        <VCardTitle class="d-flex align-center flex-wrap gap-2">
          <span>Bills</span>
          <span
            v-if="billsCaption"
            class="text-caption text-medium-emphasis font-weight-regular"
          >
            {{ billsCaption }}
            <template v-if="filteredInvoices.length !== invoices.length">
              matching · {{ invoices.length }} total
            </template>
          </span>
        </VCardTitle>
        <template #append>
          <VBtn
            variant="text"
            size="small"
            :prepend-icon="showBillingHelp ? 'ri-question-fill' : 'ri-question-line'"
            @click="showBillingHelp = !showBillingHelp"
          >
            How billing works
          </VBtn>
        </template>
        <VCardSubtitle>
          {{ allMonths ? 'All bills. Open a row for line items.' : 'One bill per student for this calendar month. Open a row for line items.' }}
        </VCardSubtitle>
      </VCardItem>
      <VCardText>
        <VAlert
          v-if="showBillingHelp"
          variant="tonal"
          color="info"
          density="compact"
          class="mb-4"
          closable
          @click:close="showBillingHelp = false"
        >
          <ul class="text-body-2 ps-4 mb-0">
            <li>One draft bill per student whose classes overlap this month.</li>
            <li>Monthly classes: billed once for the month, even if they miss days.</li>
            <li>Per-class packages: billed once for the package they bought — not from attendance.</li>
            <li>Private / variable-price classes: leave the class price empty. Record how many sessions were bought, then set the price on a <strong>Manual invoice</strong>.</li>
            <li>Packages with no price yet are skipped by Generate — bill them with a manual invoice.</li>
            <li>Inactive classes and monthly classes with no price are skipped. Issued and paid bills are not changed.</li>
            <li>The Location filter shows bills for that campus. All months and All locations show every bill.</li>
          </ul>
        </VAlert>

        <div
          v-if="loading"
          class="text-center py-10"
        >
          <VProgressCircular
            indeterminate
            color="primary"
          />
          <div class="text-caption text-medium-emphasis mt-3">
            Loading bills…
          </div>
        </div>

        <div
          v-else
          class="invoices-table-scroll"
        >
          <VTable
            class="invoices-table"
            density="compact"
            hover
          >
            <thead>
              <tr>
                <th class="col-student">
                  Student
                </th>
                <th class="col-no">
                  No.
                </th>
                <th class="col-staff">
                  Opened by
                </th>
                <th class="col-classes">
                  Classes
                </th>
                <th class="col-status">
                  Status
                </th>
                <th class="col-total text-end">
                  Total
                </th>
                <th class="col-actions">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              <template
                v-for="invoice in pagedInvoices"
                :key="invoice.id"
              >
                <tr
                  class="invoice-row"
                  :class="[
                    `invoice-row--${invoice.status}`,
                    { 'invoice-row--expanded': expandedId === invoice.id },
                  ]"
                  tabindex="0"
                  :aria-expanded="expandedId === invoice.id"
                  :aria-label="`${studentLabel(invoice)}, ${statusLabel[invoice.status] ?? invoice.status}`"
                  @click="toggleExpand(invoice.id)"
                  @keydown="onInvoiceRowKeydown($event, invoice.id)"
                >
                  <td class="col-student">
                    <div
                      class="student-name"
                      :title="studentLabel(invoice)"
                    >
                      {{ studentLabel(invoice) }}
                    </div>
                    <div class="text-caption text-medium-emphasis d-flex align-center flex-wrap gap-1">
                      <span v-if="invoice.unit_code">{{ invoice.unit_code }}</span>
                      <VChip
                        v-if="invoice.kind === 'manual'"
                        size="x-small"
                        color="info"
                        label
                      >
                        Manual
                      </VChip>
                      <span
                        v-if="allLocations && locationName(invoice.location_id)"
                        class="text-no-wrap"
                      >{{ locationName(invoice.location_id) }}</span>
                    </div>
                  </td>
                  <td class="col-no invoice-no">
                    <div>{{ invoice.invoice_no ?? '—' }}</div>
                    <div
                      v-if="invoice.receipt_no"
                      class="text-caption text-medium-emphasis"
                    >
                      {{ invoice.receipt_no }}
                    </div>
                  </td>
                  <td class="col-staff">
                    <div
                      v-if="openedBy(invoice)"
                      class="staff-name"
                      :title="openedBy(invoice)"
                    >
                      {{ openedBy(invoice) }}
                    </div>
                    <span
                      v-else
                      class="text-disabled"
                    >—</span>
                  </td>
                  <td class="col-classes">
                    <div
                      class="class-preview"
                      :title="classNames(invoice).join(' · ') || undefined"
                    >
                      {{ classPreview(invoice) }}
                    </div>
                    <div class="text-caption text-medium-emphasis text-truncate">
                      {{ periodLabel(invoice) }}
                      · {{ invoice.lines.length }} line{{ invoice.lines.length === 1 ? '' : 's' }}
                      <VIcon
                        size="14"
                        class="ms-1"
                        aria-hidden="true"
                      >
                        {{ expandedId === invoice.id ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line' }}
                      </VIcon>
                    </div>
                  </td>
                  <td class="col-status">
                    <VChip
                      size="x-small"
                      label
                      :color="statusColor[invoice.status] ?? 'grey'"
                    >
                      {{ statusLabel[invoice.status] ?? invoice.status }}
                    </VChip>
                  </td>
                  <td class="col-total text-end font-weight-medium tabular-nums">
                    {{ formatMoney(Number(invoice.total)) }}
                  </td>
                  <td
                    class="col-actions text-end"
                    @click.stop
                  >
                    <VBtn
                      v-if="invoice.status !== 'void'"
                      icon="ri-printer-line"
                      size="x-small"
                      variant="text"
                      aria-label="Print invoice"
                      title="Print / reprint"
                      @click="printInvoice(invoice)"
                    />
                    <VBtn
                      v-if="invoice.status === 'draft'"
                      icon="ri-file-check-line"
                      size="x-small"
                      variant="text"
                      color="primary"
                      aria-label="Issue bill"
                      title="Issue bill"
                      :loading="statusUpdatingId === invoice.id"
                      @click="askStatus(invoice, 'issued')"
                    />
                    <VBtn
                      v-if="invoice.status === 'issued'"
                      icon="ri-money-dollar-circle-line"
                      size="x-small"
                      variant="text"
                      color="success"
                      aria-label="Mark paid"
                      title="Mark paid — open a receipt"
                      @click="goMarkPaid(invoice)"
                    />
                    <VBtn
                      v-if="invoice.status === 'draft' || invoice.status === 'issued'"
                      icon="ri-close-circle-line"
                      size="x-small"
                      variant="text"
                      color="error"
                      aria-label="Cancel this bill"
                      title="Cancel this bill"
                      :loading="statusUpdatingId === invoice.id"
                      @click="askStatus(invoice, 'void')"
                    />
                  </td>
                </tr>
                <tr
                  v-if="expandedId === invoice.id"
                  class="invoice-detail-row"
                >
                  <td colspan="7">
                    <div class="invoice-slip">
                      <div class="invoice-slip__meta">
                        <span>
                          {{ invoice.kind === 'manual'
                            ? 'Manual invoice — lines were typed when it was issued.'
                            : 'Prices were copied when this bill was made. Changing the class later does not change issued or paid bills.' }}
                        </span>
                        <span>Period: {{ periodLabel(invoice) }}</span>
                        <span v-if="openedBy(invoice)">
                          Opened by <strong>{{ openedBy(invoice) }}</strong>
                        </span>
                        <span v-if="invoice.notes">
                          Remark: {{ invoice.notes }}
                        </span>
                      </div>
                      <VTable
                        density="compact"
                        class="invoice-lines"
                      >
                        <thead>
                          <tr>
                            <th>Class</th>
                            <th>Teacher</th>
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
                              </div>
                            </td>
                            <td class="text-body-2">
                              {{ line.staff_name || '—' }}
                            </td>
                            <td>
                              <VChip
                                size="x-small"
                                variant="tonal"
                                label
                              >
                                {{ billingLabel(line.billing_unit) }}
                              </VChip>
                            </td>
                            <td class="text-medium-emphasis tabular-nums">
                              {{ lineFormula(line) }}
                            </td>
                            <td class="text-end font-weight-medium text-no-wrap tabular-nums">
                              {{ formatMoney(Number(line.amount)) }}
                            </td>
                          </tr>
                          <tr v-if="invoice.lines.length === 0">
                            <td
                              colspan="5"
                              class="text-medium-emphasis"
                            >
                              No chargeable classes this month.
                            </td>
                          </tr>
                        </tbody>
                      </VTable>
                    </div>
                  </td>
                </tr>
              </template>
              <tr v-if="!loading && filteredInvoices.length === 0">
                <td
                  colspan="7"
                  class="text-center py-10"
                >
                  <div class="invoice-empty">
                    <VIcon
                      size="36"
                      class="mb-2 text-medium-emphasis"
                      aria-hidden="true"
                    >
                      ri-file-list-3-line
                    </VIcon>
                    <template v-if="invoices.length === 0">
                      <div class="text-body-1 font-weight-medium">
                        {{ allMonths ? 'No bills yet' : 'No bills this month' }}
                      </div>
                      <div class="text-medium-emphasis mt-1">
                        <template v-if="allMonths">
                          Pick a month and generate, or create a manual invoice.
                        </template>
                        <template v-else>
                          Enroll students with billed dates (and packages bought for per-class courses), then Generate.
                        </template>
                      </div>
                    </template>
                    <template v-else>
                      <div class="text-body-1 font-weight-medium">
                        No bills match this search or status
                      </div>
                      <VBtn
                        class="mt-3"
                        size="small"
                        variant="tonal"
                        prepend-icon="ri-filter-off-line"
                        @click="clearFilters"
                      >
                        Clear filters
                      </VBtn>
                    </template>
                  </div>
                </td>
              </tr>
            </tbody>
          </VTable>
        </div>
        <AttendancePaginationBar
          v-if="!loading && filteredInvoices.length > 0"
          v-model:page="page"
          v-model:page-size="pageSize"
          :total-pages="totalPages"
          :page-size-options="pageSizeOptions"
        />
      </VCardText>
    </VCard>

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
          Issuing locks <strong>{{ studentLabel(pendingStatus.invoice) }}</strong>
          at <strong>{{ formatMoney(Number(pendingStatus.invoice.total)) }}</strong>.
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
          :items="manualStaffOptions"
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
          <strong>{{ studentLabel(pendingStatus.invoice) }}</strong>
          will be cancelled. The invoice number is not used again.
          <template v-if="pendingStatus.invoice.kind === 'manual'">
            Any class package on it can be billed again.
          </template>
          <template v-else>
            Generate will make a new draft if the student is still in class this month, with a new number.
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
      Replaces drafts, skips issued and paid bills, and may bring back cancelled bills if the student is still in class.
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
                  {{ manualRowAmount(row) == null ? '—' : formatMoney(manualRowAmount(row)!) }}
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
              Total: {{ formatMoney(manualTotal) }}
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

.no-number-spin :deep(input[type='number']) {
  appearance: textfield;
  -moz-appearance: textfield;
}

.no-number-spin :deep(input[type='number']::-webkit-outer-spin-button),
.no-number-spin :deep(input[type='number']::-webkit-inner-spin-button) {
  -webkit-appearance: none;
  margin: 0;
}

.invoices-table-scroll {
  overflow-x: hidden;
}

.invoices-table {
  width: 100%;
  table-layout: fixed;
}

.invoices-table :deep(thead th),
.invoices-table :deep(tbody td) {
  vertical-align: middle;
}

.invoices-table :deep(thead th) {
  white-space: nowrap;
}

.invoices-table :deep(.col-student) {
  width: 18%;
  padding-left: 12px;
}

.invoices-table :deep(.col-no) {
  width: 7%;
}

.invoices-table :deep(.col-staff) {
  width: 12%;
}

.invoices-table :deep(.col-classes) {
  width: 28%;
}

.invoices-table :deep(.col-status) {
  width: 9%;
}

.invoices-table :deep(.col-total) {
  width: 12%;
}

.invoices-table :deep(.col-actions) {
  width: 14%;
  white-space: nowrap;
}

.invoices-table :deep(.student-name),
.invoices-table :deep(.class-preview),
.invoices-table :deep(.staff-name) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.invoices-table :deep(.student-name) {
  font-weight: 500;
}

.invoices-table :deep(.col-no),
.invoices-table :deep(.col-status),
.invoices-table :deep(.col-total) {
  white-space: nowrap;
}

.invoice-no,
.tabular-nums {
  font-variant-numeric: tabular-nums;
}

.invoice-no {
  letter-spacing: 0.02em;
  font-weight: 600;
}

.invoice-row {
  cursor: pointer;
}

.invoice-row td:first-child {
  box-shadow: inset 3px 0 0 rgba(var(--v-theme-on-surface), 0.16);
}

.invoice-row--draft td:first-child {
  box-shadow: inset 3px 0 0 rgb(var(--v-theme-warning));
}

.invoice-row--issued td:first-child {
  box-shadow: inset 3px 0 0 rgb(var(--v-theme-info));
}

.invoice-row--paid td:first-child {
  box-shadow: inset 3px 0 0 rgb(var(--v-theme-success));
}

.invoice-row--void {
  opacity: 0.72;
}

.invoice-row--void td:first-child {
  box-shadow: inset 3px 0 0 rgba(var(--v-theme-on-surface), 0.28);
}

.invoice-row--expanded {
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.invoice-row:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: -2px;
}

.invoice-detail-row td {
  background: rgba(var(--v-theme-on-surface), 0.03);
  padding-block: 12px !important;
}

.invoice-slip {
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.16);
  border-radius: 10px;
  padding: 12px 14px;
  background:
    linear-gradient(180deg, rgba(var(--v-theme-on-surface), 0.02), transparent 48px),
    rgb(var(--v-theme-surface));
}

.invoice-slip__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-bottom: 10px;
  color: rgba(var(--v-theme-on-surface), 0.64);
  font-size: 0.75rem;
  line-height: 1.4;
}

.invoice-lines {
  background: transparent;
}

.invoice-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  max-width: 28rem;
  margin-inline: auto;
}

@media (prefers-reduced-motion: reduce) {
  .invoice-row {
    transition: none;
  }
}
</style>
