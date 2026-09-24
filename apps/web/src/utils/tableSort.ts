export interface TableSort<K extends string> {
  key: K
  dir: 1 | -1
}

export type SortValue = string | number | null | undefined

export function compareSortValues(a: SortValue, b: SortValue): number {
  if (a == null && b == null)
    return 0
  if (a == null)
    return 1
  if (b == null)
    return -1
  if (typeof a === 'number' && typeof b === 'number')
    return a - b

  return String(a).localeCompare(String(b), undefined, { numeric: true })
}

export interface CancellableTableSort<K extends string> {
  key: K | null
  dir: 1 | -1
}

export function toggleSort<K extends string>(state: TableSort<K>, key: K) {
  if (state.key === key)
    state.dir = state.dir === 1 ? -1 : 1
  else {
    state.key = key
    state.dir = 1
  }
}

/** Ascending, then descending, then back to the unsorted list. */
export function cycleSort<K extends string>(state: CancellableTableSort<K>, key: K) {
  if (state.key !== key) {
    state.key = key
    state.dir = 1

    return
  }
  if (state.dir === 1) {
    state.dir = -1

    return
  }
  state.key = null
}

export function sortIconFor<K extends string>(state: { key: K | null; dir: 1 | -1 }, key: K): string {
  if (state.key !== key)
    return 'ri-arrow-up-down-line'

  return state.dir === 1 ? 'ri-arrow-up-line' : 'ri-arrow-down-line'
}

export function sortHeaderTitle<K extends string>(
  state: { key: K | null; dir: 1 | -1 },
  key: K,
  label: string,
): string {
  if (state.key !== key)
    return `Sort by ${label}`
  if (state.dir === 1)
    return `${label}, ascending. Click to reverse.`

  return `${label}, descending. Click to clear sort.`
}
