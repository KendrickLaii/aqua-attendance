<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title?: string
    subtitle?: string
    icon?: string
    maxWidth?: number | string
    persistent?: boolean
    actionLabel?: string
    bodyClass?: string
    centered?: boolean
  }>(),
  {
    title: undefined,
    subtitle: undefined,
    icon: undefined,
    maxWidth: 420,
    persistent: false,
    actionLabel: 'Close',
    bodyClass: 'pa-4',
    centered: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  action: []
}>()

const bodyClasses = computed(() => [
  props.bodyClass,
  props.centered ? 'text-center' : undefined,
])

function onAction() {
  emit('action')
}
</script>

<template>
  <VDialog
    :model-value="modelValue"
    :max-width="maxWidth"
    :persistent="persistent"
    scrollable
    @update:model-value="emit('update:modelValue', $event)"
  >
    <VCard>
      <VCardTitle
        v-if="title || icon"
        class="text-h6 py-4 d-flex align-center text-wrap"
      >
        <VIcon
          v-if="icon"
          :icon="icon"
          class="me-2"
        />
        {{ title }}
      </VCardTitle>
      <VCardSubtitle
        v-if="subtitle"
        class="text-wrap px-4 pb-2"
      >
        {{ subtitle }}
      </VCardSubtitle>
      <VDivider v-if="title || icon || subtitle" />
      <slot name="header-after" />
      <VCardText :class="bodyClasses">
        <slot />
      </VCardText>
      <VDivider />
      <DialogFooter>
        <VBtn
          variant="flat"
          color="primary"
          @click="onAction"
        >
          {{ actionLabel }}
        </VBtn>
      </DialogFooter>
    </VCard>
  </VDialog>
</template>
