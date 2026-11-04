<script setup lang="ts">
withDefaults(defineProps<{
  icon?: string
  text: string
  actionLabel?: string
}>(), {
  icon: 'ri-inbox-line',
  actionLabel: undefined,
})

const emit = defineEmits<{
  action: []
}>()
</script>

<template>
  <div class="d-flex flex-column align-center text-medium-emphasis py-8 gap-3">
    <VIcon
      :icon="icon"
      size="40"
    />
    <div class="text-body-2 text-center">
      {{ text }}
    </div>
    <VBtn
      v-if="actionLabel"
      color="primary"
      size="small"
      prepend-icon="ri-add-line"
      @click="emit('action')"
    >
      {{ actionLabel }}
    </VBtn>
  </div>
</template>
