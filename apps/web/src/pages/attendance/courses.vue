<script setup lang="ts">
import {
  type CourseSku,
  type CourseSpu,
  deleteCourseSku,
  deleteCourseSpu,
  listCourseSkus,
  listCourseSpus,
} from '@/api/attendance/courses'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import { type Unit, listAllUnits } from '@/api/attendance/units'
import CourseCatalogPanels from '@/components/attendance/courses/CourseCatalogPanels.vue'
import CourseRosterSection from '@/components/attendance/courses/CourseRosterSection.vue'
import CourseSkuDialog from '@/components/attendance/courses/CourseSkuDialog.vue'
import CourseSpuDialog from '@/components/attendance/courses/CourseSpuDialog.vue'
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

const selectedSpuId = ref<string | null>(null)
const rosterSkuId = ref<string | null>(null)
const catalogPanel = ref<'courses' | 'offerings' | undefined>('courses')
const catalogRef = ref<{ scrollCatalogSelection: () => void } | null>(null)
const rosterRef = ref<{ scrollIntoView: () => Promise<void> } | null>(null)

const compareCodes = (a: string, b: string) => a.localeCompare(b, undefined, { numeric: true })

const staffOptions = computed(() =>
  staffUnits.value
    .slice()
    .sort((a, b) => Number(b.is_active) - Number(a.is_active) || a.full_name.localeCompare(b.full_name))
    .map(u => ({ value: u.id, title: `${u.full_name} · ${u.code}${u.is_active ? '' : ' (inactive)'}` })),
)

const locationOptions = computed(() =>
  locations.value.map(location => ({
    id: location.id,
    title: [location.name_en, location.name_zh].filter(Boolean).join(' · '),
  })),
)

const skusForSelectedSpu = computed(() => skus.value.filter(k => k.spu_id === selectedSpuId.value))

const spuDialogOpen = ref(false)
const editingSpu = ref<CourseSpu | null>(null)
const skuDialogOpen = ref(false)
const editingSku = ref<CourseSku | null>(null)

const deleteConfirmOpen = ref(false)
const deleteConfirmLoading = ref(false)
const deleteConfirmError = ref('')
const deleteTarget = ref<{ title: string; detail: string; run: () => Promise<void> } | null>(null)

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  await loadAll()
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
      listAllUnits({ unit_type: 'staff' }),
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

function applySkuFromRoute() {
  const selection = pickCourseSelectionForSku(skus.value, skuIdFromRouteQuery(route.query))
  if (!selection)
    return
  selectedSpuId.value = selection.spuId
  rosterSkuId.value = selection.skuId
  catalogPanel.value = undefined
}

watch(() => route.query.sku, () => {
  if (skus.value.length === 0)
    return
  applySkuFromRoute()
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
  const sku = skus.value.find(k => k.id === id)
  if (sku && sku.spu_id !== selectedSpuId.value)
    selectedSpuId.value = sku.spu_id
})

function selectCourse(spuId: string) {
  selectedSpuId.value = spuId
  catalogPanel.value = 'offerings'
}

async function selectClass(skuId: string) {
  rosterSkuId.value = skuId
  catalogPanel.value = undefined
  await nextTick()
  catalogRef.value?.scrollCatalogSelection()
  await rosterRef.value?.scrollIntoView()
}

function onJumpToClass(skuId: string | null) {
  if (skuId)
    void selectClass(skuId)
  else
    rosterSkuId.value = null
}

function openCreateSpu() {
  editingSpu.value = null
  spuDialogOpen.value = true
}

function openEditSpu(spu: CourseSpu) {
  editingSpu.value = spu
  spuDialogOpen.value = true
}

function openCreateSku() {
  if (!selectedSpuId.value)
    return
  editingSku.value = null
  skuDialogOpen.value = true
}

function openEditSku(sku: CourseSku) {
  editingSku.value = sku
  skuDialogOpen.value = true
}

function closeDeleteConfirm() {
  if (deleteConfirmLoading.value)
    return
  deleteConfirmOpen.value = false
  deleteConfirmError.value = ''
  deleteTarget.value = null
}

async function confirmCatalogDelete() {
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
  deleteTarget.value = {
    title: `Delete ${spu.name_zh}?`,
    detail: `Delete course "${spu.name_zh}"? This only works if it has no class offerings.`,
    run: async () => {
      await deleteCourseSpu(spu.id)
      if (selectedSpuId.value === spu.id)
        selectedSpuId.value = null
      await loadAll()
    },
  }
  deleteConfirmError.value = ''
  deleteConfirmOpen.value = true
}

function removeSku(sku: CourseSku) {
  deleteTarget.value = {
    title: `Delete ${sku.name_zh}?`,
    detail: `Delete class "${sku.name_zh}"? This only works if no student is enrolled.`,
    run: async () => {
      await deleteCourseSku(sku.id)
      await loadAll()
    },
  }
  deleteConfirmError.value = ''
  deleteConfirmOpen.value = true
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
          Expand Courses to pick a course, then Class Offerings to pick a class. The roster below is who is in that class.
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
          v-if="catalogPanel === 'offerings'"
          variant="tonal"
          color="primary"
          prepend-icon="ri-add-line"
          @click="openCreateSpu"
        >
          Add Course
        </VBtn>
        <VBtn
          v-if="catalogPanel === 'offerings'"
          color="primary"
          prepend-icon="ri-add-line"
          :disabled="!selectedSpuId"
          @click="openCreateSku"
        >
          Add Class
        </VBtn>
        <VBtn
          v-else
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
      <CourseCatalogPanels
        ref="catalogRef"
        v-model:catalog-panel="catalogPanel"
        :spus="spus"
        :skus="skus"
        :locations="locations"
        :staff-units="staffUnits"
        :selected-spu-id="selectedSpuId"
        :roster-sku-id="rosterSkuId"
        @select-course="selectCourse"
        @select-class="selectClass"
        @create-sku="openCreateSku"
        @edit-spu="openEditSpu"
        @delete-spu="removeSpu"
        @edit-sku="openEditSku"
        @delete-sku="removeSku"
      />

      <VRow class="mt-4">
        <VCol cols="12">
          <CourseRosterSection
            ref="rosterRef"
            :sku-id="rosterSkuId"
            :skus="skus"
            :spus="spus"
            :locations="locations"
            :staff-units="staffUnits"
            @jump-to-class="onJumpToClass"
          />
        </VCol>
      </VRow>
    </template>

    <CourseSpuDialog
      v-model="spuDialogOpen"
      :editing-spu="editingSpu"
      @saved="loadAll"
    />
    <CourseSkuDialog
      v-model="skuDialogOpen"
      :editing-sku="editingSku"
      :selected-spu-id="selectedSpuId"
      :location-options="locationOptions"
      :staff-options="staffOptions"
      @saved="loadAll"
    />
    <AttendanceConfirmDialog
      v-model="deleteConfirmOpen"
      :title="deleteTarget?.title || 'Confirm delete'"
      :loading="deleteConfirmLoading"
      :error="deleteConfirmError"
      @confirm="confirmCatalogDelete"
      @cancel="closeDeleteConfirm"
      @clear-error="deleteConfirmError = ''"
    >
      {{ deleteTarget?.detail }}
    </AttendanceConfirmDialog>
  </VContainer>
</template>
