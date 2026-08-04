<script setup lang="ts">
import {
  type CourseEnrollment,
  type CourseSku,
  type CourseSpu,
  createCourseEnrollment,
  createCourseSku,
  createCourseSpu,
  deleteCourseEnrollment,
  deleteCourseSku,
  deleteCourseSpu,
  listCourseEnrollmentsWithTotal,
  listCourseSkus,
  listCourseSpus,
  updateCourseEnrollment,
  updateCourseSku,
  updateCourseSpu,
} from '@/api/attendance/courses'
import { listLocations, type LocationItem } from '@/api/attendance/locations'
import { listUnits, type Unit } from '@/api/attendance/units'
import { formatApiError } from '@/utils/formatApiDetail'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const loading = ref(true)
const loadError = ref('')

const spus = ref<CourseSpu[]>([])
const skus = ref<CourseSku[]>([])
const locations = ref<LocationItem[]>([])

const selectedSpuId = ref<string | null>(null)
const selectedSpu = computed(() => spus.value.find(s => s.id === selectedSpuId.value) ?? null)
const skusForSelectedSpu = computed(() => skus.value.filter(k => k.spu_id === selectedSpuId.value))

const locationName = (id: string | null) => locations.value.find(l => l.id === id)?.name_en ?? '—'

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  await loadAll()
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

async function removeSpu(spu: CourseSpu) {
  if (!confirm(`Delete course "${spu.name_zh}"? This only works if it has no class offerings.`))
    return
  try {
    await deleteCourseSpu(spu.id)
    if (selectedSpuId.value === spu.id)
      selectedSpuId.value = null
    await loadAll()
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Could not delete course. It may still have class offerings — set it inactive instead.')
  }
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
  is_active: true,
})

function openCreateSku() {
  if (!selectedSpuId.value)
    return
  editingSku.value = null
  Object.assign(skuForm, {
    code: '', name_zh: '', name_en: '', level: '', schedule_note: '',
    location_id: null, capacity: null, price: null, is_active: true,
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
    is_active: sku.is_active,
  })
  skuSaveError.value = ''
  skuDialogOpen.value = true
}

