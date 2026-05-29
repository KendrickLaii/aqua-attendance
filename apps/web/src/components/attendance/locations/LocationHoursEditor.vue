<script setup lang="ts">
import { applyHoursPreset, type DaySchedule, type HoursPreset } from '@/utils/locationHours'

const schedule = defineModel<DaySchedule[]>({ required: true })

function onPreset(preset: HoursPreset) {
  applyHoursPreset(schedule.value, preset)
}
</script>

<template>
  <VDivider class="mb-3" />
  <div
    class="d-flex align-center mb-2"
    style="gap:6px;"
  >
    <VIcon
      icon="ri-time-line"
      size="16"
    />
    <span class="text-subtitle-2">Business Hours</span>
  </div>

  <div
    class="d-flex flex-wrap mb-3"
    style="gap:6px;"
  >
    <VBtn
      size="x-small"
      variant="tonal"
      @click="onPreset('weekday')"
    >
      Mon–Fri 9–18
    </VBtn>
    <VBtn
      size="x-small"
      variant="tonal"
      @click="onPreset('sixday')"
    >
      Mon–Sat 9–18
    </VBtn>
    <VBtn
      size="x-small"
      variant="tonal"
      @click="onPreset('allday')"
    >
      All 9–18
    </VBtn>
    <VBtn
      size="x-small"
      variant="tonal"
      color="error"
      @click="onPreset('clear')"
    >
      Clear All
    </VBtn>
  </div>

  <table style="width:100%; border-collapse:separate; border-spacing:0 2px;">
    <tbody>
      <tr
        v-for="d in schedule"
        :key="d.key"
      >
        <td
          style="width:44px; vertical-align:middle;"
          class="text-body-2 font-weight-medium pe-1"
        >
          {{ d.short }}
        </td>
        <td style="width:48px; vertical-align:middle;">
          <VCheckbox
            v-model="d.isOpen"
            density="compact"
            hide-details
            class="ma-0 pa-0"
          />
        </td>
        <td style="vertical-align:middle; padding:2px 0;">
          <div
            v-if="d.isOpen"
            class="d-flex align-center"
            style="gap:4px;"
          >
            <VTextField
              v-model="d.openTime"
              type="time"
              density="compact"
              hide-details
              style="width:130px; min-width:100px;"
            />
            <span class="text-caption px-1">–</span>
            <VTextField
              v-model="d.closeTime"
              type="time"
              density="compact"
              hide-details
              style="width:130px; min-width:100px;"
            />
          </div>
          <span
            v-else
            class="text-caption text-medium-emphasis ps-1"
          >Closed</span>
        </td>
      </tr>
    </tbody>
  </table>
</template>
