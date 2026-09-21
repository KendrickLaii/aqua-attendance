<script setup lang="ts">
import {
  type CourseEnrollment,
  type CourseSku,
  type CourseSpu,
  createCourseEnrollment,
  createEnrollmentPurchase,
  deleteCourseEnrollment,
  listAllCourseEnrollments,
  updateCourseEnrollment,
} from '@/api/attendance/courses'
import type { LocationItem } from '@/api/attendance/locations'
import { type Unit, getUnit, listUnits } from '@/api/attendance/units'
import { billingUnitShortLabel, enrollmentStatusColor } from '@/utils/courseEnrollmentDisplay'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { formatApiError } from '@/utils/formatApiDetail'
import {
  billingWindowLabel,
  emptyToNull,
  enrollBillPreview,
  enrollDisabledReason,
  enrollPriceHint,
  enrollmentPriceParts,
  enrollmentStatusLabel,
  formatRosterDate,
  matchesRosterSearch,
  purchaseSummary,
  purchaseTooltip,
  rosterMetaLine,
  rosterPriceLabel,
  studentCode,
  studentLabel,
} from '@/utils/courseRosterDisplay'
import { type SortValue, type TableSort, compareSortValues, sortIconFor, toggleSort } from '@/utils/tableSort'

const props = defineProps<{
  skuId: string | null
  skus: CourseSku[]
  spus: CourseSpu[]
  locations: LocationItem[]
  staffUnits: Unit[]
}>()

const emit = defineEmits<{
  'jump-to-class': [skuId: string | null]
}>()

const rosterSection = ref<HTMLElement | null>(null)
const compareCodes = (a: string, b: string) => a.localeCompare(b, undefined, { numeric: true })
const locationName = (id: string | null) => props.locations.find(l => l.id === id)?.name_en ?? '—'
const staffName = (id: string | null | undefined) => props.staffUnits.find(u => u.id === id)?.full_name ?? ''
const spuName = (id: string | null | undefined) => props.spus.find(s => s.id === id)?.name_zh ?? ''

const studentSearch = ref('')
const studentOptions = ref<Unit[]>([])
const studentById = reactive<Record<string, Unit>>({})
const studentSearchLoading = ref(false)
let studentSearchRequestId = 0
const selectedStudentId = ref<string | null>(null)
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

const rosterSku = computed(() => props.skus.find(k => k.id === props.skuId) ?? null)
const activeRosterCount = computed(() => enrollments.value.filter(e => e.status === 'active').length)
const rosterAtCapacity = computed(() => {
  const cap = rosterSku.value?.capacity
  if (cap == null)
    return false

  return activeRosterCount.value >= cap
})

const rosterEditingId = ref<string | null>(null)
const topUpEnabled = false
const topUpOpen = ref(false)
const topUpEnrollment = ref<CourseEnrollment | null>(null)
const topUpQuantity = ref<number | null>(null)
const topUpPrice = ref<number | null>(null)
const topUpDate = ref('')
const topUpNote = ref('')
const topUpSaving = ref(false)

const deleteConfirmOpen = ref(false)
const deleteConfirmLoading = ref(false)
const deleteConfirmError = ref('')
const deleteTarget = ref<{ title: string; detail: string; run: () => Promise<void> } | null>(null)

function cacheStudents(units: Unit[]) {
  for (const unit of units)
    studentById[unit.id] = unit
}

function labelFor(enrollment: CourseEnrollment): string {
  return studentLabel(enrollment.unit_id, enrollment, studentById)
}

