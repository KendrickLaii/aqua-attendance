import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  payrollDetailTotals,
  payrollPaySplitError,
  payrollSummaryStatusColor,
  payrollSummaryStatusIcon,
  payrollSummaryStatusLabel,
} from './payrollDisplay'

describe('payrollPaySplitError', () => {
  it('rejects cheque + cash that do not equal net', () => {
    assert.equal(
      payrollPaySplitError({ cheque: 1000, cash: 1000, net: 9000, chequeNumber: '1' }),
      'Cheque + cash must equal net pay.',
    )
  })

  it('accepts a matching split', () => {
    assert.equal(
      payrollPaySplitError({ cheque: 5000, cash: 4000, net: 9000, chequeNumber: '518862' }),
      null,
    )
  })

  it('requires a cheque number when cheque amount is positive', () => {
    assert.equal(
      payrollPaySplitError({ cheque: 9000, cash: 0, net: 9000, chequeNumber: '' }),
      'Enter a cheque number when cheque amount is greater than 0.',
    )
  })
})

describe('payrollSummaryStatus', () => {
  it('labels holiday, weekend, complete, and incomplete days', () => {
    assert.equal(payrollSummaryStatusLabel({ is_holiday: true, is_weekend: false, is_complete: true }), 'Holiday')
    assert.equal(payrollSummaryStatusLabel({ is_holiday: false, is_weekend: true, is_complete: true }), 'Weekend')
    assert.equal(payrollSummaryStatusLabel({ is_holiday: false, is_weekend: false, is_complete: true }), 'Complete')
    assert.equal(payrollSummaryStatusLabel({ is_holiday: false, is_weekend: false, is_complete: false }), 'Incomplete')
  })

  it('colors holiday/weekend as info and workdays by completeness', () => {
    assert.equal(payrollSummaryStatusColor({ is_holiday: true, is_weekend: false, is_complete: false }), 'info')
    assert.equal(payrollSummaryStatusColor({ is_holiday: false, is_weekend: false, is_complete: true }), 'success')
    assert.equal(payrollSummaryStatusColor({ is_holiday: false, is_weekend: false, is_complete: false }), 'warning')
  })

  it('picks an icon for holiday, weekend, auto-checkout, incomplete, and complete', () => {
    assert.equal(
      payrollSummaryStatusIcon({ is_holiday: true, is_weekend: false, is_complete: true }, false),
      'ri-calendar-event-line',
    )
    assert.equal(
      payrollSummaryStatusIcon({ is_holiday: false, is_weekend: true, is_complete: true }, false),
      'ri-calendar-2-line',
    )
    assert.equal(
      payrollSummaryStatusIcon({ is_holiday: false, is_weekend: false, is_complete: false }, true),
      'ri-alarm-warning-line',
    )
    assert.equal(
      payrollSummaryStatusIcon({ is_holiday: false, is_weekend: false, is_complete: false }, false),
      'ri-error-warning-line',
    )
    assert.equal(
      payrollSummaryStatusIcon({ is_holiday: false, is_weekend: false, is_complete: true }, false),
      'ri-checkbox-circle-line',
    )
  })
})

describe('payrollDetailTotals', () => {
  it('sums hours, slots, days, and auto-checkout days', () => {
    assert.deepEqual(
      payrollDetailTotals(
        [
          { regular_hours: 8, regular_slots: 32, overtime_hours: 1, ot_slots: 4 },
          { regular_hours: 7.5, regular_slots: 30, overtime_hours: 0, ot_slots: 0 },
        ],
        1,
      ),
      {
        regular: 15.5,
        regularSlots: 62,
        overtime: 1,
        otSlots: 4,
        days: 2,
        autoCheckoutDays: 1,
      },
    )
  })
})
