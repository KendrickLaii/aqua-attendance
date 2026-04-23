<script setup lang="ts">
export interface TaxMenuItem {
  id: number
  scheduleNumber: number
  isIncluded: boolean
  analysis: string
}

const props = defineProps<{
  taxMenu: TaxMenuItem[]
}>()

const emit = defineEmits<{
  (e: 'tax-menu-update', value: TaxMenuItem[]): void
  (e: 'tab-change', value: number): void
}>()

const pinned = ref(true)
const drawerHovered = ref(false)
const menuOpen = ref(false)
const showDetails = computed(() => pinned.value || menuOpen.value || drawerHovered.value)

const visibleTabs = computed(() => props.taxMenu.filter(item => item.isIncluded))

const toggleItem = (item: TaxMenuItem) => {
  item.isIncluded = !item.isIncluded
  let seq = 1
  props.taxMenu.forEach(menuItem => {
    if (menuItem.isIncluded) menuItem.scheduleNumber = seq++
  })
  emit('tax-menu-update', [...props.taxMenu])
}

const ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']
const getDisplaySchedule = (item: TaxMenuItem) =>
  ROMAN[item.scheduleNumber - 1] ?? item.scheduleNumber.toString()

const selectedTab = ref<TaxMenuItem | null>(visibleTabs.value[0] ?? null)

watch(visibleTabs, tabs => {
  if (!selectedTab.value || !tabs.includes(selectedTab.value)) {
    selectedTab.value = tabs[0] ?? null
    emit('tab-change', selectedTab.value?.id ?? -1)
  }
})
</script>

<template>
<VNavigationDrawer
    :rail="!pinned"
    :expand-on-hover="!pinned"
    permanent
    width="210"
    rail-width="48"
    location="start"
    class="tax-menu-drawer"
    :style="{ width: (pinned || menuOpen || drawerHovered) ? '210px' : '48px' }"
  >
    <div
      class="tax-menu-drawer-inner"
      :class="{ 'tax-menu-drawer-inner--rail': !showDetails }"
      @mouseenter="drawerHovered = true"
      @mouseleave="drawerHovered = false"
    >
      <div class="tax-menu-header d-flex align-center pa-2 justify-space-between">
        <div class="tax-menu-title-wrap" :class="{ 'tax-menu-title-wrap--visible': showDetails }">
          <span class="tax-menu-title text-body-2">Tax Computation</span>
        </div>
        <div class="tax-menu-actions d-flex align-center gap-1">
          <IconBtn size="small" @click="pinned = !pinned">
                <VIcon :icon="pinned ? 'ri-pushpin-fill' : 'ri-pushpin-2-line'" />
              </IconBtn>
          <VMenu v-model="menuOpen" :close-on-content-click="false">
            <template #activator="{ props: menuProps }">
              <IconBtn v-bind="menuProps" size="small">
                <VIcon icon="ri-settings-3-line" />
              </IconBtn>
            </template>
            <VList density="compact">
              <VListSubheader>Section Control</VListSubheader>
              <VDivider />
              <VListItem
                v-for="item in taxMenu"
                :key="item.id"
                @click="toggleItem(item)"
              >
                <template #prepend>
                  <VListItemAction start>
                    <VCheckboxBtn :model-value="item.isIncluded" density="compact"/>
                  </VListItemAction>
                </template>
                <template #title>
                  <span class="cursor-pointer">{{ item.analysis }}</span>
                </template>
              </VListItem>
            </VList>
          </VMenu>
        </div>
      </div>

      <VDivider />

      <VTabs v-model="selectedTab" direction="vertical" slider-color="primary" class="tax-tabs flex-grow-1" @update:model-value="emit('tab-change', selectedTab?.id ?? 0)">
      <VTab
        v-for="(tab, index) in visibleTabs"
        :key="tab.id"
        class="tax-tab w-100"
        :value="tab"
      >
        <div class="tax-tab-content w-100 d-flex flex-column align-start text-left gap-1">
          <span class="tax-tab-id">{{ getDisplaySchedule(tab) }}</span>
          <span v-if="showDetails" class="tax-tab-analysis">{{ tab.analysis }}</span>
        </div>
      </VTab>
      </VTabs>
    </div>
  </VNavigationDrawer>
</template>

<style lang="scss" scoped>
.tax-menu-drawer {
  :deep(.v-navigation-drawer__content) {
    display: flex;
    flex-direction: column;
  }
}

.tax-menu-drawer-inner {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* title area: use max-width + opacity transition, avoid setting button jump to the right */
.tax-menu-title-wrap {
  max-width: 0;
  overflow: hidden;
  opacity: 0;
  transition: max-width 0.25s ease, opacity 0.25s ease;
}
.tax-menu-title-wrap--visible {
  max-width: 180px;
  opacity: 1;
}
.tax-menu-title {
  white-space: nowrap;
  max-width: 180px;
}
.tax-menu-actions {
  flex-shrink: 0;
  transition: margin-left 0.25s ease;
}

.tax-tabs {
  :deep(.v-tab__slider) {
    left: 0 !important;
  }
}

.tax-tab {
  justify-content: flex-start;
  min-height: 65px;
  height: auto;
  padding-block: 6px;
}

.tax-tab-id {
  font-size: 0.82rem;
  line-height: 1;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* center the roman number when collapsed: tab and content area take up the full rail width, text is centered */
.tax-menu-drawer-inner--rail.tax-menu-drawer-inner {
  :deep(.v-tab) {
    min-width: 100%;
    justify-content: center;
  }
}

.tax-tab-analysis {
  font-size: 0.82rem;
  line-height: 1;
  white-space: normal;
  /* same width with drawer expanded, avoid re-layout when hover */
  width: 170px;
  min-width: 170px;
  max-width: 170px;
}

.v-tab-item--selected {
  background-color: rgba(var(--v-theme-primary), 0.1);
}
</style>
