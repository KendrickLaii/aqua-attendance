<script setup lang="ts">
import type { CourseSku, CourseSpu } from '@/api/attendance/courses'
import type { LocationItem } from '@/api/attendance/locations'
import type { Unit } from '@/api/attendance/units'
import { billingUnitShortLabel } from '@/utils/courseEnrollmentDisplay'
import { meetingDaysLabel } from '@/utils/courseRosterDisplay'
import { type TableSort, compareSortValues, sortIconFor, toggleSort } from '@/utils/tableSort'

const props = defineProps<{
  spus: CourseSpu[]
  skus: CourseSku[]
  locations: LocationItem[]
  staffUnits: Unit[]
  selectedSpuId: string | null
  rosterSkuId: string | null
  catalogPanel: 'courses' | 'offerings' | undefined
  inClassCounts: Record<string, number>
}>()

const emit = defineEmits<{
  'update:catalogPanel': [value: 'courses' | 'offerings' | undefined]
  'select-course': [spuId: string]
  'select-class': [skuId: string]
  'create-sku': []
  'edit-spu': [spu: CourseSpu]
  'delete-spu': [spu: CourseSpu]
  'edit-sku': [sku: CourseSku]
  'delete-sku': [sku: CourseSku]
}>()

const coursesScroll = ref<HTMLElement | null>(null)
const offeringsScroll = ref<HTMLElement | null>(null)

type SpuSortKey = 'code' | 'name' | 'subject'
type SkuSortKey = 'code' | 'name' | 'billing' | 'price' | 'students'

const spuSort = reactive<TableSort<SpuSortKey>>({ key: 'code', dir: 1 })
const skuSort = reactive<TableSort<SkuSortKey>>({ key: 'code', dir: 1 })

const panelModel = computed({
  get: () => props.catalogPanel,
  set: value => emit('update:catalogPanel', value),
})

const selectedSpu = computed(() => props.spus.find(s => s.id === props.selectedSpuId) ?? null)
const rosterSku = computed(() => props.skus.find(k => k.id === props.rosterSkuId) ?? null)

const sortedSpus = computed(() => {
  const pick: Record<SpuSortKey, (s: CourseSpu) => string | null> = {
    code: s => s.code,
    name: s => s.name_zh,
    subject: s => s.subject,
  }

  return [...props.spus].sort((a, b) => compareSortValues(pick[spuSort.key](a), pick[spuSort.key](b)) * spuSort.dir)
})

const skusForSelectedSpu = computed(() => {
  const pick: Record<SkuSortKey, (k: CourseSku) => string | number | null> = {
    code: k => k.code,
    name: k => k.name_zh,
    billing: k => k.billing_unit,
    price: k => k.price,
    students: k => props.inClassCounts[k.id] ?? 0,
  }

  return props.skus
    .filter(k => k.spu_id === props.selectedSpuId)
    .sort((a, b) => compareSortValues(pick[skuSort.key](a), pick[skuSort.key](b)) * skuSort.dir)
})

function inClassLabel(sku: CourseSku): string {
  const count = props.inClassCounts[sku.id] ?? 0
  if (sku.capacity != null)
    return `${count} / ${sku.capacity}`

  return String(count)
}

const locationName = (id: string | null) => props.locations.find(l => l.id === id)?.name_en ?? '—'
const staffName = (id: string | null | undefined) => props.staffUnits.find(u => u.id === id)?.full_name ?? ''

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

watch([() => props.selectedSpuId, () => props.rosterSkuId], async () => {
  await nextTick()
  scrollCatalogSelection()
})

watch(() => props.catalogPanel, async () => {
  await nextTick()
  requestAnimationFrame(() => scrollCatalogSelection())
})

defineExpose({ scrollCatalogSelection })
</script>

