<script setup lang="ts">
import { listUnits } from '@/api/attendance/units'
import type { Unit } from '@/api/attendance/units'
import UnitQrDialogs from '@/components/attendance/UnitQrDialogs.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { openUnitQrPrintPlaceholder, printUnitQrs } from '@/utils/printUnitQrs'

definePage({ meta: {} })

const UNIT_PAGE_SIZE = 200
const SEARCH_DEBOUNCE_MS = 300

const { authStore, ensureAccess } = useAttendanceAdminGate()
const router = useRouter()

const units = ref<Unit[]>([])
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')
const filterType = ref('')
const showInactive = ref(false)
const searchQuery = ref('')
const qrDialogsRef = ref<InstanceType<typeof UnitQrDialogs> | null>(null)
const selectedIds = ref<Set<string>>(new Set())
const printing = ref(false)
const printError = ref('')

useAutoClearAlerts(loadError, printError)

const typeOptions = [
  { title: 'Student', value: 'student' },
  { title: 'Staff', value: 'staff' },
]

const unitsCapped = computed(() => units.value.length >= UNIT_PAGE_SIZE)
const checkedInCount = computed(() => units.value.filter(u => u.attendance_status === 'checked_in').length)
const selectedCount = computed(() => selectedIds.value.size)

const allVisibleSelected = computed(() =>
  units.value.length > 0 && units.value.every(u => selectedIds.value.has(u.id)),
)

const selectedUnits = computed(() =>
  units.value.filter(u => selectedIds.value.has(u.id)),
)

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  const total = units.value.length
  const countLabel = unitsCapped.value ? `${UNIT_PAGE_SIZE}+` : String(total)

  return `${countLabel} active · ${checkedInCount.value} checked in`
})

const listCaption = computed(() => {
  if (loading.value || units.value.length === 0)
    return ''

  const total = units.value.length
  if (unitsCapped.value)
    return `Showing ${total} of ${UNIT_PAGE_SIZE}+ active units`
  if (searchQuery.value || filterType.value || showInactive.value)
    return `Showing ${total} matching active unit${total === 1 ? '' : 's'}`

  return `${total} active unit${total === 1 ? '' : 's'}`
})

const emptyStateMessage = computed(() => {
  if (searchQuery.value || filterType.value || showInactive.value)
    return 'No matching active units'

  return 'No active units found'
})

const showEmptyUnitsCta = computed(() =>
  !searchQuery.value && !filterType.value && !showInactive.value,
)

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  await loadUnits()
})

async function loadUnits(isRefresh = false) {
  const softRefresh = isRefresh === true

  if (softRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    units.value = await listUnits({
      search: searchQuery.value || undefined,
      unit_type: filterType.value || undefined,
      is_active: showInactive.value ? undefined : true,
      page_size: UNIT_PAGE_SIZE,
    })
  }
  catch (e) {
    console.error('Failed to load QR units', e)
    loadError.value = formatApiError(e, 'Failed to load units. Please try again.')
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

const debouncedLoadUnits = useDebounceFn(() => loadUnits(true), SEARCH_DEBOUNCE_MS)

watch(searchQuery, () => {
  debouncedLoadUnits()
})

watch(filterType, () => {
  loadUnits(true)
})

watch(showInactive, () => {
  loadUnits(true)
})

function isSelected(id: string) {
  return selectedIds.value.has(id)
}

function setSelected(id: string, value: boolean) {
  const next = new Set(selectedIds.value)
  if (value)
    next.add(id)
  else
    next.delete(id)
  selectedIds.value = next
}

function toggleSelectAllVisible() {
  if (allVisibleSelected.value) {
    selectedIds.value = new Set()

    return
  }
  selectedIds.value = new Set(units.value.map(u => u.id))
}

function clearSelection() {
  selectedIds.value = new Set()
}

function openQR(u: Unit) {
  qrDialogsRef.value?.openQR(u)
}

async function printSelected() {
  if (!selectedUnits.value.length)
    return

  let printWindow: Window | null = null

  try {
    printWindow = openUnitQrPrintPlaceholder()
  }
  catch (e) {
    printError.value = formatApiError(e, 'Could not open print window')

    return
  }

  printing.value = true
  printError.value = ''
  try {
    await printUnitQrs(selectedUnits.value, printWindow)
  }
  catch (e) {
    printError.value = formatApiError(e, 'Could not print selected QR codes')
  }
  finally {
    printing.value = false
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
          QR Codes
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
          prepend-icon="ri-group-line"
          :to="{ name: 'attendance-units' }"
        >
          Manage units
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
      </VCol>
    </VRow>

    <VRow
      class="mb-4"
      align="center"
    >
      <VCol
        cols="12"
        sm="3"
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
        sm="2"
      >
        <VSelect
          v-model="filterType"
          :items="[{ title: 'All Types', value: '' }, ...typeOptions]"
          label="Type"
          density="compact"
          hide-details
        />
      </VCol>
      <VCol cols="auto">
        <VCheckbox
          v-model="showInactive"
          label="Show inactive"
          hide-details
          density="compact"
        />
      </VCol>
      <VCol
        cols="12"
        sm="5"
        class="d-flex flex-wrap align-center gap-2"
      >
        <VBtn
          variant="tonal"
          size="small"
          :prepend-icon="allVisibleSelected ? 'ri-checkbox-blank-line' : 'ri-checkbox-multiple-line'"
          :disabled="!units.length || loading"
          @click="toggleSelectAllVisible"
        >
          {{ allVisibleSelected ? 'Deselect all' : 'Select all' }}
        </VBtn>
        <VBtn
          v-if="selectedCount"
          variant="text"
          size="small"
          @click="clearSelection"
        >
          Clear ({{ selectedCount }})
        </VBtn>
        <VBtn
          color="primary"
          size="small"
          prepend-icon="ri-printer-line"
          :disabled="!selectedCount"
          :loading="printing"
          @click="printSelected"
        >
          Print selected{{ selectedCount ? ` (${selectedCount})` : '' }}
        </VBtn>
      </VCol>
      <VCol
        v-if="listCaption"
        cols="auto"
        class="ms-sm-auto"
      >
        <span class="text-caption text-medium-emphasis">{{ listCaption }}</span>
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

    <VAlert
      v-if="printError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="printError = ''"
    >
      {{ printError }}
    </VAlert>

    <VRow v-if="loading && !refreshing">
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

    <div
      v-else-if="units.length === 0 && !loadError"
      class="text-center text-medium-emphasis py-12"
    >
      <div class="mb-3">
        {{ emptyStateMessage }}
      </div>
      <VBtn
        v-if="showEmptyUnitsCta"
        color="primary"
        prepend-icon="ri-group-line"
        :to="{ name: 'attendance-units' }"
      >
        Go to Unit Management
      </VBtn>
    </div>

    <VRow v-else-if="!loadError">
      <VCol
        v-for="u in units"
        :key="u.id"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <UnitQrCard
          :unit="u"
          :selected="isSelected(u.id)"
          @update:selected="setSelected(u.id, $event)"
          @open-detail="openQR(u)"
        />
      </VCol>
    </VRow>

    <UnitQrDialogs
      ref="qrDialogsRef"
      @rotated="loadUnits(true)"
    />
  </VContainer>
</template>
