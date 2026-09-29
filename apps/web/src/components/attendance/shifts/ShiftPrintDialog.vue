<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import type { Unit } from '@/api/attendance/units'
import type { ShiftPrintChoice, ShiftPrintLayout, ShiftPrintPeriod } from '@/utils/printShiftWeek'

type Scope = 'all' | 'scheduled' | 'choose'

const props = defineProps<{
  modelValue: boolean
  period: ShiftPrintPeriod
  month: string
  monthItems: { value: string; title: string }[]

  /** Staff for the chosen period (the page reloads them when the month changes). */
  rows: Unit[]

  /** Shift count per staff id for the chosen period. */
  shiftCounts: Map<string, number>

  /** Open with these staff pre-picked (e.g. the row print button). */
  preselectedIds: string[] | null
  periodLabel: string
  loading: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'update:period': [value: ShiftPrintPeriod]
  'update:month': [value: string]
  'print': [choice: ShiftPrintChoice]
}>()

// Layout and toggles survive reloads, so each office keeps its own defaults (e.g. signature on).
const prefs = useStorage('aqua.shiftPrint.prefs', {
  layout: 'grid' as ShiftPrintLayout,
  showNotes: true,
  showDaysOff: true,
  pageBreak: true,
  signature: false,
}, localStorage, { mergeDefaults: true })

const scope = ref<Scope>('all')
const chosenIds = ref<string[]>([])

const effectiveLayout = computed<ShiftPrintLayout>(() => (props.period === 'month' ? 'personal' : prefs.value.layout))

watch(() => props.modelValue, open => {
  if (!open)
    return
  if (props.preselectedIds?.length) {
    scope.value = 'choose'
    prefs.value.layout = 'personal'
    chosenIds.value = [...props.preselectedIds]
  }
})

const scheduledRows = computed(() => props.rows.filter(u => (props.shiftCounts.get(u.id) ?? 0) > 0))

const selectedIds = computed(() => {
  if (scope.value === 'all')
    return props.rows.map(u => u.id)
  if (scope.value === 'scheduled')
    return scheduledRows.value.map(u => u.id)

  // Keep grid order rather than click order.
  return props.rows.filter(u => chosenIds.value.includes(u.id)).map(u => u.id)
})

const selectedShiftCount = computed(() =>
  selectedIds.value.reduce((sum, id) => sum + (props.shiftCounts.get(id) ?? 0), 0),
)

const staffItems = computed(() =>
  props.rows.map(u => ({
    value: u.id,
    title: u.full_name,
    subtitle: `${u.code} · ${props.shiftCounts.get(u.id) ?? 0} shifts`,
  })),
)

const periods: { value: ShiftPrintPeriod; title: string; text: string; icon: string }[] = [
  { value: 'week', title: 'Week', text: '印而家顯示緊嗰 7 日', icon: 'ri-calendar-2-line' },
  { value: 'month', title: 'Month', text: '揀一個月，逐日列出每更', icon: 'ri-calendar-line' },
]

const layouts: { value: ShiftPrintLayout; title: string; text: string; icon: string }[] = [
  { value: 'grid', title: 'Week grid', text: '所有人擠喺一張紙 · A4 橫向', icon: 'ri-layout-grid-line' },
  { value: 'personal', title: 'Personal schedule', text: '每個員工一張 · A4 直向', icon: 'ri-file-user-line' },
]

const toggles = computed(() => [
  { key: 'showNotes', label: 'Notes', hint: '每更下面印埋備註', icon: 'ri-sticky-note-line', show: true },
  { key: 'showDaysOff', label: 'Days off', hint: '冇更嗰日印「休」', icon: 'ri-cup-line', show: effectiveLayout.value === 'personal' },
  { key: 'pageBreak', label: 'New page per staff', hint: '每個員工由新一頁開始', icon: 'ri-file-copy-2-line', show: effectiveLayout.value === 'personal' },
  { key: 'signature', label: 'Signature line', hint: '頁尾留位俾員工簽名確認', icon: 'ri-quill-pen-line', show: effectiveLayout.value === 'personal' },
] as const)

function close() {
  emit('update:modelValue', false)
}

function print() {
  if (!selectedIds.value.length || props.loading)
    return
  emit('print', {
    layout: effectiveLayout.value,
    period: props.period,
    staffIds: selectedIds.value,
    showNotes: prefs.value.showNotes,
    showDaysOff: prefs.value.showDaysOff,
    pageBreak: prefs.value.pageBreak,
    signature: prefs.value.signature,
  })
}
</script>

