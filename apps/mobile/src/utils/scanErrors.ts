import { ApiError } from '../services/api';

export interface AllowedLocationRef {
  id: string;
  code: string | null;
  name_zh: string;
  name_en: string;
}

export function allowedLocationLabel(loc: AllowedLocationRef): string {
  return loc.name_en || loc.name_zh || loc.code || loc.id;
}

export function isLocationNotAllowedError(error: unknown): error is ApiError {
  if (!(error instanceof ApiError) || error.status !== 403) return false;
  const detail = error.detail;
  return (
    typeof detail === 'object' &&
    detail !== null &&
    (detail as { code?: string }).code === 'location_not_allowed'
  );
}

export function getLocationNotAllowedDetail(error: ApiError): {
  message: string;
  productName: string | null;
  allowedLocations: AllowedLocationRef[];
} {
  const detail = error.detail as {
    message?: string;
    product_name?: string | null;
    allowed_locations?: AllowedLocationRef[];
  };
  return {
    message: detail.message || error.message,
    productName: detail.product_name ?? null,
    allowedLocations: detail.allowed_locations ?? [],
  };
}
