<script setup lang="ts">
import { deleteUnit, listUnitsWithTotal } from '@/api/attendance/units'
import type { Unit } from '@/api/attendance/units'
import { listLocations } from '@/api/attendance/locations'
import type { LocationItem } from '@/api/attendance/locations'
import UnitQrDialogs from '@/components/attendance/UnitQrDialogs.vue'
import UnitFormDialog from '@/components/attendance/units/UnitFormDialog.vue'
import AppToastStack from '@/components/AppToastStack.vue'
import { formatLastAttendance } from '@/utils/attendanceDisplay'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

definePage({ meta: {} })

const pageSize = ref(40)
const pageSizeOptions = [10, 20, 40, 60, 100]
const SEARCH_DEBOUNCE_MS = 300

const { ensureAccess } = useAttendanceAdminGate()

const units = ref<Unit[]>([])
const locations = ref<LocationItem[]>([])
const totalCount = ref(0)
const page = ref(1)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')

useAutoClearAlerts(loadError)

const dialogOpen = ref(false)
const editingUnit = ref<Unit | null>(null)
const correctionDialog = ref(false)
const correctionTarget = ref<Unit | null>(null)

const searchQuery = ref('')
const filterType = ref('')
const filterActive = ref('')
const filterAttendance = ref('')
const filterEmployment = ref('')
const qrDialogsRef = ref<InstanceType<typeof UnitQrDialogs> | null>(null)

const deleteConfirmOpen = ref(false)
const deleteTarget = ref<Unit | null>(null)
const deleting = ref(false)
const deleteError = ref('')

const statusOptions = [
  { title: 'Active', value: 'active' },
  { title: 'Inactive', value: 'inactive' },
  { title: 'Suspended', value: 'suspended' },
]

const typeOptions = [
  { title: 'Student', value: 'student' },
  { title: 'Staff', value: 'staff' },
]

const activeFilterOptions = [
  { title: 'All statuses', value: '' },
  { title: 'Active only', value: 'active' },
  { title: 'Inactive only', value: 'inactive' },
]

const attendanceFilterOptions = [
  { title: 'All attendance', value: '' },
  { title: 'Checked in', value: 'checked_in' },
  { title: 'Checked out', value: 'checked_out' },
]

const employmentFilterOptions = [
  { title: 'All employment', value: '' },
  { title: 'Full-time', value: 'full_time' },
  { title: 'Part-time', value: 'part_time' },
]

const locationOptions = computed(() =>
  locations.value
    .filter(loc => loc.is_active)
    .map(loc => ({
      title: loc.name_en || loc.name_zh || loc.code || loc.id,
      value: loc.id,
    })),
)

const defaultLocationId = computed(() => locations.value[0]?.id ?? '')

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  const total = totalCount.value
  let label = `${total} unit${total === 1 ? '' : 's'}`
  if (filterAttendance.value === 'checked_in')
    label += ' · checked in'
  else if (filterAttendance.value === 'checked_out')
    label += ' · checked out'
  if (totalPages.value > 1)
    label += ` · page ${page.value} of ${totalPages.value}`

  return label
})

const listCaption = computed(() => {
  if (loading.value || totalCount.value === 0)
    return ''

  const from = (page.value - 1) * pageSize.value + 1
  const to = from + units.value.length - 1

  if (totalCount.value <= pageSize.value)
    return `${totalCount.value} unit${totalCount.value === 1 ? '' : 's'}`

  return `${from}–${to} of ${totalCount.value}`
})

const showEmptyCreateCta = computed(() =>
  !searchQuery.value && !filterType.value && !filterActive.value && !filterAttendance.value,
)

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  await loadLocations()
  await loadUnits()
})

async function loadLocations() {
  try {
    locations.value = await listLocations({ is_active: true, page_size: 200 })
  }
  catch (e) {
    locations.value = []
    loadError.value = formatApiError(e, 'Could not load locations. Campus fields on the unit form may be incomplete.')
  }
}

