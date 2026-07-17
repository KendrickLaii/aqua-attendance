<script setup lang="ts">
export interface StatCardItem {
  label: string
  value: string
  hint?: string
  icon: string
  color: string
}

defineProps<{
  cards: StatCardItem[]
}>()
</script>

<template>
  <VRow
    class="mb-3"
    dense
    align="stretch"
  >
    <VCol
      v-for="card in cards"
      :key="card.label"
      cols="12"
      sm="6"
      md="3"
      class="d-flex"
    >
      <VCard class="pa-3 w-100 d-flex flex-column">
        <div class="d-flex align-center justify-space-between mb-1">
          <div class="text-caption text-medium-emphasis text-truncate me-2">
            {{ card.label }}
          </div>
          <VAvatar
            :color="card.color"
            variant="tonal"
            size="32"
            rounded
            class="flex-shrink-0"
          >
            <VIcon
              :icon="card.icon"
              size="18"
            />
          </VAvatar>
        </div>
        <div
          class="text-h6 font-weight-bold"
          :class="`text-${card.color}`"
        >
          {{ card.value }}
        </div>
        <div
          v-if="card.hint"
          class="text-caption text-medium-emphasis mt-auto pt-1"
          style="min-height: 2.5em; line-height: 1.25;"
        >
          {{ card.hint }}
        </div>
      </VCard>
    </VCol>
  </VRow>
</template>
