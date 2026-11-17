<script setup lang="ts">
import { useBranding } from '@/composables/useBranding'

export interface LocationExtraForm {
  notes: string
  details_json: string
}

defineProps<{
  form: LocationExtraForm
}>()

const { brand } = useBranding()
</script>

<template>
  <VRow class="mt-1">
    <VCol cols="12">
      <VTextarea
        v-model="form.notes"
        label="Notes"
        rows="3"
        prepend-inner-icon="ri-sticky-note-line"
      />
    </VCol>
    <VCol cols="12">
      <p
        v-if="brand.key === 'cpa'"
        class="text-caption text-medium-emphasis mb-2"
      >
        Debit notes print invoice_payment from this JSON under the total. Leave it out and the note shows a reminder to add it.
      </p>
      <VTextarea
        v-model="form.details_json"
        label="Extra Details (JSON)"
        rows="4"
        hint="Free-form key/value pairs. Example: {&quot;floor&quot;:&quot;2F&quot;,&quot;room&quot;:&quot;A-01&quot;}"
        persistent-hint
        prepend-inner-icon="ri-code-line"
        :rules="[v => {
          if (!v.trim()) return true; try { JSON.parse(v); return true }
          catch { return 'Invalid JSON' }
        }]"
      />
    </VCol>
  </VRow>
</template>