async function loadUnits(isRefresh = false, resetPage = false) {
  const softRefresh = isRefresh === true

  if (resetPage)
    page.value = 1
  if (softRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const result = await listUnitsWithTotal({
      search: searchQuery.value || undefined,
      unit_type: filterType.value || undefined,
      is_active: filterActive.value === 'active' ? true : filterActive.value === 'inactive' ? false : undefined,
      attendance_status: filterAttendance.value === 'checked_in' || filterAttendance.value === 'checked_out'
        ? filterAttendance.value
        : undefined,
      employment_type: filterEmployment.value === 'part_time' || filterEmployment.value === 'full_time'
        ? filterEmployment.value
        : undefined,
      page: page.value,
      page_size: pageSize.value,
    })

    units.value = result.items
    totalCount.value = result.total
  }
  catch (e) {
    console.error('Failed to load units', e)
    loadError.value = formatApiError(e, 'Failed to load units. Please try again.')
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

const debouncedLoadUnits = useDebounceFn(() => loadUnits(true, true), SEARCH_DEBOUNCE_MS)

watch(searchQuery, () => {
  debouncedLoadUnits()
})

watch(filterType, () => {
  if (filterType.value === 'student')
    filterEmployment.value = ''
  loadUnits(true, true)
})

watch(filterActive, () => {
  loadUnits(true, true)
})

watch(filterAttendance, () => {
  loadUnits(true, true)
})

watch(filterEmployment, () => {
  loadUnits(true, true)
})

function onPageSizeChange() {
  page.value = 1
  loadUnits(true)
}

function openCreate() {
  editingUnit.value = null
  dialogOpen.value = true
}

function openEdit(p: Unit) {
  editingUnit.value = p
  dialogOpen.value = true
}


function openDeleteConfirm(p: Unit) {
  deleteError.value = ''
  deleteTarget.value = p
  deleteConfirmOpen.value = true
}

function closeDeleteConfirm() {
  deleteConfirmOpen.value = false
  deleteError.value = ''
  deleteTarget.value = null
}

async function confirmDelete() {
  if (!deleteTarget.value)
    return

  deleting.value = true
  deleteError.value = ''
  try {
    await deleteUnit(deleteTarget.value.id)
    closeDeleteConfirm()
    await loadUnits(true)
  }
  catch (e: unknown) {
    deleteError.value = formatApiError(e, 'Could not delete unit')
  }
  finally {
    deleting.value = false
  }
}

function openQR(p: Unit) {
  qrDialogsRef.value?.openQR(p)
}

function openManualCorrection(p: Unit) {
  correctionTarget.value = p
  correctionDialog.value = true
}

function typeColor(type: string) {
  return type === 'staff' ? 'info' : 'success'
}

function typeLabel(type: string) {
  return typeOptions.find(o => o.value === type)?.title ?? type
}

function employmentTypeLabel(value: string | null | undefined) {
  if (value === 'full_time')
    return 'Full-time'
  if (value === 'part_time')
    return 'Part-time'

  return '—'
}

function locationLabel(location: Unit['registered_location']) {
  if (!location)
    return '—'

  return location.name_en || location.name_zh || location.code || '—'
}

function scanLocationsLabel(p: Unit) {
  if (!p.scan_locations?.length)
    return '—'

  return p.scan_locations
    .map(loc => loc.name_en || loc.name_zh || loc.code || '')
    .filter(Boolean)
    .join(', ')
}

function statusColor(status: string) {
  if (status === 'active')
    return 'success'
  if (status === 'suspended')
    return 'warning'

  return 'grey'
}

function statusLabel(status: string) {
  return statusOptions.find(o => o.value === status)?.title ?? status
}

function rowStatusChip(p: Unit) {
  if (!p.is_active) {
    return {
      color: 'grey',
      label: 'Disabled',
      title: `Deactivated for attendance — record status: ${statusLabel(p.status)}`,
    }
  }

  return {
    color: statusColor(p.status),
    label: statusLabel(p.status),
    title: undefined as string | undefined,
  }
}
</script>

<template>
  <VContainer>
    <VRow
      class="mb-2"
      align="center"
    >
      <VCol
        cols="12"
        sm="8"
      >
        <div class="text-h5 font-weight-medium">
          Unit Management
        </div>
        <div class="text-body-2 text-medium-emphasis">
          {{ pageSubtitle }}
        </div>
      </VCol>
      <VCol
        cols="12"
        sm="4"
        class="d-flex flex-wrap justify-sm-end gap-2"
      >
        <VBtn
          variant="outlined"
          color="primary"
          prepend-icon="ri-qr-code-line"
          :to="{ name: 'attendance-qr-codes' }"
        >
          QR Codes
        </VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="refreshing"
          @click="loadUnits(true)"
        >
          Refresh
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          @click="openCreate"
        >
          Add Unit
        </VBtn>
      </VCol>
    </VRow>

    <!-- Attendance filter uses server-side attendance_status — see GET /api/units -->
    <VRow
      class="mb-4"
      align="center"
    >
      <VCol
        cols="12"
        sm="4"
        md="3"
      >
        <VTextField
          v-model="searchQuery"
          placeholder="Search units..."
          prepend-inner-icon="ri-search-line"
          density="compact"
          hide-details
          clearable
        />
      </VCol>
      <VCol
        cols="12"
        sm="4"
        md="3"
      >
        <VSelect
          v-model="filterType"
          :items="[{ title: 'All Types', value: '' }, ...typeOptions]"
          label="Type"
          density="compact"
          hide-details
        />
      </VCol>
      <VCol
        cols="12"
        sm="4"
        md="3"
      >
        <VSelect
          v-model="filterActive"
          :items="activeFilterOptions"
          label="Active status"
          density="compact"
          hide-details
        />
      </VCol>
      <VCol
        cols="12"
        sm="4"
        md="3"
      >
        <VSelect
          v-model="filterAttendance"
          :items="attendanceFilterOptions"
          label="Attendance"
          density="compact"
          hide-details
        />
      </VCol>
      <VCol
        cols="12"
        sm="4"
        md="3"
      >
        <VSelect
          v-model="filterEmployment"
          :items="employmentFilterOptions"
          label="Employment"
          density="compact"
          hide-details
          :disabled="filterType === 'student'"
        />
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
      <template #append>
        <VBtn
          variant="text"
          size="small"
          @click="loadUnits(true)"
        >
          Retry
        </VBtn>
      </template>
    </VAlert>

    <VCard :loading="loading">
      <VCardTitle class="d-flex align-center justify-space-between flex-wrap gap-2">
        <span>Units</span>
        <span
          v-if="listCaption"
          class="text-caption text-medium-emphasis"
        >
          {{ listCaption }}
        </span>
      </VCardTitle>
      <div class="units-table-scroll">
        <VTable class="units-table">
          <thead>
            <tr>
              <th width="100">
                Code
              </th>
              <th width="130">
                Full Name
              </th>
              <th width="80">
                Type
              </th>
              <th width="120">
                Registered location
              </th>
              <th width="120">
                Scan locations
              </th>
              <th width="100">
                Employment
              </th>
              <th width="90">
                Status
              </th>
              <th width="180">
                Last check-in / out
              </th>
              <th
                class="col-phone"
                width="110"
              >
                Phone
              </th>
              <th
                class="col-school"
                width="130"
              >
                School / Class
              </th>
              <th class="col-actions">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="p in units"
              :key="p.id"
              :class="{ 'unit-row-inactive': !p.is_active }"
            >
              <td class="font-weight-medium">
                {{ p.code }}
              </td>
              <td>{{ p.full_name }}</td>
              <td>
                <VChip
                  :color="typeColor(p.unit_type)"
                  size="small"
                  label
                >
                  {{ typeLabel(p.unit_type) }}
                </VChip>
              </td>
              <td>{{ locationLabel(p.registered_location) }}</td>
              <td class="col-school">
                {{ scanLocationsLabel(p) }}
              </td>
              <td>
                <span v-if="p.unit_type === 'staff'">{{ employmentTypeLabel(p.staff_profile?.employment_type) }}</span>
                <span
                  v-else
                  class="text-medium-emphasis"
                >—</span>
              </td>
              <td>
                <VChip
                  :color="rowStatusChip(p).color"
                  size="small"
                  label
                  :title="rowStatusChip(p).title"
                >
                  {{ rowStatusChip(p).label }}
                </VChip>
              </td>
              <td>
                <div
                  class="text-caption"
                  :class="p.last_event_at && p.attendance_status === 'checked_in' ? 'text-success' : 'text-medium-emphasis'"
                >
                  {{ formatLastAttendance(p, { compact: true }) }}
                </div>
              </td>
              <td class="col-phone">
                {{ p.phone || '-' }}
              </td>
              <td class="col-school">
                {{ p.student_profile?.school_name ? `${p.student_profile.school_name} / ${p.student_profile.grade_class || '-'}` : '-' }}
              </td>
              <td class="col-actions">
                <div class="d-flex flex-nowrap align-center">
                  <VBtn
                    icon
                    size="small"
                    variant="text"
                    color="primary"
                    :disabled="!p.is_active"
                    :title="p.is_active ? 'QR Code' : 'QR unavailable — unit is inactive'"
                    :aria-label="`View QR code for ${p.full_name}`"
                    @click="openQR(p)"
                  >
                    <VIcon icon="ri-qr-code-line" />
                  </VBtn>
                  <VBtn
                    icon
                    size="small"
                    variant="text"
                    color="info"
                    title="Manual"
                    :aria-label="`Manual correction for ${p.full_name}`"
                    @click="openManualCorrection(p)"
                  >
                    <VIcon icon="ri-edit-box-line" />
                  </VBtn>
                  <VBtn
                    icon
                    size="small"
                    variant="text"
                    title="Edit"
                    :aria-label="`Edit ${p.full_name}`"
                    @click="openEdit(p)"
                  >
                    <VIcon icon="ri-edit-line" />
                  </VBtn>
                  <VBtn
                    icon
                    size="small"
                    variant="text"
                    color="error"
                    title="Delete"
                    :aria-label="`Delete ${p.full_name}`"
                    @click="openDeleteConfirm(p)"
                  >
                    <VIcon icon="ri-delete-bin-line" />
                  </VBtn>
                </div>
              </td>
            </tr>
            <tr v-if="units.length === 0 && !loading">
              <td
                colspan="8"
                class="text-center text-medium-emphasis py-6"
              >
                <div class="mb-3">
                  {{ searchQuery || filterType || filterActive || filterAttendance ? 'No units match your search or filters' : 'No units yet' }}
                </div>
                <VBtn
                  v-if="showEmptyCreateCta"
                  color="primary"
                  prepend-icon="ri-add-line"
                  @click="openCreate"
                >
                  Add Unit
                </VBtn>
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <div
        v-if="!loading && units.length > 0"
        class="d-flex flex-wrap align-center justify-space-between gap-2 pa-4 pt-0"
      >
        <div class="d-flex align-center gap-2">
          <span class="text-caption text-medium-emphasis">
            Page {{ page }} of {{ totalPages }}
          </span>
          <VSelect
            v-model="pageSize"
            :items="pageSizeOptions"
            density="compact"
            variant="plain"
            hide-details
            style="max-width: 70px;"
            @update:model-value="onPageSizeChange"
          />
          <span class="text-caption text-medium-emphasis">per page</span>
        </div>
        <VPagination
          v-model="page"
          :length="totalPages"
          :total-visible="5"
          density="compact"
          size="small"
          @update:model-value="loadUnits(true)"
        />
      </div>
      <div class="text-caption text-medium-emphasis px-4 pb-3 d-md-none">
        Swipe sideways to see more columns. Phone and school are hidden on small screens.
      </div>
    </VCard>

    <UnitFormDialog
      v-model="dialogOpen"
      :editing-unit="editingUnit"
      :location-options="locationOptions"
      :default-location-id="defaultLocationId"
      @saved="loadUnits(true)"
    />


    <AttendanceConfirmDialog
      v-model="deleteConfirmOpen"
      :title="`Delete ${deleteTarget?.full_name}?`"
      :loading="deleting"
      :error="deleteError"
      @confirm="confirmDelete"
      @cancel="closeDeleteConfirm"
      @clear-error="deleteError = ''"
    >
      This will permanently remove
      <strong>{{ deleteTarget?.full_name }}</strong> ({{ deleteTarget?.code }}).
      People with attendance, enrollments, invoices, or payroll cannot be deleted — set them inactive instead.
      This action cannot be undone.
    </AttendanceConfirmDialog>

    <AppToastStack />

    <UnitQrDialogs
      ref="qrDialogsRef"
      @rotated="loadUnits(true)"
    />

    <ManualCorrectionDialog
      v-model="correctionDialog"
      :unit="correctionTarget"
      @saved="loadUnits(true)"
    />
  </VContainer>
</template>

<style scoped lang="scss">
.unit-row-inactive {
  opacity: 0.55;
}

.units-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.units-table :deep(thead th),
.units-table :deep(tbody td) {
  vertical-align: middle;
  white-space: nowrap;
}

.units-table :deep(.col-actions) {
  position: sticky;
  right: 0;
  background: rgb(var(--v-theme-surface));
  white-space: nowrap;
  width: 1%;
  z-index: 2;
  border-left: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.units-table :deep(thead th.col-actions) {
  z-index: 3;
}

@media (max-width: 960px) {
  .units-table :deep(.col-phone),
  .units-table :deep(.col-school) {
    display: none;
  }
}
</style>
