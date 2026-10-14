<script setup lang="ts">
withDefaults(defineProps<{
  text: string
  location?: 'top' | 'bottom' | 'start' | 'end'
  inline?: boolean
}>(), {
  location: 'top',
  inline: false,
})
</script>

<template>
  <VBtn
    icon
    variant="text"
    size="x-small"
    density="comfortable"
    color="medium-emphasis"
    :aria-label="text"
    :class="inline ? 'help-bubble ms-0' : 'help-bubble ms-1'"
  >
    <VIcon
      size="16"
      icon="ri-question-line"
    />
    <VTooltip
      activator="parent"
      :location="location"
      max-width="320"
      open-on-focus
    >
      {{ text }}
    </VTooltip>
  </VBtn>
</template>