<template>
  <VDialog
    :model-value="modelValue"
    max-width="580"
    scrollable
    @update:model-value="emit('update:modelValue', $event)"
  >
    <VCard
      title="Print shift schedule"
      :subtitle="periodLabel"
    >
      <VCardText>
        <!-- Period -->
        <div class="text-overline text-medium-emphasis mb-1">
          Period
        </div>
        <div class="period-options mb-2">
          <button
            v-for="p in periods"
            :key="p.value"
            type="button"
            class="layout-option"
            :class="{ active: period === p.value }"
            :aria-pressed="period === p.value"
            @click="emit('update:period', p.value)"
          >
            <VIcon
              :icon="p.icon"
              size="22"
              class="mb-1"
            />
            <span class="font-weight-medium">{{ p.title }}</span>
            <span class="text-caption text-medium-emphasis">{{ p.text }}</span>
          </button>
        </div>
        <div
          v-if="period === 'month'"
          class="d-flex align-center gap-3 mb-5"
        >
          <VSelect
            :model-value="month"
            :items="monthItems"
            label="Month"
            density="compact"
            hide-details
            class="month-select"
            @update:model-value="emit('update:month', $event)"
          />
          <VProgressCircular
            v-if="loading"
            indeterminate
            size="20"
            width="2"
            color="primary"
          />
        </div>
        <div
          v-else
          class="mb-5"
        />

        <!-- Layout -->
        <div class="text-overline text-medium-emphasis mb-1">
          Layout
        </div>
        <div class="layout-options mb-1">
          <button
            v-for="l in layouts"
            :key="l.value"
            type="button"
            class="layout-option"
            :class="{ active: effectiveLayout === l.value }"
            :disabled="period === 'month' && l.value === 'grid'"
            :aria-pressed="effectiveLayout === l.value"
            @click="prefs.layout = l.value"
          >
            <VIcon
              :icon="l.icon"
              size="22"
              class="mb-1"
            />
            <span class="font-weight-medium">{{ l.title }}</span>
            <span class="text-caption text-medium-emphasis">{{ l.text }}</span>
          </button>
        </div>
        <p
          class="text-caption text-medium-emphasis mb-5"
          :class="{ invisible: period !== 'month' }"
        >
          月份會用個人更表印，每個星期有小計，月尾有全月總數。
        </p>

        <!-- Staff -->
        <div class="text-overline text-medium-emphasis mb-1">
          Staff
        </div>
        <VRadioGroup
          v-model="scope"
          density="compact"
          hide-details
          class="mb-2"
        >
          <VRadio
            value="all"
            :label="`All staff shown (${rows.length})`"
          />
          <VRadio
            value="scheduled"
            :label="`Only staff with shifts this ${period} (${scheduledRows.length})`"
          />
          <VRadio
            value="choose"
            label="Choose staff…"
          />
        </VRadioGroup>
        <VAutocomplete
          v-if="scope === 'choose'"
          v-model="chosenIds"
          :items="staffItems"
          label="Staff to print"
          multiple
          chips
          closable-chips
          clearable
          density="comfortable"
          class="mb-2"
        />

        <!-- Toggles -->
        <div class="text-overline text-medium-emphasis mt-3 mb-1">
          Include
        </div>
        <div class="toggle-list">
          <template
            v-for="t in toggles"
            :key="t.key"
          >
            <label
              v-if="t.show"
              class="toggle-row"
              :class="{ on: prefs[t.key] }"
            >
              <VIcon
                :icon="t.icon"
                size="20"
                class="toggle-icon"
              />
              <span class="toggle-text">
                <span class="text-body-2 font-weight-medium">{{ t.label }}</span>
                <span class="text-caption text-medium-emphasis">{{ t.hint }}</span>
              </span>
              <VSwitch
                v-model="prefs[t.key]"
                color="primary"
                density="compact"
                hide-details
                inset
                :aria-label="t.label"
              />
            </label>
          </template>
        </div>
        <p class="text-caption text-medium-emphasis mt-2 mb-0">
          版面同開關會記住喺呢部機。
        </p>
      </VCardText>

      <VCardActions>
        <span class="text-body-2 text-medium-emphasis ps-2">
          {{ selectedIds.length }} staff · {{ selectedShiftCount }} shift{{ selectedShiftCount === 1 ? '' : 's' }}
        </span>
        <VSpacer />
        <VBtn
          variant="text"
          @click="close"
        >
          Cancel
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-printer-line"
          :disabled="!selectedIds.length || loading"
          @click="print"
        >
          Print
        </VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>

<style scoped>
.month-select {
  max-inline-size: 200px;
}

.period-options,
.layout-options {
  display: grid;
  gap: 10px;
  grid-template-columns: 1fr 1fr;
}

.layout-option {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  padding: 12px;
  text-align: start;
  transition: border-color 0.12s ease, box-shadow 0.12s ease;
}

.layout-option.active {
  border-color: rgb(var(--v-theme-primary));
  box-shadow: 0 0 0 1px rgb(var(--v-theme-primary));
}

.layout-option.active .v-icon {
  color: rgb(var(--v-theme-primary));
}

.layout-option:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.layout-option:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
}

.invisible {
  visibility: hidden;
}

.toggle-list {
  overflow: hidden;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
}

.toggle-row {
  display: flex;
  align-items: center;
  cursor: pointer;
  gap: 12px;
  padding-block: 4px;
  padding-inline: 12px 4px;
  transition: background-color 0.12s ease;
}

.toggle-row + .toggle-row {
  border-block-start: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.toggle-row.on {
  background: rgba(var(--v-theme-primary), 0.05);
}

.toggle-row.on .toggle-icon {
  color: rgb(var(--v-theme-primary));
}

.toggle-text {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-inline-size: 0;
}

@media (prefers-reduced-motion: reduce) {
  .layout-option,
  .toggle-row {
    transition: none;
  }
}
</style>
