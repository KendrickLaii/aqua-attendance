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

export function toggleSort<K extends string>(state: TableSort<K>, key: K) {
  if (state.key === key)
    state.dir = state.dir === 1 ? -1 : 1
  else {
    state.key = key
    state.dir = 1
  }
}

export function sortIconFor<K extends string>(state: TableSort<K>, key: K): string {
  if (state.key !== key)
    return 'ri-arrow-up-down-line'

  return state.dir === 1 ? 'ri-arrow-up-line' : 'ri-arrow-down-line'
}
