<script setup lang="ts">
definePage({
  meta: {
    layout: 'blank',
    public: true,
  },
})

const router = useRouter()

onMounted(() => {
  router.replace({ name: 'attendance-login' })
})
</script>

<template>
  <div class="d-flex align-center justify-center" style="min-height: 100vh">
    <VProgressCircular indeterminate color="primary" size="48" />
  </div>
</template>
