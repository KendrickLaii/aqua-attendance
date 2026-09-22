import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  GENERATE_CONFIRM,
  JOIN_CLASS_HINT,
  LEAVE_CLASS_CONFIRM,
  MANUAL_CREDIT_HINT,
  REMOVE_RECORD_BILLED,
  REMOVE_RECORD_CONFIRM,
  VOID_RECEIPT_HINT,
  leaveClassUnbilledNote,
  mapEnrollmentApiError,
} from './billingStaffCopy'

describe('billingStaffCopy', () => {
  it('tells staff to Generate after joining a class', () => {
    assert.match(JOIN_CLASS_HINT, /Generate/)
  })

  it('tells staff Leave class does not change issued bills', () => {
    assert.match(LEAVE_CLASS_CONFIRM, /Leave class|Back in class|Generate/)
    assert.match(leaveClassUnbilledNote(4), /4 堂未出單/)
    assert.equal(leaveClassUnbilledNote(0), '')
  })

  it('points billed-delete errors at Leave class', () => {
    assert.equal(
      mapEnrollmentApiError('Enrollment has billed invoices. Unenroll instead of deleting.'),
      REMOVE_RECORD_BILLED,
    )
    assert.equal(mapEnrollmentApiError('Campus list failed'), 'Campus list failed')
    assert.match(REMOVE_RECORD_CONFIRM, /Leave class/)
  })

  it('warns that Generate can revive cancelled bills', () => {
    assert.match(GENERATE_CONFIRM, /取消咗嘅單可能會出返嚟/)
  })

  it('explains credit notes and voided receipt numbers', () => {
    assert.match(MANUAL_CREDIT_HINT, /credit note/)
    assert.match(VOID_RECEIPT_HINT, /Remove/)
  })
})
