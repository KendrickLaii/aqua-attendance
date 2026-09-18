import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { createRequestGate } from './requestGate';

describe('createRequestGate', () => {
  it('marks an in-flight request stale after a newer one starts', () => {
    const gate = createRequestGate();
    const first = gate.start();
    const second = gate.start();

    assert.equal(first.isCurrent(), false);
    assert.equal(second.isCurrent(), true);
  });
});
