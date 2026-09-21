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

export async function fetchAllAttendancePages<T>(
  path: string,
  params?: Record<string, unknown>,
  pageSize = 200,
): Promise<AttendanceListResult<T>> {
  const first = await fetchAttendanceListWithTotal<T>(path, { ...params, page: 1, page_size: pageSize })
  const items = [...first.items]
  const total = first.total
  let page = 2
  while (items.length < total) {
    const next = await fetchAttendanceListWithTotal<T>(path, { ...params, page, page_size: pageSize })
    if (next.items.length === 0)
      break
    items.push(...next.items)
    page += 1
  }

  return { items, total }
}
