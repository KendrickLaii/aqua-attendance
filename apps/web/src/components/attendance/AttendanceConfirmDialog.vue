<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    confirmLabel?: string
    cancelLabel?: string
    confirmColor?: string
    loading?: boolean
    error?: string
    maxWidth?: number | string
  }>(),
  {
    confirmLabel: 'Delete',
    cancelLabel: 'Cancel',
    confirmColor: 'error',
    loading: false,
    error: '',
    maxWidth: 420,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: []
  cancel: []
  clearError: []
}>()

function close() {
  emit('update:modelValue', false)
  emit('cancel')
}

function onConfirm() {
  emit('confirm')
}
</script>

<template>
  <VDialog
    :model-value="modelValue"
    :max-width="maxWidth"
    persistent
    @update:model-value="emit('update:modelValue', $event)"
  >
    <VCard>
      <VCardTitle class="text-h6 py-4">
        {{ title }}
      </VCardTitle>
      <VDivider />
      <VCardText class="pa-4">
        <VAlert
          v-if="error"
          type="error"
          variant="tonal"
          density="compact"
          class="mb-3"
          closable
          @click:close="emit('clearError')"
        >
          {{ error }}
        </VAlert>
        <slot />
      </VCardText>
      <VDivider />
      <DialogFooter>
        <VBtn
          variant="outlined"
          color="primary"
          :disabled="loading"
          @click="close"
        >
          {{ cancelLabel }}
        </VBtn>
        <VBtn
          variant="flat"
          :color="confirmColor"
          :loading="loading"
          @click="onConfirm"
        >
          {{ confirmLabel }}
        </VBtn>
      </DialogFooter>
    </VCard>
  </VDialog>
</template>