<template>
  <VExpansionPanels
    v-model="panelModel"
    variant="accordion"
    class="catalog-panels mb-4"
    :mandatory="false"
  >
    <VExpansionPanel value="courses">
      <template #title>
        <div class="catalog-panel__heading">
          <div class="text-subtitle-1">
            Courses
          </div>
          <div class="text-caption text-medium-emphasis">
            <template v-if="selectedSpu">
              {{ selectedSpu.code }} · {{ selectedSpu.name_zh }}
            </template>
            <template v-else>
              {{ sortedSpus.length }} course{{ sortedSpus.length === 1 ? '' : 's' }}
            </template>
          </div>
        </div>
      </template>
      <template #text>
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
                  class="sortable col-code"
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
                @click="emit('select-course', spu.id)"
              >
                <td class="col-code">{{ spu.code }}</td>
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
                    @click.stop="emit('edit-spu', spu)"
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
                    @click.stop="emit('delete-spu', spu)"
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
      </template>
    </VExpansionPanel>

    <VExpansionPanel value="offerings">
      <template #title>
        <div class="catalog-panel__heading">
          <div class="text-subtitle-1">
            Class Offerings
          </div>
          <div class="text-caption text-medium-emphasis">
            <template v-if="rosterSku">
              {{ rosterSku.code }} · {{ rosterSku.name_zh }}
            </template>
            <template v-else-if="selectedSpu">
              {{ skusForSelectedSpu.length }} class{{ skusForSelectedSpu.length === 1 ? '' : 'es' }} in {{ selectedSpu.name_zh }}
            </template>
            <template v-else>
              Pick a course first
            </template>
          </div>
        </div>
      </template>
      <template #text>
        <div class="catalog-toolbar">
          <span class="catalog-toolbar__label">
            <template v-if="selectedSpu">
              {{ selectedSpu.code }} · {{ selectedSpu.name_zh }}
            </template>
            <template v-else>
              Pick a course first
            </template>
          </span>
          <VBtn
            size="small"
            color="primary"
            prepend-icon="ri-add-line"
            :disabled="!selectedSpuId"
            @click="emit('create-sku')"
          >
            Add Class
          </VBtn>
        </div>
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
                  class="sortable col-code"
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
                  @click="toggleSort(skuSort, 'students')"
                >
                  In class
                  <VIcon
                    :icon="sortIconFor(skuSort, 'students')"
                    size="14"
                    class="ms-1 sort-icon"
                    :class="{ 'sort-icon--active': skuSort.key === 'students' }"
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
                @click="emit('select-class', sku.id)"
              >
                <td class="col-code">{{ sku.code }}</td>
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
                <td>{{ billingUnitShortLabel(sku.billing_unit ?? 'monthly') }}</td>
                <td
                  class="text-end tabular-nums"
                  :title="`${props.inClassCounts[sku.id] ?? 0} in class`"
                >
                  {{ inClassLabel(sku) }}
                </td>
                <td class="text-end">
                  {{ sku.price != null ? sku.price : '—' }}
                </td>
                <td class="text-end col-actions">
                  <VBtn
                    icon
                    size="x-small"
                    variant="text"
                    @click.stop="emit('edit-sku', sku)"
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
                    @click.stop="emit('delete-sku', sku)"
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
                  Select a course above to see its class offerings.
                </td>
              </tr>
            </tbody>
          </VTable>
        </div>
      </template>
    </VExpansionPanel>
  </VExpansionPanels>
</template>

<style scoped>
.catalog-panels :deep(.v-expansion-panel-title) {
  align-items: center;
  min-height: 64px;
  padding-inline: 16px 12px;
}

.catalog-panels :deep(.v-expansion-panel-text__wrapper) {
  padding: 0;
}

.catalog-panel__heading {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  min-width: 0;
  flex: 1 1 auto;
  padding-inline-end: 12px;
}

.catalog-panel__heading .text-caption {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.catalog-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 48px;
  padding: 8px 16px;
  border-block-end: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.catalog-toolbar__label {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.8125rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.catalog-scroll {
  max-height: 18rem;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.catalog-scroll :deep(.v-table) {
  width: 100%;
}

.catalog-scroll :deep(.v-table__wrapper) {
  overflow: visible;
}

.catalog-scroll :deep(table) {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}

.catalog-scroll :deep(.col-code) {
  width: 1%;
  white-space: nowrap;
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

.catalog-cell > .catalog-cell__primary {
  flex: 1 1 auto;
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

.offerings-table :deep(.col-actions) {
  position: sticky;
  inset-inline-end: 0;
  z-index: 1;
  white-space: nowrap;
  width: 1%;
  background: rgb(var(--v-theme-surface));
  border-inline-start: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.offerings-table :deep(tr.bg-primary-lighten-5 td.col-actions) {
  background:
    linear-gradient(rgba(var(--v-theme-primary), 0.08), rgba(var(--v-theme-primary), 0.08)),
    rgb(var(--v-theme-surface));
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
</style>
