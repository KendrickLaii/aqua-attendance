<script setup lang="ts">
/**
 * Marker for days / events closed by day-boundary auto checkout (23:59).
 * Pass either event `source` or summary `attendance_notes`.
 */
import { computed } from 'vue'
import {
  isAutoCheckoutDayNotes,
  isAutoCheckoutSource,
  isDayBoundaryCheckoutTime,
} from '@/utils/attendanceDisplay'

const props = withDefaults(defineProps<{
  source?: string | null
  notes?: string | null
  /** Summary last_check_out — used when notes were not persisted yet */
  lastCheckOut?: string | null
  size?: 'x-small' | 'small' | 'default'
}>(), {
  size: 'x-small',
})

const visible = computed(() =>
  isAutoCheckoutSource(props.source)
  || isAutoCheckoutDayNotes(props.notes)
  || isDayBoundaryCheckoutTime(props.lastCheckOut),
)

const tooltip = computed(() =>
  props.notes?.trim()
  || 'Day-boundary auto checkout (23:59)',
)
</script>

<template>
  <VChip
    v-if="visible"
    color="warning"
    :size="size"
    label
    prepend-icon="ri-time-line"
    :title="tooltip"
  >
    Auto checkout
  </VChip>
</template>
