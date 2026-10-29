import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import type { CourseEnrollment, CourseSku } from '../api/attendance/courses'
import {
  emptyToNull,
  enrollBillPreview,
  enrollDisabledReason,
  enrollmentPriceParts,
  enrollmentStatusLabel,
  existingEnrollmentHint,
  formatRosterDate,
  lastDayOfMonth,
  matchesRosterSearch,
  purchaseSummary,
  renewEndDate,
  rosterPriceLabel,
  skuBillingPreview,
} from './courseRosterDisplay'

function sku(over: Partial<CourseSku> = {}): CourseSku {
  return {
    id: 'sku-1',
    spu_id: 'spu-1',
    code: 'MATH-P3',
    name_zh: '小三数学',
    name_en: null,
    level: 'P3',
    schedule_note: 'Tue 18:00',
    location_id: null,
    staff_id: null,
    capacity: 8,
    price: 800,
    billing_unit: 'monthly',
    meeting_weekdays: ['tuesday'],
    is_active: true,
    created_at: '',
    updated_at: '',
    ...over,
  }
}

function enrollment(over: Partial<CourseEnrollment> = {}): CourseEnrollment {
  return {
    id: 'e1',
    unit_id: 'u1',
    sku_id: 'sku-1',
    status: 'active',
    enrolled_at: '2026-03-01T00:00:00Z',
    start_date: '2026-03-01',
    end_date: null,
    unit_price: null,
    notes: null,
    purchases: [],
    unit_code: 'STU-1',
    unit_name: 'Chan Tai Man',
    created_at: '',
    updated_at: '',
    ...over,
  }
}

describe('formatRosterDate / emptyToNull', () => {
  it('keeps the calendar day and uses the empty label', () => {
    assert.equal(formatRosterDate('2026-03-15T12:00:00Z'), '2026-03-15')
    assert.equal(formatRosterDate(null), '—')
    assert.equal(formatRosterDate(null, 'Already started'), 'Already started')
  })

  it('turns blank strings into null', () => {
    assert.equal(emptyToNull('  '), null)
    assert.equal(emptyToNull('2026-03-01'), '2026-03-01')
  })
})

describe('rosterPriceLabel / skuBillingPreview', () => {
  it('labels monthly vs per-session prices', () => {
    assert.equal(rosterPriceLabel(sku()), 'HK$800.00 / month')
    assert.equal(rosterPriceLabel(sku({ billing_unit: 'per_session', price: 120 })), 'HK$120.00 / session')
    assert.equal(rosterPriceLabel(sku({ price: null })), 'No price — Generate will skip this class')
  })

  it('explains generate skip when the class has no price', () => {
    assert.match(skuBillingPreview('monthly', null), /no price/i)
    assert.match(skuBillingPreview('per_session', 120), /sessions purchased/)
  })
})

describe('purchaseSummary', () => {
  it('counts total and unbilled sessions', () => {
    const row = enrollment({
      purchases: [
        { id: 'p1', enrollment_id: 'e1', purchased_quantity: 8, unit_price: 120, purchased_at: '2026-03-01', billed_invoice_line_id: 'line-1', notes: null, created_at: '' },
        { id: 'p2', enrollment_id: 'e1', purchased_quantity: 4, unit_price: 120, purchased_at: '2026-04-01', billed_invoice_line_id: null, notes: null, created_at: '' },
      ],
    })

    assert.deepEqual(purchaseSummary(row), { total: 12, unbilledQty: 4 })
  })
})

describe('enrollment labels', () => {
  it('maps status and price override vs class price', () => {
    assert.equal(enrollmentStatusLabel('active'), 'In class')
    assert.equal(enrollmentStatusLabel('cancelled'), 'Left')
    assert.equal(enrollmentStatusLabel('completed'), 'Left')
    assert.deepEqual(enrollmentPriceParts(enrollment({ unit_price: 900 }), sku()), {
      amount: 'HK$900.00',
      hint: 'this student',
    })
    assert.deepEqual(enrollmentPriceParts(enrollment(), sku()), {
      amount: 'HK$800.00',
      hint: 'class / month',
    })
    assert.equal(enrollmentPriceParts(enrollment(), sku({ price: null })), null)
  })
})

describe('matchesRosterSearch', () => {
  it('matches API name/code without a cached unit', () => {
    assert.equal(matchesRosterSearch(enrollment(), 'tai'), true)
    assert.equal(matchesRosterSearch(enrollment(), 'STU-1'), true)
    assert.equal(matchesRosterSearch(enrollment(), 'nobody'), false)
  })
})

