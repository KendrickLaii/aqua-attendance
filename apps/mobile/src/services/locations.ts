import { locationDisplayName as formatLocationName, type LocationNameLocale } from '../utils/locationName';
import { apiRequest } from './api';

export interface LocationItem {
  id: string;
  code: string | null;
  name_zh: string | null;
  name_en: string;
  region: string | null;
  is_active: boolean;
}

export function locationDisplayName(
  loc: LocationItem,
  locale: LocationNameLocale = 'en',
): string {
  return formatLocationName(loc, locale);
}

export async function listLocations(params?: {
  is_active?: boolean;
  page_size?: number;
}): Promise<LocationItem[]> {
  const qs = new URLSearchParams();
  if (params?.is_active !== undefined)
    qs.set('is_active', String(params.is_active));
  if (params?.page_size)
    qs.set('page_size', String(params.page_size));
  const query = qs.toString() ? `?${qs.toString()}` : '';
  return apiRequest<LocationItem[]>(`/locations${query}`);
}

/** Locations this staff member may scan at (staff_shift token). */
export async function listStaffLocations(): Promise<LocationItem[]> {
  const data = await apiRequest<LocationItem[]>('/staff-shifts/locations');
  return data.filter((loc) => loc.is_active);
}
