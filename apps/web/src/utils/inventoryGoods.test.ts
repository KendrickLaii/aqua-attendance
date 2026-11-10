import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import type { InventoryProduct } from '../api/attendance/inventory'
import { buildOptionSuggestions, canonicalOption, canonicalValue } from './inventoryGoods'

function product(createdAt: string, options: Record<string, string[]> | null): InventoryProduct {
  return { created_at: createdAt, options } as unknown as InventoryProduct
}

describe('buildOptionSuggestions', () => {
  it('groups names case-insensitively and uses the majority spelling', () => {
    const result = buildOptionSuggestions([
      product('2026-01-01', { size: ['S'] }),
      product('2026-01-02', { Size: ['M'] }),
      product('2026-01-03', { Size: ['L'] }),
    ])

    assert.equal(result.length, 1)
    assert.equal(result[0].name, 'Size')
  })

  it('breaks spelling ties in favour of the earliest product', () => {
    const result = buildOptionSuggestions([
      product('2026-01-02', { SIZE: ['S'] }),
      product('2026-01-01', { size: ['M'] }),
    ])

    assert.equal(result[0].name, 'size')
  })

  it('merges values by first appearance', () => {
    const result = buildOptionSuggestions([
      product('2026-01-02', { Size: ['M', 'L', 'XL', 'XXL'] }),
      product('2026-01-01', { Size: ['S', 'M', 'L', 'XL'] }),
    ])

    assert.deepEqual(result[0].values, ['S', 'M', 'L', 'XL', 'XXL'])
  })

  it('de-duplicates values case-insensitively keeping the first spelling', () => {
    const result = buildOptionSuggestions([
      product('2026-01-01', { Colour: ['Red', 'blue'] }),
      product('2026-01-02', { colour: ['RED', 'Blue', 'Green'] }),
    ])

    assert.deepEqual(result[0].values, ['Red', 'blue', 'Green'])
  })

  it('sorts by number of products using the option, then name, and ignores products without options', () => {
    const result = buildOptionSuggestions([
      product('2026-01-01', { Width: ['26'] }),
      product('2026-01-02', { Size: ['S'], Colour: ['Red'] }),
      product('2026-01-03', { Size: ['M'] }),
      product('2026-01-04', null),
    ])

    assert.deepEqual(result.map(s => s.name), ['Size', 'Colour', 'Width'])
  })
})

describe('canonical helpers', () => {
  const suggestions = [{ name: 'Size', values: ['S', 'M', 'XL'] }]

  it('snaps option names to the canonical spelling and passes unknown names through trimmed', () => {
    assert.equal(canonicalOption(' size ', suggestions), 'Size')
    assert.equal(canonicalOption(' Colour ', suggestions), 'Colour')
  })

  it('snaps values to the suggested spelling and passes unknown values through trimmed', () => {
    assert.equal(canonicalValue('xl', suggestions[0]), 'XL')
    assert.equal(canonicalValue(' XXL ', suggestions[0]), 'XXL')
    assert.equal(canonicalValue(' m ', undefined), 'm')
  })
})
