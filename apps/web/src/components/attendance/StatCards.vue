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
  >
    <VCol
      v-for="card in cards"
      :key="card.label"
      cols="12"
      sm="6"
      md="3"
    >
      <VCard class="pa-3">
        <div class="d-flex align-center justify-space-between mb-1">
          <div class="text-caption text-medium-emphasis">
            {{ card.label }}
          </div>
          <VAvatar
            :color="card.color"
            variant="tonal"
            size="32"
            rounded
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
          class="text-caption text-medium-emphasis"
        >
          {{ card.hint }}
        </div>
      </VCard>
    </VCol>
  </VRow>
</template>
