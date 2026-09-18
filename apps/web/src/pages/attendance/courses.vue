<script setup lang="ts">
import {
  type BillingUnit,
  type CourseEnrollment,
  type CourseSku,
  type CourseSpu,
  type Weekday,
  createCourseEnrollment,
  createCourseSku,
  createCourseSpu,
  createEnrollmentPurchase,
  deleteCourseEnrollment,
  deleteCourseSku,
  deleteCourseSpu,
  listAllCourseEnrollments,
  listCourseSkus,
  listCourseSpus,
  updateCourseEnrollment,
  updateCourseSku,
  updateCourseSpu,
} from '@/api/attendance/courses'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import { type Unit, getUnit, listUnits } from '@/api/attendance/units'
import { pickCourseSelectionForSku, skuIdFromRouteQuery } from '@/utils/courseEnrollmentDisplay'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()
const route = useRoute()

const loading = ref(true)
const loadError = ref('')

useAutoClearAlerts(loadError)

const spus = ref<CourseSpu[]>([])
const skus = ref<CourseSku[]>([])
const locations = ref<LocationItem[]>([])
const staffUnits = ref<Unit[]>([])

const staffOptions = computed(() =>
  staffUnits.value
    .slice()
    .sort((a, b) => Number(b.is_active) - Number(a.is_active) || a.full_name.localeCompare(b.full_name))
    .map(u => ({ value: u.id, title: `${u.full_name} · ${u.code}${u.is_active ? '' : ' (inactive)'}` })),
)

const staffName = (id: string | null | undefined) => staffUnits.value.find(u => u.id === id)?.full_name ?? ''

// Natural sort for codes — F2 before F10.
const compareCodes = (a: string, b: string) => a.localeCompare(b, undefined, { numeric: true })

// ---- sortable table headers ----
interface TableSort<K extends string> {
  key: K
  dir: 1 | -1
}

type SortValue = string | number | null | undefined

function compareSortValues(a: SortValue, b: SortValue): number {
  if (a == null && b == null)
    return 0
  if (a == null)
    return 1
  if (b == null)
    return -1
  if (typeof a === 'number' && typeof b === 'number')
    return a - b

  return String(a).localeCompare(String(b), undefined, { numeric: true })
}

function toggleSort<K extends string>(state: TableSort<K>, key: K) {
  if (state.key === key) {
    state.dir = state.dir === 1 ? -1 : 1
  }
  else {
    state.key = key
    state.dir = 1
  }
}

function sortIconFor<K extends string>(state: TableSort<K>, key: K): string {
  if (state.key !== key)
    return 'ri-arrow-up-down-line'

  return state.dir === 1 ? 'ri-arrow-up-line' : 'ri-arrow-down-line'
}

const selectedSpuId = ref<string | null>(null)
const selectedSpu = computed(() => spus.value.find(s => s.id === selectedSpuId.value) ?? null)
const coursesScroll = ref<HTMLElement | null>(null)
const offeringsScroll = ref<HTMLElement | null>(null)

type SpuSortKey = 'code' | 'name' | 'subject'
type SkuSortKey = 'code' | 'name' | 'billing' | 'price'

const spuSort = reactive<TableSort<SpuSortKey>>({ key: 'code', dir: 1 })
const skuSort = reactive<TableSort<SkuSortKey>>({ key: 'code', dir: 1 })

const sortedSpus = computed(() => {
  const pick: Record<SpuSortKey, (s: CourseSpu) => SortValue> = {
    code: s => s.code,
    name: s => s.name_zh,
    subject: s => s.subject,
  }

  return [...spus.value].sort((a, b) => compareSortValues(pick[spuSort.key](a), pick[spuSort.key](b)) * spuSort.dir)
})

const skusForSelectedSpu = computed(() => {
  const pick: Record<SkuSortKey, (k: CourseSku) => SortValue> = {
    code: k => k.code,
    name: k => k.name_zh,
    billing: k => k.billing_unit,
    price: k => k.price,
  }

  return skus.value
    .filter(k => k.spu_id === selectedSpuId.value)
    .sort((a, b) => compareSortValues(pick[skuSort.key](a), pick[skuSort.key](b)) * skuSort.dir)
})

const locationName = (id: string | null) => locations.value.find(l => l.id === id)?.name_en ?? '—'

const spuName = (id: string | null | undefined) => spus.value.find(s => s.id === id)?.name_zh ?? ''

const billingUnitOptions: { title: string; value: BillingUnit }[] = [
  { title: 'Monthly (月費)', value: 'monthly' },
  { title: 'Per session (堂費)', value: 'per_session' },
]

const weekdayOptions: { title: string; value: Weekday }[] = [
  { title: 'Mon', value: 'monday' },
  { title: 'Tue', value: 'tuesday' },
  { title: 'Wed', value: 'wednesday' },
  { title: 'Thu', value: 'thursday' },
  { title: 'Fri', value: 'friday' },
  { title: 'Sat', value: 'saturday' },
  { title: 'Sun', value: 'sunday' },
]

function billingUnitLabel(unit: BillingUnit): string {
  return unit === 'per_session' ? '堂費' : '月費'
}

function meetingDaysLabel(days: Weekday[] | null | undefined): string {
  if (!days?.length)
    return '—'
  const titles = weekdayOptions.filter(d => days.includes(d.value)).map(d => d.title)

  return titles.join('/')
}

const locationOptions = computed(() =>
  locations.value.map(location => ({
    id: location.id,
    title: [location.name_en, location.name_zh].filter(Boolean).join(' · '),
  })),
)

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  await Promise.all([loadAll(), loadStudentOptions()])
  applySkuFromRoute()
})

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    const [spuList, skuList, locationList, staffList] = await Promise.all([
      listCourseSpus(),
      listCourseSkus(),
      listLocations({ is_active: true }),
      listUnits({ unit_type: 'staff', page_size: 200 }),
    ])

    spus.value = [...spuList].sort((a, b) => compareCodes(a.code, b.code))
    skus.value = [...skuList].sort((a, b) => compareCodes(a.code, b.code))
    locations.value = [...locationList].sort((a, b) => a.name_en.localeCompare(b.name_en))
    staffUnits.value = staffList
    if (!selectedSpuId.value && spuList.length > 0)
      selectedSpuId.value = spuList[0].id
  }
  catch (e) {
    console.error('Failed to load courses', e)
    loadError.value = formatApiError(e, 'Failed to load courses.')
  }
  finally {
    loading.value = false
  }
}

// ---------------- SPU dialog ----------------

const spuDialogOpen = ref(false)
const spuSaving = ref(false)
const spuSaveError = ref('')
const editingSpu = ref<CourseSpu | null>(null)
const spuForm = reactive({ code: '', name_zh: '', name_en: '', subject: '', description: '', is_active: true })
const spuCanSave = computed(() => spuForm.code.trim().length > 0 && spuForm.name_zh.trim().length > 0)

function openCreateSpu() {
  editingSpu.value = null
  Object.assign(spuForm, { code: '', name_zh: '', name_en: '', subject: '', description: '', is_active: true })
  spuSaveError.value = ''
  spuDialogOpen.value = true
}

function openEditSpu(spu: CourseSpu) {
  editingSpu.value = spu
  Object.assign(spuForm, {
    code: spu.code,
    name_zh: spu.name_zh,
    name_en: spu.name_en ?? '',
    subject: spu.subject ?? '',
    description: spu.description ?? '',
    is_active: spu.is_active,
  })
  spuSaveError.value = ''
  spuDialogOpen.value = true
}

async function saveSpu() {
  if (!spuCanSave.value)
    return
  spuSaving.value = true
  spuSaveError.value = ''

  const payload = {
    code: spuForm.code.trim(),
    name_zh: spuForm.name_zh.trim(),
    name_en: spuForm.name_en.trim() || null,
    subject: spuForm.subject.trim() || null,
    description: spuForm.description.trim() || null,
    is_active: spuForm.is_active,
  }

  try {
    if (editingSpu.value)
      await updateCourseSpu(editingSpu.value.id, payload)
    else
      await createCourseSpu(payload)

    spuDialogOpen.value = false
    await loadAll()
  }
  catch (e) {
    spuSaveError.value = formatApiError(e, 'Could not save course.')
  }
  finally {
    spuSaving.value = false
  }
}

const deleteConfirmOpen = ref(false)
const deleteConfirmLoading = ref(false)
const deleteConfirmError = ref('')

interface CourseDeleteTarget {
  kind: 'spu' | 'sku' | 'enrollment'
  title: string
  detail: string
  run: () => Promise<void>
}

const deleteTarget = ref<CourseDeleteTarget | null>(null)

function closeDeleteConfirm() {
  if (deleteConfirmLoading.value)
    return
  deleteConfirmOpen.value = false
  deleteConfirmError.value = ''
  deleteTarget.value = null
}

function openDeleteConfirm(target: NonNullable<typeof deleteTarget.value>) {
  deleteTarget.value = target
  deleteConfirmError.value = ''
  deleteConfirmOpen.value = true
}

async function confirmCourseDelete() {
  if (!deleteTarget.value)
    return

  deleteConfirmLoading.value = true
  deleteConfirmError.value = ''
  try {
    await deleteTarget.value.run()
    deleteConfirmOpen.value = false
    deleteTarget.value = null
  }
  catch (e) {
    deleteConfirmError.value = formatApiError(e, 'Could not delete this item.')
  }
  finally {
    deleteConfirmLoading.value = false
  }
}

