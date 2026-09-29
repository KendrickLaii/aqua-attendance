import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import type { Shift } from '../api/attendance/shifts'
import {
  SHIFT_COLORS,
  addDays,
  avatarColor,
  buildShiftCsv,
  findOverlaps,
  formatMonthLabel,
  formatShiftHours,
  formatWeekRange,
  groupShiftsByCell,
  isWeekend,
  mondayOf,
  monthDates,
  monthOfWeek,
  monthOptions,
  overlappingShiftIds,
  readableTextColor,
  staffInitials,
  staffRowsForLocation,
  totalMinutes,
  weekDates,
  weekFromQuery,
} from './shiftDisplay'

function shift(partial: Partial<Shift>): Shift {
  return {
    id: 's1',
    unit_id: 'u1',
    location_id: 'l1',
    shift_date: '2026-09-28',
    start_time: '09:00:00',
    end_time: '13:00:00',
    title: 'Morning',
    color: '#4CAF50',
    notes: null,
    template_id: null,
    created_by_id: null,
    updated_by_id: null,
    created_at: '',
    updated_at: '',
    ...partial,
  }
}

describe('week helpers', () => {
  it('finds Monday for any day, including Sunday', () => {
    assert.equal(mondayOf(new Date(2026, 8, 29)), '2026-09-28')
    assert.equal(mondayOf(new Date(2026, 9, 4)), '2026-09-28')
    assert.equal(mondayOf(new Date(2026, 8, 28)), '2026-09-28')
  })

  it('crosses month and year boundaries', () => {
    assert.equal(addDays('2026-12-28', 7), '2027-01-04')
    assert.deepEqual(weekDates('2026-09-28').at(-1), '2026-10-04')
    assert.equal(formatWeekRange('2026-09-28'), '28 Sep – 4 Oct 2026')
    assert.equal(formatWeekRange('2026-12-28'), '28 Dec 2026 – 3 Jan 2027')
  })
})

describe('hours', () => {
  it('sums shift durations', () => {
    const minutes = totalMinutes([shift({}), shift({ start_time: '18:00:00', end_time: '21:30:00' })])

    assert.equal(minutes, 450)
    assert.equal(formatShiftHours(minutes), '7.5h')
    assert.equal(formatShiftHours(0), '0h')
  })
})

describe('overlaps', () => {
  const a = shift({ id: 'a' })
  const b = shift({ id: 'b', start_time: '12:00:00', end_time: '15:00:00' })
  const touching = shift({ id: 'c', start_time: '13:00:00', end_time: '14:00:00' })
  const otherStaff = shift({ id: 'd', unit_id: 'u2' })
  const otherDay = shift({ id: 'e', shift_date: '2026-09-29' })

  it('flags only same staff, same day, intersecting times', () => {
    assert.deepEqual([...overlappingShiftIds([a, b, touching, otherStaff, otherDay])].sort(), ['a', 'b', 'c'])
    assert.deepEqual([...overlappingShiftIds([a, touching, otherStaff, otherDay])], [])
  })

  it('ignores the shift being edited', () => {
    assert.deepEqual(findOverlaps(a, [a]), [])
    assert.deepEqual(findOverlaps({ ...a, id: undefined }, [a]).map(s => s.id), ['a'])
  })
})

describe('groupShiftsByCell', () => {
  it('groups by staff + date sorted by start', () => {
    const late = shift({ id: 'late', start_time: '18:00:00', end_time: '20:00:00' })
    const map = groupShiftsByCell([late, shift({ id: 'early' })])

    assert.deepEqual(map.get('u1|2026-09-28')?.map(s => s.id), ['early', 'late'])
  })
})

describe('staffRowsForLocation', () => {
  const staff = [
    { id: 'home', is_active: true, registered_location_id: 'l1', scan_location_ids: ['l1'] },
    { id: 'scan', is_active: true, registered_location_id: 'l2', scan_location_ids: ['l2', 'l1'] },
    { id: 'other', is_active: true, registered_location_id: 'l2', scan_location_ids: ['l2'] },
    { id: 'gone', is_active: false, registered_location_id: 'l1', scan_location_ids: ['l1'] },
  ]

  it('keeps staff linked to the location and anyone with a shift', () => {
    assert.deepEqual(staffRowsForLocation(staff, [], 'l1').map(u => u.id), ['home', 'scan'])
    assert.deepEqual(staffRowsForLocation(staff, [{ unit_id: 'gone' }], 'l1').map(u => u.id), ['home', 'scan', 'gone'])
    assert.deepEqual(staffRowsForLocation(staff, [], null).map(u => u.id), ['home', 'scan', 'other'])
  })
})

describe('presentation helpers', () => {
  it('picks readable text colour', () => {
    assert.equal(readableTextColor('#1E3A8A'), '#FFFFFF')
    assert.equal(readableTextColor('#FF9800'), 'rgba(0, 0, 0, 0.87)')
    for (const c of SHIFT_COLORS.slice(0, -1))
      assert.equal(readableTextColor(c), '#FFFFFF', c)
    assert.equal(readableTextColor('#F9A825'), 'rgba(0, 0, 0, 0.87)')
    assert.equal(readableTextColor('#FFFFFF'), 'rgba(0, 0, 0, 0.87)')
  })

  it('builds initials for English and Chinese names', () => {
    assert.equal(staffInitials('chan tai man'), 'CT')
    assert.equal(staffInitials('陳大文'), '陳')
    assert.equal(staffInitials('  '), '?')
  })

  it('keeps avatar colour stable per id', () => {
    assert.equal(avatarColor('abc'), avatarColor('abc'))
  })

  it('detects weekends', () => {
    assert.equal(isWeekend('2026-10-03'), true)
    assert.equal(isWeekend('2026-10-04'), true)
    assert.equal(isWeekend('2026-10-05'), false)
  })

  it('normalises ?week= to a Monday', () => {
    const now = new Date(2026, 8, 30)

    assert.equal(weekFromQuery('2026-10-01', now), '2026-09-28')
    assert.equal(weekFromQuery('garbage', now), '2026-09-28')
    assert.equal(weekFromQuery(undefined, now), '2026-09-28')
  })
})

describe('month helpers', () => {
  it('lists every day of the month, including leap February', () => {
    assert.equal(monthDates('2026-09').length, 30)
    assert.equal(monthDates('2026-09').at(-1), '2026-09-30')
    assert.equal(monthDates('2028-02').length, 29)
  })

  it('labels months and picks the month owning a week', () => {
    assert.equal(formatMonthLabel('2026-09'), 'September 2026')
    assert.equal(monthOfWeek('2026-09-28'), '2026-10')
    assert.equal(monthOfWeek('2026-09-21'), '2026-09')
  })

  it('builds month options across a year boundary', () => {
    const options = monthOptions('2026-01', 1, 3)

    assert.deepEqual(options.map(o => o.value), ['2025-12', '2026-01', '2026-02'])
  })
})

describe('buildShiftCsv', () => {
  it('escapes commas and quotes and adds a BOM', () => {
    const csv = buildShiftCsv([{
      date: '2026-09-28',
      staffName: '陳大文',
      staffCode: 'STF-1',
      locationName: 'Branch A',
      shift: { start_time: '09:00:00', end_time: '13:30:00', title: 'Morning', notes: 'cover "Amy", front desk' },
    }])

    assert.ok(csv.startsWith('\uFEFFDate,Weekday,'))
    assert.ok(csv.includes('2026-09-28,Mon,陳大文,STF-1,Branch A,09:00,13:30,4.5,Morning,"cover ""Amy"", front desk"'))
  })
})