function codeFor(enrollment: CourseEnrollment): string {
  return studentCode(enrollment.unit_id, enrollment, studentById)
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
    const missing = items.filter(e => !e.unit_name && !studentById[e.unit_id])
    if (missing.length)
      await ensureStudentNames(missing)
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
    if (requestId === studentSearchRequestId)
      enrollError.value = formatApiError(e, 'Could not load students. Search by name, or pick from the list after it reloads.')
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

watch(() => props.skuId, id => {
  enrollError.value = ''
  rosterEditingId.value = null
  rosterSearch.value = ''
  rosterStatusFilter.value = 'active'
  loadRoster(id)
})

onMounted(() => {
  loadStudentOptions()
  if (props.skuId)
    loadRoster(props.skuId)
})

function enrollNeedsPurchasedQuantity() {
  return rosterSku.value?.billing_unit === 'per_session'
}

const enrollPreview = computed(() => enrollBillPreview({
  sku: rosterSku.value,
  unitPrice: enrollUnitPrice.value,
  purchasedQuantity: enrollPurchasedQuantity.value,
}))

const classOptions = computed(() =>
  props.skus
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

const metaLine = computed(() => {
  const sku = rosterSku.value
  if (!sku)
    return ''

  return rosterMetaLine({
    sku,
    staffName: staffName(sku.staff_id),
    locationName: sku.location_id ? locationName(sku.location_id) : '',
  })
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

const rosterRows = computed(() => {
  const sku = rosterSku.value

  const pick: Record<RosterSortKey, (e: CourseEnrollment) => SortValue> = {
    student: e => e.unit_name || studentById[e.unit_id]?.full_name || null,
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
    if (query && !matchesRosterSearch(e, query, studentById))
      return false

    return true
  })
})

const disabledReason = computed(() => enrollDisabledReason({
  skuId: props.skuId,
  sku: rosterSku.value,
  atCapacity: rosterAtCapacity.value,
  studentId: selectedStudentId.value,
  activeUnitIds: activeRosterUnitIds.value,
  purchasedQuantity: enrollPurchasedQuantity.value,
}))

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

async function enrollStudent() {
  if (!selectedStudentId.value || !props.skuId || rosterSku.value?.is_active === false || rosterAtCapacity.value)
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
      sku_id: props.skuId,
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

function openDeleteConfirm(target: NonNullable<typeof deleteTarget.value>) {
  deleteTarget.value = target
  deleteConfirmError.value = ''
  deleteConfirmOpen.value = true
}

function closeDeleteConfirm() {
  if (deleteConfirmLoading.value)
    return
  deleteConfirmOpen.value = false
  deleteConfirmError.value = ''
  deleteTarget.value = null
}

async function confirmDelete() {
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

function cancelEnrollment(enrollment: CourseEnrollment) {
  const unbilledQty = purchaseSummary(enrollment).unbilledQty

  openDeleteConfirm({
    title: `Unenroll ${labelFor(enrollment)}?`,
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
    enrollSuccess.value = `${labelFor(enrollment)} re-activated.`
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
    enrollSuccess.value = `Added ${created.purchased_quantity} session${created.purchased_quantity === 1 ? '' : 's'} for ${labelFor(topUpEnrollment.value)} — billed on the next Generate.`
    topUpOpen.value = false
  }
  catch (e) {
    enrollError.value = formatApiError(e, 'Could not add top-up.')
  }
  finally {
    topUpSaving.value = false
  }
}

async function scrollIntoView() {
  await nextTick()
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  rosterSection.value?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
}

defineExpose({ scrollIntoView })
</script>

<template>
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
            v-if="metaLine"
            class="roster-identity__meta"
          >
            {{ metaLine }}
          </div>
        </div>
        <div class="roster-identity__aside">
          <VAutocomplete
            :model-value="skuId"
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
            @update:model-value="emit('jump-to-class', $event)"
          >
            <template #item="{ props: itemProps, item }">
              <VListItem
                v-bind="itemProps"
                :title="`${item.raw.code} · ${item.raw.name_zh}`"
                :subtitle="`${spuName(item.raw.spu_id)} · ${billingUnitShortLabel(item.raw.billing_unit ?? 'monthly')}`"
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
              :disabled="!skuId"
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
              :disabled="!skuId"
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
              :disabled="!skuId"
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
              :disabled="!skuId"
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
              :hint="enrollPriceHint(rosterSku)"
              persistent-hint
              :disabled="!skuId"
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
              :disabled="Boolean(disabledReason)"
              :title="disabledReason || undefined"
              @click="enrollStudent"
            >
              Enroll
            </VBtn>
          </VCol>
        </VRow>
        <div
          v-if="enrollPreview"
          class="text-caption text-medium-emphasis mt-2 d-flex align-center"
        >
          <VIcon
            icon="ri-bill-line"
            size="14"
            class="me-1"
          />
          {{ enrollPreview }}
        </div>
        <div
          v-if="disabledReason && selectedStudentId"
          class="text-caption text-medium-emphasis mt-1"
        >
          {{ disabledReason }}
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
          :disabled="!skuId"
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
        v-if="!skuId"
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
                  <span class="roster-student__name">{{ labelFor(e) }}</span>
                  <span class="roster-student__code">{{ codeFor(e) }}</span>
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
                <template v-if="enrollmentPriceParts(e, rosterSku)">
                  <div>{{ enrollmentPriceParts(e, rosterSku)?.amount }}</div>
                  <div class="text-caption text-medium-emphasis">
                    {{ enrollmentPriceParts(e, rosterSku)?.hint }}
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

    <VDialog
      v-model="editDialogOpen"
      max-width="480"
    >
      <VCard v-if="editingEnrollment && enrollmentDates[editingEnrollment.id]">
        <VCardTitle>Edit {{ labelFor(editingEnrollment) }}</VCardTitle>
        <VCardSubtitle>
          {{ codeFor(editingEnrollment) }}
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

    <AttendanceConfirmDialog
      v-model="deleteConfirmOpen"
      :title="deleteTarget?.title || 'Confirm delete'"
      :loading="deleteConfirmLoading"
      :error="deleteConfirmError"
      @confirm="confirmDelete"
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
  </div>
</template>

<style scoped>
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

.roster-table :deep(.col-actions) {
  position: sticky;
  inset-inline-end: 0;
  z-index: 1;
  white-space: nowrap;
  width: 1%;
  background: rgb(var(--v-theme-surface));
  border-inline-start: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
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
