import { type Ref, nextTick } from 'vue'
import type { InventoryItem } from '@/api/attendance/inventory'
import { useToast } from '@/composables/useToast'

/**
 * Feedback for item pickers inside document line tables: inactive items are
 * rejected, and picking an item that is already on another line with the same
 * price merges the quantities into that line.
 */
export function useInventoryLinePicker<T extends { item_id?: string | null }>(options: {
  lines: Ref<T[]>
  itemById: (id: string) => InventoryItem | undefined
  qtyKey: string

  /** Lines merge only when item and every one of these price fields match (empty = 0). */
  priceKeys?: string[]
}) {
  const toast = useToast()

  async function onPickItem(index: number) {
    await nextTick()

    const lines = options.lines.value
    const line = lines[index]
    const itemId = line?.item_id
    if (!line || !itemId)
      return

    const item = options.itemById(itemId)
    if (!item)
      return

    if (!item.is_active) {
      toast.show(`${item.sku_code} is inactive and cannot be added`, 'warning', 4000)
      line.item_id = ''

      return
    }

    const source = line as unknown as Record<string, unknown>
    const priceKeys = options.priceKeys ?? []

    const samePrices = (other: T) => {
      const o = other as unknown as Record<string, unknown>

      return priceKeys.every(key => (Number(o[key]) || 0) === (Number(source[key]) || 0))
    }

    const duplicateIndex = lines.findIndex((l, i) => i !== index && l.item_id === itemId && samePrices(l))
    if (duplicateIndex < 0)
      return

    const target = lines[duplicateIndex] as unknown as Record<string, unknown>
    const added = Number(source[options.qtyKey]) || 1

    target[options.qtyKey] = (Number(target[options.qtyKey]) || 0) + added
    lines.splice(index, 1)
    toast.show(`Qty +${added} for ${item.sku_code}`, 'info', 3000)
  }

  return { onPickItem }
}
