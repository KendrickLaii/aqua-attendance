import { $attendanceApi } from '@/utils/attendanceApi'
import { fetchAttendanceListWithTotal } from '@/utils/attendanceListApi'

// ---- Customers ----

export type InventoryCustomerType = 'individual' | 'company'

export interface InventoryCustomer {
  id: string
  code: string
  name_zh: string
  name_en: string | null
  type: InventoryCustomerType
  contact_name: string | null
  phone: string | null
  email: string | null
  address: string | null
  student_unit_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface InventoryCustomerPayload {
  code: string
  name_zh: string
  name_en?: string | null
  type?: InventoryCustomerType
  contact_name?: string | null
  phone?: string | null
  email?: string | null
  address?: string | null
  is_active?: boolean
}

export async function listCustomers(params?: {
  is_active?: boolean
  type?: InventoryCustomerType
  search?: string
  page?: number
  page_size?: number
}) {
  return await fetchAttendanceListWithTotal<InventoryCustomer>('/inventory/customers', params)
}

export async function createCustomer(payload: InventoryCustomerPayload): Promise<InventoryCustomer> {
  return await $attendanceApi('/inventory/customers', { method: 'POST', body: payload })
}

export async function createCustomerFromStudent(unitId: string): Promise<InventoryCustomer> {
  return await $attendanceApi(`/inventory/customers/from-student/${unitId}`, { method: 'POST' })
}

export async function updateCustomer(
  id: string,
  payload: Partial<InventoryCustomerPayload>,
): Promise<InventoryCustomer> {
  return await $attendanceApi(`/inventory/customers/${id}`, { method: 'PATCH', body: payload })
}

// ---- Sales orders ----

export type SalesOrderStatus = 'draft' | 'confirmed' | 'partial' | 'fulfilled' | 'cancelled'

export interface SalesOrderLine {
  id: string
  item_id: string
  sku_code: string
  name_zh: string
  qty: number
  shipped_qty: number
  unit_price: number
  discount_amount: number
  amount: number
}

export interface SalesOrder {
  id: string
  so_no: string
  customer_id: string
  buyer_name: string
  location_id: string
  order_date: string
  status: SalesOrderStatus
  discount_amount: number
  total: number
  notes: string | null
  pf_no: string | null
  pf_issued_at: string | null
  pf_valid_until: string | null
  created_by: string | null
  created_at: string
  updated_at: string
  lines: SalesOrderLine[]
  customer_name: string | null
  customer_code: string | null
  location_name: string | null
}

export interface SalesOrderLinePayload {
  item_id: string
  qty: number
  unit_price: number
  discount_amount?: number
}

export interface SalesOrderPayload {
  customer_id: string
  location_id: string
  order_date: string
  discount_amount?: number
  notes?: string | null
  lines?: SalesOrderLinePayload[]
}

export interface ProformaDoc {
  pf_no: string
  so_no: string
  issued_at: string
  valid_until: string | null
  order_date: string
  location_name_zh: string | null
  location_name_en: string | null
  location_address: string | null
  location_phone: string | null
  location_email: string | null
  customer_name: string
  customer_code: string | null
  customer_contact: string | null
  customer_phone: string | null
  customer_email: string | null
  customer_address: string | null
  lines: SalesOrderLine[]
  discount_amount: number
  subtotal: number
  total: number
  notes: string | null
}

export async function listSalesOrders(params?: {
  customer_id?: string
  location_id?: string
  status?: SalesOrderStatus
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}) {
  return await fetchAttendanceListWithTotal<SalesOrder>('/inventory/sales-orders', params)
}

export async function getSalesOrder(id: string): Promise<SalesOrder> {
  return await $attendanceApi(`/inventory/sales-orders/${id}`)
}

export async function createSalesOrder(payload: SalesOrderPayload): Promise<SalesOrder> {
  return await $attendanceApi('/inventory/sales-orders', { method: 'POST', body: payload })
}

export async function updateSalesOrder(
  id: string,
  payload: Partial<SalesOrderPayload>,
): Promise<SalesOrder> {
  return await $attendanceApi(`/inventory/sales-orders/${id}`, { method: 'PATCH', body: payload })
}

export async function deleteSalesOrder(id: string): Promise<void> {
  return await $attendanceApi(`/inventory/sales-orders/${id}`, { method: 'DELETE' })
}

export async function confirmSalesOrder(id: string): Promise<SalesOrder> {
  return await $attendanceApi(`/inventory/sales-orders/${id}/confirm`, { method: 'POST' })
}

export async function cancelSalesOrder(id: string): Promise<SalesOrder> {
  return await $attendanceApi(`/inventory/sales-orders/${id}/cancel`, { method: 'POST' })
}

export async function issueProforma(id: string, pfValidUntil?: string | null): Promise<SalesOrder> {
  return await $attendanceApi(`/inventory/sales-orders/${id}/proforma`, {
    method: 'POST',
    body: { pf_valid_until: pfValidUntil || null },
  })
}

export async function getProforma(id: string): Promise<ProformaDoc> {
  return await $attendanceApi(`/inventory/sales-orders/${id}/proforma`)
}

// ---- Delivery orders ----

export type DeliveryOrderStatus = 'draft' | 'confirmed' | 'void'

export interface DeliveryOrderLine {
  id: string
  so_line_id: string
  item_id: string
  qty: number
  sku_code: string | null
  name_zh: string | null
}

export interface DeliveryOrder {
  id: string
  do_no: string
  so_id: string
  customer_id: string
  location_id: string
  delivery_date: string
  status: DeliveryOrderStatus
  notes: string | null
  created_by: string | null
  created_at: string
  updated_at: string
  lines: DeliveryOrderLine[]
  so_no_ref: string | null
  customer_name: string | null
  location_name: string | null
}

export interface DeliveryOrderLinePayload {
  so_line_id: string
  item_id: string
  qty: number
}

export interface DeliveryOrderPayload {
  so_id: string
  delivery_date: string
  notes?: string | null
  lines?: DeliveryOrderLinePayload[]
}

export async function listDeliveryOrders(params?: {
  customer_id?: string
  location_id?: string
  so_id?: string
  status?: DeliveryOrderStatus
  search?: string
  page?: number
  page_size?: number
}) {
  return await fetchAttendanceListWithTotal<DeliveryOrder>('/inventory/delivery-orders', params)
}

export async function getDeliveryOrder(id: string): Promise<DeliveryOrder> {
  return await $attendanceApi(`/inventory/delivery-orders/${id}`)
}

export async function createDeliveryOrder(payload: DeliveryOrderPayload): Promise<DeliveryOrder> {
  return await $attendanceApi('/inventory/delivery-orders', { method: 'POST', body: payload })
}

export async function updateDeliveryOrder(
  id: string,
  payload: { delivery_date?: string; notes?: string | null; lines?: DeliveryOrderLinePayload[] },
): Promise<DeliveryOrder> {
  return await $attendanceApi(`/inventory/delivery-orders/${id}`, { method: 'PATCH', body: payload })
}

export async function deleteDeliveryOrder(id: string): Promise<void> {
  return await $attendanceApi(`/inventory/delivery-orders/${id}`, { method: 'DELETE' })
}

export async function confirmDeliveryOrder(id: string): Promise<DeliveryOrder> {
  return await $attendanceApi(`/inventory/delivery-orders/${id}/confirm`, { method: 'POST' })
}

export async function voidDeliveryOrder(id: string): Promise<DeliveryOrder> {
  return await $attendanceApi(`/inventory/delivery-orders/${id}/void`, { method: 'POST' })
}
