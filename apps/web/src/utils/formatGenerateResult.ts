export interface SummaryGenerateResult {
  created: number
  updated: number
  total_days: number
  orphans_deleted?: number
  auto_checkouts?: number
}

export interface StaleSummaryUnit {
  unit_id: string
  unit_code: string | null
  unit_name: string | null
  reason: 'no_summary' | 'outdated'
}

export interface PayrollGenerateResult {
  created: number
  updated: number
  skipped: number
  stale_summaries?: StaleSummaryUnit[]
}

function formatPeriod(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, '0')}`
}

function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return count === 1 ? singular : pluralForm
}

function orphanDetail(orphansDeleted: number | undefined): string | undefined {
  if (!orphansDeleted || orphansDeleted <= 0)
    return undefined

  return `Removed ${orphansDeleted} orphan ${plural(orphansDeleted, 'summary', 'summaries')} with no usable events.`
}

export function formatSummaryGenerateMessage(
  result: SummaryGenerateResult,
  year: number,
  month: number,
  existingSummaryDays = 0,
): { title: string; detail?: string } {
  const period = formatPeriod(year, month)
  const { total_days, created, updated } = result
  const orphanNote = orphanDetail(result.orphans_deleted)

  if (total_days === 0) {
    if (orphanNote) {
      return {
        title: `No check-in events for ${period}`,
        detail: orphanNote,
      }
    }

    if (existingSummaryDays > 0) {
      const rowLabel = plural(existingSummaryDays, 'daily row')
      return {
        title: `No check-in events for ${period}`,
        detail: `Nothing was recalculated. The ${existingSummaryDays} ${rowLabel} below are existing summary data (seed or manual) — not computed from attendance events.`,
      }
    }

    return {
      title: `No check-in events for ${period}`,
      detail: 'No summaries exist for this month yet. Add check-in events, then Generate.',
    }
  }

  const dayLabel = plural(total_days, 'daily summary')
  const withOrphan = (detail?: string) => {
    if (!orphanNote)
      return detail
    return detail ? `${detail} ${orphanNote}` : orphanNote
  }

  if (created === total_days) {
    return {
      title: `Generated ${total_days} ${dayLabel} for ${period}`,
      detail: withOrphan('Calculated from attendance events.'),
    }
  }

  if (created === 0) {
    return {
      title: `Refreshed ${total_days} ${dayLabel} for ${period}`,
      detail: withOrphan('Recalculated from attendance events. Existing rows were updated, not duplicated.'),
    }
  }

  return {
    title: `Processed ${total_days} ${dayLabel} for ${period}`,
    detail: withOrphan(`${created} new, ${updated} refreshed from attendance events.`),
  }
}

function staleWarning(
  stale: StaleSummaryUnit[] | undefined,
  period: string,
): string | undefined {
  if (!stale || stale.length === 0)
    return undefined

  const missing = stale.filter(s => s.reason === 'no_summary').length
  const outdated = stale.filter(s => s.reason === 'outdated').length
  const people = plural(stale.length, 'staff member', 'staff members')
  const reasons: string[] = []

  if (outdated > 0)
    reasons.push(`${outdated} with attendance changed after their summary`)
  if (missing > 0)
    reasons.push(`${missing} with events but no summary yet`)

  return `${stale.length} ${people} may be out of date (${reasons.join(', ')}). Re-generate attendance summaries for ${period}, then run payroll again.`
}

export function formatPayrollGenerateMessage(
  result: PayrollGenerateResult,
  year: number,
  month: number,
): { title: string; detail?: string; warning?: string } {
  const period = formatPeriod(year, month)
  const { created, updated, skipped } = result
  const processed = created + updated
  const warning = staleWarning(result.stale_summaries, period)

  if (processed === 0 && skipped === 0) {
    return {
      title: `No summaries for ${period}`,
      detail: 'Generate attendance summaries first, then run payroll.',
      warning,
    }
  }

  if (processed === 0 && skipped > 0) {
    const recordLabel = plural(skipped, 'record')

    return {
      title: `No payroll changes for ${period}`,
      detail: `All ${skipped} ${recordLabel} are already approved or paid.`,
      warning,
    }
  }

  const personLabel = plural(processed, 'person')

  let title: string
  let detail: string | undefined

  if (created === processed) {
    title = `Generated payroll for ${processed} ${personLabel} — ${period}`
    detail = 'Hours aggregated from attendance summaries.'
  }
  else if (created === 0) {
    title = `Refreshed payroll for ${updated} ${personLabel} — ${period}`
    detail = 'Hours recalculated from attendance summaries.'
  }
  else {
    title = `Processed payroll for ${processed} ${personLabel} — ${period}`
    detail = `${created} new, ${updated} refreshed.`
  }

  if (skipped > 0) {
    const skipLabel = plural(skipped, 'approved/paid record')
    detail = detail
      ? `${detail} ${skipped} ${skipLabel} skipped.`
      : `${skipped} ${skipLabel} skipped.`
  }

  return { title, detail, warning }
}
