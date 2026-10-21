<script setup lang="ts">
export interface DocChainStep {
  label: string
  hint?: string
  state: 'done' | 'current' | 'todo' | 'void'
  to?: string
}

defineProps<{ steps: DocChainStep[] }>()
</script>

<template>
  <div class="d-flex align-center flex-wrap gap-1 doc-chain">
    <template
      v-for="(step, i) in steps"
      :key="i"
    >
      <VIcon
        v-if="i > 0"
        icon="ri-arrow-right-s-line"
        size="small"
        class="text-medium-emphasis"
      />
      <VChip
        :color="step.state === 'current' ? 'primary' : step.state === 'done' ? 'success' : step.state === 'void' ? 'error' : undefined"
        :variant="step.state === 'todo' ? 'outlined' : 'tonal'"
        size="small"
        :to="step.to"
        :link="!!step.to"
      >
        {{ step.label }}
        <span
          v-if="step.hint"
          class="ms-1 text-caption"
        >{{ step.hint }}</span>
      </VChip>
    </template>
  </div>
</template>
