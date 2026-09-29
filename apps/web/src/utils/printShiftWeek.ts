import type { Shift } from '../api/attendance/shifts'
import { cellKey, formatDayHeader, formatShiftHours, hhmm, parseIsoDate, totalMinutes } from './shiftDisplay'

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** grid = everyone on one landscape sheet; personal = one portrait schedule per staff member. */
export type ShiftPrintLayout = 'grid' | 'personal'

export interface ShiftPrintStaff { id: string; name: string; code: string }

export type ShiftPrintPeriod = 'week' | 'month'

export interface ShiftPrintOptions {
  layout: ShiftPrintLayout

  /** Month prints use the personal layout only (31 columns do not fit a grid). */
  period: ShiftPrintPeriod

  /** e.g. "28 Sep – 4 Oct 2026" or "September 2026". */
  periodLabel: string
  locationLabel: string
  dates: string[]
  staff: ShiftPrintStaff[]
  shiftsByCell: Map<string, Shift[]>

  /** When set, each shift shows its branch (used for "All locations"). */
  locationNames?: Map<string, string>
  showNotes: boolean

  /** Personal layout: list days without shifts as "Off". */
  showDaysOff: boolean

  /** Personal layout: start each staff member on a new page. */
  pageBreak: boolean

  /** Personal layout: add a staff signature line (for confirming 報更). */
  signature: boolean
  printedAt: string
}

