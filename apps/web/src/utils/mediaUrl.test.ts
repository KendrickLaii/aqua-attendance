import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { needsAuthenticatedMediaFetch } from './mediaUrl'

describe('needsAuthenticatedMediaFetch', () => {
  it('loads upload paths directly in img and print', () => {
    assert.equal(needsAuthenticatedMediaFetch('/api/uploads/abc.jpg'), false)
    assert.equal(needsAuthenticatedMediaFetch('http://localhost:8000/api/uploads/abc.jpg'), false)
  })

  it('leaves public https and data URLs alone', () => {
    assert.equal(needsAuthenticatedMediaFetch('https://cdn.example.com/logo.png'), false)
    assert.equal(needsAuthenticatedMediaFetch('data:image/png;base64,xx'), false)
    assert.equal(needsAuthenticatedMediaFetch(''), false)
  })
})
