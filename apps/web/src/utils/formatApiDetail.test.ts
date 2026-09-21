import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { formatApiDetail, formatApiError } from './formatApiDetail'

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

describe('formatApiError', () => {
  it('keeps the fallback when a helper load has no API body', () => {
    assert.equal(
      formatApiError({ statusCode: 500 }, 'Could not load locations.'),
      'Could not load locations.',
    )
  })

  it('prefers API detail over the fallback', () => {
    assert.equal(
      formatApiError({ data: { detail: 'Campus list failed' } }, 'Could not load locations.'),
      'Campus list failed',
    )
  })
})
