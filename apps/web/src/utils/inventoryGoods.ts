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

export interface OptionSuggestion {
  name: string
  values: string[]
}

const normalise = (text: string) => text.trim().toLowerCase()

/** Option names and values already used by products, for dropdown suggestions. */
export function buildOptionSuggestions(products: InventoryProduct[]): OptionSuggestion[] {
  const sorted = [...products].sort((a, b) => a.created_at.localeCompare(b.created_at))

  interface Group {
    spellings: Map<string, { count: number; first: number }>
    values: string[]
    seenValues: Set<string>
    products: number
  }
  const groups = new Map<string, Group>()
  let order = 0

  for (const product of sorted) {
    for (const [rawName, rawValues] of Object.entries(product.options ?? {})) {
      const name = rawName.trim()
      const key = normalise(name)

      if (!key)
        continue

      const group: Group = groups.get(key) ?? { spellings: new Map(), values: [], seenValues: new Set(), products: 0 }

      groups.set(key, group)
      group.products += 1

      const spelling = group.spellings.get(name) ?? { count: 0, first: order++ }

      spelling.count += 1
      group.spellings.set(name, spelling)

      for (const rawValue of rawValues) {
        const value = rawValue.trim()
        const valueKey = normalise(value)

        if (value && !group.seenValues.has(valueKey)) {
          group.seenValues.add(valueKey)
          group.values.push(value)
        }
      }
    }
  }

  return [...groups.values()]
    .map(group => {
      const [name] = [...group.spellings.entries()].sort(
        (a, b) => b[1].count - a[1].count || a[1].first - b[1].first,
      )[0]

      return { name, values: group.values, products: group.products }
    })
    .sort((a, b) => b.products - a.products || a.name.localeCompare(b.name))
    .map(({ name, values }) => ({ name, values }))
}

export function canonicalOption(name: string, suggestions: OptionSuggestion[]): string {
  const trimmed = name.trim()

  return suggestions.find(s => normalise(s.name) === normalise(trimmed))?.name ?? trimmed
}

export function canonicalValue(value: string, suggestion: OptionSuggestion | undefined): string {
  const trimmed = value.trim()

  return suggestion?.values.find(v => normalise(v) === normalise(trimmed)) ?? trimmed
}

export const NAME_REQUIRED_HINT = 'Chinese or English name required. 中文或英文名填一個。'

export function namesMissing(nameZh: string | null | undefined, nameEn: string | null | undefined): boolean {
  return !(nameZh ?? '').trim() && !(nameEn ?? '').trim()
}

/** The server fills a blank Chinese name from the English one; show that fallback as blank when editing. */
export function zhForEdit(nameZh: string | null | undefined, nameEn: string | null | undefined): string {
  const zh = nameZh ?? ''

  return zh && zh === (nameEn ?? '') ? '' : zh
}
