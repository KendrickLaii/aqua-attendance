export const enrollmentStatusColor: Record<string, string> = {
  active: 'success',
  completed: 'info',
  cancelled: 'grey',
}

const STATUS_ORDER: Record<string, number> = {
  active: 0,
  completed: 1,
  cancelled: 2,
}

export function billingUnitShortLabel(unit: string | null | undefined): string {
  return unit === 'per_session' ? '堂費' : '月費'
}

export function formatEnrollmentRange(
  start: string | null | undefined,
  end: string | null | undefined,
): string {
  const from = start?.slice(0, 10) || null
  const to = end?.slice(0, 10) || null
  if (!from && !to)
    return 'Already started → Ongoing'
  if (!from)
    return `Already started → ${to}`
  if (!to)
    return `${from} → Ongoing`

  return `${from} → ${to}`
}

export type UnitEnrollmentLike = {
  id: string
  sku_id: string
  status: string
}

export type UnitSkuLike = {
  id: string
  name_zh: string
}

export type UnitEnrollmentRow<E extends UnitEnrollmentLike = UnitEnrollmentLike, S extends UnitSkuLike = UnitSkuLike> = {
  enrollment: E
  sku: S | null
}

export function buildUnitEnrollmentRows<E extends UnitEnrollmentLike, S extends UnitSkuLike>(
  enrollments: E[],
  skus: S[],
): UnitEnrollmentRow<E, S>[] {
  const byId = new Map(skus.map(sku => [sku.id, sku]))
  const rows = enrollments.map(enrollment => ({
    enrollment,
    sku: byId.get(enrollment.sku_id) ?? null,
  }))

  return rows.sort((a, b) => {
    const statusRank = (STATUS_ORDER[a.enrollment.status] ?? 9) - (STATUS_ORDER[b.enrollment.status] ?? 9)
    if (statusRank !== 0)
      return statusRank
    const nameA = a.sku?.name_zh ?? ''
    const nameB = b.sku?.name_zh ?? ''

    return nameA.localeCompare(nameB, 'zh-Hant')
  })
}

export function skuIdFromRouteQuery(query: { sku?: unknown }): string | null {
  return typeof query.sku === 'string' && query.sku.length > 0 ? query.sku : null
}

export function pickCourseSelectionForSku(
  skus: Array<{ id: string; spu_id: string }>,
  skuId: string | null,
): { spuId: string; skuId: string } | null {
  if (!skuId)
    return null
  const sku = skus.find(item => item.id === skuId)
  if (!sku)
    return null

  return { spuId: sku.spu_id, skuId: sku.id }
}
