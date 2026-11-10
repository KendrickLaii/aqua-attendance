<script setup lang="ts">
import {
  type InventoryBrand,
  type InventoryCategory,
  listInventoryBrands,
  listInventoryCategories,
} from '@/api/attendance/inventory'
import InventoryBrandDialog from '@/components/attendance/inventory/InventoryBrandDialog.vue'
import InventoryCategoryDialog from '@/components/attendance/inventory/InventoryCategoryDialog.vue'
import InventoryEmptyState from '@/components/attendance/inventory/InventoryEmptyState.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const loading = ref(true)
const loadError = ref('')

useAutoClearAlerts(loadError)

const categories = ref<InventoryCategory[]>([])
const brands = ref<InventoryBrand[]>([])

const categoryDialogOpen = ref(false)
const editingCategory = ref<InventoryCategory | null>(null)
const defaultParentId = ref<string | null>(null)
const brandDialogOpen = ref(false)
const editingBrand = ref<InventoryBrand | null>(null)

const byName = (a: { name_zh: string }, b: { name_zh: string }) =>
  a.name_zh.localeCompare(b.name_zh, 'zh-Hant')

const categoryTree = computed(() => {
  const tops = categories.value.filter(c => !c.parent_id).sort(byName)

  return tops.map(parent => ({
    parent,
    children: categories.value.filter(c => c.parent_id === parent.id).sort(byName),
  }))
})

const sortedBrands = computed(() => [...brands.value].sort(byName))

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  await loadAll()
})

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    const [categoryList, brandList] = await Promise.all([listInventoryCategories(), listInventoryBrands()])

    categories.value = categoryList
    brands.value = brandList
  }
  catch (e) {
    console.error('Failed to load categories and brands', e)
    loadError.value = formatApiError(e, 'Failed to load categories and brands.')
  }
  finally {
    loading.value = false
  }
}

function openCreateCategory(parentId: string | null = null) {
  editingCategory.value = null
  defaultParentId.value = parentId
  categoryDialogOpen.value = true
}

function openEditCategory(category: InventoryCategory) {
  editingCategory.value = category
  defaultParentId.value = null
  categoryDialogOpen.value = true
}

function openCreateBrand() {
  editingBrand.value = null
  brandDialogOpen.value = true
}

function openEditBrand(brand: InventoryBrand) {
  editingBrand.value = brand
  brandDialogOpen.value = true
}

function label(entity: { name_zh: string; name_en: string | null }): string {
  return [entity.name_zh, entity.name_en].filter(Boolean).join(' · ')
}
</script>

<template>
  <VContainer>
    <VRow
      class="mb-2"
      align="center"
    >
      <VCol>
        <div class="text-h5 font-weight-medium">
          Categories & Brands
        </div>
        <div class="text-body-2 text-medium-emphasis">
          Categories have up to two levels (e.g. Home Appliances › Smartphones). Brand is a separate field. 分類最多兩層，品牌係獨立欄位。
        </div>
      </VCol>
      <VCol cols="auto">
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-arrow-left-line"
          :to="{ name: 'attendance-inventory-items' }"
        >
          Back to items
        </VBtn>
      </VCol>
    </VRow>

    <VAlert
      v-if="loadError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="loadError = ''"
    >
      {{ loadError }}
    </VAlert>

    <VRow v-if="loading">
      <VCol
        cols="12"
        class="text-center py-12"
      >
        <VProgressCircular
          indeterminate
          color="primary"
          size="48"
        />
      </VCol>
    </VRow>

    <VRow v-else>
      <VCol
        cols="12"
        md="6"
      >
        <VCard>
          <VCardItem title="Categories">
            <template #append>
              <VBtn
                color="primary"
                size="small"
                prepend-icon="ri-add-line"
                @click="openCreateCategory"
              >
                New category
              </VBtn>
            </template>
          </VCardItem>
          <VDivider />
          <VList
            v-if="categoryTree.length"
            density="comfortable"
          >
            <template
              v-for="node in categoryTree"
              :key="node.parent.id"
            >
              <VListItem :class="{ 'text-disabled': !node.parent.is_active }">
                <VListItemTitle class="font-weight-medium">
                  {{ label(node.parent) }}
                  <VChip
                    v-if="!node.parent.is_active"
                    size="x-small"
                    class="ms-2"
                  >
                    Inactive
                  </VChip>
                </VListItemTitle>
                <template #append>
                  <VBtn
                    variant="text"
                    size="small"
                    prepend-icon="ri-add-line"
                    @click="openCreateCategory(node.parent.id)"
                  >
                    Sub-category
                  </VBtn>
                  <VBtn
                    icon="ri-pencil-line"
                    variant="text"
                    size="small"
                    aria-label="Edit category"
                    @click="openEditCategory(node.parent)"
                  />
                </template>
              </VListItem>
              <VListItem
                v-for="child in node.children"
                :key="child.id"
                class="ps-10"
                :class="{ 'text-disabled': !child.is_active }"
              >
                <VListItemTitle>
                  <span class="text-medium-emphasis me-1">›</span>
                  {{ label(child) }}
                  <VChip
                    v-if="!child.is_active"
                    size="x-small"
                    class="ms-2"
                  >
                    Inactive
                  </VChip>
                </VListItemTitle>
                <template #append>
                  <VBtn
                    icon="ri-pencil-line"
                    variant="text"
                    size="small"
                    aria-label="Edit sub-category"
                    @click="openEditCategory(child)"
                  />
                </template>
              </VListItem>
            </template>
          </VList>
          <InventoryEmptyState
            v-else
            icon="ri-folder-line"
            text="No categories yet"
            action-label="New category"
            @action="openCreateCategory"
          />
        </VCard>
      </VCol>

      <VCol
        cols="12"
        md="6"
      >
        <VCard>
          <VCardItem title="Brands">
            <template #append>
              <VBtn
                color="primary"
                size="small"
                prepend-icon="ri-add-line"
                @click="openCreateBrand"
              >
                New brand
              </VBtn>
            </template>
          </VCardItem>
          <VDivider />
          <VList
            v-if="sortedBrands.length"
            density="comfortable"
          >
            <VListItem
              v-for="brand in sortedBrands"
              :key="brand.id"
              :class="{ 'text-disabled': !brand.is_active }"
            >
              <VListItemTitle>
                {{ label(brand) }}
                <VChip
                  v-if="!brand.is_active"
                  size="x-small"
                  class="ms-2"
                >
                  Inactive
                </VChip>
              </VListItemTitle>
              <template #append>
                <VBtn
                  icon="ri-pencil-line"
                  variant="text"
                  size="small"
                  aria-label="Edit brand"
                  @click="openEditBrand(brand)"
                />
              </template>
            </VListItem>
          </VList>
          <InventoryEmptyState
            v-else
            icon="ri-price-tag-3-line"
            text="No brands yet"
            action-label="New brand"
            @action="openCreateBrand"
          />
        </VCard>
      </VCol>
    </VRow>

    <InventoryCategoryDialog
      v-model="categoryDialogOpen"
      :editing-category="editingCategory"
      :categories="categories"
      :default-parent-id="defaultParentId"
      @saved="loadAll"
    />
    <InventoryBrandDialog
      v-model="brandDialogOpen"
      :editing-brand="editingBrand"
      @saved="loadAll"
    />
  </VContainer>
</template>
