<script setup lang="ts">
const props = defineProps<{ status: string }>()

const colors: Record<string, string> = {
  draft: 'secondary',
  ordered: 'info',
  partial: 'warning',
  received: 'success',
  cancelled: 'error',
  confirmed: 'success',
  void: 'error',
}

const color = computed(() => colors[props.status] ?? 'secondary')
</script>

<template>
  <VChip
    :color="color"
    size="small"
    variant="tonal"
    class="text-capitalize"
  >
    {{ status }}
  </VChip>
</template>
