export interface SummaryGenerateResult {
  created: number
  updated: number
  total_days: number
  orphans_deleted?: number
  auto_checkouts?: number
}

export interface PayrollGenerateResult {
  created: number
  updated: number
  skipped: number
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

export function formatPayrollGenerateMessage(
  result: PayrollGenerateResult,
  year: number,
  month: number,
): { title: string; detail?: string } {
  const period = formatPeriod(year, month)
  const { created, updated, skipped } = result
  const processed = created + updated

  if (processed === 0 && skipped === 0) {
    return {
      title: `No summaries for ${period}`,
      detail: 'Generate attendance summaries first, then run payroll.',
    }
  }

  if (processed === 0 && skipped > 0) {
    const recordLabel = plural(skipped, 'record')
    return {
      title: `No payroll changes for ${period}`,
      detail: `All ${skipped} ${recordLabel} are already approved or paid.`,
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

  return { title, detail }
}