function removeSpu(spu: CourseSpu) {
  openDeleteConfirm({
    kind: 'spu',
    title: `Delete ${spu.name_zh}?`,
    detail: `Delete course "${spu.name_zh}"? This only works if it has no class offerings.`,
    run: async () => {
      await deleteCourseSpu(spu.id)
      if (selectedSpuId.value === spu.id)
        selectedSpuId.value = null
      await loadAll()
    },
  })
}

// ---------------- SKU dialog ----------------

const skuDialogOpen = ref(false)
const skuSaving = ref(false)
const skuSaveError = ref('')
const editingSku = ref<CourseSku | null>(null)

const skuForm = reactive({
  code: '',
  name_zh: '',
  name_en: '',
  level: '',
  schedule_note: '',
  location_id: null as string | null,
  staff_id: null as string | null,
  capacity: null as number | null,
  price: null as number | null,
  billing_unit: 'monthly' as BillingUnit,
  meeting_weekdays: [] as Weekday[],
  is_active: true,
})

const skuCanSave = computed(() => {
  return !!(skuForm.code.trim() && skuForm.name_zh.trim())
})

const skuBillingPreview = computed(() => {
  const raw = skuForm.price
  const hasPrice = raw != null && !Number.isNaN(Number(raw))
  const priceText = hasPrice ? `HK$${Number(raw).toFixed(2)}` : 'no price (Generate skips this class)'
  if (skuForm.billing_unit === 'per_session')
    return `Bills ${priceText} × sessions purchased, once, when the student is enrolled. Not affected by attendance.`

  return `Bills ${priceText} once for each overlapping month. Class days are shown on the roster only.`
})

function openCreateSku() {
  if (!selectedSpuId.value)
    return
  editingSku.value = null
  Object.assign(skuForm, {
    code: '',
    name_zh: '',
    name_en: '',
    level: '',
    schedule_note: '',
    location_id: null,
    staff_id: null,
    capacity: null,
    price: null,
    billing_unit: 'monthly' as BillingUnit,
    meeting_weekdays: [] as Weekday[],
    is_active: true,
  })
  skuSaveError.value = ''
  skuDialogOpen.value = true
}

function openEditSku(sku: CourseSku) {
  editingSku.value = sku
  Object.assign(skuForm, {
    code: sku.code,
    name_zh: sku.name_zh,
    name_en: sku.name_en ?? '',
    level: sku.level ?? '',
    schedule_note: sku.schedule_note ?? '',
    location_id: sku.location_id,
    staff_id: sku.staff_id,
    capacity: sku.capacity,
    price: sku.price,
    billing_unit: sku.billing_unit,
    meeting_weekdays: [...(sku.meeting_weekdays ?? [])],
    is_active: sku.is_active,
  })
  skuSaveError.value = ''
  skuDialogOpen.value = true
}

async function saveSku() {
  if (!selectedSpuId.value || !skuCanSave.value)
    return
  skuSaving.value = true
  skuSaveError.value = ''

  const payload = {
    spu_id: selectedSpuId.value,
    code: skuForm.code.trim(),
    name_zh: skuForm.name_zh.trim(),
    name_en: skuForm.name_en.trim() || null,
    level: skuForm.level.trim() || null,
    schedule_note: skuForm.schedule_note.trim() || null,
    location_id: skuForm.location_id,
    staff_id: skuForm.staff_id,
    capacity: skuForm.capacity,
    price: skuForm.price,
    billing_unit: skuForm.billing_unit,
    meeting_weekdays: skuForm.meeting_weekdays,
    is_active: skuForm.is_active,
  }

  try {
    if (editingSku.value)
      await updateCourseSku(editingSku.value.id, payload)
    else
      await createCourseSku(payload)

    skuDialogOpen.value = false
    await loadAll()
  }
  catch (e) {
    skuSaveError.value = formatApiError(e, 'Could not save class offering.')
  }
  finally {
    skuSaving.value = false
  }
}

function removeSku(sku: CourseSku) {
  openDeleteConfirm({
    kind: 'sku',
    title: `Delete ${sku.name_zh}?`,
    detail: `Delete class "${sku.name_zh}"? This only works if no student is enrolled.`,
    run: async () => {
      await deleteCourseSku(sku.id)
      await loadAll()
    },
  })
}

// ---------------- Enrollments (class roster) ----------------

const studentSearch = ref('')
const studentOptions = ref<Unit[]>([])
const studentById = reactive<Record<string, Unit>>({})
const studentSearchLoading = ref(false)
let studentSearchRequestId = 0
const selectedStudentId = ref<string | null>(null)
const rosterSkuId = ref<string | null>(null)
const enrollStartDate = ref<string | null>('')
const enrollEndDate = ref<string | null>('')
const enrollPurchasedQuantity = ref<number | null>(null)
const enrollUnitPrice = ref<number | null>(null)
const enrolling = ref(false)
const enrollError = ref('')
const enrollSuccess = ref('')

useAutoClearAlerts(enrollSuccess)

const enrollments = ref<CourseEnrollment[]>([])
const enrollmentsLoading = ref(false)
const enrollmentDates = ref<Record<string, { start: string; end: string; price: string }>>({})
const enrollmentDateSavingId = ref<string | null>(null)
let rosterRequestId = 0

const rosterSku = computed(() => skus.value.find(k => k.id === rosterSkuId.value) ?? null)
const activeRosterCount = computed(() => enrollments.value.filter(e => e.status === 'active').length)

const rosterAtCapacity = computed(() => {
  const cap = rosterSku.value?.capacity
  if (cap == null)
    return false

  return activeRosterCount.value >= cap
})

const rosterEditingId = ref<string | null>(null)

// Top-up UI hidden for now — backend purchase endpoints stay available.
const topUpEnabled = false
const topUpOpen = ref(false)
const topUpEnrollment = ref<CourseEnrollment | null>(null)
const topUpQuantity = ref<number | null>(null)
const topUpPrice = ref<number | null>(null)
const topUpDate = ref<string>('')
const topUpNote = ref('')
const topUpSaving = ref(false)

function formatRosterDate(value: string | null | undefined, empty = '—'): string {
  if (!value)
    return empty

  return String(value).slice(0, 10)
}

function rosterPriceLabel(sku: CourseSku): string {
  if (sku.price == null)
    return 'No price — Generate will skip this class'
  const amount = `HK$${Number(sku.price).toFixed(2)}`

  return sku.billing_unit === 'per_session' ? `${amount} / session` : `${amount} / month`
}

function beginEditEnrollmentDates(enrollment: CourseEnrollment) {
  rosterEditingId.value = enrollment.id
  enrollmentDates.value[enrollment.id] = {
    start: enrollment.start_date ?? '',
    end: enrollment.end_date ?? '',
    price: enrollment.unit_price != null ? String(enrollment.unit_price) : '',
  }
}

function cancelEditEnrollmentDates(enrollment: CourseEnrollment) {
  enrollmentDates.value[enrollment.id] = {
    start: enrollment.start_date ?? '',
    end: enrollment.end_date ?? '',
    price: enrollment.unit_price != null ? String(enrollment.unit_price) : '',
  }
  rosterEditingId.value = null
}

function cacheStudents(units: Unit[]) {
  for (const unit of units)
    studentById[unit.id] = unit
}

function studentLabel(unitId: string): string {
  return studentById[unitId]?.full_name ?? '…'
}

function studentCode(unitId: string): string {
  return studentById[unitId]?.code ?? ''
}

function emptyToNull(value: string | null | undefined): string | null {
  const trimmed = value?.trim()

  return trimmed || null
}

function syncEnrollmentDates(items: CourseEnrollment[]) {
  enrollmentDates.value = Object.fromEntries(
    items.map(e => [e.id, { start: e.start_date ?? '', end: e.end_date ?? '', price: e.unit_price != null ? String(e.unit_price) : '' }]),
  )
}

async function ensureStudentNames(items: CourseEnrollment[]) {
  const missingIds = [...new Set(items.map(e => e.unit_id).filter(id => !studentById[id]))]
  if (missingIds.length === 0)
    return

  const loaded = await Promise.all(missingIds.map(async id => {
    try {
      return await getUnit(id)
    }
    catch (e) {
      console.error('Failed to load student for roster', e)

      return null
    }
  }))

  cacheStudents(loaded.filter((u): u is Unit => u != null))
}

async function loadRoster(skuId: string | null) {
  const requestId = ++rosterRequestId

  enrollments.value = []
  if (!skuId)
    return

  enrollmentsLoading.value = true
  try {
    const items = await listAllCourseEnrollments({ sku_id: skuId })
    if (requestId !== rosterRequestId)
      return
    enrollments.value = items
    syncEnrollmentDates(items)
    await ensureStudentNames(items)
  }
  catch (e) {
    console.error('Failed to load roster', e)
    if (requestId === rosterRequestId)
      enrollError.value = formatApiError(e, 'Could not load class roster.')
  }
  finally {
    if (requestId === rosterRequestId)
      enrollmentsLoading.value = false
  }
}

async function loadStudentOptions(search?: string) {
  const requestId = ++studentSearchRequestId

  studentSearchLoading.value = true
  try {
    const students = await listUnits({
      unit_type: 'student',
      is_active: true,
      search: search || undefined,
      page_size: 20,
    })

    if (requestId === studentSearchRequestId) {
      studentOptions.value = students
        .filter(u => u.status === 'active')
        .sort((a, b) => a.full_name.localeCompare(b.full_name))
      cacheStudents(studentOptions.value)
    }
  }
  catch (e) {
    console.error('Failed to load students', e)
  }
  finally {
    if (requestId === studentSearchRequestId)
      studentSearchLoading.value = false
  }
}

const searchDebounce = useDebounceFn(() => loadStudentOptions(studentSearch.value.trim()), 300)

