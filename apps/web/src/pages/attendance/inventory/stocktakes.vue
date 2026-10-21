<script setup lang="ts">
import {
  type InventoryItem,
  type InventoryStocktake,
  type InventoryStocktakeDetail,
  type InventoryStocktakeStatus,
  applyInventoryStocktake,
  cancelInventoryStocktake,
  createInventoryStocktake,
  getInventoryStocktake,
  listInventoryItems,
  listInventoryStocktakes,
  updateInventoryStocktakeLines,
} from '@/api/attendance/inventory'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const loading = ref(true)
const loadError = ref('')
const actionError = ref('')

useAutoClearAlerts(loadError)
useAutoClearAlerts(actionError)

const locations = ref<LocationItem[]>([])
const items = ref<InventoryItem[]>([])
const stocktakes = ref<InventoryStocktake[]>([])

const locationFilter = ref<string | null>(null)
const statusFilter = ref<InventoryStocktakeStatus | null>(null)

const createDialogOpen = ref(false)
const createForm = reactive({ location_id: null as string | null, note: '' })
const creating = ref(false)

const selected = ref<InventoryStocktakeDetail | null>(null)
const detailLoading = ref(false)
const counts = ref<Record<string, number | null>>({})
const saving = ref(false)

const statusOptions = [
  { value: 'draft' as const, title: 'Draft' },
  { value: 'applied' as const, title: 'Applied' },
  { value: 'cancelled' as const, title: 'Cancelled' },
]

const locationOptions = computed(() =>
  locations.value.map(l => ({
    value: l.id,
    title: [l.name_en, l.name_zh].filter(Boolean).join(' · '),
  })),
)

const itemById = computed(() => new Map(items.value.map(i => [i.id, i])))
const locationById = computed(() => new Map(locations.value.map(l => [l.id, l])))

const isDraft = computed(() => selected.value?.status === 'draft')

const changedLines = computed(() => {
  if (!selected.value)
    return 0

  return selected.value.lines.filter(l => counts.value[l.item_id] !== l.counted_qty).length
})

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  loading.value = true
  try {
    const [locationList, itemList] = await Promise.all([
      listLocations({ is_active: true }),
      listInventoryItems(),
    ])

    locations.value = locationList
    items.value = itemList
    await loadList()
  }
  catch (e) {
    console.error('Failed to load stocktakes', e)
    loadError.value = formatApiError(e, 'Failed to load stocktakes.')
  }
  finally {
    loading.value = false
  }
})

async function loadList() {
  const result = await listInventoryStocktakes({
    location_id: locationFilter.value ?? undefined,
    status: statusFilter.value ?? undefined,
  })

  stocktakes.value = result.items
}

function onFiltersChange() {
  loadList()
}

function itemLabel(id: string): string {
  const item = itemById.value.get(id)

  return item ? `${item.sku_code} · ${item.name_zh}` : id
}

function locationLabel(id: string): string {
  const location = locationById.value.get(id)

  return location ? [location.name_en, location.name_zh].filter(Boolean).join(' · ') : id
}

function statusColor(status: string): string {
  return { draft: 'warning', applied: 'success', cancelled: 'default' }[status] ?? 'default'
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString()
}

async function selectStocktake(take: InventoryStocktake) {
  detailLoading.value = true
  actionError.value = ''
  try {
    const detail = await getInventoryStocktake(take.id)

    selected.value = detail
    counts.value = Object.fromEntries(detail.lines.map(l => [l.item_id, l.counted_qty]))
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to load stocktake.')
  }
  finally {
    detailLoading.value = false
  }
}

async function saveCounts(): Promise<boolean> {
  if (!selected.value)
    return false
  try {
    const lines = selected.value.lines.map(l => ({
      item_id: l.item_id,
      counted_qty: counts.value[l.item_id] ?? null,
    }))

    const detail = await updateInventoryStocktakeLines(selected.value.id, lines)

    selected.value = detail
    counts.value = Object.fromEntries(detail.lines.map(l => [l.item_id, l.counted_qty]))

    return true
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to save counts.')

    return false
  }
}

async function applyTake() {
  if (!selected.value)
    return
  saving.value = true
  actionError.value = ''
  try {
    if (!(await saveCounts()))
      return
    selected.value = await applyInventoryStocktake(selected.value.id)
    await loadList()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to apply stocktake.')
  }
  finally {
    saving.value = false
  }
}

async function cancelTake() {
  if (!selected.value)
    return
  saving.value = true
  actionError.value = ''
  try {
    await cancelInventoryStocktake(selected.value.id)
    selected.value = { ...selected.value, status: 'cancelled' }
    await loadList()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to cancel stocktake.')
  }
  finally {
    saving.value = false
  }
}

function openCreate() {
  createForm.location_id = locationFilter.value
  createForm.note = ''
  actionError.value = ''
  createDialogOpen.value = true
}

