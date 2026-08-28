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

const selectedSpuId = ref<string | null>(null)
const selectedSpu = computed(() => spus.value.find(s => s.id === selectedSpuId.value) ?? null)
const skusForSelectedSpu = computed(() => skus.value.filter(k => k.spu_id === selectedSpuId.value))

const locationName = (id: string | null) => locations.value.find(l => l.id === id)?.name_en ?? '—'

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
    const [spuList, skuList, locationList] = await Promise.all([
      listCourseSpus(),
      listCourseSkus(),
      listLocations({ is_active: true }),
    ])

    spus.value = spuList
    skus.value = skuList
    locations.value = locationList
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
  capacity: null as number | null,
  price: null as number | null,
  billing_unit: 'monthly' as BillingUnit,
  meeting_weekdays: [] as Weekday[],
  is_active: true,
})

const skuCanSave = computed(() => {
  if (!skuForm.code.trim() || !skuForm.name_zh.trim())
    return false
  if (skuForm.billing_unit === 'per_session' && skuForm.meeting_weekdays.length === 0)
    return false

  return true
})

const skuBillingPreview = computed(() => {
  const raw = skuForm.price
  const hasPrice = raw != null && !Number.isNaN(Number(raw))
  const priceText = hasPrice ? `HK$${Number(raw).toFixed(2)}` : 'no price (Generate skips this class)'
  if (skuForm.billing_unit === 'per_session') {
    if (!skuForm.meeting_weekdays.length)
      return `Select at least one class day. Save stays disabled until then.`
    const location = locations.value.find(item => item.id === skuForm.location_id)
    const where = location ? `scans at ${location.name_en}` : 'scans at any campus'

    return `Bills ${priceText} × days on campus (${meetingDaysLabel(skuForm.meeting_weekdays)} ∩ ${where}). No scan that month = no invoice line.`
  }

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
const enrollStartDate = ref('')
const enrollEndDate = ref('')
const enrolling = ref(false)
const enrollError = ref('')

const enrollments = ref<CourseEnrollment[]>([])
const enrollmentsLoading = ref(false)
const enrollmentDates = ref<Record<string, { start: string; end: string }>>({})
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
  }
}

