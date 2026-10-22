<script lang="ts">
export interface InventoryDocAction {
  label: string
  tooltip?: string
  disabled?: boolean
  onClick: () => void
}

export interface InventoryDocMoreItem {
  label: string
  sub?: string
  icon: string
  danger?: boolean
  onClick: () => void
}
</script>

<script setup lang="ts">
defineProps<{
  primary?: InventoryDocAction | null
  secondary?: InventoryDocAction | null
  more?: InventoryDocMoreItem[]
  loading?: boolean
}>()

const menuOpen = ref(false)
</script>

<template>
  <div class="d-flex align-center gap-2">
    <VTooltip
      v-if="secondary"
      :text="secondary.tooltip || ''"
      location="bottom"
      :disabled="!secondary.tooltip"
    >
      <template #activator="{ props }">
        <VBtn
          v-bind="props"
          variant="tonal"
          color="primary"
          size="small"
          :loading="loading"
          :disabled="secondary!.disabled"
          @click="secondary!.onClick()"
        >
          {{ secondary.label }}
        </VBtn>
      </template>
    </VTooltip>
    <VTooltip
      v-if="primary"
      :text="primary.tooltip || ''"
      location="bottom"
      :disabled="!primary.tooltip"
    >
      <template #activator="{ props }">
        <VBtn
          v-bind="props"
          color="primary"
          size="small"
          :loading="loading"
          :disabled="primary!.disabled"
          @click="primary!.onClick()"
        >
          {{ primary.label }}
        </VBtn>
      </template>
    </VTooltip>
    <VMenu
      v-if="more && more.length"
      v-model="menuOpen"
    >
      <template #activator="{ props }">
        <VBtn
          v-bind="props"
          icon="ri-more-2-fill"
          variant="text"
          size="small"
          aria-label="更多操作"
        >
          <VIcon>ri-more-2-fill</VIcon>
          <VTooltip
            activator="parent"
            text="更多操作"
            location="bottom"
          />
        </VBtn>
      </template>
      <VList density="compact">
        <template
          v-for="(item, i) in more"
          :key="item.label"
        >
          <VDivider v-if="item.danger && (i === 0 || !more[i - 1].danger)" />
          <VListItem
            :class="{ 'text-error': item.danger }"
            @click="menuOpen = false; item.onClick()"
          >
            <template #prepend>
              <VIcon
                :icon="item.icon"
                :color="item.danger ? 'error' : undefined"
                size="small"
              />
            </template>
            <VListItemTitle>{{ item.label }}</VListItemTitle>
            <VListItemSubtitle v-if="item.sub">
              {{ item.sub }}
            </VListItemSubtitle>
          </VListItem>
        </template>
      </VList>
    </VMenu>
  </div>
</template>
