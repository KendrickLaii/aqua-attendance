import { $attendanceApi } from '@/utils/attendanceApi'

export interface Product {
  id: string
  code: string
  full_name: string
  english_name: string | null
  product_type: string
  is_active: boolean
  status: string
  attendance_status: 'checked_in' | 'checked_out'
  qr_token_version: number
  last_event_at: string | null
  last_event_location: string | null
  gender: string | null
  date_of_birth: string | null
  phone: string | null
  address: string | null
  email: string | null
  emergency_contact_name: string | null
  emergency_contact_phone: string | null
  school_name: string | null
  grade_class: string | null
  guardian1_name: string | null
  guardian1_relationship: string | null
  guardian1_phone: string | null
  guardian2_name: string | null
  guardian2_relationship: string | null
  guardian2_phone: string | null
  whatsapp_enabled: boolean
  remarks: string | null
  created_at: string
  updated_at: string
}

export async function listProducts(params?: {
  product_type?: string
  is_active?: boolean
  search?: string
  page?: number
  page_size?: number
}): Promise<Product[]> {
  return await $attendanceApi('/products', { params })
}

export async function getProduct(productId: string): Promise<Product> {
  return await $attendanceApi(`/products/${productId}`)
}

export async function createProduct(payload: {
  code: string
  full_name: string
  english_name?: string | null
  product_type: string
  status?: string
  gender?: string | null
  date_of_birth?: string | null
  phone?: string | null
  address?: string | null
  email?: string | null
  emergency_contact_name?: string | null
  emergency_contact_phone?: string | null
  school_name?: string | null
  grade_class?: string | null
  guardian1_name?: string | null
  guardian1_relationship?: string | null
  guardian1_phone?: string | null
  guardian2_name?: string | null
  guardian2_relationship?: string | null
  guardian2_phone?: string | null
  whatsapp_enabled?: boolean
  remarks?: string | null
}): Promise<Product> {
  return await $attendanceApi('/products', { method: 'POST', body: payload })
}

export async function updateProduct(productId: string, payload: {
  code?: string
  full_name?: string
  english_name?: string | null
  product_type?: string
  is_active?: boolean
  status?: string
  gender?: string | null
  date_of_birth?: string | null
  phone?: string | null
  address?: string | null
  email?: string | null
  emergency_contact_name?: string | null
  emergency_contact_phone?: string | null
  school_name?: string | null
  grade_class?: string | null
  guardian1_name?: string | null
  guardian1_relationship?: string | null
  guardian1_phone?: string | null
  guardian2_name?: string | null
  guardian2_relationship?: string | null
  guardian2_phone?: string | null
  whatsapp_enabled?: boolean
  remarks?: string | null
}): Promise<Product> {
  return await $attendanceApi(`/products/${productId}`, { method: 'PATCH', body: payload })
}

export async function deleteProduct(productId: string): Promise<void> {
  await $attendanceApi(`/products/${productId}`, { method: 'DELETE' })
}