watch(studentSearch, value => {
  if (value.trim())
    searchDebounce()
  else if (!selectedStudentId.value)
    loadStudentOptions()
})

watch(skusForSelectedSpu, list => {
  if (list.length === 0) {
    rosterSkuId.value = null

    return
  }
  if (!list.some(k => k.id === rosterSkuId.value))
    rosterSkuId.value = list[0].id
})

watch(rosterSkuId, id => {
  enrollError.value = ''
  rosterEditingId.value = null
  rosterSearch.value = ''
  rosterStatusFilter.value = 'active'

  const sku = skus.value.find(k => k.id === id)
  if (sku && sku.spu_id !== selectedSpuId.value)
    selectedSpuId.value = sku.spu_id
  loadRoster(id)
})

function applySkuFromRoute() {
  const selection = pickCourseSelectionForSku(skus.value, skuIdFromRouteQuery(route.query))
  if (!selection)
    return
  selectedSpuId.value = selection.spuId
  rosterSkuId.value = selection.skuId
}

watch(() => route.query.sku, () => {
  if (skus.value.length === 0)
    return
  applySkuFromRoute()
})

function enrollNeedsPurchasedQuantity() {
  return rosterSku.value?.billing_unit === 'per_session'
}

const enrollPriceHint = computed(() => {
  const sku = rosterSku.value
  if (!sku)
    return ''
  if (sku.price == null)
    return 'No class price — enter this student\'s monthly price, or Generate will skip them.'

  return `Leave empty to use the class price (${rosterPriceLabel(sku)}).`
})

const enrollEffectivePrice = computed(() => enrollUnitPrice.value ?? rosterSku.value?.price ?? null)

const enrollBillPreview = computed(() => {
  const sku = rosterSku.value
  if (!sku)
    return ''
  const price = enrollEffectivePrice.value
  if (sku.billing_unit === 'per_session') {
    const qty = enrollPurchasedQuantity.value
    if (qty == null || qty <= 0)
      return 'Per-session class — enter how many sessions this student bought. Billed once, not monthly.'
    if (sku.price != null)
      return `${qty} session${qty === 1 ? '' : 's'} recorded — bill it from the Manual invoice (default HK$${sku.price.toFixed(2)}/session, adjustable when issuing).`

    return `${qty} session${qty === 1 ? '' : 's'} recorded — set the price when you issue the manual invoice.`
  }
  if (price == null)
    return 'No class price — this student will be skipped at Generate until a price is set.'

  return `Bills HK$${price.toFixed(2)} every month that overlaps the billed window.`
})

const classOptions = computed(() =>
  skus.value
    .slice()
    .sort((a, b) => compareCodes(a.code, b.code))
    .map(k => ({ ...k, title: `${k.code} · ${k.name_zh}` })),
)

const activeRosterUnitIds = computed(
  () => new Set(enrollments.value.filter(e => e.status === 'active').map(e => e.unit_id)),
)

type RosterSortKey = 'student' | 'status' | 'sessions' | 'price' | 'window'
type RosterStatusFilter = 'active' | 'ended' | 'all'

const rosterSort = reactive<TableSort<RosterSortKey>>({ key: 'student', dir: 1 })
const rosterSearch = ref('')
const rosterStatusFilter = ref<RosterStatusFilter>('active')
const rosterSection = ref<HTMLElement | null>(null)

const rosterStatusCounts = computed(() => {
  let active = 0
  let ended = 0
  for (const e of enrollments.value) {
    if (e.status === 'active')
      active++
    else
      ended++
  }

  return { active, ended, all: enrollments.value.length }
})

const rosterStatusFilters = computed(() => [
  { value: 'active' as const, title: 'In class', count: rosterStatusCounts.value.active },
  { value: 'ended' as const, title: 'Left', count: rosterStatusCounts.value.ended },
  { value: 'all' as const, title: 'All', count: rosterStatusCounts.value.all },
])

const rosterCapacityPercent = computed(() => {
  const cap = rosterSku.value?.capacity
  if (!cap)
    return 0

  return Math.min(100, Math.round((activeRosterCount.value / cap) * 100))
})

const rosterMetaLine = computed(() => {
  const sku = rosterSku.value
  if (!sku)
    return ''

  return [
    sku.schedule_note,
    sku.meeting_weekdays?.length ? meetingDaysLabel(sku.meeting_weekdays) : '',
    staffName(sku.staff_id),
    sku.location_id ? locationName(sku.location_id) : '',
    `${billingUnitLabel(sku.billing_unit ?? 'monthly')} · ${rosterPriceLabel(sku)}`,
  ].filter(Boolean).join(' · ')
})

const editingEnrollment = computed(() =>
  enrollments.value.find(e => e.id === rosterEditingId.value) ?? null,
)

const editDialogOpen = computed({
  get: () => rosterEditingId.value != null,
  set: (open: boolean) => {
    if (!open && rosterEditingId.value) {
      const current = editingEnrollment.value
      if (current)
        cancelEditEnrollmentDates(current)
      else
        rosterEditingId.value = null
    }
  },
})

function enrollmentStatusLabel(status: string): string {
  if (status === 'active')
    return 'In class'
  if (status === 'completed')
    return 'Completed'
  if (status === 'cancelled')
    return 'Left'

  return status
}

function billingWindowLabel(enrollment: CourseEnrollment): string {
  return `${formatRosterDate(enrollment.start_date, 'Already started')} → ${formatRosterDate(enrollment.end_date, 'Ongoing')}`
}

function enrollmentPriceParts(enrollment: CourseEnrollment): { amount: string; hint: string } | null {
  const sku = rosterSku.value
  if (enrollment.unit_price != null) {
    return {
      amount: `HK$${Number(enrollment.unit_price).toFixed(2)}`,
      hint: 'this student',
    }
  }
  if (sku?.price != null) {
    return {
      amount: `HK$${Number(sku.price).toFixed(2)}`,
      hint: sku.billing_unit === 'per_session' ? 'class / session' : 'class / month',
    }
  }

  return null
}

function matchesRosterSearch(enrollment: CourseEnrollment, query: string): boolean {
  const name = (studentById[enrollment.unit_id]?.full_name ?? '').toLowerCase()
  const code = (studentById[enrollment.unit_id]?.code ?? '').toLowerCase()

  return name.includes(query) || code.includes(query)
}

// Roster rows sort by the selected column; rows with a missing value sink to the bottom (asc).
const rosterRows = computed(() => {
  const sku = rosterSku.value

  const pick: Record<RosterSortKey, (e: CourseEnrollment) => SortValue> = {
    student: e => studentById[e.unit_id]?.full_name ?? null,
    status: e => e.status,
    sessions: e => purchaseSummary(e).total,
    price: e => e.unit_price ?? sku?.price ?? null,
    window: e => e.start_date ?? e.end_date ?? null,
  }

  return [...enrollments.value].sort((a, b) => {
    if (rosterSort.key === 'student') {
      const byStatus = Number(b.status === 'active') - Number(a.status === 'active')
      if (byStatus)
        return byStatus
    }

    return compareSortValues(pick[rosterSort.key](a), pick[rosterSort.key](b)) * rosterSort.dir
  })
})

const filteredRosterRows = computed(() => {
  const query = rosterSearch.value.trim().toLowerCase()

  return rosterRows.value.filter(e => {
    if (rosterStatusFilter.value === 'active' && e.status !== 'active')
      return false
    if (rosterStatusFilter.value === 'ended' && e.status === 'active')
      return false
    if (query && !matchesRosterSearch(e, query))
      return false

    return true
  })
})

const enrollDisabledReason = computed(() => {
  if (!rosterSkuId.value)
    return 'Pick a class first.'
  if (rosterSku.value?.is_active === false)
    return 'This class is inactive — Generate skips it.'
  if (rosterAtCapacity.value)
    return 'This class is full.'
  if (!selectedStudentId.value)
    return 'Search and pick a student.'
  if (activeRosterUnitIds.value.has(selectedStudentId.value))
    return 'This student is already in the class.'
  if (enrollNeedsPurchasedQuantity() && !enrollPurchasedQuantity.value)
    return 'Enter how many sessions this student bought.'

  return ''
})

async function selectClass(skuId: string) {
  rosterSkuId.value = skuId
  await nextTick()
  scrollCatalogSelection()
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  rosterSection.value?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
}

function scrollRowInCatalog(container: HTMLElement | null) {
  const row = container?.querySelector('tr.bg-primary-lighten-5') as HTMLElement | null
  if (!container || !row)
    return

  const box = container.getBoundingClientRect()
  const rowBox = row.getBoundingClientRect()
  if (rowBox.top < box.top)
    container.scrollTop -= box.top - rowBox.top
  else if (rowBox.bottom > box.bottom)
    container.scrollTop += rowBox.bottom - box.bottom
}

function scrollCatalogSelection() {
  scrollRowInCatalog(coursesScroll.value)
  scrollRowInCatalog(offeringsScroll.value)
}

watch([selectedSpuId, rosterSkuId], async () => {
  await nextTick()
  scrollCatalogSelection()
})