describe('enrollDisabledReason', () => {
  it('blocks enroll when the class is missing, inactive, or full for a new student', () => {
    const monthly = sku()

    assert.equal(enrollDisabledReason({
      skuId: null,
      sku: null,
      atCapacity: false,
      studentId: null,
      activeUnitIds: new Set(),
      purchasedQuantity: null,
    }), 'Pick a class first.')

    assert.equal(enrollDisabledReason({
      skuId: monthly.id,
      sku: { ...monthly, is_active: false },
      atCapacity: false,
      studentId: 'u1',
      activeUnitIds: new Set(),
      purchasedQuantity: null,
    }), 'This class is inactive — Generate skips it.')

    assert.equal(enrollDisabledReason({
      skuId: monthly.id,
      sku: monthly,
      atCapacity: false,
      studentId: null,
      activeUnitIds: new Set(),
      purchasedQuantity: null,
    }), 'Search and pick a student.')

    assert.equal(enrollDisabledReason({
      skuId: monthly.id,
      sku: monthly,
      atCapacity: true,
      studentId: 'u1',
      activeUnitIds: new Set(),
      purchasedQuantity: null,
    }), 'This class is full.')
  })

  it('requires session count for per-session classes', () => {
    const perSession = sku({ billing_unit: 'per_session' })

    assert.equal(enrollDisabledReason({
      skuId: perSession.id,
      sku: perSession,
      atCapacity: false,
      studentId: 'u1',
      activeUnitIds: new Set(),
      purchasedQuantity: null,
    }), 'Enter how many sessions this student bought.')
  })

  it('lets an in-class student top up or update instead of blocking', () => {
    const perSession = sku({ billing_unit: 'per_session' })
    const monthly = sku()

    // In-class per_session still needs a quantity for the new purchase.
    assert.equal(enrollDisabledReason({
      skuId: perSession.id,
      sku: perSession,
      atCapacity: false,
      studentId: 'u1',
      activeUnitIds: new Set(['u1']),
      purchasedQuantity: null,
    }), 'Enter how many sessions to add.')

    // Capacity never blocks someone already in class — no new seat.
    assert.equal(enrollDisabledReason({
      skuId: perSession.id,
      sku: perSession,
      atCapacity: true,
      studentId: 'u1',
      activeUnitIds: new Set(['u1']),
      purchasedQuantity: 4,
    }), '')

    assert.equal(enrollDisabledReason({
      skuId: monthly.id,
      sku: monthly,
      atCapacity: true,
      studentId: 'u1',
      activeUnitIds: new Set(['u1']),
      purchasedQuantity: null,
    }), '')
  })
})

describe('existingEnrollmentHint', () => {
  it('explains the per-session top-up with the running total', () => {
    const row = enrollment({
      purchases: [
        { id: 'p1', enrollment_id: 'e1', purchased_quantity: 8, unit_price: 120, purchased_at: '2026-03-01', billed_invoice_line_id: null, notes: null, created_at: '' },
      ],
    })

    assert.equal(
      existingEnrollmentHint(sku({ billing_unit: 'per_session' }), row),
      'Already in class (8 sessions so far) — this adds a new purchase record. Each top-up is billed separately.',
    )
  })

  it('shows the current billing window for monthly classes', () => {
    const row = enrollment({ start_date: '2026-03-01', end_date: '2026-05-31' })

    assert.equal(
      existingEnrollmentHint(sku(), row),
      'Already in class — this updates the current billing window (2026-03-01 → 2026-05-31).',
    )
    assert.equal(existingEnrollmentHint(sku(), null), '')
  })
})

describe('renewEndDate', () => {
  it('extends to the last day of the month after the current end', () => {
    assert.equal(renewEndDate('2026-09-30'), '2026-10-31')
    assert.equal(renewEndDate('2026-01-15'), '2026-02-28')
    assert.equal(renewEndDate('2024-01-31'), '2024-02-29')
    assert.equal(renewEndDate('2026-12-01'), '2027-01-31')
  })
})

describe('lastDayOfMonth', () => {
  it('uses the last calendar day of that month', () => {
    assert.equal(lastDayOfMonth('2026-10-02'), '2026-10-31')
    assert.equal(lastDayOfMonth('2026-02-10'), '2026-02-28')
    assert.equal(lastDayOfMonth('2024-02-01'), '2024-02-29')
  })
})

describe('enrollBillPreview', () => {
  it('describes monthly vs per-session billing', () => {
    assert.match(enrollBillPreview({ sku: sku(), unitPrice: null, purchasedQuantity: null }), /every month/)
    assert.match(
      enrollBillPreview({ sku: sku({ billing_unit: 'per_session' }), unitPrice: null, purchasedQuantity: 8 }),
      /8 sessions/,
    )
  })
})
