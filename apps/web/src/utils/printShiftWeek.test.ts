import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import type { Shift } from '../api/attendance/shifts'
import { type ShiftPrintOptions, buildShiftPrintHtml } from './printShiftWeek'
import { groupShiftsByCell, monthDates, weekDates } from './shiftDisplay'

function shift(partial: Partial<Shift>): Shift {
  return {
    id: 's1',
    unit_id: 'amy',
    location_id: 'l1',
    shift_date: '2026-09-28',
    start_time: '09:00:00',
    end_time: '13:00:00',
    title: 'Morning',
    color: '#2E7D32',
    notes: null,
    template_id: null,
    created_by_id: null,
    updated_by_id: null,
    created_at: '',
    updated_at: '',
    ...partial,
  }
}

const shifts = [
  shift({ id: 'a1', notes: 'cover <front desk>' }),
  shift({ id: 'a2', start_time: '18:00:00', end_time: '21:30:00', title: 'Evening' }),
  shift({ id: 'b1', unit_id: 'ben', shift_date: '2026-09-30' }),
]

function options(partial: Partial<ShiftPrintOptions> = {}): ShiftPrintOptions {
  return {
    layout: 'personal',
    period: 'week',
    periodLabel: '28 Sep – 4 Oct 2026',
    locationLabel: 'Branch A',
    dates: weekDates('2026-09-28'),
    staff: [{ id: 'amy', name: 'Amy Chan', code: 'STF-1' }],
    shiftsByCell: groupShiftsByCell(shifts),
    showNotes: false,
    showDaysOff: true,
    pageBreak: true,
    signature: false,
    printedAt: '29 Sep 2026 14:00',
    ...partial,
  }
}

describe('buildShiftPrintHtml — personal', () => {
  it('prints only the chosen staff with their weekly total', () => {
    const html = buildShiftPrintHtml(options())

    assert.ok(html.includes('size: A4 portrait'))
    assert.ok(html.includes('Amy Chan'))
    assert.ok(!html.includes('ben'))
    assert.ok(html.includes('<b>7.5h</b><span>2 shifts</span>'))
    assert.ok(html.includes('rowspan="2"'))
    assert.equal(html.match(/>Off</g)?.length, 6)
  })

  it('hides days off, notes and signature unless asked; escapes notes', () => {
    const plain = buildShiftPrintHtml(options({ showDaysOff: false }))

    assert.ok(!plain.includes('>Off<'))
    assert.ok(!plain.includes('front desk'))
    assert.ok(!plain.includes('Staff signature'))

    const full = buildShiftPrintHtml(options({ showNotes: true, signature: true }))

    assert.ok(full.includes('cover &lt;front desk&gt;'))
    assert.ok(full.includes('Staff signature'))
  })

  it('adds a page break per staff and a location column when given names', () => {
    const html = buildShiftPrintHtml(options({
      staff: [{ id: 'amy', name: 'Amy Chan', code: 'STF-1' }, { id: 'ben', name: 'Ben Lee', code: 'STF-2' }],
      locationNames: new Map([['l1', 'Branch A']]),
    }))

    assert.equal(html.match(/class="sheet break"/g)?.length, 2)
    assert.ok(html.includes('<th>Location</th>'))
  })
})

describe('buildShiftPrintHtml — month', () => {
  const month = (partial: Partial<ShiftPrintOptions> = {}) => options({
    period: 'month',
    periodLabel: 'September 2026',
    dates: monthDates('2026-09'),
    shiftsByCell: groupShiftsByCell([
      ...shifts,
      shift({ id: 'a3', shift_date: '2026-09-01', start_time: '10:00:00', end_time: '12:00:00' }),
    ]),
    ...partial,
  })

  it('lists the whole month with weekly subtotals and a month total', () => {
    const html = buildShiftPrintHtml(month())

    assert.ok(html.includes('September 2026'))
    assert.ok(html.includes('size: A4 portrait'))
    assert.ok(html.includes('<b>9.5h</b><span>3 shifts</span>'))

    // Sept 2026: weeks end 6, 13, 20, 27 Sep + month end 30 Sep.
    assert.equal(html.match(/class="subtotal"/g)?.length, 5)
    assert.ok(html.includes('Tue</b> 1 Sep'))
    assert.ok(html.includes('Wed</b> 30 Sep'))
  })

  it('never uses the landscape grid for a month', () => {
    assert.ok(buildShiftPrintHtml(month({ layout: 'grid' })).includes('size: A4 portrait'))
  })
})

describe('buildShiftPrintHtml — grid', () => {
  it('uses landscape and one row per chosen staff', () => {
    const html = buildShiftPrintHtml(options({ layout: 'grid' }))

    assert.ok(html.includes('size: A4 landscape'))
    assert.equal(html.match(/<td class="staff">/g)?.length, 1)
    assert.ok(html.includes('1 staff member'))
  })
})
