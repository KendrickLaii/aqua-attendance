import { $attendanceApi } from '@/utils/attendanceApi'
import { fetchAttendanceListWithTotal } from '@/utils/attendanceListApi'

// ---- Suppliers ----

export interface InventorySupplier {
  id: string
  code: string
  name_zh: string
  name_en: string | null
  contact_name: string | null
  phone: string | null
  email: string | null
  address: string | null
  payment_terms: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface InventorySupplierPayload {
  code: string
  name_zh: string
  name_en?: string | null
  contact_name?: string | null
  phone?: string | null
  email?: string | null
  address?: string | null
  payment_terms?: string | null
  is_active?: boolean
}

export async function listSuppliers(params?: {
  is_active?: boolean
  search?: string
  page?: number
  page_size?: number
}) {
  return await fetchAttendanceListWithTotal<InventorySupplier>('/inventory/suppliers', params)
}

export async function createSupplier(payload: InventorySupplierPayload): Promise<InventorySupplier> {
  return await $attendanceApi('/inventory/suppliers', { method: 'POST', body: payload })
}

export async function updateSupplier(
  id: string,
  payload: Partial<InventorySupplierPayload>,
): Promise<InventorySupplier> {
  return await $attendanceApi(`/inventory/suppliers/${id}`, { method: 'PATCH', body: payload })
}

// ---- Purchase orders ----

export type PurchaseOrderStatus = 'draft' | 'ordered' | 'partial' | 'received' | 'cancelled'
export type InventoryDocStatus = 'draft' | 'confirmed' | 'void'

export interface PurchaseOrderLine {
  id: string
  item_id: string
  sku_code: string
  name_zh: string
  ordered_qty: number
  received_qty: number
  unit_cost: number
  discount_amount: number
  amount: number
}

export interface PurchaseOrder {
  id: string
  po_no: string
  supplier_id: string
  location_id: string
  order_date: string
  expected_date: string | null
  status: PurchaseOrderStatus
  discount_amount: number
  total: number
  notes: string | null
  created_by: string | null
  created_at: string
  updated_at: string
  lines: PurchaseOrderLine[]
  supplier_name: string | null
  location_name: string | null
}

export interface PurchaseOrderLinePayload {
  item_id: string
  ordered_qty: number
  unit_cost: number
  discount_amount?: number
}

export interface PurchaseOrderPayload {
  supplier_id: string
  location_id: string
  order_date: string
  expected_date?: string | null
  discount_amount?: number
  notes?: string | null
  lines?: PurchaseOrderLinePayload[]
}

export async function listPurchaseOrders(params?: {
  supplier_id?: string
  location_id?: string
  status?: PurchaseOrderStatus
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}) {
  return await fetchAttendanceListWithTotal<PurchaseOrder>('/inventory/purchase-orders', params)
}

export async function getPurchaseOrder(id: string): Promise<PurchaseOrder> {
  return await $attendanceApi(`/inventory/purchase-orders/${id}`)
}

export async function createPurchaseOrder(payload: PurchaseOrderPayload): Promise<PurchaseOrder> {
  return await $attendanceApi('/inventory/purchase-orders', { method: 'POST', body: payload })
}

export async function updatePurchaseOrder(
  id: string,
  payload: Partial<PurchaseOrderPayload>,
): Promise<PurchaseOrder> {
  return await $attendanceApi(`/inventory/purchase-orders/${id}`, { method: 'PATCH', body: payload })
}

export async function deletePurchaseOrder(id: string): Promise<void> {
  return await $attendanceApi(`/inventory/purchase-orders/${id}`, { method: 'DELETE' })
}

export async function orderPurchaseOrder(id: string): Promise<PurchaseOrder> {
  return await $attendanceApi(`/inventory/purchase-orders/${id}/order`, { method: 'POST' })
}

export async function cancelPurchaseOrder(id: string): Promise<PurchaseOrder> {
  return await $attendanceApi(`/inventory/purchase-orders/${id}/cancel`, { method: 'POST' })
}

// ---- Goods receipts ----

export interface GoodsReceiptLine {
  id: string
  item_id: string
  po_line_id: string | null
  qty: number
  unit_cost: number
  sku_code: string | null
  name_zh: string | null
}

export interface GoodsReceipt {
  id: string
  grn_no: string
  po_id: string | null
  supplier_id: string
  location_id: string
  receipt_date: string
  status: InventoryDocStatus
  notes: string | null
  created_by: string | null
  created_at: string
  updated_at: string
  lines: GoodsReceiptLine[]
  supplier_name: string | null
  location_name: string | null
  po_no: string | null
}

export interface GoodsReceiptLinePayload {
  item_id: string
  qty: number
  unit_cost: number
  po_line_id?: string | null
}

export interface GoodsReceiptPayload {
  po_id?: string | null
  supplier_id: string
  location_id: string
  receipt_date: string
  notes?: string | null
  allow_over_receipt?: boolean
  lines?: GoodsReceiptLinePayload[]
}

export async function listGoodsReceipts(params?: {
  supplier_id?: string
  location_id?: string
  po_id?: string
  status?: InventoryDocStatus
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}) {
  return await fetchAttendanceListWithTotal<GoodsReceipt>('/inventory/goods-receipts', params)
}

export async function getGoodsReceipt(id: string): Promise<GoodsReceipt> {
  return await $attendanceApi(`/inventory/goods-receipts/${id}`)
}

export async function createGoodsReceipt(payload: GoodsReceiptPayload): Promise<GoodsReceipt> {
  return await $attendanceApi('/inventory/goods-receipts', { method: 'POST', body: payload })
}

export async function updateGoodsReceipt(
  id: string,
  payload: { receipt_date?: string; notes?: string | null; lines?: GoodsReceiptLinePayload[]; allow_over_receipt?: boolean },
): Promise<GoodsReceipt> {
  return await $attendanceApi(`/inventory/goods-receipts/${id}`, { method: 'PATCH', body: payload })
}

export async function deleteGoodsReceipt(id: string): Promise<void> {
  return await $attendanceApi(`/inventory/goods-receipts/${id}`, { method: 'DELETE' })
}

export async function confirmGoodsReceipt(id: string, allowOverReceipt = false): Promise<GoodsReceipt> {
  return await $attendanceApi(`/inventory/goods-receipts/${id}/confirm`, {
    method: 'POST',
    body: { allow_over_receipt: allowOverReceipt },
  })
}

export async function voidGoodsReceipt(id: string): Promise<GoodsReceipt> {
  return await $attendanceApi(`/inventory/goods-receipts/${id}/void`, { method: 'POST' })
}

// ---- Purchase returns ----

export interface PurchaseReturnLine {
  id: string
  item_id: string
  qty: number
  unit_cost: number
  sku_code: string | null
  name_zh: string | null
}

export interface PurchaseReturn {
  id: string
  prt_no: string
  supplier_id: string
  location_id: string
  grn_id: string | null
  return_date: string
  status: InventoryDocStatus
  notes: string | null
  created_by: string | null
  created_at: string
  updated_at: string
  lines: PurchaseReturnLine[]
  supplier_name: string | null
  location_name: string | null
  grn_no: string | null
}

export interface PurchaseReturnLinePayload {
  item_id: string
  qty: number
  unit_cost: number
}

export interface PurchaseReturnPayload {
  supplier_id: string
  location_id: string
  grn_id?: string | null
  return_date: string
  notes?: string | null
  lines?: PurchaseReturnLinePayload[]
}

export async function listPurchaseReturns(params?: {
  supplier_id?: string
  location_id?: string
  grn_id?: string
  status?: InventoryDocStatus
  page?: number
  page_size?: number
}) {
  return await fetchAttendanceListWithTotal<PurchaseReturn>('/inventory/purchase-returns', params)
}

export async function getPurchaseReturn(id: string): Promise<PurchaseReturn> {
  return await $attendanceApi(`/inventory/purchase-returns/${id}`)
}

export async function createPurchaseReturn(payload: PurchaseReturnPayload): Promise<PurchaseReturn> {
  return await $attendanceApi('/inventory/purchase-returns', { method: 'POST', body: payload })
}

export async function updatePurchaseReturn(
  id: string,
  payload: { grn_id?: string | null; return_date?: string; notes?: string | null; lines?: PurchaseReturnLinePayload[] },
): Promise<PurchaseReturn> {
  return await $attendanceApi(`/inventory/purchase-returns/${id}`, { method: 'PATCH', body: payload })
}

export async function deletePurchaseReturn(id: string): Promise<void> {
  return await $attendanceApi(`/inventory/purchase-returns/${id}`, { method: 'DELETE' })
}

export async function confirmPurchaseReturn(id: string): Promise<PurchaseReturn> {
  return await $attendanceApi(`/inventory/purchase-returns/${id}/confirm`, { method: 'POST' })
}

export async function voidPurchaseReturn(id: string): Promise<PurchaseReturn> {
  return await $attendanceApi(`/inventory/purchase-returns/${id}/void`, { method: 'POST' })
}