/** What the print dialog collects; the page turns it into ShiftPrintOptions. */
export type ShiftPrintChoice = Pick<ShiftPrintOptions, 'layout' | 'period' | 'showNotes' | 'showDaysOff' | 'pageBreak' | 'signature'> & {
  staffIds: string[]
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

function staffShifts(o: ShiftPrintOptions, staffId: string): Shift[] {
  return o.dates.flatMap(d => o.shiftsByCell.get(cellKey(staffId, d)) ?? [])
}

function renderGrid(o: ShiftPrintOptions): string {
  const headCells = o.dates.map(d => {
    const { weekday, day } = formatDayHeader(d)

    return `<th>${weekday}<br><span class="sub">${day}</span></th>`
  }).join('')

  const bodyRows = o.staff.map(row => {
    const cells = o.dates.map(d => {
      const shifts = o.shiftsByCell.get(cellKey(row.id, d)) ?? []

      return `<td>${shifts.map(s => `
        <div class="shift" style="border-left-color:${escapeHtml(s.color)}">
          <b>${hhmm(s.start_time)}–${hhmm(s.end_time)}</b>
          ${s.title ? `<div>${escapeHtml(s.title)}</div>` : ''}
          ${o.locationNames?.get(s.location_id) ? `<div class="sub">${escapeHtml(o.locationNames.get(s.location_id)!)}</div>` : ''}
          ${o.showNotes && s.notes ? `<div class="sub">${escapeHtml(s.notes)}</div>` : ''}
        </div>`).join('')}</td>`
    }).join('')

    return `<tr>
      <td class="staff">${escapeHtml(row.name)}<br><span class="sub">${escapeHtml(row.code)}</span></td>
      ${cells}
      <td class="num">${formatShiftHours(totalMinutes(staffShifts(o, row.id)))}</td>
    </tr>`
  }).join('')

  return `
  <h1>Shift Schedule</h1>
  <p class="subtitle">${escapeHtml(o.periodLabel)} · ${escapeHtml(o.locationLabel)} · ${plural(o.staff.length, 'staff member')}</p>
  <table class="grid">
    <thead><tr><th class="staff">Staff</th>${headCells}<th class="num">Total</th></tr></thead>
    <tbody>${bodyRows || '<tr><td colspan="9">No staff selected.</td></tr>'}</tbody>
  </table>`
}

function renderPersonal(o: ShiftPrintOptions): string {
  const showLocation = !!o.locationNames
  const colCount = 4 + (showLocation ? 1 : 0) + (o.showNotes ? 1 : 0)
  const monthly = o.period === 'month'

  return o.staff.map(person => {
    const all = staffShifts(o, person.id)

    let weekMinutes = 0

    const rows = o.dates.map((d, idx) => {
      const { weekday, day } = formatDayHeader(d)
      const shifts = o.shiftsByCell.get(cellKey(person.id, d)) ?? []
      const dayCell = (span: number) => `<td class="day" rowspan="${span}"><b>${weekday}</b> ${day}</td>`
      const weekStartClass = monthly && idx > 0 && parseIsoDate(d).getDay() === 1 ? ' week-start' : ''

      let html = ''
      if (!shifts.length) {
        if (o.showDaysOff)
          html = `<tr class="off${weekStartClass}">${dayCell(1)}<td colspan="${colCount - 1}">Off</td></tr>`
      }
      else {
        html = shifts.map((s, i) => `<tr class="${i === 0 ? weekStartClass.trim() : ''}">
        ${i === 0 ? dayCell(shifts.length) : ''}
        <td class="time"><span class="swatch" style="background:${escapeHtml(s.color)}"></span>${hhmm(s.start_time)}–${hhmm(s.end_time)}</td>
        <td>${escapeHtml(s.title ?? '')}</td>
        ${showLocation ? `<td>${escapeHtml(o.locationNames!.get(s.location_id) ?? '')}</td>` : ''}
        <td class="num">${formatShiftHours(totalMinutes([s]))}</td>
        ${o.showNotes ? `<td class="notes">${escapeHtml(s.notes ?? '')}</td>` : ''}
      </tr>`).join('')
      }

      // Month view: subtotal after each Sunday and at month end so weekly hours are easy to check.
      weekMinutes += totalMinutes(shifts)
      if (monthly && (parseIsoDate(d).getDay() === 0 || idx === o.dates.length - 1)) {
        html += `<tr class="subtotal">
          <td colspan="${colCount - 1 - (o.showNotes ? 1 : 0)}">Week total</td>
          <td class="num">${formatShiftHours(weekMinutes)}</td>
          ${o.showNotes ? '<td></td>' : ''}
        </tr>`
        weekMinutes = 0
      }

      return html
    }).join('')

    return `<section class="sheet${o.pageBreak ? ' break' : ''}">
      <header class="sheet-head">
        <div>
          <h1>${escapeHtml(person.name)} <span class="code">${escapeHtml(person.code)}</span></h1>
          <p class="subtitle">Shift schedule · ${escapeHtml(o.periodLabel)} · ${escapeHtml(o.locationLabel)}</p>
        </div>
        <div class="total"><b>${formatShiftHours(totalMinutes(all))}</b><span>${plural(all.length, 'shift')}</span></div>
      </header>
      <table class="personal">
        <thead><tr>
          <th class="day">Day</th><th class="time">Time</th><th>Shift</th>
          ${showLocation ? '<th>Location</th>' : ''}
          <th class="num">Hours</th>
          ${o.showNotes ? '<th>Notes</th>' : ''}
        </tr></thead>
        <tbody>${all.length || o.showDaysOff ? rows : `<tr><td colspan="${colCount}">No shifts this ${o.period}.</td></tr>`}</tbody>
      </table>
      ${o.signature ? '<div class="sign"><span>Staff signature</span><span>Date</span></div>' : ''}
    </section>`
  }).join('') || '<p>No staff selected.</p>'
}

export function buildShiftPrintHtml(o: ShiftPrintOptions): string {
  const landscape = o.layout === 'grid' && o.period === 'week'

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Shift Schedule — ${escapeHtml(o.periodLabel)}</title>
  <style>
    @page { size: A4 ${landscape ? 'landscape' : 'portrait'}; margin: 12mm; }
    * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; padding: 16px; color: #111; }
    h1 { font-size: 18px; margin: 0 0 2px; }
    .code { color: #777; font-size: 13px; font-weight: 400; }
    .subtitle { font-size: 12px; color: #555; margin: 0 0 12px; }
    .sub { color: #777; font-size: 10px; font-weight: 400; }
    table { width: 100%; border-collapse: collapse; font-size: 11px; }
    th, td { border: 1px solid #ccc; padding: 4px 6px; vertical-align: top; text-align: left; }
    th { background: #f2f2f2; font-weight: 600; }
    td.num, th.num { text-align: right; white-space: nowrap; }
    tr { break-inside: avoid; }

    table.grid { table-layout: fixed; }
    .grid th.staff, .grid td.staff { width: 14%; }
    .grid th.num, .grid td.num { width: 6%; }
    .shift { border-left: 4px solid #999; padding: 2px 4px; margin-bottom: 3px; background: #fafafa; break-inside: avoid; }

    .sheet { margin-bottom: 28px; break-inside: avoid; }
    .sheet.break { break-after: page; margin-bottom: 0; }
    .sheet.break:last-child { break-after: auto; }
    .sheet-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; border-bottom: 2px solid #111; margin-bottom: 10px; }
    .total { text-align: right; }
    .total b { display: block; font-size: 20px; }
    .total span { color: #555; font-size: 11px; }
    table.personal { font-size: 12px; }
    .personal th.day, .personal td.day { width: 22%; }
    .personal th.time, .personal td.time { width: 18%; white-space: nowrap; }
    .personal td.notes { color: #555; }
    .swatch { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 6px; }
    tr.off td { color: #999; }
    tr.week-start td { border-top: 2px solid #888; }
    tr.subtotal td { background: #f7f7f7; color: #444; font-size: 11px; font-weight: 600; }
    tr.subtotal td:first-child { text-align: right; }
    .sign { display: flex; gap: 32px; margin-top: 36px; font-size: 11px; color: #555; }
    .sign span { flex: 1; border-top: 1px solid #111; padding-top: 4px; }
    .sign span:last-child { flex: 0 0 30%; }

    footer { margin-top: 12px; color: #999; font-size: 10px; }
    @media print { body { padding: 0; } }
  </style>
</head>
<body>
  ${landscape ? renderGrid(o) : renderPersonal(o)}
  <footer>Printed ${escapeHtml(o.printedAt)}</footer>
</body>
</html>`
}

/** Call synchronously from a click handler (pop-up blockers); data must already be loaded. */
export function printShiftWeek(options: ShiftPrintOptions) {
  const printWindow = window.open('about:blank', '_blank')
  if (!printWindow)
    throw new Error('Pop-up blocked. Allow pop-ups to print the shift schedule.')

  printWindow.document.open()
  printWindow.document.write(buildShiftPrintHtml(options))
  printWindow.document.close()
  printWindow.focus()
  printWindow.print()
}
