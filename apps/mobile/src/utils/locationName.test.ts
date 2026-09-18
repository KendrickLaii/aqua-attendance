import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { locationDisplayName } from './locationName';

const loc = {
  id: 'loc-1',
  code: 'TST',
  name_en: 'Tsim Sha Tsui',
  name_zh: '尖沙咀',
};

describe('locationDisplayName', () => {
  it('prefers Chinese name when locale is zh-Hant', () => {
    assert.equal(locationDisplayName(loc, 'zh-Hant'), '尖沙咀');
  });

  it('prefers English name when locale is en', () => {
    assert.equal(locationDisplayName(loc, 'en'), 'Tsim Sha Tsui');
  });

  it('falls back to the other language when the preferred name is empty', () => {
    assert.equal(
      locationDisplayName({ ...loc, name_zh: '' }, 'zh-Hant'),
      'Tsim Sha Tsui',
    );
    assert.equal(
      locationDisplayName({ ...loc, name_en: '' }, 'en'),
      '尖沙咀',
    );
  });
});
