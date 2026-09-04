import type { AttendanceSummary } from '@/api/attendance/summaries'
import { formatAttendanceDateTime, formatSummaryDateWithWeekday } from '@/utils/attendanceDisplay'
import {
  type DetailTotals,
  formatDayHours,
  formatDaySlots,
  formatTotalHours,
  formatTotalSlots,
  summaryStatusLabel,
} from '@/utils/summaryDisplay'

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** Call synchronously from a click handler before any await. */
export function openSummaryPrintPlaceholder(): Window {
  const printWindow = window.open('about:blank', '_blank')
  if (!printWindow)
    throw new Error('Pop-up blocked. Allow pop-ups to print attendance summaries.')

  printWindow.document.open()
  printWindow.document.write(`<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Attendance Summary</title></head>
<body style="font-family:system-ui,sans-serif;padding:24px;color:#333">
  <p>Preparing attendance summary…</p>
</body></html>`)
  printWindow.document.close()

  return printWindow
}

export interface SummaryPrintOptions {
  unitName: string
  unitCode: string
  monthLabel: string
  summaries: AttendanceSummary[]
  totals: DetailTotals
}

export function renderSummaryPrintWindow(printWindow: Window, options: SummaryPrintOptions) {
  const { unitName, unitCode, monthLabel, summaries, totals } = options

  const rows = summaries.map(s => `
    <tr>
      <td>${escapeHtml(formatSummaryDateWithWeekday(s.summary_date))}</td>
      <td>${s.first_check_in ? escapeHtml(formatAttendanceDateTime(s.first_check_in)) : '—'}</td>
      <td>${s.last_check_out ? escapeHtml(formatAttendanceDateTime(s.last_check_out)) : '—'}</td>
      <td class="num">${escapeHtml(formatDayHours(s, s.regular_hours))}</td>
      <td class="num">${escapeHtml(formatDaySlots(s, s.regular_slots))}</td>
      <td class="num">${escapeHtml(formatDayHours(s, s.overtime_hours))}</td>
      <td class="num">${escapeHtml(formatDaySlots(s, s.ot_slots))}</td>
      <td>${escapeHtml(summaryStatusLabel(s))}</td>
    </tr>
  `).join('')

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Attendance Summary — ${escapeHtml(unitName)}</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: system-ui, -apple-system, Segoe UI, sans-serif;
      margin: 0;
      padding: 24px;
      color: #111;
    }
    h1 {
      font-size: 18px;
      margin: 0 0 2px;
      font-weight: 700;
    }
    .subtitle {
      font-size: 13px;
      color: #555;
      margin: 0 0 16px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    th, td {
      border: 1px solid #ccc;
      padding: 5px 8px;
      text-align: left;
    }
    th {
      background: #f2f2f2;
      font-weight: 600;
    }
    td.num, th.num {
      text-align: right;
    }
    tfoot td {
      font-weight: 700;
      background: #fafafa;
    }
    @media print {
      body { padding: 0; }
      table { font-size: 11px; }
    }
  </style>
</head>
<body>
  <h1>${escapeHtml(unitName)} <span style="color:#888;font-weight:400">(${escapeHtml(unitCode)})</span></h1>
  <p class="subtitle">${escapeHtml(monthLabel)} · ${totals.days} day${totals.days === 1 ? '' : 's'}</p>
  <table>
    <thead>
      <tr>
        <th>Date</th>
        <th>First In</th>
        <th>Last Out</th>
        <th class="num">Regular</th>
        <th class="num">Reg slots</th>
        <th class="num">OT</th>
        <th class="num">OT slots</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
    <tfoot>
      <tr>
        <td colspan="3">Total</td>
        <td class="num">${escapeHtml(formatTotalHours(totals.regular, totals.reliable))}</td>
        <td class="num">${escapeHtml(formatTotalSlots(totals.regularSlots, totals.reliable))}</td>
        <td class="num">${escapeHtml(formatTotalHours(totals.overtime, totals.reliable))}</td>
        <td class="num">${escapeHtml(formatTotalSlots(totals.otSlots, totals.reliable))}</td>
        <td></td>
      </tr>
    </tfoot>
  </table>
</body>
</html>`

  printWindow.document.open()
  printWindow.document.write(html)
  printWindow.document.close()
}

/** Call synchronously from a click handler; the given data must already be loaded. */
export function printAttendanceSummaries(printWindow: Window, options: SummaryPrintOptions) {
  if (!options.summaries.length)
    return

  renderSummaryPrintWindow(printWindow, options)
  printWindow.focus()
  printWindow.print()
}
