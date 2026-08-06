<script setup lang="ts">
/**
 * Compact date cell: weekday badge (MON–SUN) + YYYY-MM-DD.
 * Weekend badges use a quieter info tint.
 */
import { computed } from 'vue'
import { getSummaryDateParts } from '@/utils/attendanceDisplay'

const props = defineProps<{
  date: string | null | undefined
}>()

const parts = computed(() => getSummaryDateParts(props.date))
</script>

<template>
  <div
    v-if="parts"
    class="summary-date-cell"
    :title="`${parts.weekday} · ${parts.dateKey}`"
  >
    <span
      class="summary-date-weekday"
      :class="parts.isWeekend ? 'is-weekend' : 'is-weekday'"
    >
      {{ parts.weekday }}
    </span>
    <span class="summary-date-value">{{ parts.dateKey }}</span>
  </div>
  <span
    v-else
    class="text-medium-emphasis"
  >—</span>
</template>

<style scoped lang="scss">
.summary-date-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.summary-date-weekday {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  min-inline-size: 2.4rem;
  padding-block: 2px;
  padding-inline: 6px;
  border-radius: 4px;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  line-height: 1.35;
}

.summary-date-weekday.is-weekday {
  background: rgba(var(--v-theme-on-surface), 0.06);
  color: rgba(var(--v-theme-on-surface), 0.72);
}

.summary-date-weekday.is-weekend {
  background: rgba(var(--v-theme-info), 0.12);
  color: rgb(var(--v-theme-info));
}

.summary-date-value {
  font-variant-numeric: tabular-nums;
  font-weight: 500;
  letter-spacing: -0.01em;
}
</style>
