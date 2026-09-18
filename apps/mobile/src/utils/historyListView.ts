export type HistoryListView =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'empty' }
  | { kind: 'ready' };

export function historyListView(opts: {
  initialLoading: boolean;
  error: string;
  eventCount: number;
}): HistoryListView {
  if (opts.initialLoading) return { kind: 'loading' };
  if (opts.error) return { kind: 'error', message: opts.error };
  if (opts.eventCount === 0) return { kind: 'empty' };
  return { kind: 'ready' };
}
