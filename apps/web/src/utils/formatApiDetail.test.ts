import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { formatApiDetail } from './formatApiDetail'

describe('formatApiDetail', () => {
  it('reads message from a structured FastAPI detail object', () => {
    assert.equal(
      formatApiDetail({
        message: 'Attendance summaries are stale. Generate attendance summaries for this month, then run payroll again.',
        stale_summaries: [{ unit_id: 'x', reason: 'outdated' }],
      }),
      'Attendance summaries are stale. Generate attendance summaries for this month, then run payroll again.',
    )
  })
})
