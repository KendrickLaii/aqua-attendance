import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { needsAuthenticatedMediaFetch } from './mediaUrl'

describe('needsAuthenticatedMediaFetch', () => {
  it('requires a cookie fetch for local upload paths', () => {
    assert.equal(needsAuthenticatedMediaFetch('/api/uploads/abc.jpg'), true)
    assert.equal(needsAuthenticatedMediaFetch('http://localhost:8000/api/uploads/abc.jpg'), true)
  })

  it('leaves public https and data URLs alone', () => {
    assert.equal(needsAuthenticatedMediaFetch('https://cdn.example.com/logo.png'), false)
    assert.equal(needsAuthenticatedMediaFetch('data:image/png;base64,xx'), false)
    assert.equal(needsAuthenticatedMediaFetch(''), false)
  })
})
