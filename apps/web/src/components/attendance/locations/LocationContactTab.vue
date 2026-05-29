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
      sm="4"
    >
      <VTextField
        v-model="form.contact_person"
        label="Contact Person"
        prepend-inner-icon="ri-user-line"
      />
    </VCol>
    <VCol
      cols="12"
      sm="4"
    >
      <VTextField
        v-model="form.phone"
        label="Phone"
        prepend-inner-icon="ri-phone-line"
      />
    </VCol>
    <VCol
      cols="12"
      sm="4"
    >
      <VTextField
        v-model="form.email"
        label="Email"
        prepend-inner-icon="ri-mail-line"
      />
    </VCol>
  </VRow>
</template>
