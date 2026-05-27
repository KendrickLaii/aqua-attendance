import { $attendanceApi } from '@/utils/attendanceApi'

export interface LocationDetailPhoto {
  url: string
  caption?: string | null
  sort_order?: number
}

export interface LocationItem {
  id: string
  code: string | null
  name_zh: string | null
  name_en: string
  location_type: string | null
  region: string | null
  business_hours: string | null
  icon_url: string | null
  main_photo_url: string | null
  detail_photos: LocationDetailPhoto[] | null
  address: string | null
  contact_person: string | null
  phone: string | null
  email: string | null
  notes: string | null
  details: Record<string, unknown> | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface LocationPayload {
  code?: string | null
  name_zh?: string | null
  name_en: string
  location_type?: string | null
  region?: string | null
  business_hours?: string | null
  icon_url?: string | null
  main_photo_url?: string | null
  detail_photos?: LocationDetailPhoto[] | null
  address?: string | null
  contact_person?: string | null
  phone?: string | null
  email?: string | null
  notes?: string | null
  details?: Record<string, unknown> | null
  is_active?: boolean
}

export async function listLocations(params?: {
  is_active?: boolean
  search?: string
  page?: number
  page_size?: number
}): Promise<LocationItem[]> {
  return await $attendanceApi('/locations', { params })
}

export async function createLocation(payload: LocationPayload): Promise<LocationItem> {
  return await $attendanceApi('/locations', { method: 'POST', body: payload })
}

export async function updateLocation(locationId: string, payload: Partial<LocationPayload>): Promise<LocationItem> {
  return await $attendanceApi(`/locations/${locationId}`, { method: 'PATCH', body: payload })
}

export async function deleteLocation(locationId: string): Promise<void> {
  await $attendanceApi(`/locations/${locationId}`, { method: 'DELETE' })
}
