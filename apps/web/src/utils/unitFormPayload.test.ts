import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  buildUnitSavePayload,
  emptyUnitForm,
  unitSaveValidationError,
} from './unitFormPayload'

describe('unitFormPayload', () => {
  it('rejects staff without employment type or missing locations', () => {
    const form = emptyUnitForm()

    form.unit_type = 'staff'
    form.registered_location_id = 'loc-1'
    form.scan_location_ids = ['loc-1']
    assert.equal(unitSaveValidationError(form), 'Employment type is required for staff')

    form.staff_profile.employment_type = 'part_time'
    form.registered_location_id = ''
    assert.equal(unitSaveValidationError(form), 'Registered location is required')

    form.registered_location_id = 'loc-1'
    form.scan_location_ids = []
    assert.equal(unitSaveValidationError(form), 'Select at least one scan location')

    form.scan_location_ids = ['loc-1']
    assert.equal(unitSaveValidationError(form), null)
  })

  it('builds a student create payload with filled guardians only', () => {
    const form = emptyUnitForm()

    form.code = ' S001 '
    form.full_name = ' Chan '
    form.registered_location_id = 'loc-1'
    form.scan_location_ids = ['loc-1']
    form.english_name = '  '
    form.student_profile.school_name = ' ABC '
    form.guardians = [
      { name: 'Mum', relationship: 'Mother', phone: '123' },
      { name: '   ', relationship: 'Father', phone: '456' },
    ]

    const payload = buildUnitSavePayload(form)

    assert.equal(payload.code, 'S001')
    assert.equal(payload.full_name, 'Chan')
    assert.equal(payload.english_name, null)
    assert.deepEqual(payload.student_profile, {
      gender: null,
      date_of_birth: null,
      school_name: 'ABC',
      grade_class: null,
      student_id: null,
      academic_notes: null,
      guardians: {
        guardian1: { name: 'Mum', relationship: 'Mother', phone: '123' },
      },
    })
    assert.equal('staff_profile' in payload, false)
  })

  it('parses staff pay numbers and drops empty strings', () => {
    const form = emptyUnitForm()

    form.unit_type = 'staff'
    form.code = 'T01'
    form.full_name = 'Ada'
    form.registered_location_id = 'loc-1'
    form.scan_location_ids = ['loc-1']
    form.staff_profile.employment_type = 'full_time'
    form.staff_profile.pay_type = 'hourly'
    form.staff_profile.hourly_rate = '120.5'
    form.staff_profile.ot_multiplier = ''

    const payload = buildUnitSavePayload(form)

    assert.equal(payload.staff_profile?.hourly_rate, 120.5)
    assert.equal(payload.staff_profile?.ot_multiplier, null)
    assert.equal(payload.staff_profile?.employment_type, 'full_time')
    assert.equal('student_profile' in payload, false)
  })
})
