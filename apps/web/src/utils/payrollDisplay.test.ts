import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { payrollPaySplitError } from './payrollDisplay'

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
