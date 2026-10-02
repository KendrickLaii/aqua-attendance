import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { openCloseForLocationDate } from './locationHours'

describe('openCloseForLocationDate', () => {
  it('uses the weekday from hours_schedule', () => {
    const location = {
      business_hours: null,
      details: {
        hours_schedule: [
          { day: 'fri', isOpen: true, openTime: '9:00', closeTime: '13:00' },
          { day: 'sat', isOpen: false, openTime: '09:00', closeTime: '18:00' },
        ],
      },
    }

    // 2026-10-02 is a Friday
    assert.deepEqual(openCloseForLocationDate(location, '2026-10-02'), { open: '09:00', close: '13:00' })
    assert.equal(openCloseForLocationDate(location, '2026-10-03'), null)
  })

  it('reads structured business hours when there is no schedule', () => {
    const location = {
      business_hours: {
        friday: { open: '10:00', close: '18:30' },
      },
      details: null,
    }

    assert.deepEqual(openCloseForLocationDate(location, '2026-10-02'), { open: '10:00', close: '18:30' })
    assert.equal(openCloseForLocationDate(location, '2026-10-04'), null)
  })
})
