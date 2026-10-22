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
import AttendanceConfirmDialog from '@/components/attendance/AttendanceConfirmDialog.vue'
import InventoryDocChain, { type DocChainStep } from '@/components/attendance/inventory/InventoryDocChain.vue'
import { type InventoryDocAction, type InventoryDocMoreItem } from '@/components/attendance/inventory/InventoryDocActions.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { useConfirmAction } from '@/composables/useConfirmAction'
import { useDirtyGuard } from '@/composables/useDirtyGuard'
import { useLatestRequest } from '@/composables/useLatestRequest'

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

const listReq = useLatestRequest()
const confirm = useConfirmAction()
const dirty = useDirtyGuard('未儲存的盤點數量會消失。')

const lineSearch = ref('')
const lineView = ref<'all' | 'unfilled' | 'diff'>('all')
const reviewOpen = ref(false)
const countInputRefs = new Map<string, { focus: () => void }>()
let suppressDirty = false

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

const route = useRoute()
const router = useRouter()

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

const totalLines = computed(() => selected.value?.lines.length ?? 0)

const filledCount = computed(() => {
  if (!selected.value)
    return 0

  return selected.value.lines.filter(l => counts.value[l.item_id] != null).length
})

const visibleLines = computed(() => {
  if (!selected.value)
    return []
  const term = lineSearch.value.trim().toLowerCase()

  return selected.value.lines.filter(l => {
    if (lineView.value === 'unfilled' && counts.value[l.item_id] != null)
      return false
    if (lineView.value === 'diff'
      && (counts.value[l.item_id] == null || counts.value[l.item_id] === l.system_qty))
      return false
    if (term) {
      const item = itemById.value.get(l.item_id)

      return [item?.sku_code ?? '', item?.name_zh ?? '', item?.name_en ?? '']
        .some(v => v.toLowerCase().includes(term))
    }

    return true
  })
})

const reviewSummary = computed(() => {
  const up: { label: string; system: number; counted: number; diff: number }[] = []
  const down: { label: string; system: number; counted: number; diff: number }[] = []
  let same = 0
  let unfilled = 0

  for (const l of selected.value?.lines ?? []) {
    const c = counts.value[l.item_id]
    if (c == null) {
      unfilled++
      continue
    }
    const diff = c - l.system_qty

    if (diff > 0)
      up.push({ label: itemLabel(l.item_id), system: l.system_qty, counted: c, diff })
    else if (diff < 0)
      down.push({ label: itemLabel(l.item_id), system: l.system_qty, counted: c, diff })
    else
      same++
  }

  return { up, down, same, unfilled, changed: [...up, ...down] }
})

const chainSteps = computed<DocChainStep[]>(() => {
  const t = selected.value
  if (!t)
    return []

  return [
    { label: '1 選分校開單', state: 'done' },
    {
      label: '2 逐項點數',
      state: t.status === 'draft' ? 'current' : 'done',
      hint: t.status === 'draft' ? `${filledCount.value} / ${totalLines.value}` : undefined,
    },
    { label: '3 檢查差異並套用', state: t.status === 'applied' ? 'done' : 'todo' },
  ]
})

watch(counts, () => {
  if (!suppressDirty && isDraft.value)
    dirty.dirty.value = true
}, { deep: true })

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

    if (route.query.action === 'new') {
      openCreate()

      const rest = { ...route.query }

      delete rest.action
      router.replace({ query: rest })
    }
  }
  catch (e) {
    console.error('Failed to load stocktakes', e)
    loadError.value = formatApiError(e, 'Failed to load stocktakes.')
  }
  finally {
    loading.value = false
  }
})

const countErrors = computed(() => {
  if (!selected.value || !isDraft.value)
    return {} as Record<string, string>
  const out: Record<string, string> = {}

  for (const l of selected.value.lines) {
    const v = counts.value[l.item_id]
    if (v != null && (!Number.isInteger(v) || v < 0))
      out[l.item_id] = 'Must be a whole number ≥ 0'
  }

  return out
})

const hasCountErrors = computed(() => Object.keys(countErrors.value).length > 0)

const docPrimary = computed<InventoryDocAction | null>(() =>
  isDraft.value
    ? { label: 'Review & Apply', tooltip: '檢查差異並套用，庫存會調整到實際數量', disabled: hasCountErrors.value, onClick: askApply }
    : null,
)

const docSecondary = computed<InventoryDocAction | null>(() =>
  isDraft.value
    ? { label: `Save Progress${changedLines.value ? ` (${changedLines.value})` : ''}`, tooltip: '先儲存已填的數量，之後再繼續盤點', disabled: changedLines.value === 0, onClick: saveCounts }
    : null,
)

