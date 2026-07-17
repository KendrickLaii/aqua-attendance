<script setup lang="ts">
const page = defineModel<number>('page', { required: true })
const pageSize = defineModel<number>('pageSize', { required: true })

defineProps<{
  totalPages: number
  pageSizeOptions?: number[]
  caption?: string
  showPageLabel?: boolean
}>()

const emit = defineEmits<{
  change: []
}>()

function onPageSizeChange() {
  page.value = 1
  emit('change')
}

function onPageChange() {
  emit('change')
}
</script>

<template>
  <div class="d-flex flex-wrap align-center justify-space-between gap-2 pa-4 pt-0">
    <div class="d-flex align-center gap-2">
      <span
        v-if="showPageLabel !== false"
        class="text-caption text-medium-emphasis"
      >
        <template v-if="caption">
          {{ caption }}
        </template>
        <template v-else>
          Page {{ page }} of {{ totalPages }}
        </template>
      </span>
      <span
        v-else-if="caption"
        class="text-caption text-medium-emphasis"
      >
        {{ caption }}
      </span>
      <VSelect
        v-model="pageSize"
        :items="pageSizeOptions ?? [10, 20, 40, 60, 100]"
        density="compact"
        variant="plain"
        hide-details
        style="max-width: 80px;"
        @update:model-value="onPageSizeChange"
      />
      <span class="text-caption text-medium-emphasis">per page</span>
    </div>
    <VPagination
      v-model="page"
      :length="totalPages"
      :total-visible="5"
      density="compact"
      size="small"
      @update:model-value="onPageChange"
    />
  </div>
</template>
