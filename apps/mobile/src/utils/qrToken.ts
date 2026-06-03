/**
 * Normalize camera / paste input into a raw QR JWT for POST /attendance/scan.
 */
export function normalizeQrToken(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return trimmed;

  // Full URL with ?token= or ?qr_token=
  try {
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
      const url = new URL(trimmed);
      const fromQuery =
        url.searchParams.get('qr_token') ||
        url.searchParams.get('token') ||
        url.searchParams.get('t');
      if (fromQuery?.trim()) return fromQuery.trim();
    }
  } catch {
    // not a URL — use as-is
  }

  // Strip accidental quotes from copy/paste
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1).trim();
  }

  return trimmed;
}
