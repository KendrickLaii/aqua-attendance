<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    confirmLabel?: string
    cancelLabel?: string
    confirmColor?: string
    tone?: 'danger' | 'warning' | 'info'
    details?: string[]
    loading?: boolean
    error?: string
    maxWidth?: number | string
  }>(),
  {
    confirmLabel: 'Delete',
    cancelLabel: 'Cancel',
    confirmColor: 'error',
    tone: undefined,
    details: () => [],
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

const effectiveTone = computed(() =>
  props.tone ?? (props.confirmColor === 'error' ? 'danger' : 'info'),
)

const toneMeta = computed(() => {
  switch (effectiveTone.value) {
    case 'danger':
      return { icon: 'ri-error-warning-line', color: 'error' }
    case 'warning':
      return { icon: 'ri-alert-line', color: 'warning' }
    default:
      return { icon: 'ri-question-line', color: 'primary' }
  }
})

const effectiveConfirmColor = computed(() => (props.tone ? toneMeta.value.color : props.confirmColor))

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
      <VCardTitle class="d-flex align-center gap-3 py-4">
        <VAvatar
          :color="toneMeta.color"
          variant="tonal"
          size="36"
        >
          <VIcon :icon="toneMeta.icon" />
        </VAvatar>
        <span class="text-h6">{{ title }}</span>
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
          aria-live="polite"
          @click:close="emit('clearError')"
        >
          {{ error }}
        </VAlert>
        <slot />
        <div
          v-if="details.length"
          class="mt-3"
        >
          <div class="text-caption text-medium-emphasis mb-1">
            會發生什麼 What will happen:
          </div>
          <ul class="ps-5 text-body-2">
            <li
              v-for="(d, i) in details"
              :key="i"
            >
              {{ d }}
            </li>
          </ul>
        </div>
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
          :color="effectiveConfirmColor"
          :loading="loading"
          @click="onConfirm"
        >
          {{ confirmLabel }}
        </VBtn>
      </DialogFooter>
    </VCard>
  </VDialog>
</template>
