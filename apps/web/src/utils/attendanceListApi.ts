import { $attendanceApi } from '@/utils/attendanceApi'

export interface AttendanceListResult<T> {
  items: T[]
  total: number
}

export async function fetchAttendanceListWithTotal<T>(
  path: string,
  params?: Record<string, unknown>,
): Promise<AttendanceListResult<T>> {
  let total = 0

  const items = await $attendanceApi<T[]>(path, {
    params,
    onResponse({ response }) {
      const header = response.headers.get('X-Total-Count')
      if (header)
        total = Number.parseInt(header, 10) || 0
    },
  })

  if (!total)
    total = items.length

  return { items, total }
}
