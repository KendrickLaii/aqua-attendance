import { deleteItemAsync, getItemAsync, setItemAsync } from './storage';

/** Persisted default scan location and check-in/out mode. */
export const DEFAULT_LOCATION_KEY = 'attendance-default-location-id';
export const DEFAULT_EVENT_TYPE_KEY = 'attendance-default-event-type';

/** @deprecated Migrated to DEFAULT_* keys on read */
const LEGACY_LOCATION_KEY = 'attendance-scan-location-id';
const LEGACY_EVENT_TYPE_KEY = 'attendance-scan-event-type';

export type ScanEventType = 'check_in' | 'check_out';

export interface ScanPrefs {
  locationId: string | null;
  eventType: ScanEventType;
}

export async function loadScanPrefs(): Promise<ScanPrefs> {
  let locationId = await getItemAsync(DEFAULT_LOCATION_KEY);
  let eventTypeRaw = await getItemAsync(DEFAULT_EVENT_TYPE_KEY);

  if (!locationId) {
    const legacyLoc = await getItemAsync(LEGACY_LOCATION_KEY);
    if (legacyLoc) {
      locationId = legacyLoc;
      await setItemAsync(DEFAULT_LOCATION_KEY, legacyLoc);
      await deleteItemAsync(LEGACY_LOCATION_KEY);
    }
  }
  if (!eventTypeRaw) {
    const legacyType = await getItemAsync(LEGACY_EVENT_TYPE_KEY);
    if (legacyType === 'check_in' || legacyType === 'check_out') {
      eventTypeRaw = legacyType;
      await setItemAsync(DEFAULT_EVENT_TYPE_KEY, legacyType);
      await deleteItemAsync(LEGACY_EVENT_TYPE_KEY);
    }
  }

  const eventType: ScanEventType =
    eventTypeRaw === 'check_out' ? 'check_out' : 'check_in';
  return { locationId: locationId || null, eventType };
}

export async function saveDefaultLocation(locationId: string): Promise<void> {
  await setItemAsync(DEFAULT_LOCATION_KEY, locationId);
}

export async function clearDefaultLocation(): Promise<void> {
  await deleteItemAsync(DEFAULT_LOCATION_KEY);
}

export async function saveDefaultEventType(eventType: ScanEventType): Promise<void> {
  await setItemAsync(DEFAULT_EVENT_TYPE_KEY, eventType);
}

/** Drop stored default if the location is missing or inactive. */
export function resolveDefaultLocationId(
  storedId: string | null,
  activeLocationIds: string[],
): string | null {
  if (!storedId) return null;
  return activeLocationIds.includes(storedId) ? storedId : null;
}