async function enrollStudent() {
  if (!selectedStudentId.value || !rosterSkuId.value || rosterSku.value?.is_active === false || rosterAtCapacity.value)
    return
  if (activeRosterUnitIds.value.has(selectedStudentId.value)) {
    enrollError.value = 'This student is already enrolled in this class.'

    return
  }
  if (enrollNeedsPurchasedQuantity() && !enrollPurchasedQuantity.value) {
    enrollError.value = 'Enter how many sessions this student purchased.'

    return
  }

  const startDate = emptyToNull(enrollStartDate.value)
  const endDate = emptyToNull(enrollEndDate.value)
  if (startDate && endDate && endDate < startDate) {
    enrollError.value = 'Last billed day must be on or after first billed day.'

    return
  }
  if (enrollUnitPrice.value != null && enrollUnitPrice.value < 0) {
    enrollError.value = 'Price cannot be negative.'

    return
  }

  enrolling.value = true
  enrollError.value = ''
  try {
    const created = await createCourseEnrollment({
      unit_id: selectedStudentId.value,
      sku_id: rosterSkuId.value,
      start_date: startDate,
      end_date: endDate,
      purchased_quantity: enrollNeedsPurchasedQuantity() ? enrollPurchasedQuantity.value : null,
      unit_price: enrollNeedsPurchasedQuantity() ? null : enrollUnitPrice.value,
    })

    enrollments.value = [created, ...enrollments.value]
    enrollmentDates.value = {
      [created.id]: { start: created.start_date ?? '', end: created.end_date ?? '', price: created.unit_price != null ? String(created.unit_price) : '' },
      ...enrollmentDates.value,
    }

    const picked = studentOptions.value.find(u => u.id === selectedStudentId.value)
    if (picked)
      cacheStudents([picked])

    enrollSuccess.value = `${picked?.full_name ?? 'Student'} enrolled in ${rosterSku.value?.name_zh ?? 'class'}.`
    selectedStudentId.value = null
    studentSearch.value = ''
    enrollStartDate.value = ''
    enrollEndDate.value = ''
    enrollPurchasedQuantity.value = null
    enrollUnitPrice.value = null
    rosterStatusFilter.value = 'active'
  }
  catch (e) {
    enrollError.value = formatApiError(e, 'Could not enroll student.')
  }
  finally {
    enrolling.value = false
  }
}

async function saveEnrollmentDates(enrollment: CourseEnrollment) {
  const draft = enrollmentDates.value[enrollment.id]
  if (!draft)
    return

  const startDate = emptyToNull(draft.start)
  const endDate = emptyToNull(draft.end)
  if (startDate && endDate && endDate < startDate) {
    enrollError.value = 'Last billed day must be on or after first billed day.'

    return
  }

  const trimmedPrice = draft.price.trim()
  const unitPrice = trimmedPrice ? Number(trimmedPrice) : null
  if (unitPrice != null && (Number.isNaN(unitPrice) || unitPrice < 0)) {
    enrollError.value = 'Price must be zero or more.'

    return
  }

  enrollmentDateSavingId.value = enrollment.id
  enrollError.value = ''
  try {
    const updated = await updateCourseEnrollment(enrollment.id, {
      start_date: startDate,
      end_date: endDate,
      unit_price: unitPrice,
    })

    const idx = enrollments.value.findIndex(e => e.id === enrollment.id)

    if (idx !== -1)
      enrollments.value[idx] = updated

    enrollmentDates.value[enrollment.id] = {
      start: updated.start_date ?? '',
      end: updated.end_date ?? '',
      price: updated.unit_price != null ? String(updated.unit_price) : '',
    }
    rosterEditingId.value = null
  }
  catch (e) {
    enrollError.value = formatApiError(e, 'Could not update dates.')
  }
  finally {
    enrollmentDateSavingId.value = null
  }
}

function cancelEnrollment(enrollment: CourseEnrollment) {
  const unbilledQty = purchaseSummary(enrollment).unbilledQty

  openDeleteConfirm({
    kind: 'enrollment',
    title: `Unenroll ${studentLabel(enrollment.unit_id)}?`,
    detail: unbilledQty > 0
      ? `Stops billing going forward — issued invoices stay. Note: ${unbilledQty} session${unbilledQty === 1 ? '' : 's'} not yet billed; you can still bill them via a manual invoice.`
      : 'Stops billing going forward — issued invoices stay. You can re-activate later.',
    run: async () => {
      const updated = await updateCourseEnrollment(enrollment.id, { status: 'cancelled' })
      const idx = enrollments.value.findIndex(e => e.id === enrollment.id)
      if (idx !== -1)
        enrollments.value[idx] = updated
    },
  })
}

async function reactivateEnrollment(enrollment: CourseEnrollment) {
  try {
    const updated = await updateCourseEnrollment(enrollment.id, { status: 'active' })
    const idx = enrollments.value.findIndex(e => e.id === enrollment.id)
    if (idx !== -1)
      enrollments.value[idx] = updated
    enrollSuccess.value = `${studentLabel(enrollment.unit_id)} re-activated.`
  }
  catch (e) {
    enrollError.value = formatApiError(e, 'Could not re-activate enrollment.')
  }
}

function removeEnrollment(enrollment: CourseEnrollment) {
  const { total, unbilledQty } = purchaseSummary(enrollment)

  const purchaseNote = total > 0
    ? ` This also removes ${total} session purchase record${total === 1 ? '' : 's'}${unbilledQty > 0 ? ` (${unbilledQty} never billed)` : ''} — issued invoices keep their snapshots.`
    : ''

  openDeleteConfirm({
    kind: 'enrollment',
    title: 'Remove enrollment?',
    detail: `Remove this enrollment record entirely?${purchaseNote} For a student who is just leaving, Unenroll keeps the record instead.`,
    run: async () => {
      await deleteCourseEnrollment(enrollment.id)
      enrollments.value = enrollments.value.filter(e => e.id !== enrollment.id)
    },
  })
}

function openTopUp(enrollment: CourseEnrollment) {
  topUpEnrollment.value = enrollment
  topUpQuantity.value = null
  topUpPrice.value = enrollment.unit_price ?? rosterSku.value?.price ?? null
  topUpDate.value = new Date().toLocaleDateString('en-CA')
  topUpNote.value = ''
  topUpOpen.value = true
}

async function saveTopUp() {
  if (!topUpEnrollment.value || !topUpQuantity.value || topUpQuantity.value <= 0)
    return
  if (topUpPrice.value == null || topUpPrice.value < 0)
    return

  topUpSaving.value = true
  try {
    const created = await createEnrollmentPurchase(topUpEnrollment.value.id, {
      purchased_quantity: topUpQuantity.value,
      unit_price: topUpPrice.value,
      purchased_at: topUpDate.value,
      notes: topUpNote.value.trim() || null,
    })

    const idx = enrollments.value.findIndex(e => e.id === topUpEnrollment.value!.id)
    if (idx !== -1) {
      const existing = enrollments.value[idx]

      existing.purchases = [...existing.purchases, created]
    }
    enrollSuccess.value = `Added ${created.purchased_quantity} session${created.purchased_quantity === 1 ? '' : 's'} for ${studentLabel(topUpEnrollment.value.unit_id)} — billed on the next Generate.`
    topUpOpen.value = false
  }
  catch (e) {
    enrollError.value = formatApiError(e, 'Could not add top-up.')
  }
  finally {
    topUpSaving.value = false
  }
}

const enrollmentStatusColor: Record<string, string> = {
  active: 'success',
  completed: 'info',
  cancelled: 'grey',
}

function purchaseSummary(e: CourseEnrollment) {
  const purchases = e.purchases ?? []
  const unbilled = purchases.filter(p => p.billed_invoice_line_id === null)

  return {
    total: purchases.reduce((sum, p) => sum + p.purchased_quantity, 0),
    unbilledQty: unbilled.reduce((sum, p) => sum + p.purchased_quantity, 0),
  }
}

