<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    confirmLabel?: string
    confirmColor?: string
    loading?: boolean
    error?: string
  }>(),
  {
    confirmLabel: 'Delete',
    confirmColor: 'error',
    loading: false,
    error: '',
  },
)
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: []
  cancel: []
  'clear-error': []
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
    max-width="420"
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
          @click:close="emit('clear-error')"
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
          Cancel
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