async function saveSku() {
  if (!selectedSpuId.value)
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

async function removeSku(sku: CourseSku) {
  if (!confirm(`Delete class "${sku.name_zh}"? This only works if no student is enrolled.`))
    return
  try {
    await deleteCourseSku(sku.id)
    await loadAll()
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Could not delete class. It may still have enrolled students — set it inactive instead.')
  }
}

// ---------------- Enrollments ----------------

const studentSearch = ref('')
const studentOptions = ref<Unit[]>([])
const studentSearchLoading = ref(false)
const selectedStudentId = ref<string | null>(null)
const enrollSkuId = ref<string | null>(null)
const enrolling = ref(false)
const enrollError = ref('')

const enrollments = ref<CourseEnrollment[]>([])
const enrollmentsLoading = ref(false)

const activeSkuOptions = computed(() =>
  skus.value
    .filter(k => k.is_active)
    .map(k => ({ ...k, spuName: spus.value.find(s => s.id === k.spu_id)?.name_zh ?? '' })),
)

const searchDebounce = useDebounceFn(async () => {
  if (!studentSearch.value.trim()) {
    studentOptions.value = []

    return
  }
  studentSearchLoading.value = true
  try {
    studentOptions.value = await listUnits({ unit_type: 'student', search: studentSearch.value.trim(), page_size: 20 })
  }
  catch (e) {
    console.error('Failed to search students', e)
  }
  finally {
    studentSearchLoading.value = false
  }
}, 300)

watch(studentSearch, () => searchDebounce())

watch(selectedStudentId, async id => {
  enrollments.value = []
  if (!id)
    return
  enrollmentsLoading.value = true
  try {
    const result = await listCourseEnrollmentsWithTotal({ unit_id: id, page_size: 100 })
    enrollments.value = result.items
  }
  catch (e) {
    console.error('Failed to load enrollments', e)
  }
  finally {
    enrollmentsLoading.value = false
  }
})

function skuLabel(skuId: string): string {
  const sku = skus.value.find(k => k.id === skuId)
  if (!sku)
    return skuId
  const spuName = spus.value.find(s => s.id === sku.spu_id)?.name_zh
  return spuName ? `${spuName} · ${sku.name_zh}` : sku.name_zh
}

async function enrollStudent() {
  if (!selectedStudentId.value || !enrollSkuId.value)
    return
  enrolling.value = true
  enrollError.value = ''
  try {
    const created = await createCourseEnrollment({ unit_id: selectedStudentId.value, sku_id: enrollSkuId.value })
    enrollments.value = [created, ...enrollments.value]
    enrollSkuId.value = null
  }
  catch (e) {
    enrollError.value = formatApiError(e, 'Could not enroll student.')
  }
  finally {
    enrolling.value = false
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

async function removeEnrollment(enrollment: CourseEnrollment) {
  if (!confirm('Remove this enrollment record?'))
    return
  try {
    await deleteCourseEnrollment(enrollment.id)
    enrollments.value = enrollments.value.filter(e => e.id !== enrollment.id)
  }
  catch (e) {
    enrollError.value = formatApiError(e, 'Could not remove enrollment.')
  }
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
          Courses (SPU) group class offerings (SKU); students enroll in a SKU.
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
                  <td class="text-end">
                    {{ sku.price != null ? sku.price : '—' }}
                  </td>
                  <td class="text-end">
                    <VBtn
                      icon
                      size="x-small"
                      variant="text"
                      @click="openEditSku(sku)"
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
                      @click="removeSku(sku)"
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
                    colspan="7"
                    class="text-center text-medium-emphasis py-6"
                  >
                    No class offerings yet for this course.
                  </td>
                </tr>
                <tr v-if="!selectedSpuId">
                  <td
                    colspan="7"
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

      <!-- Enrollments -->
      <VRow class="mt-4">
        <VCol cols="12">
          <VCard title="Student Enrollments">
            <VCardText>
              <VRow align="center">
                <VCol
                  cols="12"
                  md="5"
                >
                  <VAutocomplete
                    v-model="selectedStudentId"
                    v-model:search="studentSearch"
                    :items="studentOptions"
                    :loading="studentSearchLoading"
                    item-title="full_name"
                    item-value="id"
                    label="Find student"
                    placeholder="Type a student's name or code..."
                    prepend-inner-icon="ri-search-line"
                    density="compact"
                    hide-details
                    clearable
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
                  md="5"
                >
                  <VSelect
                    v-model="enrollSkuId"
                    :items="activeSkuOptions"
                    item-value="id"
                    label="Enroll in class"
                    density="compact"
                    hide-details
                    :disabled="!selectedStudentId"
                  >
                    <template #item="{ props: itemProps, item }">
                      <VListItem
                        v-bind="itemProps"
                        :title="item.raw.name_zh"
                        :subtitle="item.raw.spuName"
                      />
                    </template>
                    <template #selection="{ item }">
                      {{ item.raw.name_zh }}
                    </template>
                  </VSelect>
                </VCol>
                <VCol
                  cols="12"
                  md="2"
                >
                  <VBtn
                    color="primary"
                    block
                    :loading="enrolling"
                    :disabled="!selectedStudentId || !enrollSkuId"
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
                v-if="!selectedStudentId"
                class="text-center text-medium-emphasis py-8"
              >
                Search and pick a student above to view or manage their course enrollments.
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
                    <th>Class</th>
                    <th>Status</th>
                    <th>Enrolled</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="e in enrollments"
                    :key="e.id"
                  >
                    <td>{{ skuLabel(e.sku_id) }}</td>
                    <td>
                      <VChip
                        size="x-small"
                        :color="enrollmentStatusColor[e.status] ?? 'grey'"
                      >
                        {{ e.status }}
                      </VChip>
                    </td>
                    <td>{{ e.enrolled_at }}</td>
                    <td class="text-end">
                      <VBtn
                        v-if="e.status === 'active'"
                        size="x-small"
                        variant="text"
                        @click="cancelEnrollment(e)"
                      >
                        Cancel
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
                    </td>
                  </tr>
                  <tr v-if="enrollments.length === 0">
                    <td
                      colspan="4"
                      class="text-center text-medium-emphasis py-6"
                    >
                      No enrollments yet for this student.
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
      max-width="480"
    >
      <VCard :title="editingSpu ? 'Edit Course' : 'Add Course'">
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
          <VRow>
            <VCol cols="6">
              <VTextField
                v-model="spuForm.code"
                label="Code"
                density="compact"
              />
            </VCol>
            <VCol cols="6">
              <VTextField
                v-model="spuForm.subject"
                label="Subject"
                density="compact"
              />
            </VCol>
            <VCol cols="6">
              <VTextField
                v-model="spuForm.name_zh"
                label="Name (Chinese)"
                density="compact"
              />
            </VCol>
            <VCol cols="6">
              <VTextField
                v-model="spuForm.name_en"
                label="Name (English)"
                density="compact"
              />
            </VCol>
            <VCol cols="12">
              <VTextarea
                v-model="spuForm.description"
                label="Description"
                density="compact"
                rows="2"
              />
            </VCol>
            <VCol cols="12">
              <VCheckbox
                v-model="spuForm.is_active"
                label="Active"
                hide-details
                density="compact"
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
      max-width="560"
    >
      <VCard :title="editingSku ? 'Edit Class Offering' : 'Add Class Offering'">
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
          <VRow>
            <VCol cols="6">
              <VTextField
                v-model="skuForm.code"
                label="Code"
                density="compact"
              />
            </VCol>
            <VCol cols="6">
              <VTextField
                v-model="skuForm.level"
                label="Level"
                placeholder="e.g. P3"
                density="compact"
              />
            </VCol>
            <VCol cols="6">
              <VTextField
                v-model="skuForm.name_zh"
                label="Name (Chinese)"
                density="compact"
              />
            </VCol>
            <VCol cols="6">
              <VTextField
                v-model="skuForm.name_en"
                label="Name (English)"
                density="compact"
              />
            </VCol>
            <VCol cols="12">
              <VTextField
                v-model="skuForm.schedule_note"
                label="Schedule"
                placeholder="e.g. Tue 18:00-19:30"
                density="compact"
              />
            </VCol>
            <VCol cols="6">
              <VSelect
                v-model="skuForm.location_id"
                :items="locations"
                item-title="name_en"
                item-value="id"
                label="Location"
                density="compact"
                clearable
              />
            </VCol>
            <VCol cols="3">
              <VTextField
                v-model.number="skuForm.capacity"
                label="Capacity"
                type="number"
                density="compact"
              />
            </VCol>
            <VCol cols="3">
              <VTextField
                v-model.number="skuForm.price"
                label="Price"
                type="number"
                density="compact"
              />
            </VCol>
            <VCol cols="12">
              <VCheckbox
                v-model="skuForm.is_active"
                label="Active"
                hide-details
                density="compact"
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
            @click="saveSku"
          >
            Save
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>