const docMore = computed<InventoryDocMoreItem[]>(() =>
  isDraft.value
    ? [{ label: 'Cancel take', sub: '取消這張盤點單,不能復原', icon: 'ri-close-circle-line', danger: true, onClick: askCancel }]
    : [],
)

async function loadList() {
  const token = listReq.next()

  const result = await listInventoryStocktakes({
    location_id: locationFilter.value ?? undefined,
    status: statusFilter.value ?? undefined,
  })

  if (!listReq.isLatest(token))
    return
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

const detailAnchor = ref<{ $el: HTMLElement } | null>(null)
const reducedMotion = usePreferredReducedMotion()

async function scrollToDetail() {
  await nextTick()
  detailAnchor.value?.$el.scrollIntoView({
    behavior: reducedMotion.value === 'reduce' ? 'auto' : 'smooth',
    block: 'start',
  })
}

async function selectStocktake(take: InventoryStocktake) {
  if (isDraft.value && dirty.dirty.value && !(await dirty.confirmDiscard()))
    return
  detailLoading.value = true
  actionError.value = ''
  try {
    const detail = await getInventoryStocktake(take.id)

    suppressDirty = true
    selected.value = detail
    counts.value = Object.fromEntries(detail.lines.map(l => [l.item_id, l.counted_qty]))
    dirty.markClean()
    nextTick(() => {
      suppressDirty = false
    })
    await scrollToDetail()
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
  if (hasCountErrors.value) {
    actionError.value = 'Counts must be whole numbers ≥ 0.'

    return false
  }
  try {
    const lines = selected.value.lines.map(l => ({
      item_id: l.item_id,
      counted_qty: counts.value[l.item_id] ?? null,
    }))

    const detail = await updateInventoryStocktakeLines(selected.value.id, lines)

    suppressDirty = true
    selected.value = detail
    counts.value = Object.fromEntries(detail.lines.map(l => [l.item_id, l.counted_qty]))
    dirty.markClean()
    nextTick(() => {
      suppressDirty = false
    })

    return true
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to save counts.')

    return false
  }
}

function askApply() {
  if (!selected.value)
    return
  reviewOpen.value = true
}

function fillAllSystem() {
  for (const l of selected.value?.lines ?? []) {
    if (counts.value[l.item_id] == null)
      counts.value[l.item_id] = l.system_qty
  }
}

function fillLineSystem(itemId: string) {
  const line = selected.value?.lines.find(l => l.item_id === itemId)
  if (line)
    counts.value[itemId] = line.system_qty
}

function setCountInputRef(el: unknown, itemId: string) {
  if (el)
    countInputRefs.set(itemId, el as { focus: () => void })
  else
    countInputRefs.delete(itemId)
}

function focusNextLine(itemId: string) {
  const idx = visibleLines.value.findIndex(l => l.item_id === itemId)
  const next = visibleLines.value[idx + 1]

  if (next)
    countInputRefs.get(next.item_id)?.focus()
}

function statusZh(status: string): string {
  return { draft: '草稿', applied: '已套用', cancelled: '已取消' }[status] ?? status
}

async function performApply() {
  if (!selected.value)
    return
  saving.value = true
  actionError.value = ''
  try {
    if (!(await saveCounts()))
      return
    selected.value = await applyInventoryStocktake(selected.value.id)
    dirty.markClean()
    reviewOpen.value = false
    await loadList()
  }
  catch (e) {
    actionError.value = formatApiError(e, 'Failed to apply stocktake.')
  }
  finally {
    saving.value = false
  }
}

function askCancel() {
  if (!selected.value)
    return
  confirm.ask(
    'Cancel this stocktake?',
    '取消後這張草稿盤點單會作廢，已填但未儲存的數量會消失。',
    { label: 'Cancel take', details: ['盤點單變成已取消', '不能復原'] },
    performCancel,
  )
}

async function performCancel() {
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
    nextTick(() => {
      const first = visibleLines.value[0]

      if (first)
        countInputRefs.get(first.item_id)?.focus()
    })
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
        <div class="text-body-2 text-medium-emphasis">
          這一頁做盤點：實際數一次貨架上的數量，讓系統自動調整。
        </div>
      </VCol>
      <VCol
        cols="auto"
        class="d-flex gap-2"
      >
        <VTooltip
          text="重新整理"
          location="bottom"
        >
          <template #activator="{ props }">
            <VBtn
              v-bind="props"
              icon="ri-refresh-line"
              variant="tonal"
              color="primary"
              :loading="loading"
              aria-label="重新整理"
              @click="loadList"
            />
          </template>
        </VTooltip>
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
      <VCol cols="12">
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
          <VList style="max-height: 360px; overflow-y: auto">
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
                  {{ statusZh(take.status) }}
                </VChip>
              </template>
            </VListItem>
            <VListItem v-if="stocktakes.length === 0">
              <VListItemTitle class="text-medium-emphasis">
                No stocktakes yet — click "New Stocktake" to count a location.
              </VListItemTitle>
            </VListItem>
          </VList>
        </VCard>
      </VCol>

      <VCol
        ref="detailAnchor"
        cols="12"
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
              {{ statusZh(selected.status) }}
            </VChip>
            <VSpacer />
            <InventoryDocActions
              :primary="docPrimary"
              :secondary="docSecondary"
              :more="docMore"
              :loading="saving"
            />
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
          <VCardText>
            <InventoryDocChain
              :steps="chainSteps"
              class="mb-3"
            />
            <VAlert
              v-if="isDraft"
              type="info"
              variant="tonal"
              density="compact"
              class="mb-3"
            >
              系統已記下開單當下的數量。請到貨架實際數一次，把數到的數字填進「實際數量」。沒填的品項不會被調整。全部填完後按「Review & Apply」。
            </VAlert>
            <template v-if="isDraft">
              <div class="d-flex flex-wrap align-center gap-3 mb-3">
                <VTextField
                  v-model="lineSearch"
                  density="compact"
                  label="搜尋品項"
                  prepend-inner-icon="ri-search-line"
                  hide-details
                  clearable
                  style="width: 240px; flex-shrink: 0"
                />
                <VChipGroup
                  v-model="lineView"
                  mandatory
                  selected-class="text-primary"
                  style="flex-shrink: 0"
                >
                  <VChip
                    value="all"
                    size="small"
                    variant="outlined"
                    filter
                  >
                    全部
                  </VChip>
                  <VChip
                    value="unfilled"
                    size="small"
                    variant="outlined"
                    filter
                  >
                    只看未填
                  </VChip>
                  <VChip
                    value="diff"
                    size="small"
                    variant="outlined"
                    filter
                  >
                    只看有差異
                  </VChip>
                </VChipGroup>
                <VBtn
                  variant="tonal"
                  size="small"
                  style="flex-shrink: 0"
                  @click="fillAllSystem"
                >
                  全部先填系統數量
                </VBtn>
                <span class="text-body-2 text-medium-emphasis ms-auto">已填 {{ filledCount }} / {{ totalLines }} 項</span>
              </div>
              <VProgressLinear
                :model-value="totalLines ? (filledCount / totalLines) * 100 : 0"
                color="primary"
                height="6"
                rounded
                class="mb-3"
              />
            </template>
          </VCardText>
          <div class="overflow-x-auto">
            <VTable>
              <thead>
                <tr>
                  <th>Item</th>
                  <th class="text-end">
                    系統數量
                  </th>
                  <th
                    class="text-end"
                    style="width: 200px"
                  >
                    實際數量
                  </th>
                  <th class="text-end">
                    差異
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="line in visibleLines"
                  :key="line.id"
                >
                  <td>{{ itemLabel(line.item_id) }}</td>
                  <td class="text-end tabular-nums">
                    {{ line.system_qty }}
                  </td>
                  <td class="text-end">
                    <div
                      v-if="isDraft"
                      class="d-flex align-center justify-end gap-1"
                    >
                      <VTextField
                        :ref="el => setCountInputRef(el, line.item_id)"
                        v-model.number="counts[line.item_id]"
                        type="number"
                        min="0"
                        step="1"
                        density="compact"
                        hide-details="auto"
                        variant="outlined"
                        style="max-width: 130px"
                        :error="!!countErrors[line.item_id]"
                        :error-messages="countErrors[line.item_id]"
                        @keydown.enter="focusNextLine(line.item_id)"
                      />
                      <VBtn
                        icon="ri-equal-line"
                        variant="text"
                        size="x-small"
                        aria-label="填入系統數量"
                        title="填入系統數量"
                        @click="fillLineSystem(line.item_id)"
                      />
                    </div>
                    <template v-else>
                      {{ line.counted_qty ?? '—' }}
                    </template>
                  </td>
                  <td class="text-end tabular-nums">
                    <template v-if="(isDraft ? counts[line.item_id] : line.counted_qty) !== null">
                      <VChip
                        size="x-small"
                        variant="tonal"
                        :color="((isDraft ? counts[line.item_id] : line.counted_qty)! - line.system_qty) > 0 ? 'success' : ((isDraft ? counts[line.item_id] : line.counted_qty)! - line.system_qty) < 0 ? 'error' : 'secondary'"
                      >
                        {{ ((isDraft ? counts[line.item_id] : line.counted_qty)! - line.system_qty) > 0 ? `多了 +${(isDraft ? counts[line.item_id] : line.counted_qty)! - line.system_qty}` : ((isDraft ? counts[line.item_id] : line.counted_qty)! - line.system_qty) < 0 ? `少了 ${(isDraft ? counts[line.item_id] : line.counted_qty)! - line.system_qty}` : '相符' }}
                      </VChip>
                    </template>
                    <template v-else>
                      <span class="text-medium-emphasis">未填</span>
                    </template>
                  </td>
                </tr>
              </tbody>
            </VTable>
          </div>
        </VCard>
        <VCard v-else>
          <VCardText class="text-center text-medium-emphasis py-12">
            從上面的列表選一張盤點單，或按下面的按鈕為一個分校開始盤點。
            <div class="mt-3">
              <VBtn
                color="primary"
                prepend-icon="ri-add-line"
                @click="openCreate"
              >
                New Stocktake
              </VBtn>
            </div>
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
            選擇要盤點的分校。系統會列出這個分校所有啟用中的品項，和現在的系統數量。
          </VAlert>
          <VSelect
            v-model="createForm.location_id"
            :items="locationOptions"
            label="Location *"
            density="comfortable"
            class="mb-3"
            :error="!createForm.location_id"
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

    <VDialog
      v-model="reviewOpen"
      max-width="560"
    >
      <VCard>
        <VCardTitle class="d-flex align-center gap-3 py-4">
          <VAvatar
            color="warning"
            variant="tonal"
            size="36"
          >
            <VIcon icon="ri-survey-line" />
          </VAvatar>
          <span class="text-h6">檢查差異並套用？</span>
        </VCardTitle>
        <VDivider />
        <VCardText class="pa-4">
          <div class="d-flex flex-wrap gap-4 mb-3">
            <VChip
              color="success"
              variant="tonal"
              size="small"
            >
              {{ reviewSummary.up.length }} 項會增加
            </VChip>
            <VChip
              color="error"
              variant="tonal"
              size="small"
            >
              {{ reviewSummary.down.length }} 項會減少
            </VChip>
            <VChip
              color="secondary"
              variant="tonal"
              size="small"
            >
              {{ reviewSummary.same }} 項相符
            </VChip>
            <VChip
              variant="outlined"
              size="small"
            >
              {{ reviewSummary.unfilled }} 項未填（不調整）
            </VChip>
          </div>
          <VTable
            v-if="reviewSummary.changed.length"
            density="compact"
          >
            <thead>
              <tr>
                <th>品項</th>
                <th class="text-end">
                  系統 → 實際
                </th>
                <th class="text-end">
                  差異
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="r in reviewSummary.changed"
                :key="r.label"
              >
                <td>{{ r.label }}</td>
                <td class="text-end tabular-nums">
                  {{ r.system }} → {{ r.counted }}
                </td>
                <td
                  class="text-end tabular-nums"
                  :class="r.diff > 0 ? 'text-success' : 'text-error'"
                >
                  {{ r.diff > 0 ? `+${r.diff}` : r.diff }}
                </td>
              </tr>
            </tbody>
          </VTable>
          <VAlert
            v-else
            type="info"
            variant="tonal"
            density="compact"
          >
            沒有差異，套用後盤點單會標記為已套用，庫存不變。
          </VAlert>
        </VCardText>
        <VDivider />
        <DialogFooter>
          <VBtn
            variant="outlined"
            color="primary"
            :disabled="saving"
            @click="reviewOpen = false"
          >
            Back
          </VBtn>
          <VBtn
            variant="flat"
            color="warning"
            :loading="saving"
            @click="performApply"
          >
            Apply Adjustments
          </VBtn>
        </DialogFooter>
      </VCard>
    </VDialog>

    <AttendanceConfirmDialog
      v-model="confirm.open.value"
      :title="confirm.title.value"
      :confirm-label="confirm.label.value"
      :confirm-color="confirm.color.value"
      :tone="confirm.tone.value"
      :details="confirm.details.value"
      :loading="confirm.loading.value"
      @confirm="confirm.run"
    >
      {{ confirm.message.value }}
    </AttendanceConfirmDialog>
  </VContainer>
</template>
