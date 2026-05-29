import type { LocationDetailPhoto } from '@/api/attendance/locations'

export interface DetailPhotoRow {
  url: string
  caption: string
  previewError: boolean
}

export function defaultDetailPhotoRows(): DetailPhotoRow[] {
  return [{ url: '', caption: '', previewError: false }]
}

export function detailPhotosToRows(photos: LocationDetailPhoto[] | null | undefined): DetailPhotoRow[] {
  if (photos?.length) {
    return photos.map(p => ({
      url: p.url,
      caption: p.caption || '',
      previewError: false,
    }))
  }

  return defaultDetailPhotoRows()
}

export function buildDetailPhotos(rows: DetailPhotoRow[]): LocationDetailPhoto[] | null {
  const items = rows
    .map((row, i) => ({ url: row.url.trim(), caption: row.caption.trim() || null, sort_order: i }))
    .filter(r => r.url)

  return items.length ? items : null
}

export function addDetailPhotoRow(rows: DetailPhotoRow[]) {
  rows.push({ url: '', caption: '', previewError: false })
}

export function removeDetailPhotoRow(rows: DetailPhotoRow[], index: number) {
  if (rows.length <= 1)
    rows[0] = { url: '', caption: '', previewError: false }
  else
    rows.splice(index, 1)
}
