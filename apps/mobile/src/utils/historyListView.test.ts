import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { historyListView } from './historyListView';

describe('historyListView', () => {
  it('shows loading instead of empty while the first page is in flight', () => {
    assert.equal(
      historyListView({ initialLoading: true, error: '', eventCount: 0 }).kind,
      'loading',
    );
  });

  it('shows empty only after a finished load with no rows', () => {
    assert.equal(
      historyListView({ initialLoading: false, error: '', eventCount: 0 }).kind,
      'empty',
    );
  });

  it('shows error over empty when the first load fails', () => {
    const view = historyListView({
      initialLoading: false,
      error: 'Failed to load history',
      eventCount: 0,
    });
    assert.equal(view.kind, 'error');
  });
});
