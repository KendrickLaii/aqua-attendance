<script setup lang="ts">
import { useAuthenticatedMediaSrc } from '@/composables/useAuthenticatedMediaSrc'

const props = defineProps<{
  url: string | null
}>()

const src = useAuthenticatedMediaSrc(() => props.url)
</script>

<template>
  <VAvatar
    size="40"
    rounded="lg"
    class="item-thumb"
  >
    <VImg
      v-if="url && src"
      :src="src"
      cover
    />
    <VIcon
      v-else
      icon="ri-image-line"
      size="20"
      class="text-medium-emphasis"
    />
  </VAvatar>
</template>

<style scoped>
.item-thumb {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgba(var(--v-theme-on-surface), 0.04);
}
</style>
