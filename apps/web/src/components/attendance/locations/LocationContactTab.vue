<script setup lang="ts">
export interface LocationContactForm {
  address: string
  contact_person: string
  phone: string
  email: string
}

defineProps<{
  form: LocationContactForm
}>()

const { brand } = useBranding()
</script>

<template>
  <VRow class="mt-1">
    <VCol cols="12">
      <VTextField
        v-model="form.address"
        label="Address"
        prepend-inner-icon="ri-road-map-line"
      />
    </VCol>
    <VCol
      cols="12"
      :sm="brand.key === 'cpa' ? 12 : 4"
    >
      <VTextarea
        v-if="brand.key === 'cpa'"
        v-model="form.contact_person"
        label="Contact Person"
        prepend-inner-icon="ri-user-line"
        rows="5"
        maxlength="255"
        counter
        no-resize
      />
      <VTextField
        v-else
        v-model="form.contact_person"
        label="Contact Person"
        prepend-inner-icon="ri-user-line"
      />
    </VCol>
    <VCol
      cols="12"
      :sm="brand.key === 'cpa' ? 6 : 4"
    >
      <VTextField
        v-model="form.phone"
        label="Phone"
        prepend-inner-icon="ri-phone-line"
      />
    </VCol>
    <VCol
      cols="12"
      :sm="brand.key === 'cpa' ? 6 : 4"
    >
      <VTextField
        v-model="form.email"
        label="Email"
        prepend-inner-icon="ri-mail-line"
      />
    </VCol>
  </VRow>
</template>