function purchaseTooltip(e: CourseEnrollment): string {
  return (e.purchases ?? [])
    .map(p => [
      formatRosterDate(p.purchased_at),
      p.unit_price != null ? `${p.purchased_quantity} × ${Number(p.unit_price).toFixed(2)}` : `${p.purchased_quantity} session${p.purchased_quantity === 1 ? '' : 's'} · price TBD`,
      p.billed_invoice_line_id === null ? 'unbilled' : 'billed',
      p.notes ?? '',
    ].filter(Boolean).join(' · '))
    .join('\n')
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
          Course Management
        </div>
        <div class="text-body-2 text-medium-emphasis">
          Pick a course, then a class. The roster below is who is in that class.
        </div>
      </VCol>
      <VCol
        cols="auto"
        class="d-flex gap-2"
      >
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="loading"
          @click="loadAll"
        >
          Refresh
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          @click="openCreateSpu"
        >
          Add Course
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

    <VRow v-if="loading">
      <VCol
        cols="12"
        class="text-center py-12"
      >
        <VProgressCircular
          indeterminate
          color="primary"
          size="48"
        />
      </VCol>
    </VRow>

    <template v-else>
      <VRow class="catalog-row">
        <!-- Courses (SPU) -->
        <VCol
          cols="12"
          md="5"
        >
          <VCard class="catalog-card">
            <VCardItem>
              <VCardTitle>Courses</VCardTitle>
              <VCardSubtitle v-if="sortedSpus.length">
                {{ sortedSpus.length }} course{{ sortedSpus.length === 1 ? '' : 's' }}
              </VCardSubtitle>
            </VCardItem>
            <div
              ref="coursesScroll"
              class="catalog-scroll"
            >
            <VTable
              density="compact"
              hover
              class="courses-table"
            >
              <thead>
                <tr>
                  <th
                    class="sortable"
                    @click="toggleSort(spuSort, 'code')"
                  >
                    Code
                    <VIcon
                      :icon="sortIconFor(spuSort, 'code')"
                      size="14"
                      class="ms-1 sort-icon"
                      :class="{ 'sort-icon--active': spuSort.key === 'code' }"
                    />
                  </th>
                  <th
                    class="sortable"
                    style="min-width: 8rem;"
                    @click="toggleSort(spuSort, 'name')"
                  >
                    Name
                    <VIcon
                      :icon="sortIconFor(spuSort, 'name')"
                      size="14"
                      class="ms-1 sort-icon"
                      :class="{ 'sort-icon--active': spuSort.key === 'name' }"
                    />
                  </th>
                  <th
                    class="sortable"
                    @click="toggleSort(spuSort, 'subject')"
                  >
                    Subject
                    <VIcon
                      :icon="sortIconFor(spuSort, 'subject')"
                      size="14"
                      class="ms-1 sort-icon"
                      :class="{ 'sort-icon--active': spuSort.key === 'subject' }"
                    />
                  </th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="spu in sortedSpus"
                  :key="spu.id"
                  :class="{ 'bg-primary-lighten-5': spu.id === selectedSpuId }"
                  style="cursor: pointer;"
                  @click="selectedSpuId = spu.id"
                >
                  <td>{{ spu.code }}</td>
                  <td class="text-no-wrap">
                    {{ spu.name_zh }}
                    <VChip
                      v-if="!spu.is_active"
                      size="x-small"
                      color="grey"
                      class="ms-1"
                    >
                      inactive
                    </VChip>
                  </td>
                  <td>{{ spu.subject ?? '—' }}</td>
                  <td class="text-end">
                    <VBtn
                      icon
                      size="x-small"
                      variant="text"
                      @click.stop="openEditSpu(spu)"
                    >
                      <VIcon
                        icon="ri-edit-line"
                        size="16"
                      />
                    </VBtn>
                    <VBtn
                      icon
                      size="x-small"
                      variant="text"
                      color="error"
                      @click.stop="removeSpu(spu)"
                    >
                      <VIcon
                        icon="ri-delete-bin-line"
                        size="16"
                      />
                    </VBtn>
                  </td>
                </tr>
                <tr v-if="spus.length === 0">
                  <td
                    colspan="4"
                    class="text-center text-medium-emphasis py-6"
                  >
                    No courses yet. Click <strong>Add Course</strong> to create one.
                  </td>
                </tr>
              </tbody>
            </VTable>
            </div>
          </VCard>
        </VCol>

        <!-- Class offerings (SKU) for selected SPU -->
        <VCol
          cols="12"
          md="7"
        >
          <VCard class="catalog-card">
            <VCardItem>
              <VCardTitle>
                Class Offerings
                <span
                  v-if="selectedSpu"
                  class="text-body-2 text-medium-emphasis"
                >— {{ selectedSpu.name_zh }}</span>
              </VCardTitle>
              <VCardSubtitle v-if="skusForSelectedSpu.length">
                {{ skusForSelectedSpu.length }} class{{ skusForSelectedSpu.length === 1 ? '' : 'es' }}
              </VCardSubtitle>
              <template #append>
                <VBtn
                  size="small"
                  color="primary"
                  prepend-icon="ri-add-line"
                  :disabled="!selectedSpuId"
                  @click="openCreateSku"
                >
                  Add Class
                </VBtn>
              </template>
            </VCardItem>
            <div
              ref="offeringsScroll"
              class="catalog-scroll"
            >
            <VTable
              density="compact"
              hover
              class="offerings-table"
            >
              <thead>
                <tr>
                  <th
                    class="sortable"
                    @click="toggleSort(skuSort, 'code')"
                  >
                    Code
                    <VIcon
                      :icon="sortIconFor(skuSort, 'code')"
                      size="14"
                      class="ms-1 sort-icon"
                      :class="{ 'sort-icon--active': skuSort.key === 'code' }"
                    />
                  </th>
                  <th
                    class="sortable"
                    style="min-width: 10rem;"
                    @click="toggleSort(skuSort, 'name')"
                  >
                    Name
                    <VIcon
                      :icon="sortIconFor(skuSort, 'name')"
                      size="14"
                      class="ms-1 sort-icon"
                      :class="{ 'sort-icon--active': skuSort.key === 'name' }"
                    />
                  </th>
                  <th>Schedule</th>
                  <th
                    class="sortable"
                    @click="toggleSort(skuSort, 'billing')"
                  >
                    Billing
                    <VIcon
                      :icon="sortIconFor(skuSort, 'billing')"
                      size="14"
                      class="ms-1 sort-icon"
                      :class="{ 'sort-icon--active': skuSort.key === 'billing' }"
                    />
                  </th>
                  <th
                    class="sortable text-end"
                    @click="toggleSort(skuSort, 'price')"
                  >
                    <VIcon
                      :icon="sortIconFor(skuSort, 'price')"
                      size="14"
                      class="me-1 sort-icon"
                      :class="{ 'sort-icon--active': skuSort.key === 'price' }"
                    />
                    Price
                  </th>
                  <th class="text-end col-actions" />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="sku in skusForSelectedSpu"
                  :key="sku.id"
                  :class="{ 'bg-primary-lighten-5': sku.id === rosterSkuId }"
                  style="cursor: pointer;"
                  @click="selectClass(sku.id)"
                >
                  <td>{{ sku.code }}</td>
                  <td>
                    <div class="catalog-cell">
                      <span class="catalog-cell__primary">
                        {{ sku.name_zh }}
                      </span>
                      <VChip
                        v-if="sku.id === rosterSkuId"
                        size="x-small"
                        color="primary"
                        variant="tonal"
                      >
                        roster
                      </VChip>
                      <VChip
                        v-if="!sku.is_active"
                        size="x-small"
                        color="grey"
                      >
                        inactive
                      </VChip>
                    </div>
                    <div class="catalog-cell__secondary">
                      {{ [sku.level, meetingDaysLabel(sku.meeting_weekdays)].filter(v => v && v !== '—').join(' · ') || '—' }}
                    </div>
                  </td>
                  <td>
                    <div
                      class="catalog-cell__primary"
                      :title="sku.schedule_note || undefined"
                    >
                      {{ sku.schedule_note ?? '—' }}
                    </div>
                    <div
                      v-if="sku.location_id || staffName(sku.staff_id)"
                      class="catalog-cell__secondary"
                      :title="[sku.location_id ? locationName(sku.location_id) : '', staffName(sku.staff_id)].filter(Boolean).join(' · ')"
                    >
                      {{ [sku.location_id ? locationName(sku.location_id) : '', staffName(sku.staff_id)].filter(Boolean).join(' · ') }}
                    </div>
                  </td>
                  <td>{{ billingUnitLabel(sku.billing_unit ?? 'monthly') }}</td>
                  <td class="text-end">
                    {{ sku.price != null ? sku.price : '—' }}
                  </td>
                  <td class="text-end col-actions">
                    <VBtn
                      icon
                      size="x-small"
                      variant="text"
                      @click.stop="openEditSku(sku)"
                    >
                      <VIcon
                        icon="ri-edit-line"
                        size="16"
                      />
                    </VBtn>
                    <VBtn
                      icon
                      size="x-small"
                      variant="text"
                      color="error"
                      @click.stop="removeSku(sku)"
                    >
                      <VIcon
                        icon="ri-delete-bin-line"
                        size="16"
                      />
                    </VBtn>
                  </td>
                </tr>
                <tr v-if="selectedSpuId && skusForSelectedSpu.length === 0">
                  <td
                    colspan="6"
                    class="text-center text-medium-emphasis py-6"
                  >
                    No class offerings yet for this course.
                  </td>
                </tr>
                <tr v-if="!selectedSpuId">
                  <td
                    colspan="9"
                    class="text-center text-medium-emphasis py-6"
                  >
                    Select a course on the left to see its class offerings.
                  </td>
                </tr>
              </tbody>
            </VTable>
            </div>
          </VCard>
        </VCol>
      </VRow>

      <!-- Class roster -->
      <VRow class="mt-4">
        <VCol cols="12">
          <div
            ref="rosterSection"
            class="roster-anchor"
          >
          <VCard class="roster-board">
            <div class="roster-identity">
              <div class="roster-identity__main">
                <div class="text-caption text-medium-emphasis text-uppercase roster-kicker">
                  Class roster · 班次名冊
                </div>
                <div
                  v-if="rosterSku"
                  class="roster-identity__title"
                >
                  <span class="roster-code">{{ rosterSku.code }}</span>
                  <span>{{ rosterSku.name_zh }}</span>
                </div>
                <div
                  v-else
                  class="text-h6"
                >
                  Pick a class to open its roll
                </div>
                <div
                  v-if="rosterMetaLine"
                  class="roster-identity__meta"
                >
                  {{ rosterMetaLine }}
                </div>
              </div>
              <div class="roster-identity__aside">
                <VAutocomplete
                  v-model="rosterSkuId"
                  :items="classOptions"
                  item-title="title"
                  item-value="id"
                  label="Jump to class"
                  placeholder="Code or name"
                  prepend-inner-icon="ri-search-line"
                  density="compact"
                  hide-details
                  clearable
                  :disabled="classOptions.length === 0"
                  class="roster-class-switcher"
                >
                  <template #item="{ props: itemProps, item }">
                    <VListItem
                      v-bind="itemProps"
                      :title="`${item.raw.code} · ${item.raw.name_zh}`"
                      :subtitle="`${spuName(item.raw.spu_id)} · ${billingUnitLabel(item.raw.billing_unit ?? 'monthly')}`"
                    >
                      <template
                        v-if="!item.raw.is_active"
                        #append
                      >
                        <VChip
                          size="x-small"
                          color="grey"
                        >
                          inactive
                        </VChip>
                      </template>
                    </VListItem>
                  </template>
                  <template #selection="{ item }">
                    <span class="roster-class-switcher__selection">{{ item.raw.code }} · {{ item.raw.name_zh }}</span>
                  </template>
                </VAutocomplete>
                <div
                  v-if="rosterSku"
                  class="roster-capacity"
                >
                  <div class="d-flex align-center justify-space-between">
                    <span class="text-subtitle-2">
                      {{ activeRosterCount }}{{ rosterSku.capacity != null ? ` / ${rosterSku.capacity}` : '' }} in class
                    </span>
                    <VChip
                      v-if="rosterAtCapacity"
                      size="x-small"
                      color="warning"
                      variant="tonal"
                    >
                      Full
                    </VChip>
                    <VChip
                      v-else-if="!rosterSku.is_active"
                      size="x-small"
                      color="warning"
                      variant="tonal"
                    >
                      Inactive
                    </VChip>
                  </div>
                  <VProgressLinear
                    v-if="rosterSku.capacity != null"
                    :model-value="rosterCapacityPercent"
                    :color="rosterAtCapacity ? 'warning' : 'primary'"
                    height="6"
                    rounded
                    class="mt-1"
                  />
                </div>
              </div>
            </div>

            <VDivider />

            <VSheet
              v-if="rosterSku"
              class="enroll-sheet pa-4 mx-4 mt-4"
              rounded="lg"
              border
            >
              <div class="d-flex align-baseline flex-wrap ga-2 mb-3">
                <span class="text-subtitle-2">Enroll a student</span>
                <span class="text-caption text-medium-emphasis">
                  Billing days are inclusive — leave dates blank for already-started / ongoing.
                </span>
              </div>
              <VRow dense>
                <VCol
                  cols="12"
                  md="6"
                >
                  <VAutocomplete
                    v-model="selectedStudentId"
                    v-model:search="studentSearch"
                    :items="studentOptions"
                    :loading="studentSearchLoading"
                    item-title="full_name"
                    item-value="id"
                    label="Student"
                    placeholder="Search name or code"
                    prepend-inner-icon="ri-search-line"
                    density="comfortable"
                    hide-details
                    clearable
                    no-filter
                    :disabled="!rosterSkuId"
                  >
                    <template #item="{ props: itemProps, item }">
                      <VListItem
                        v-bind="itemProps"
                        :subtitle="item.raw.code"
                      >
                        <template
                          v-if="activeRosterUnitIds.has(item.raw.id)"
                          #append
                        >
                          <VChip
                            size="x-small"
                            variant="tonal"
                            color="success"
                          >
                            in roster
                          </VChip>
                        </template>
                      </VListItem>
                    </template>
                  </VAutocomplete>
                </VCol>
                <VCol
                  cols="6"
                  md="3"
                >
                  <VTextField
                    v-model="enrollStartDate"
                    label="Start date"
                    type="date"
                    density="comfortable"
                    hide-details
                    :disabled="!rosterSkuId"
                    clearable
                  />
                </VCol>
                <VCol
                  cols="6"
                  md="3"
                >
                  <VTextField
                    v-model="enrollEndDate"
                    label="End date"
                    type="date"
                    density="comfortable"
                    hide-details
                    :disabled="!rosterSkuId"
                    clearable
                  />
                </VCol>
                <VCol
                  v-if="enrollNeedsPurchasedQuantity()"
                  cols="6"
                  md="3"
                >
                  <VTextField
                    v-model.number="enrollPurchasedQuantity"
                    label="Sessions bought"
                    type="number"
                    min="1"
                    density="comfortable"
                    :hint="enrollPurchasedQuantity ? `${enrollPurchasedQuantity} session${enrollPurchasedQuantity === 1 ? '' : 's'}` : 'One-time purchase, billed once'"
                    persistent-hint
                    :disabled="!rosterSkuId"
                  />
                </VCol>
                <VCol
                  v-if="rosterSku?.billing_unit !== 'per_session'"
                  cols="6"
                  md="3"
                >
                  <VTextField
                    v-model.number="enrollUnitPrice"
                    label="Price / month"
                    type="number"
                    min="0"
                    step="0.01"
                    prefix="HK$"
                    density="comfortable"
                    :hint="enrollPriceHint"
                    persistent-hint
                    :disabled="!rosterSkuId"
                  />
                </VCol>
                <VCol
                  cols="12"
                  md="3"
                  class="d-flex align-start"
                >
                  <VBtn
                    color="primary"
                    block
                    height="48"
                    :loading="enrolling"
                    :disabled="Boolean(enrollDisabledReason)"
                    :title="enrollDisabledReason || undefined"
                    @click="enrollStudent"
                  >
                    Enroll
                  </VBtn>
                </VCol>
              </VRow>
              <div
                v-if="enrollBillPreview"
                class="text-caption text-medium-emphasis mt-2 d-flex align-center"
              >
                <VIcon
                  icon="ri-bill-line"
                  size="14"
                  class="me-1"
                />
                {{ enrollBillPreview }}
              </div>
              <div
                v-if="enrollDisabledReason && selectedStudentId"
                class="text-caption text-medium-emphasis mt-1"
              >
                {{ enrollDisabledReason }}
              </div>
            </VSheet>

            <div class="roster-toolbar">
              <VChipGroup
                v-model="rosterStatusFilter"
                mandatory
                selected-class="text-primary"
              >
                <VChip
                  v-for="chip in rosterStatusFilters"
                  :key="chip.value"
                  :value="chip.value"
                  size="small"
                  variant="outlined"
                  filter
                  class="text-no-wrap"
                >
                  {{ chip.title }} ({{ chip.count }})
                </VChip>
              </VChipGroup>
              <VTextField
                v-model="rosterSearch"
                label="Find student"
                placeholder="Name or code"
                prepend-inner-icon="ri-search-line"
                density="compact"
                hide-details
                clearable
                autocomplete="off"
                spellcheck="false"
                :disabled="!rosterSkuId"
                class="roster-search"
              />
            </div>

            <VAlert
              v-if="enrollError"
              type="error"
              variant="tonal"
              density="compact"
              class="mx-4 mb-3"
              closable
              @click:close="enrollError = ''"
            >
              {{ enrollError }}
            </VAlert>
            <VAlert
              v-if="enrollSuccess"
              type="success"
              variant="tonal"
              density="compact"
              class="mx-4 mb-3"
              closable
              @click:close="enrollSuccess = ''"
            >
              {{ enrollSuccess }}
            </VAlert>

            <div
              v-if="!rosterSkuId"
              class="roster-empty"
            >
              <VIcon
                icon="ri-group-line"
                size="36"
                class="mb-2"
              />
              <div class="text-subtitle-1">
                No class selected
              </div>
              <div class="text-body-2 text-medium-emphasis">
                Click a class above, or search by code in Jump to class.
              </div>
            </div>

            <VProgressLinear
              v-else-if="enrollmentsLoading"
              indeterminate
              color="primary"
              class="my-4"
            />

            <div
              v-else
              class="roster-table-wrap"
            >
              <VTable
                density="comfortable"
                hover
                class="roster-table"
              >
                <thead>
                  <tr>
                    <th
                      class="sortable"
                      @click="toggleSort(rosterSort, 'student')"
                    >
                      Student
                      <VIcon
                        :icon="sortIconFor(rosterSort, 'student')"
                        size="14"
                        class="ms-1 sort-icon"
                        :class="{ 'sort-icon--active': rosterSort.key === 'student' }"
                      />
                    </th>
                    <th
                      class="sortable"
                      @click="toggleSort(rosterSort, 'status')"
                    >
                      Status
                      <VIcon
                        :icon="sortIconFor(rosterSort, 'status')"
                        size="14"
                        class="ms-1 sort-icon"
                        :class="{ 'sort-icon--active': rosterSort.key === 'status' }"
                      />
                    </th>
                    <th
                      v-if="rosterSku?.billing_unit === 'per_session'"
                      class="sortable"
                      @click="toggleSort(rosterSort, 'sessions')"
                    >
                      Sessions
                      <VIcon
                        :icon="sortIconFor(rosterSort, 'sessions')"
                        size="14"
                        class="ms-1 sort-icon"
                        :class="{ 'sort-icon--active': rosterSort.key === 'sessions' }"
                      />
                    </th>
                    <th
                      class="sortable text-end"
                      @click="toggleSort(rosterSort, 'price')"
                    >
                      <VIcon
                        :icon="sortIconFor(rosterSort, 'price')"
                        size="14"
                        class="me-1 sort-icon"
                        :class="{ 'sort-icon--active': rosterSort.key === 'price' }"
                      />
                      Price
                    </th>
                    <th
                      class="sortable"
                      @click="toggleSort(rosterSort, 'window')"
                    >
                      Billing window
                      <VIcon
                        :icon="sortIconFor(rosterSort, 'window')"
                        size="14"
                        class="ms-1 sort-icon"
                        :class="{ 'sort-icon--active': rosterSort.key === 'window' }"
                      />
                    </th>
                    <th class="text-end col-actions">
                      <span class="text-caption text-medium-emphasis">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="e in filteredRosterRows"
                    :key="e.id"
                    :class="{ 'roster-row--left': e.status !== 'active' }"
                  >
                    <td>
                      <div class="roster-student">
                        <span class="roster-student__name">{{ studentLabel(e.unit_id) }}</span>
                        <span class="roster-student__code">{{ studentCode(e.unit_id) }}</span>
                      </div>
                    </td>
                    <td>
                      <VChip
                        size="small"
                        variant="tonal"
                        :color="enrollmentStatusColor[e.status] ?? 'grey'"
                      >
                        {{ enrollmentStatusLabel(e.status) }}
                      </VChip>
                    </td>
                    <td v-if="rosterSku?.billing_unit === 'per_session'">
                      <VTooltip
                        v-if="e.purchases.length > 0"
                        :text="purchaseTooltip(e)"
                        location="top"
                      >
                        <template #activator="{ props: tooltipProps }">
                          <span v-bind="tooltipProps">
                            {{ purchaseSummary(e).total }} session{{ purchaseSummary(e).total === 1 ? '' : 's' }}
                            <VChip
                              v-if="purchaseSummary(e).unbilledQty > 0"
                              size="x-small"
                              color="warning"
                              variant="tonal"
                              class="ms-1"
                            >
                              {{ purchaseSummary(e).unbilledQty }} unbilled
                            </VChip>
                          </span>
                        </template>
                      </VTooltip>
                      <template v-else>
                        —
                      </template>
                    </td>
                    <td class="text-end">
                      <template v-if="enrollmentPriceParts(e)">
                        <div>{{ enrollmentPriceParts(e)?.amount }}</div>
                        <div class="text-caption text-medium-emphasis">
                          {{ enrollmentPriceParts(e)?.hint }}
                        </div>
                      </template>
                      <template v-else>
                        —
                      </template>
                    </td>
                    <td>
                      <div>{{ billingWindowLabel(e) }}</div>
                      <div class="text-caption text-medium-emphasis">
                        Added {{ formatRosterDate(e.enrolled_at) }}
                      </div>
                    </td>
                    <td class="text-end text-no-wrap col-actions">
                      <VBtn
                        size="small"
                        variant="text"
                        @click="beginEditEnrollmentDates(e)"
                      >
                        Edit
                      </VBtn>
                      <VBtn
                        icon
                        size="small"
                        variant="text"
                        aria-label="More actions"
                      >
                        <VIcon
                          icon="ri-more-2-line"
                          size="18"
                        />
                        <VMenu activator="parent">
                          <VList density="compact">
                            <VListItem
                              v-if="e.status === 'active'"
                              prepend-icon="ri-user-unfollow-line"
                              title="Unenroll"
                              @click="cancelEnrollment(e)"
                            />
                            <VListItem
                              v-else
                              prepend-icon="ri-user-follow-line"
                              title="Re-activate"
                              @click="reactivateEnrollment(e)"
                            />
                            <VListItem
                              v-if="topUpEnabled && rosterSku?.billing_unit === 'per_session' && e.status === 'active'"
                              prepend-icon="ri-add-circle-line"
                              title="Top up sessions"
                              @click="openTopUp(e)"
                            />
                            <VListItem
                              prepend-icon="ri-delete-bin-line"
                              title="Remove record"
                              class="text-error"
                              @click="removeEnrollment(e)"
                            />
                          </VList>
                        </VMenu>
                      </VBtn>
                    </td>
                  </tr>
                  <tr v-if="filteredRosterRows.length === 0">
                    <td
                      :colspan="rosterSku?.billing_unit === 'per_session' ? 6 : 5"
                      class="text-center py-10"
                    >
                      <template v-if="enrollments.length === 0">
                        <VIcon
                          icon="ri-user-add-line"
                          size="32"
                          class="mb-2"
                        />
                        <div class="text-subtitle-1">
                          Nobody on this roll yet
                        </div>
                        <div class="text-body-2 text-medium-emphasis">
                          Enroll the first student with the form above.
                        </div>
                      </template>
                      <template v-else-if="rosterSearch.trim()">
                        <div class="text-body-2 text-medium-emphasis">
                          No student matches “{{ rosterSearch.trim() }}”.
                        </div>
                      </template>
                      <template v-else-if="rosterStatusFilter === 'active' && rosterStatusCounts.ended > 0">
                        <div class="text-body-2 text-medium-emphasis mb-3">
                          No one currently in this class.
                        </div>
                        <VBtn
                          variant="tonal"
                          size="small"
                          @click="rosterStatusFilter = 'ended'"
                        >
                          Show {{ rosterStatusCounts.ended }} who left
                        </VBtn>
                      </template>
                      <template v-else>
                        <div class="text-body-2 text-medium-emphasis">
                          No students in this filter.
                        </div>
                      </template>
                    </td>
                  </tr>
                </tbody>
              </VTable>
            </div>
          </VCard>
          </div>
        </VCol>
      </VRow>
    </template>

    <VDialog
      v-model="editDialogOpen"
      max-width="480"
    >
      <VCard v-if="editingEnrollment && enrollmentDates[editingEnrollment.id]">
        <VCardTitle>Edit {{ studentLabel(editingEnrollment.unit_id) }}</VCardTitle>
        <VCardSubtitle>
          {{ studentCode(editingEnrollment.unit_id) }}
          · {{ enrollmentStatusLabel(editingEnrollment.status) }}
        </VCardSubtitle>
        <VCardText>
          <VRow dense>
            <VCol cols="12">
              <VTextField
                v-model="enrollmentDates[editingEnrollment.id].price"
                label="Price"
                type="number"
                min="0"
                step="0.01"
                prefix="HK$"
                density="comfortable"
                :hint="rosterSku ? `Blank uses the class price (${rosterPriceLabel(rosterSku)}).` : 'Blank uses the class price.'"
                persistent-hint
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
            >
              <VTextField
                v-model="enrollmentDates[editingEnrollment.id].start"
                label="Start date"
                hint="First billed day. Blank = already started."
                persistent-hint
                type="date"
                density="comfortable"
                clearable
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
            >
              <VTextField
                v-model="enrollmentDates[editingEnrollment.id].end"
                label="End date"
                hint="Last billed day. Blank = ongoing."
                persistent-hint
                type="date"
                density="comfortable"
                clearable
              />
            </VCol>
          </VRow>
          <VAlert
            v-if="enrollError"
            type="error"
            variant="tonal"
            density="compact"
            class="mt-3"
            closable
            @click:close="enrollError = ''"
          >
            {{ enrollError }}
          </VAlert>
        </VCardText>
        <VDivider />
        <DialogFooter>
          <VBtn
            variant="outlined"
            color="primary"
            @click="editDialogOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :loading="enrollmentDateSavingId === editingEnrollment.id"
            @click="saveEnrollmentDates(editingEnrollment)"
          >
            Save
          </VBtn>
        </DialogFooter>
      </VCard>
    </VDialog>

    <!-- SPU create/edit dialog -->
    <VDialog
      v-model="spuDialogOpen"
      max-width="520"
    >
      <VCard :title="editingSpu ? 'Edit course' : 'Add course'">
        <VCardText>
          <VAlert
            v-if="spuSaveError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            {{ spuSaveError }}
          </VAlert>
          <p class="text-body-2 text-medium-emphasis mb-4">
            A course is the subject family (SPU). Class offerings (SKU) sit underneath it.
          </p>
          <VRow>
            <VCol cols="6">
              <VTextField
                v-model="spuForm.code"
                label="Code"
                placeholder="MATH"
                hint="Short unique id. Required."
                persistent-hint
                density="comfortable"
              />
            </VCol>
            <VCol cols="6">
              <VTextField
                v-model="spuForm.subject"
                label="Subject"
                placeholder="math"
                hint="Optional grouping label."
                persistent-hint
                density="comfortable"
              />
            </VCol>
            <VCol cols="12">
              <VTextField
                v-model="spuForm.name_zh"
                label="Chinese name"
                placeholder="小學數學"
                hint="Shown on the roster and invoices. Required."
                persistent-hint
                density="comfortable"
              />
            </VCol>
            <VCol cols="12">
              <VTextField
                v-model="spuForm.name_en"
                label="English name"
                placeholder="Primary Math"
                hint="Optional."
                persistent-hint
                density="comfortable"
              />
            </VCol>
            <VCol cols="12">
              <VTextarea
                v-model="spuForm.description"
                label="Description"
                hint="Optional notes for staff. Not used for billing."
                persistent-hint
                density="comfortable"
                rows="2"
              />
            </VCol>
            <VCol cols="12">
              <VSwitch
                v-model="spuForm.is_active"
                label="Active course"
                hint="Inactive courses stay in the list but you should not add new classes under them."
                persistent-hint
                density="comfortable"
                color="primary"
              />
            </VCol>
          </VRow>
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="spuDialogOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :loading="spuSaving"
            :disabled="!spuCanSave"
            @click="saveSpu"
          >
            Save
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <!-- SKU create/edit dialog -->
    <VDialog
      v-model="skuDialogOpen"
      max-width="640"
      scrollable
    >
      <VCard :title="editingSku ? 'Edit class' : 'Add class'">
        <VCardText>
          <VAlert
            v-if="skuSaveError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            {{ skuSaveError }}
          </VAlert>
          <VAlert
            type="info"
            variant="tonal"
            density="compact"
            class="mb-4"
          >
            {{ skuBillingPreview }}
          </VAlert>

          <div class="text-subtitle-2 mb-2">
            Identity
          </div>
          <VRow>
            <VCol cols="6">
              <VTextField
                v-model="skuForm.code"
                label="Class code"
                placeholder="MATH-P3-TUE"
                hint="Unique. Required."
                persistent-hint
                density="comfortable"
              />
            </VCol>
            <VCol cols="6">
              <VTextField
                v-model="skuForm.level"
                label="Level"
                placeholder="P3"
                hint="Optional, e.g. P3 / F5 / A1."
                persistent-hint
                density="comfortable"
              />
            </VCol>
            <VCol cols="12">
              <VTextField
                v-model="skuForm.name_zh"
                label="Chinese name"
                placeholder="小學數學 P3 週二班"
                hint="Shown on invoices. Required."
                persistent-hint
                density="comfortable"
              />
            </VCol>
            <VCol cols="12">
              <VTextField
                v-model="skuForm.name_en"
                label="English name"
                hint="Optional."
                persistent-hint
                density="comfortable"
              />
            </VCol>
          </VRow>

          <div class="text-subtitle-2 mt-4 mb-2">
            When and where
          </div>
          <VRow>
            <VCol cols="12">
              <VTextField
                v-model="skuForm.schedule_note"
                label="Time note"
                placeholder="Tue 18:00–19:30"
                hint="For staff display only. Not used for billing."
                persistent-hint
                density="comfortable"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
            >
              <VSelect
                v-model="skuForm.location_id"
                :items="locationOptions"
                item-title="title"
                item-value="id"
                label="Campus"
                hint="Display only. Invoices filter by each student's registered campus, not this."
                persistent-hint
                density="comfortable"
                clearable
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
            >
              <VAutocomplete
                v-model="skuForm.staff_id"
                :items="staffOptions"
                label="Teacher / staff"
                hint="Optional. The staff member who teaches this class."
                persistent-hint
                density="comfortable"
                clearable
              />
            </VCol>
            <VCol
              cols="12"
              sm="4"
            >
              <VTextField
                v-model.number="skuForm.capacity"
                label="Capacity"
                type="number"
                min="0"
                hint="Roster size only. Not billed."
                persistent-hint
                density="comfortable"
              />
            </VCol>
            <VCol
              cols="12"
              sm="8"
            >
              <div class="text-body-2 mb-1">
                Class days
              </div>
              <div class="text-caption text-medium-emphasis mb-2">
                Optional. Shown on the roster for reference only; not used to calculate the bill.
              </div>
              <VChipGroup
                v-model="skuForm.meeting_weekdays"
                multiple
                selected-class="text-primary"
              >
                <VChip
                  v-for="day in weekdayOptions"
                  :key="day.value"
                  :value="day.value"
                  filter
                  variant="outlined"
                  size="small"
                >
                  {{ day.title }}
                </VChip>
              </VChipGroup>
            </VCol>
          </VRow>

          <div class="text-subtitle-2 mt-4 mb-2">
            Billing
          </div>
          <VRow>
            <VCol cols="6">
              <VSelect
                v-model="skuForm.billing_unit"
                :items="billingUnitOptions"
                item-title="title"
                item-value="value"
                label="How this class is charged"
                hint="One method per class."
                persistent-hint
                density="comfortable"
              />
            </VCol>
            <VCol cols="6">
              <VTextField
                v-model.number="skuForm.price"
                :label="skuForm.billing_unit === 'per_session' ? 'Price per session' : 'Monthly price'"
                type="number"
                min="0"
                step="0.01"
                prefix="HK$"
                hint="Leave empty to skip this class at Generate — or for variable-rate classes like 私補, leave empty and set a per-student price on each enrollment."
                persistent-hint
                density="comfortable"
              />
            </VCol>
            <VCol cols="12">
              <VSwitch
                v-model="skuForm.is_active"
                label="Active class"
                hint="Off: hidden from new enrollments and skipped at Generate. Issued/paid bills stay."
                persistent-hint
                density="comfortable"
                color="primary"
              />
            </VCol>
          </VRow>
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="skuDialogOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :loading="skuSaving"
            :disabled="!skuCanSave"
            @click="saveSku"
          >
            Save
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <AttendanceConfirmDialog
      v-model="deleteConfirmOpen"
      :title="deleteTarget?.title || 'Confirm delete'"
      :loading="deleteConfirmLoading"
      :error="deleteConfirmError"
      @confirm="confirmCourseDelete"
      @cancel="closeDeleteConfirm"
      @clear-error="deleteConfirmError = ''"
    >
      {{ deleteTarget?.detail }}
    </AttendanceConfirmDialog>

    <VDialog
      v-if="topUpEnabled"
      v-model="topUpOpen"
      max-width="420"
      persistent
    >
      <VCard>
        <VCardTitle>Top up sessions</VCardTitle>
        <VCardText>
          <VRow>
            <VCol cols="12">
              <VNumberInput
                v-model="topUpQuantity"
                label="Sessions purchased"
                :min="1"
                density="compact"
                hide-details
              />
            </VCol>
            <VCol cols="12">
              <VNumberInput
                v-model="topUpPrice"
                label="Price per session"
                :min="0"
                density="compact"
                hide-details
              />
            </VCol>
            <VCol cols="12">
              <VTextField
                v-model="topUpDate"
                label="Purchase date"
                type="date"
                density="compact"
                hide-details
              />
            </VCol>
            <VCol cols="12">
              <VTextField
                v-model="topUpNote"
                label="Note (optional)"
                density="compact"
                hide-details
              />
            </VCol>
          </VRow>
          <VAlert
            v-if="enrollError"
            type="error"
            variant="tonal"
            class="mt-4"
            density="compact"
          >
            {{ enrollError }}
          </VAlert>
        </VCardText>
        <VCardActions class="justify-end">
          <VBtn
            variant="text"
            @click="topUpOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :loading="topUpSaving"
            :disabled="topUpQuantity == null || topUpQuantity < 1 || topUpPrice == null || topUpPrice < 0"
            @click="saveTopUp"
          >
            Add top-up
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>

<style scoped>
.catalog-row {
  align-items: stretch;
}

.catalog-row > .v-col {
  display: flex;
}

.catalog-card {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 20rem;
  overflow: hidden;
}

.catalog-card :deep(.v-card-item) {
  flex: 0 0 auto;
}

.catalog-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
}

