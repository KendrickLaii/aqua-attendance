import { $attendanceApi } from '@/utils/attendanceApi'
import { fetchAllAttendancePages, fetchAttendanceListWithTotal } from '@/utils/attendanceListApi'

export interface InventoryCategory {
  id: string
  name_zh: string
  name_en: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface InventoryCategoryPayload {
  name_zh: string
  name_en?: string | null
  is_active?: boolean
}

export interface InventoryItem {
  id: string
  sku_code: string
  name_zh: string
  name_en: string | null
  category_id: string | null
  unit_of_measure: string | null
  cost_price: number | null
  sale_price: number | null
  reorder_level: number
  avg_cost: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface InventoryItemPayload {
  sku_code: string
  name_zh: string
  name_en?: string | null
  category_id?: string | null
  unit_of_measure?: string | null
  cost_price?: number | null
  sale_price?: number | null
  reorder_level?: number
  is_active?: boolean
}

export interface InventoryStock {
  id: string
  item_id: string
  location_id: string
  quantity: number
  reserved: number
  available: number
  updated_at: string
}

export type InventoryMovementType = 'in' | 'out' | 'adjust'
export type InventoryMovementTypeOut = 'in' | 'out' | 'adjust' | 'transfer_in' | 'transfer_out'

export type InventoryInReasonCode = 'opening' | 'sales_return' | 'other'
export type InventoryOutReasonCode = 'damage' | 'loss' | 'gift' | 'sample' | 'internal_use' | 'supplier_return' | 'sale' | 'other'

export interface InventoryMovement {
  id: string
  item_id: string
  location_id: string
  type: InventoryMovementTypeOut
  quantity_delta: number
  balance_after: number
  reason: string | null
  reason_code: string | null
  unit_cost: number | null
  reference: string | null
  created_by: string | null
  created_at: string
}

export interface InventoryMovementPayload {
  item_id: string
  location_id: string
  type: InventoryMovementType
  quantity: number
  reason?: string | null
  reason_code?: string | null
  reference?: string | null
}

export interface InventoryTransferPayload {
  item_id: string
  from_location_id: string
  to_location_id: string
  quantity: number
  reason?: string | null
}

export interface InventoryTransferResult {
  transfer_id: string
  out_movement: InventoryMovement
  in_movement: InventoryMovement
}

export type InventoryStocktakeStatus = 'draft' | 'applied' | 'cancelled'

export interface InventoryStocktake {
  id: string
  location_id: string
  status: InventoryStocktakeStatus
  note: string | null
  created_by: string | null
  created_at: string
  applied_at: string | null
}

export interface InventoryStocktakeLine {
  id: string
  item_id: string
  system_qty: number
  counted_qty: number | null
}

export interface InventoryStocktakeDetail extends InventoryStocktake {
  lines: InventoryStocktakeLine[]
}

export interface InventoryImportResult {
  created: number
  updated: number
  skipped: number
  errors: { row: number; error: string }[]
}

// ---- Categories ----

export async function listInventoryCategories(params?: { is_active?: boolean }): Promise<InventoryCategory[]> {
  return await $attendanceApi('/inventory/categories', { params })
}

export async function createInventoryCategory(payload: InventoryCategoryPayload): Promise<InventoryCategory> {
  return await $attendanceApi('/inventory/categories', { method: 'POST', body: payload })
}

export async function updateInventoryCategory(
  id: string,
  payload: Partial<InventoryCategoryPayload>,
): Promise<InventoryCategory> {
  return await $attendanceApi(`/inventory/categories/${id}`, { method: 'PATCH', body: payload })
}

// ---- Items ----

export async function listInventoryItems(params?: {
  category_id?: string
  is_active?: boolean
  low_stock?: boolean
  search?: string
}): Promise<InventoryItem[]> {
  const result = await fetchAllAttendancePages<InventoryItem>('/inventory/items', params)

  return result.items
}

export async function createInventoryItem(payload: InventoryItemPayload): Promise<InventoryItem> {
  return await $attendanceApi('/inventory/items', { method: 'POST', body: payload })
}

export async function updateInventoryItem(
  id: string,
  payload: Partial<InventoryItemPayload>,
): Promise<InventoryItem> {
  return await $attendanceApi(`/inventory/items/${id}`, { method: 'PATCH', body: payload })
}

// ---- Stocks ----

export async function listInventoryStocks(params?: {
  location_id?: string
  item_id?: string
}): Promise<InventoryStock[]> {
  return await $attendanceApi('/inventory/stocks', { params })
}

export async function listLowStock(params?: { location_id?: string }): Promise<InventoryStock[]> {
  return await $attendanceApi('/inventory/low-stock', { params })
}

// ---- Movements ----

export async function createInventoryMovement(payload: InventoryMovementPayload): Promise<InventoryMovement> {
  return await $attendanceApi('/inventory/movements', { method: 'POST', body: payload })
}

export async function listInventoryMovements(params?: {
  item_id?: string
  location_id?: string
  type?: InventoryMovementTypeOut
  reason_code?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}) {
  return await fetchAttendanceListWithTotal<InventoryMovement>('/inventory/movements', params)
}

// ---- Transfers ----

export async function createInventoryTransfer(payload: InventoryTransferPayload): Promise<InventoryTransferResult> {
  return await $attendanceApi('/inventory/transfers', { method: 'POST', body: payload })
}

// ---- Stocktakes ----

export async function listInventoryStocktakes(params?: {
  location_id?: string
  status?: InventoryStocktakeStatus
  page?: number
  page_size?: number
}) {
  return await fetchAttendanceListWithTotal<InventoryStocktake>('/inventory/stocktakes', params)
}

export async function getInventoryStocktake(id: string): Promise<InventoryStocktakeDetail> {
  return await $attendanceApi(`/inventory/stocktakes/${id}`)
}

export async function createInventoryStocktake(payload: {
  location_id: string
  item_ids?: string[] | null
  note?: string | null
}): Promise<InventoryStocktakeDetail> {
  return await $attendanceApi('/inventory/stocktakes', { method: 'POST', body: payload })
}

export async function updateInventoryStocktakeLines(
  id: string,
  lines: { item_id: string; counted_qty: number | null }[],
): Promise<InventoryStocktakeDetail> {
  return await $attendanceApi(`/inventory/stocktakes/${id}/lines`, {
    method: 'PATCH',
    body: { lines },
  })
}

export async function applyInventoryStocktake(id: string): Promise<InventoryStocktakeDetail> {
  return await $attendanceApi(`/inventory/stocktakes/${id}/apply`, { method: 'POST' })
}

export async function cancelInventoryStocktake(id: string): Promise<InventoryStocktake> {
  return await $attendanceApi(`/inventory/stocktakes/${id}/cancel`, { method: 'POST' })
}

// ---- CSV export ----

export async function exportInventoryItemsCSV(): Promise<Blob> {
  return await $attendanceApi<Blob>('/inventory/export/items.csv', { responseType: 'blob' })
}

export async function exportInventoryStocksCSV(params?: { location_id?: string }): Promise<Blob> {
  return await $attendanceApi<Blob>('/inventory/export/stocks.csv', { params, responseType: 'blob' })
}

// ---- CSV import ----

export async function importInventoryItemsCSV(file: File): Promise<InventoryImportResult> {
  const body = new FormData()

  body.append('file', file)

  return await $attendanceApi('/inventory/import/items', { method: 'POST', body })
}

export async function importOpeningStockCSV(file: File): Promise<InventoryImportResult> {
  const body = new FormData()

  body.append('file', file)

  return await $attendanceApi('/inventory/import/opening-stock', { method: 'POST', body })
}
