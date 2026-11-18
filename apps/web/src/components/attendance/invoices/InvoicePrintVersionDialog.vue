<script setup lang="ts">
import type { TuitionInvoicePrintVersion } from '@/utils/printTuitionInvoice'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'select': [version: TuitionInvoicePrintVersion]
}>()

const open = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})

// Emit synchronously: the parent opens the print window inside this click.
function choose(version: TuitionInvoicePrintVersion) {
  open.value = false
  emit('select', version)
}
</script>

<template>
  <VDialog
    v-model="open"
    max-width="420"
  >
    <VCard>
      <VCardTitle class="text-h6 py-4">
        Print version
      </VCardTitle>
      <VDivider />
      <VCardText class="pa-4 d-flex flex-column gap-3">
        <VBtn
          variant="flat"
          color="primary"
          block
          prepend-icon="ri-printer-line"
          @click="choose('full')"
        >
          Version 1 · Full
        </VBtn>
        <VBtn
          variant="outlined"
          color="primary"
          block
          prepend-icon="ri-printer-line"
          @click="choose('detailed')"
        >
          Version 2 · With price &amp; qty
        </VBtn>
      </VCardText>
      <VDivider />
      <DialogFooter>
        <VBtn
          variant="outlined"
          color="primary"
          @click="open = false"
        >
          Cancel
        </VBtn>
      </DialogFooter>
    </VCard>
  </VDialog>
</template>