.catalog-scroll :deep(.v-table) {
  width: 100%;
}

.catalog-scroll :deep(table) {
  width: 100%;
  table-layout: fixed;
  border-collapse: separate;
  border-spacing: 0;
}

.catalog-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.catalog-cell > .catalog-cell__primary {
  flex: 1 1 auto;
  min-width: 0;
}

.catalog-scroll :deep(thead th) {
  position: sticky;
  top: 0;
  z-index: 3;
  background: rgb(var(--v-theme-surface));
  box-shadow: inset 0 -1px 0 rgba(var(--v-border-color), var(--v-border-opacity));
}

.catalog-scroll :deep(thead .col-actions) {
  z-index: 4;
}

.catalog-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.catalog-cell__primary,
.catalog-cell__secondary {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.catalog-cell__secondary {
  color: rgba(var(--v-theme-on-surface), 0.55);
  font-size: 0.75rem;
  line-height: 1.2;
}

:deep(tr.bg-primary-lighten-5) td {
  background: rgba(var(--v-theme-primary), 0.08);
}

.offerings-table :deep(.col-actions),
.roster-table :deep(.col-actions) {
  position: sticky;
  inset-inline-end: 0;
  z-index: 1;
  white-space: nowrap;
  width: 1%;
  background: rgb(var(--v-theme-surface));
  border-inline-start: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.offerings-table :deep(tr.bg-primary-lighten-5 td.col-actions),
.roster-table :deep(tr.bg-primary-lighten-5 td.col-actions) {
  background:
    linear-gradient(rgba(var(--v-theme-primary), 0.08), rgba(var(--v-theme-primary), 0.08)),
    rgb(var(--v-theme-surface));
}

.roster-anchor {
  scroll-margin-top: 12px;
}

.roster-board {
  overflow: hidden;
}

.enroll-sheet {
  background: rgba(var(--v-theme-primary), 0.04);
}

.roster-identity {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 24px;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 24px 16px;
  background:
    linear-gradient(
      90deg,
      rgba(var(--v-theme-primary), 0.14) 0,
      rgba(var(--v-theme-primary), 0.14) 5px,
      rgba(var(--v-theme-primary), 0.045) 5px
    );
}

.roster-kicker {
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}

.roster-identity__title {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 12px;
  font-size: 1.35rem;
  font-weight: 600;
  line-height: 1.3;
}

.roster-code {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.03em;
  color: rgb(var(--v-theme-primary));
}

.roster-identity__meta {
  margin-top: 8px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.8125rem;
  line-height: 1.45;
}

.roster-identity__main {
  flex: 1 1 16rem;
  min-width: 0;
}

.roster-identity__aside {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1 1 28rem;
  max-width: 36rem;
  min-width: min(100%, 20rem);
}

.roster-class-switcher {
  width: 100%;
}

.roster-class-switcher :deep(.v-field__input) {
  flex-wrap: nowrap;
  overflow: hidden;
}

.roster-class-switcher__selection {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.roster-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  align-items: center;
  padding: 12px 24px 16px;
}

.roster-search {
  width: 220px;
  max-width: 100%;
}

.roster-empty {
  text-align: center;
  padding: 48px 16px;
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.roster-table-wrap {
  overflow-x: auto;
}

.roster-student {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.roster-student__name {
  font-weight: 600;
}

.roster-student__code {
  font-size: 0.75rem;
  color: rgba(var(--v-theme-on-surface), 0.55);
  font-variant-numeric: tabular-nums;
}

.roster-row--left td {
  opacity: 0.58;
}

th.sortable {
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}

th.sortable:hover {
  color: rgb(var(--v-theme-primary));
}

.sort-icon {
  opacity: 0.3;
}

.sort-icon--active {
  opacity: 1;
  color: rgb(var(--v-theme-primary));
}

@media (max-width: 600px) {
  .roster-identity,
  .roster-toolbar {
    padding-inline: 16px;
  }

  .roster-identity__aside,
  .roster-class-switcher,
  .roster-search {
    width: 100%;
    max-width: none;
    min-width: 0;
  }
}
</style>
