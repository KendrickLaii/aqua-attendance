<script setup lang="ts">
const ATTENDANCE_FORM_FIELD_DEFAULTS = {
  VTextField: { density: 'compact', variant: 'outlined', hideDetails: 'auto' },
  VSelect: { density: 'compact', variant: 'outlined', hideDetails: 'auto' },
  VTextarea: { density: 'compact', variant: 'outlined', hideDetails: 'auto' },
  VSwitch: { density: 'compact', hideDetails: true },
} as const

withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    icon?: string
    maxWidth?: number | string
    saving?: boolean
    error?: string | null
    saveLabel?: string
    bodyClass?: string
    bodyStyle?: string | Record<string, string>
    formDefaults?: boolean
  }>(),
  {
    icon: undefined,
    maxWidth: 500,
    saving: false,
    error: '',
    saveLabel: 'Save',
    bodyClass: 'pa-4',
    bodyStyle: undefined,
    formDefaults: true,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  save: []
  cancel: []
  'clear-error': []
}>()

function close() {
  emit('update:modelValue', false)
  emit('cancel')
}

function onSave() {
  emit('save')
}
</script>

<template>
  <VDialog
    :model-value="modelValue"
    :max-width="maxWidth"
    scrollable
    @update:model-value="emit('update:modelValue', $event)"
  >
    <VCard>
      <VCardTitle class="text-h6 py-4 d-flex align-center">
        <VIcon
          v-if="icon"
          :icon="icon"
          class="me-2"
        />
        {{ title }}
      </VCardTitle>
      <VDivider />
      <slot name="header-after" />
      <VCardText
        :class="bodyClass"
        :style="bodyStyle"
      >
        <VAlert
          v-if="error"
          type="error"
          variant="tonal"
          density="compact"
          class="mb-4"
          closable
          @click:close="emit('clear-error')"
        >
          {{ error }}
        </VAlert>
        <VDefaultsProvider
          v-if="formDefaults"
          :defaults="ATTENDANCE_FORM_FIELD_DEFAULTS"
        >
          <slot />
        </VDefaultsProvider>
        <slot v-else />
      </VCardText>
      <VDivider />
      <DialogFooter>
        <VBtn
          variant="outlined"
          color="primary"
          :disabled="saving"
          @click="close"
        >
          Cancel
        </VBtn>
        <VBtn
          variant="flat"
          color="primary"
          :loading="saving"
          @click="onSave"
        >
          {{ saveLabel }}
        </VBtn>
      </DialogFooter>
    </VCard>
  </VDialog>
</template>
