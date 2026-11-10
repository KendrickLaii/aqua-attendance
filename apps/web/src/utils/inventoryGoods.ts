import type { InventoryCategory, InventoryItem, InventoryProduct } from '@/api/attendance/inventory'

export type GoodsEditing =
  | { kind: 'item'; item: InventoryItem }
  | { kind: 'product'; product: InventoryProduct }

export const MAX_VARIANT_COMBINATIONS = 200

export interface CategoryOption {
  value: string
  title: string
}

const CHILD_INDENT = String.fromCodePoint(0x3000)

const byZhName = (a: InventoryCategory, b: InventoryCategory) => a.name_zh.localeCompare(b.name_zh, 'zh-Hant')

function categoryTitle(category: InventoryCategory): string {
  return [category.name_zh, category.name_en].filter(Boolean).join(' · ')
}

/** Parent first, then its children prefixed with a full-width space and "›". Inactive entries are skipped unless `keepId` points at one. */
export function buildCategoryOptions(categories: InventoryCategory[], keepId?: string | null): CategoryOption[] {
  const visible = (c: InventoryCategory) => c.is_active || c.id === keepId
  const tops = categories.filter(c => !c.parent_id).sort(byZhName)
  const options: CategoryOption[] = []

  for (const parent of tops) {
    const children = categories.filter(c => c.parent_id === parent.id && visible(c)).sort(byZhName)

    if (visible(parent) || children.length)
      options.push({ value: parent.id, title: categoryTitle(parent) })
    for (const child of children)
      options.push({ value: child.id, title: `${CHILD_INDENT}› ${categoryTitle(child)}` })
  }

  return options
}

/** "家用電器 › 智能手機" for sub-categories, plain name for top-level, '—' when unset. */
export function categoryPath(categories: InventoryCategory[], categoryId: string | null): string {
  const category = categories.find(c => c.id === categoryId)

  if (!category)
    return '—'

  const parent = category.parent_id ? categories.find(c => c.id === category.parent_id) : undefined

  return parent ? `${parent.name_zh} › ${category.name_zh}` : category.name_zh
}

/** The category plus its direct children, used for the "selecting a parent includes its children" filter. */
export function categoryIdsWithChildren(categories: InventoryCategory[], categoryId: string): Set<string> {
  return new Set([categoryId, ...categories.filter(c => c.parent_id === categoryId).map(c => c.id)])
}