async function submitCreate() {
  if (!createForm.location_id)
    return
  creating.value = true
  actionError.value = ''
  try {
    const detail = await createInventoryStocktake({
      location_id: createForm.location_id,
      note: createForm.note.trim() || null,
    })

    createDialogOpen.value = false
    await loadList()
    await selectStocktake(detail as InventoryStocktake)
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to create stocktake.')
  }
  finally {
    creating.value = false
  }
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
          Stocktakes 盤點
        </div>
      </VCol>
      <VCol
        cols="auto"
        class="d-flex gap-2"
      >
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="loading"
          @click="loadList"
        >
          Refresh
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          @click="openCreate"
        >
          New Stocktake
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
    <VAlert
      v-if="actionError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="actionError = ''"
    >
      {{ actionError }}
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
        md="4"
      >
        <VCard>
          <VCardText class="d-flex flex-wrap gap-3">
            <VSelect
              v-model="locationFilter"
              :items="locationOptions"
              label="Location"
              density="comfortable"
              hide-details
              clearable
              @update:model-value="onFiltersChange"
            />
            <VSelect
              v-model="statusFilter"
              :items="statusOptions"
              label="Status"
              density="comfortable"
              hide-details
              clearable
              @update:model-value="onFiltersChange"
            />
          </VCardText>
          <VList>
            <VListItem
              v-for="take in stocktakes"
              :key="take.id"
              :active="selected?.id === take.id"
              @click="selectStocktake(take)"
            >
              <VListItemTitle>{{ locationLabel(take.location_id) }}</VListItemTitle>
              <VListItemSubtitle>
                {{ formatDateTime(take.created_at) }}<template v-if="take.note">
                  · {{ take.note }}
                </template>
              </VListItemSubtitle>
              <template #append>
                <VChip
                  :color="statusColor(take.status)"
                  size="small"
                  variant="tonal"
                >
                  {{ take.status }}
                </VChip>
              </template>
            </VListItem>
            <VListItem v-if="stocktakes.length === 0">
              <VListItemTitle class="text-medium-emphasis">
                No stocktakes yet.
              </VListItemTitle>
            </VListItem>
          </VList>
        </VCard>
      </VCol>

      <VCol
        cols="12"
        md="8"
      >
        <VCard v-if="detailLoading">
          <VCardText class="text-center py-12">
            <VProgressCircular
              indeterminate
              color="primary"
              size="40"
            />
          </VCardText>
        </VCard>
        <VCard v-else-if="selected">
          <VCardTitle class="d-flex align-center gap-3">
            <span>{{ locationLabel(selected.location_id) }}</span>
            <VChip
              :color="statusColor(selected.status)"
              size="small"
              variant="tonal"
            >
              {{ selected.status }}
            </VChip>
            <VSpacer />
            <template v-if="isDraft">
              <VBtn
                variant="tonal"
                color="primary"
                size="small"
                :loading="saving"
                :disabled="changedLines === 0"
                @click="saveCounts"
              >
                Save counts{{ changedLines ? ` (${changedLines})` : '' }}
              </VBtn>
              <VBtn
                color="primary"
                size="small"
                :loading="saving"
                @click="applyTake"
              >
                Apply
              </VBtn>
              <VBtn
                variant="text"
                color="error"
                size="small"
                :loading="saving"
                @click="cancelTake"
              >
                Cancel take
              </VBtn>
            </template>
          </VCardTitle>
          <VCardSubtitle>
            Created {{ formatDateTime(selected.created_at) }}
            <template v-if="selected.applied_at">
              · Applied {{ formatDateTime(selected.applied_at) }}
            </template>
            <template v-if="selected.note">
              · {{ selected.note }}
            </template>
          </VCardSubtitle>
          <VTable>
            <thead>
              <tr>
                <th>Item</th>
                <th class="text-end">
                  System qty
                </th>
                <th
                  class="text-end"
                  style="width: 160px"
                >
                  Counted qty
                </th>
                <th class="text-end">
                  Diff
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="line in selected.lines"
                :key="line.id"
              >
                <td>{{ itemLabel(line.item_id) }}</td>
                <td class="text-end">
                  {{ line.system_qty }}
                </td>
                <td class="text-end">
                  <VTextField
                    v-if="isDraft"
                    v-model.number="counts[line.item_id]"
                    type="number"
                    min="0"
                    density="compact"
                    hide-details
                    variant="outlined"
                  />
                  <template v-else>
                    {{ line.counted_qty ?? '—' }}
                  </template>
                </td>
                <td class="text-end">
                  <template v-if="(isDraft ? counts[line.item_id] : line.counted_qty) !== null">
                    {{ (isDraft ? counts[line.item_id] : line.counted_qty)! - line.system_qty }}
                  </template>
                  <template v-else>
                    —
                  </template>
                </td>
              </tr>
            </tbody>
          </VTable>
        </VCard>
        <VCard v-else>
          <VCardText class="text-center text-medium-emphasis py-12">
            Select a stocktake to count items, or create a new one.
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <VDialog
      v-model="createDialogOpen"
      max-width="480"
    >
      <VCard title="New stocktake">
        <VCardText>
          <VAlert
            type="info"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            Snapshots the current stock of every active item at the chosen location.
          </VAlert>
          <VSelect
            v-model="createForm.location_id"
            :items="locationOptions"
            label="Location"
            density="comfortable"
            class="mb-3"
          />
          <VTextField
            v-model="createForm.note"
            label="Note"
            hint="Optional."
            persistent-hint
            density="comfortable"
          />
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="createDialogOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :loading="creating"
            :disabled="!createForm.location_id"
            @click="submitCreate"
          >
            Create
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>