function cancelEditEnrollmentDates(enrollment: CourseEnrollment) {
  enrollmentDates.value[enrollment.id] = {
    start: enrollment.start_date ?? '',
    end: enrollment.end_date ?? '',
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

function emptyToNull(value: string): string | null {
  const trimmed = value.trim()

  return trimmed || null
}

function syncEnrollmentDates(items: CourseEnrollment[]) {
  enrollmentDates.value = Object.fromEntries(
    items.map(e => [e.id, { start: e.start_date ?? '', end: e.end_date ?? '' }]),
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
      studentOptions.value = students.filter(u => u.status === 'active')
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

async function enrollStudent() {
  if (!selectedStudentId.value || !rosterSkuId.value || rosterSku.value?.is_active === false || rosterAtCapacity.value)
    return

  const startDate = emptyToNull(enrollStartDate.value)
  const endDate = emptyToNull(enrollEndDate.value)
  if (startDate && endDate && endDate < startDate) {
    enrollError.value = 'Last billed day must be on or after first billed day.'

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
    })

    enrollments.value = [created, ...enrollments.value]
    enrollmentDates.value = {
      [created.id]: { start: created.start_date ?? '', end: created.end_date ?? '' },
      ...enrollmentDates.value,
    }

    const picked = studentOptions.value.find(u => u.id === selectedStudentId.value)
    if (picked)
      cacheStudents([picked])

    selectedStudentId.value = null
    studentSearch.value = ''
    enrollStartDate.value = ''
    enrollEndDate.value = ''
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

  enrollmentDateSavingId.value = enrollment.id
  enrollError.value = ''
  try {
    const updated = await updateCourseEnrollment(enrollment.id, {
      start_date: startDate,
      end_date: endDate,
    })

    const idx = enrollments.value.findIndex(e => e.id === enrollment.id)

    if (idx !== -1)
      enrollments.value[idx] = updated

    enrollmentDates.value[enrollment.id] = {
      start: updated.start_date ?? '',
      end: updated.end_date ?? '',
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

async function cancelEnrollment(enrollment: CourseEnrollment) {
  try {
    const updated = await updateCourseEnrollment(enrollment.id, { status: 'cancelled' })
    const idx = enrollments.value.findIndex(e => e.id === enrollment.id)
    if (idx !== -1)
      enrollments.value[idx] = updated
  }
  catch (e) {
    enrollError.value = formatApiError(e, 'Could not update enrollment.')
  }
}

function removeEnrollment(enrollment: CourseEnrollment) {
  openDeleteConfirm({
    kind: 'enrollment',
    title: 'Remove enrollment?',
    detail: 'Remove this enrollment record?',
    run: async () => {
      await deleteCourseEnrollment(enrollment.id)
      enrollments.value = enrollments.value.filter(e => e.id !== enrollment.id)
    },
  })
}

const enrollmentStatusColor: Record<string, string> = {
  active: 'success',
  completed: 'info',
  cancelled: 'grey',
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
          Pick a class to see its roster. Billing is on the SKU (月費 or 堂費).
          Same student cannot re-enroll the same class code later without deleting the old row.
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
      <VRow>
        <!-- Courses (SPU) -->
        <VCol
          cols="12"
          md="5"
        >
          <VCard title="Courses">
            <VTable
              density="compact"
              hover
            >
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Subject</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="spu in spus"
                  :key="spu.id"
                  :class="{ 'bg-primary-lighten-5': spu.id === selectedSpuId }"
                  style="cursor: pointer;"
                  @click="selectedSpuId = spu.id"
                >
                  <td>{{ spu.code }}</td>
                  <td>
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
          </VCard>
        </VCol>

        <!-- Class offerings (SKU) for selected SPU -->
        <VCol
          cols="12"
          md="7"
        >
          <VCard>
            <VCardItem>
              <VCardTitle>
                Class Offerings
                <span
                  v-if="selectedSpu"
                  class="text-body-2 text-medium-emphasis"
                >— {{ selectedSpu.name_zh }}</span>
              </VCardTitle>
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
            <VTable
              density="compact"
              hover
            >
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Level</th>
                  <th>Schedule</th>
                  <th>Location</th>
                  <th>Billing</th>
                  <th>Days</th>
                  <th class="text-end">
                    Price
                  </th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="sku in skusForSelectedSpu"
                  :key="sku.id"
                  :class="{ 'bg-primary-lighten-5': sku.id === rosterSkuId }"
                  style="cursor: pointer;"
                  @click="rosterSkuId = sku.id"
                >
                  <td>{{ sku.code }}</td>
                  <td>
                    {{ sku.name_zh }}
                    <VChip
                      v-if="!sku.is_active"
                      size="x-small"
                      color="grey"
                      class="ms-1"
                    >
                      inactive
                    </VChip>
                  </td>
                  <td>{{ sku.level ?? '—' }}</td>
                  <td>{{ sku.schedule_note ?? '—' }}</td>
                  <td>{{ locationName(sku.location_id) }}</td>
                  <td>{{ billingUnitLabel(sku.billing_unit ?? 'monthly') }}</td>
                  <td>{{ meetingDaysLabel(sku.meeting_weekdays) }}</td>
                  <td class="text-end">
                    {{ sku.price != null ? sku.price : '—' }}
                  </td>
                  <td class="text-end">
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
                    colspan="9"
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
          </VCard>
        </VCol>
      </VRow>

      <!-- Class roster -->
      <VRow class="mt-4">
        <VCol cols="12">
          <VCard>
            <VCardItem>
              <VCardTitle>
                Class roster
                <span class="text-body-2 text-medium-emphasis ms-1">班次名冊</span>
              </VCardTitle>
              <VCardSubtitle>
                <template v-if="rosterSku">
                  {{ rosterSku.code }} · {{ rosterSku.name_zh }}
                  <span v-if="rosterSku.schedule_note"> · {{ rosterSku.schedule_note }}</span>
                </template>
                <template v-else>
                  Click a class above, or pick one here.
                </template>
              </VCardSubtitle>
              <template #append>
                <div
                  v-if="rosterSku"
                  class="d-flex flex-wrap align-center ga-2 justify-end"
                >
                  <VChip
                    size="small"
                    variant="tonal"
                    color="primary"
                  >
                    {{ billingUnitLabel(rosterSku.billing_unit ?? 'monthly') }}
                    · {{ rosterPriceLabel(rosterSku) }}
                  </VChip>
                  <VChip
                    v-if="rosterSku.meeting_weekdays?.length"
                    size="small"
                    variant="tonal"
                  >
                    {{ meetingDaysLabel(rosterSku.meeting_weekdays) }}
                  </VChip>
                  <VChip
                    size="small"
                    variant="tonal"
                  >
                    {{ activeRosterCount }}{{ rosterSku.capacity != null ? ` / ${rosterSku.capacity}` : '' }} enrolled
                  </VChip>
                  <VChip
                    v-if="rosterAtCapacity"
                    size="small"
                    variant="tonal"
                    color="warning"
                  >
                    Full
                  </VChip>
                  <VChip
                    v-if="!rosterSku.is_active"
                    size="small"
                    variant="tonal"
                    color="warning"
                  >
                    Inactive — Generate skips this class
                  </VChip>
                </div>
              </template>
            </VCardItem>
            <VCardText>
              <div class="text-subtitle-2 mb-1">
                Enroll a student
              </div>
              <div class="text-caption text-medium-emphasis mb-3">
                First / last billed days are inclusive. Leave first blank if already started, last blank if ongoing.
                Generate only bills months that overlap this window.
              </div>
              <VRow>
                <VCol
                  cols="12"
                  md="6"
                >
                  <VSelect
                    v-model="rosterSkuId"
                    :items="skusForSelectedSpu"
                    item-title="name_zh"
                    item-value="id"
                    label="Class"
                    placeholder="Select a class"
                    density="comfortable"
                    hide-details
                    :disabled="skusForSelectedSpu.length === 0"
                  >
                    <template #item="{ props: itemProps, item }">
                      <VListItem
                        v-bind="itemProps"
                        :title="`${item.raw.code} · ${item.raw.name_zh}`"
                        :subtitle="`${billingUnitLabel(item.raw.billing_unit ?? 'monthly')} · ${rosterPriceLabel(item.raw)}`"
                      />
                    </template>
                    <template #selection="{ item }">
                      {{ item.raw.code }} · {{ item.raw.name_zh }}
                    </template>
                  </VSelect>
                </VCol>
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
                      />
                    </template>
                  </VAutocomplete>
                </VCol>
                <VCol
                  cols="12"
                  sm="6"
                  md="4"
                >
                  <VTextField
                    v-model="enrollStartDate"
                    label="First billed day"
                    type="date"
                    density="comfortable"
                    hide-details
                    :disabled="!rosterSkuId"
                    clearable
                  />
                </VCol>
                <VCol
                  cols="12"
                  sm="6"
                  md="4"
                >
                  <VTextField
                    v-model="enrollEndDate"
                    label="Last billed day"
                    type="date"
                    density="comfortable"
                    hide-details
                    :disabled="!rosterSkuId"
                    clearable
                  />
                </VCol>
                <VCol
                  cols="12"
                  md="4"
                  class="d-flex align-center"
                >
                  <VBtn
                    color="primary"
                    block
                    height="48"
                    :loading="enrolling"
                    :disabled="!selectedStudentId || !rosterSkuId || rosterSku?.is_active === false || rosterAtCapacity"
                    @click="enrollStudent"
                  >
                    Enroll
                  </VBtn>
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

              <div
                v-if="!rosterSkuId"
                class="text-center text-medium-emphasis py-8"
              >
                Select a class to see who is enrolled and add students with a start and end date.
              </div>

              <VProgressLinear
                v-else-if="enrollmentsLoading"
                indeterminate
                color="primary"
                class="my-4"
              />

              <VTable
                v-else
                density="compact"
                class="mt-3"
              >
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Status</th>
                    <th>First billed</th>
                    <th>Last billed</th>
                    <th>Added</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="e in enrollments"
                    :key="e.id"
                  >
                    <td>
                      {{ studentLabel(e.unit_id) }}
                      <div class="text-caption text-medium-emphasis">
                        {{ studentCode(e.unit_id) }}
                      </div>
                    </td>
                    <td>
                      <VChip
                        size="x-small"
                        :color="enrollmentStatusColor[e.status] ?? 'grey'"
                      >
                        {{ e.status }}
                      </VChip>
                    </td>
                    <td>
                      <VTextField
                        v-if="rosterEditingId === e.id && enrollmentDates[e.id]"
                        v-model="enrollmentDates[e.id].start"
                        type="date"
                        density="compact"
                        hide-details
                        style="max-width: 160px;"
                      />
                      <span v-else>{{ formatRosterDate(e.start_date, 'Already started') }}</span>
                    </td>
                    <td>
                      <VTextField
                        v-if="rosterEditingId === e.id && enrollmentDates[e.id]"
                        v-model="enrollmentDates[e.id].end"
                        type="date"
                        density="compact"
                        hide-details
                        style="max-width: 160px;"
                      />
                      <span v-else>{{ formatRosterDate(e.end_date, 'Ongoing') }}</span>
                    </td>
                    <td>{{ formatRosterDate(e.enrolled_at) }}</td>
                    <td class="text-end text-no-wrap">
                      <template v-if="rosterEditingId === e.id">
                        <VBtn
                          size="x-small"
                          variant="text"
                          color="primary"
                          :loading="enrollmentDateSavingId === e.id"
                          @click="saveEnrollmentDates(e)"
                        >
                          Save
                        </VBtn>
                        <VBtn
                          size="x-small"
                          variant="text"
                          @click="cancelEditEnrollmentDates(e)"
                        >
                          Cancel
                        </VBtn>
                      </template>
                      <template v-else>
                        <VBtn
                          size="x-small"
                          variant="text"
                          @click="beginEditEnrollmentDates(e)"
                        >
                          Edit dates
                        </VBtn>
                        <VBtn
                          v-if="e.status === 'active'"
                          size="x-small"
                          variant="text"
                          @click="cancelEnrollment(e)"
                        >
                          Unenroll
                        </VBtn>
                        <VBtn
                          icon
                          size="x-small"
                          variant="text"
                          color="error"
                          @click="removeEnrollment(e)"
                        >
                          <VIcon
                            icon="ri-delete-bin-line"
                            size="16"
                          />
                        </VBtn>
                      </template>
                    </td>
                  </tr>
                  <tr v-if="enrollments.length === 0">
                    <td
                      colspan="6"
                      class="text-center text-medium-emphasis py-6"
                    >
                      No students in this class yet. Search a name, set billed days, then Enroll.
                    </td>
                  </tr>
                </tbody>
              </VTable>
            </VCardText>
          </VCard>
        </VCol>
      </VRow>
    </template>

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
                hint="For staff display only. Billing uses class days below, not this text."
                persistent-hint
                density="comfortable"
              />
            </VCol>
            <VCol cols="8">
              <VSelect
                v-model="skuForm.location_id"
                :items="locationOptions"
                item-title="title"
                item-value="id"
                label="Campus"
                hint="堂費 matches scans at this location. Leave empty to count any campus."
                persistent-hint
                density="comfortable"
                clearable
              />
            </VCol>
            <VCol cols="4">
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
            <VCol cols="12">
              <div class="text-body-2 mb-1">
                Class days
              </div>
              <div class="text-caption text-medium-emphasis mb-2">
                {{ skuForm.billing_unit === 'per_session' ? 'Required for 堂費. Generate bills these weekdays ∩ campus scans.' : 'Optional for 月費. Shown on the roster; not used to calculate the bill.' }}
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
                hint="Leave empty to skip this class at Generate."
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
  </VContainer>
</template>
