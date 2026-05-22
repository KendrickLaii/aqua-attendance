export function formatAttendanceDateTime(iso: string | null | undefined): string {
  if (!iso)
    return '—'
  const d = new Date(iso)
  return `${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
}

export function formatAttendanceTime(iso: string | null | undefined): string {
  if (!iso)
    return '—'
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export interface LastAttendanceInfo {
  attendance_status: 'checked_in' | 'checked_out'
  last_event_at: string | null
  last_event_location?: string | null
}

/** Human-readable line for product list / QR cards. */
export function formatLastAttendance(p: LastAttendanceInfo): string {
  if (!p.last_event_at)
    return 'No scans yet'

  const when = formatAttendanceDateTime(p.last_event_at)
  const action = p.attendance_status === 'checked_in' ? 'Checked in' : 'Checked out'
  const where = p.last_event_location?.trim()
  if (where)
    return `${action} · ${when} · ${where}`
  return `${action} · ${when}`
}
