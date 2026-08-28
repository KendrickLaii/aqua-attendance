import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  billingUnitShortLabel,
  buildUnitEnrollmentRows,
  formatEnrollmentRange,
  pickCourseSelectionForSku,
  skuIdFromRouteQuery,
} from './courseEnrollmentDisplay'

describe('billingUnitShortLabel', () => {
  it('labels per_session as 堂費', () => {
    assert.equal(billingUnitShortLabel('per_session'), '堂費')
  })

  it('labels monthly and unknown as 月費', () => {
    assert.equal(billingUnitShortLabel('monthly'), '月費')
    assert.equal(billingUnitShortLabel(undefined), '月費')
  })
})

describe('formatEnrollmentRange', () => {
  it('uses Already started / Ongoing when dates are blank', () => {
    assert.equal(formatEnrollmentRange(null, null), 'Already started → Ongoing')
    assert.equal(formatEnrollmentRange(null, '2026-08-31'), 'Already started → 2026-08-31')
    assert.equal(formatEnrollmentRange('2026-06-01', null), '2026-06-01 → Ongoing')
  })

  it('keeps the calendar day from ISO timestamps', () => {
    assert.equal(formatEnrollmentRange('2026-06-01T00:00:00Z', '2026-08-31'), '2026-06-01 → 2026-08-31')
  })
})

describe('buildUnitEnrollmentRows', () => {
  it('joins SKUs and puts active classes first', () => {
    const rows = buildUnitEnrollmentRows(
      [
        { id: 'e2', sku_id: 's2', status: 'cancelled' },
        { id: 'e1', sku_id: 's1', status: 'active' },
        { id: 'e3', sku_id: 'missing', status: 'completed' },
      ],
      [
        { id: 's2', name_zh: 'P3 English' },
        { id: 's1', name_zh: 'P3 Math' },
      ],
    )

    assert.deepEqual(rows.map(row => row.enrollment.id), ['e1', 'e3', 'e2'])
    assert.equal(rows[0].sku?.name_zh, 'P3 Math')
    assert.equal(rows[2].sku?.name_zh, 'P3 English')
    assert.equal(rows[1].sku, null)
  })
})

describe('course query', () => {
  it('reads sku from the route query', () => {
    assert.equal(skuIdFromRouteQuery({ sku: 'abc' }), 'abc')
    assert.equal(skuIdFromRouteQuery({ sku: ['abc'] }), null)
    assert.equal(skuIdFromRouteQuery({}), null)
  })

  it('selects the matching SPU and SKU', () => {
    assert.deepEqual(
      pickCourseSelectionForSku(
        [{ id: 'sku-2', spu_id: 'spu-b' }, { id: 'sku-1', spu_id: 'spu-a' }],
        'sku-1',
      ),
      { spuId: 'spu-a', skuId: 'sku-1' },
    )
    assert.equal(pickCourseSelectionForSku([{ id: 'sku-1', spu_id: 'spu-a' }], 'missing'), null)
  })
})
