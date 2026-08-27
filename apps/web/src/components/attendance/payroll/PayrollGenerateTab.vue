<script setup lang="ts">
import type { Unit } from '@/api/attendance/units'

const props = defineProps<{
  monthLabel: string
  units: Unit[]
  unitsLoading: boolean
  unitsError: string
  selectedIds: string[]
  search: string
  showAllStaff: boolean
  staffWithSummariesCount: number
  generating: boolean
  generateError: string
}>()

const emit = defineEmits<{
  'update:search': [value: string]
  'update:showAllStaff': [value: boolean]
  'update:selectedIds': [value: string[]]
  generate: []
}>()

const searchModel = computed({
  get: () => props.search,
  set: (value: string) => emit('update:search', value ?? ''),
})

const showAllStaffModel = computed({
  get: () => props.showAllStaff,
  set: (value: boolean) => emit('update:showAllStaff', value),
})

const filteredUnits = computed(() => {
  const q = props.search.trim().toLowerCase()
  if (!q)
    return props.units

  return props.units.filter(u =>
    u.full_name.toLowerCase().includes(q) || u.code.toLowerCase().includes(q),
  )
})

const allSelected = computed({
  get: () => props.units.length > 0 && props.selectedIds.length === props.units.length,
  set: (val: boolean) => {
    emit('update:selectedIds', val ? props.units.map(u => u.id) : [])
  },
})

const selectedCount = computed(() => props.selectedIds.length)

function toggleUnit(id: string) {
  const next = [...props.selectedIds]
  const idx = next.indexOf(id)
  if (idx === -1)
    next.push(id)
  else
    next.splice(idx, 1)

  emit('update:selectedIds', next)
}
</script>

<template>
  <VCard class="payroll-wizard">
    <div class="pa-4 pa-md-6">
      <div class="d-flex align-center gap-3 mb-6">
        <VAvatar
          color="primary"
          variant="tonal"
          rounded
        >
          <VIcon icon="ri-magic-line" />
        </VAvatar>
        <div>
          <h2 class="text-h6 mb-0">
            Generate payroll
          </h2>
          <p class="text-body-2 text-medium-emphasis mb-0">
            Create or refresh slips from attendance summaries for {{ monthLabel }}.
            You will land on Review next to edit and approve.
          </p>
        </div>
      </div>

      <VAlert
        v-if="generateError"
        type="error"
        variant="tonal"
        density="compact"
        class="mb-4"
      >
        {{ generateError }}
      </VAlert>

      <VCard
        variant="outlined"
        class="mb-4"
      >
        <VCardItem>
          <template #prepend>
            <VAvatar
              color="primary"
              variant="tonal"
              size="36"
              rounded
            >
              <VIcon
                icon="ri-group-line"
                size="20"
              />
            </VAvatar>
          </template>
          <VCardTitle class="text-subtitle-1">
            Staff
          </VCardTitle>
          <VCardSubtitle>
            {{ units.length }} shown · {{ selectedCount }} selected
            <template v-if="!showAllStaff">
              · {{ staffWithSummariesCount }} with summaries this month
            </template>
          </VCardSubtitle>
        </VCardItem>
        <VCardText>
          <div class="d-flex align-center gap-3 mb-3 flex-wrap">
            <VTextField
              v-model="searchModel"
              label="Search by name or code"
              density="compact"
              prepend-inner-icon="ri-search-line"
              clearable
              hide-details
              style="max-inline-size: 280px;"
            />
            <VCheckbox
              v-model="allSelected"
              label="Select all"
              density="compact"
              hide-details
              color="primary"
            />
            <VCheckbox
              v-model="showAllStaffModel"
              label="Show all staff"
              density="compact"
              hide-details
              color="secondary"
            />
          </div>

          <VProgressLinear
            v-if="unitsLoading"
            indeterminate
            color="primary"
            class="mb-2"
          />
          <VAlert
            v-else-if="unitsError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-2"
          >
            {{ unitsError }}
          </VAlert>

          <div class="unit-list">
            <VListItem
              v-for="u in filteredUnits"
              :key="u.id"
              :title="u.full_name"
              :subtitle="u.code"
              density="comfortable"
              class="unit-list-item"
              :active="selectedIds.includes(u.id)"
              color="primary"
              @click="toggleUnit(u.id)"
            >
              <template #prepend>
                <VCheckbox
                  :model-value="selectedIds.includes(u.id)"
                  density="comfortable"
                  hide-details
                  color="primary"
                  @click.stop="toggleUnit(u.id)"
                />
              </template>
              <template #append>
                <VChip
                  size="x-small"
                  variant="tonal"
                  color="primary"
                  prepend-icon="ri-user-line"
                  label
                >
                  Staff
                </VChip>
              </template>
            </VListItem>
            <div
              v-if="!unitsLoading && filteredUnits.length === 0"
              class="text-center text-medium-emphasis py-8"
            >
              <template v-if="!showAllStaff && search.trim() === ''">
                No staff with summaries for {{ monthLabel }}.
                Generate Summaries first, or enable Show all staff.
              </template>
              <template v-else>
                No staff units found.
              </template>
            </div>
          </div>
        </VCardText>
      </VCard>

      <div class="d-flex align-center justify-space-between flex-wrap gap-3 mt-2">
        <div class="text-caption text-medium-emphasis">
          <VIcon
            icon="ri-information-line"
            size="14"
            class="me-1"
          />
          Uses summaries for {{ monthLabel }}. Approved and paid slips are left unchanged.
        </div>
        <VBtn
          color="primary"
          size="large"
          :loading="generating"
          :disabled="selectedCount === 0"
          prepend-icon="ri-magic-line"
          @click="emit('generate')"
        >
          Generate payroll
        </VBtn>
      </div>
    </div>
  </VCard>
</template>

<style scoped lang="scss">
.payroll-wizard {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.unit-list {
  max-block-size: 340px;
  overflow-y: auto;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
}

.unit-list-item {
  cursor: pointer;
}
</style>
