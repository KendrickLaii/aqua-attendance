import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  RefreshControl,
  Pressable,
  ActivityIndicator,
} from 'react-native';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import { useI18n } from '../i18n/I18nContext';
import { listAttendance, type AttendanceEvent } from '../services/attendance';
import { colors, layout, radius, spacing, typography } from '../theme';
import {
  formatAttendanceDateTime,
  getAttendanceDateKey,
  getAttendanceDateRangeIso,
  shiftAttendanceDateKey,
} from '../utils/attendanceTimezone';
import { historyListView } from '../utils/historyListView';
import { createRequestGate } from '../utils/requestGate';

type EventTypeFilter = '' | 'check_in' | 'check_out';
type DateRangeFilter = 'today' | 'yesterday' | '7d' | '30d';
type LoadMode = 'replace' | 'append' | 'refresh';

const PAGE_SIZE = 25;

/** Hong Kong calendar day ranges as UTC ISO (aligned with web Log filters). */
function getDateRange(filter: DateRangeFilter): { from: string; to: string } {
  const today = getAttendanceDateKey();
  let fromKey = today;
  let toKey = today;

  switch (filter) {
    case 'today':
      break;
    case 'yesterday':
      fromKey = shiftAttendanceDateKey(today, -1);
      toKey = fromKey;
      break;
    case '7d':
      fromKey = shiftAttendanceDateKey(today, -6);
      break;
    case '30d':
      fromKey = shiftAttendanceDateKey(today, -29);
      break;
  }

  const range = getAttendanceDateRangeIso(fromKey, toKey);
  return { from: range.date_from, to: range.date_to };
}

interface ChipProps {
  label: string;
  active: boolean;
  onPress: () => void;
}

function Chip({ label, active, onPress }: ChipProps) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      style={[styles.chip, active && styles.chipActive]}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

export default function HistoryScreen() {
  const { t, dateLocale } = useI18n();
  const gateRef = useRef(createRequestGate());
  const [events, setEvents] = useState<AttendanceEvent[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [eventFilter, setEventFilter] = useState<EventTypeFilter>('');
  const [dateFilter, setDateFilter] = useState<DateRangeFilter>('today');

  const buildParams = useCallback(
    (pageNum: number): Record<string, string> => {
      const range = getDateRange(dateFilter);
      const params: Record<string, string> = {
        page: String(pageNum),
        page_size: String(PAGE_SIZE),
        date_from: range.from,
        date_to: range.to,
        include_voided: 'true',
      };
      if (eventFilter) params.event_type = eventFilter;
      return params;
    },
    [eventFilter, dateFilter],
  );

  const load = useCallback(
    async (targetPage: number, mode: LoadMode) => {
      const req = gateRef.current.start();
      if (mode === 'replace') {
        setInitialLoading(true);
        setLoadingMore(false);
        setLoadError('');
        setEvents([]);
        setTotal(0);
      } else if (mode === 'refresh') {
        setLoadError('');
      }
      try {
        const { events: data, total: totalCount } = await listAttendance(buildParams(targetPage));
        if (!req.isCurrent()) return;
        setEvents((prev) => (mode === 'append' ? [...prev, ...data] : data));
        setTotal(totalCount);
        setPage(targetPage);
        setLoadError('');
      } catch (e: unknown) {
        if (!req.isCurrent()) return;
        const msg = e instanceof Error ? e.message : t('history.loadFailed');
        setLoadError(msg);
        if (mode !== 'append') setEvents([]);
      } finally {
        if (!req.isCurrent()) return;
        setInitialLoading(false);
        setRefreshing(false);
        setLoadingMore(false);
      }
    },
    [buildParams, t],
  );

  useEffect(() => {
    void load(1, 'replace');
  }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    await load(1, 'refresh');
  }

  async function onLoadMore() {
    if (initialLoading || loadingMore || refreshing || events.length >= total) return;
    setLoadingMore(true);
    await load(page + 1, 'append');
  }

  function eventTypeLabel(eventType: string): string {
    if (eventType === 'check_in') return t('eventType.check_in');
    if (eventType === 'check_out') return t('eventType.check_out');
    if (eventType === 'manual_correction') return t('eventType.manual_correction');
    return eventType;
  }

  function sourceLabel(source: string): string {
    if (!source) return '';
    return source.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
  }

  function renderItem({ item }: { item: AttendanceEvent }) {
    const { date, time } = formatAttendanceDateTime(item.recorded_at, dateLocale);
    const isIn = item.event_type === 'check_in';
    const isVoided = !!item.voided_at;
    return (
      <View style={[styles.row, isVoided && styles.rowVoided]}>
        <View style={[styles.strip, { backgroundColor: isIn ? colors.checkIn : colors.checkOut }]} />
        <View style={styles.rowBody}>
          <View style={styles.rowTop}>
            <View style={styles.badgeGroup}>
              <Badge label={eventTypeLabel(item.event_type)} tone={isIn ? 'success' : 'warning'} />
              {item.source ? (
                <Badge label={sourceLabel(item.source)} tone="neutral" style={styles.badgeGap} />
              ) : null}
              {isVoided ? (
                <Badge label={t('history.voided')} tone="error" style={styles.badgeGap} />
              ) : null}
            </View>
            <Text style={styles.time}>{time}</Text>
          </View>
          <Text style={[styles.unitName, isVoided && styles.textVoided]}>
            {item.unit_name || item.unit_code || t('common.dash')}
          </Text>
          {item.location ? (
            <Text style={[styles.location, isVoided && styles.textVoided]}>{item.location}</Text>
          ) : null}
          <Text style={[styles.date, isVoided && styles.textVoided]}>{date}</Text>
        </View>
      </View>
    );
  }

  const view = historyListView({
    initialLoading,
    error: loadError,
    eventCount: events.length,
  });
  const canLoadMore = events.length < total && !loadingMore && !initialLoading;

  return (
    <View style={styles.container}>
      <View style={styles.filterWrap}>
        <Text style={styles.filterTitle}>{t('history.filterTitle')}</Text>
        <View style={styles.chipRow}>
          <Chip label={t('history.all')} active={eventFilter === ''} onPress={() => setEventFilter('')} />
          <Chip
            label={t('eventType.check_in')}
            active={eventFilter === 'check_in'}
            onPress={() => setEventFilter('check_in')}
          />
          <Chip
            label={t('eventType.check_out')}
            active={eventFilter === 'check_out'}
            onPress={() => setEventFilter('check_out')}
          />
        </View>
        <View style={styles.chipRow}>
          <Chip label={t('history.today')} active={dateFilter === 'today'} onPress={() => setDateFilter('today')} />
          <Chip
            label={t('history.yesterday')}
            active={dateFilter === 'yesterday'}
            onPress={() => setDateFilter('yesterday')}
          />
          <Chip
            label={t('history.last7Days')}
            active={dateFilter === '7d'}
            onPress={() => setDateFilter('7d')}
          />
          <Chip
            label={t('history.last30Days')}
            active={dateFilter === '30d'}
            onPress={() => setDateFilter('30d')}
          />
        </View>
      </View>

      {view.kind === 'error' ? (
        <View style={styles.errorWrap}>
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{loadError}</Text>
          </View>
          <Button label={t('common.retry')} onPress={() => load(1, 'replace')} variant="secondary" />
        </View>
      ) : null}

      <FlatList
        data={events}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />
        }
        onEndReached={onLoadMore}
        onEndReachedThreshold={0.5}
        ListFooterComponent={
          loadingMore ? (
            <ActivityIndicator style={styles.footerSpinner} color={colors.primary} />
          ) : canLoadMore ? (
            <View style={styles.loadMoreWrap}>
              <Button label={t('history.loadMore')} onPress={onLoadMore} variant="secondary" />
            </View>
          ) : events.length > 0 ? (
            <Text style={styles.noMore}>{t('history.noMore')}</Text>
          ) : null
        }
        ListEmptyComponent={
          view.kind === 'loading' ? (
            <View style={styles.empty}>
              <ActivityIndicator size="large" color={colors.primary} />
              <Text style={styles.emptyText}>{t('common.loading')}</Text>
            </View>
          ) : view.kind === 'empty' ? (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>{t('history.empty')}</Text>
            </View>
          ) : null
        }
        contentContainerStyle={styles.listContent}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  filterWrap: {
    paddingHorizontal: layout.screenPadding,
    paddingTop: layout.screenPadding,
    paddingBottom: spacing.md,
    gap: spacing.sm,
  },
  filterTitle: { ...typography.label, marginBottom: spacing.xs },
  chipRow: { flexDirection: 'row', gap: spacing.sm, flexWrap: 'wrap' },
  chip: {
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    justifyContent: 'center',
  },
  chipActive: {
    backgroundColor: colors.primaryMuted,
    borderColor: colors.primarySoft,
  },
  chipText: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  chipTextActive: { color: colors.primary },
  listContent: { padding: layout.screenPadding, flexGrow: 1, paddingBottom: spacing.xxxl },
  errorWrap: { padding: layout.screenPadding, paddingBottom: 0, gap: spacing.md },
  errorBox: {
    backgroundColor: colors.errorSoft,
    borderRadius: radius.md,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.errorSoft,
  },
  errorText: { ...typography.body, color: colors.error },
  row: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
    overflow: 'hidden',
  },
  strip: { width: 4 },
  rowBody: { flex: 1, padding: spacing.lg },
  rowTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  time: { ...typography.caption, fontWeight: '600' },
  unitName: { ...typography.bodyStrong, marginBottom: spacing.xs },
  location: { ...typography.caption, marginBottom: spacing.xs },
  date: { ...typography.caption },
  rowVoided: { opacity: 0.6 },
  textVoided: { textDecorationLine: 'line-through' as const },
  badgeGroup: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', flex: 1, marginRight: spacing.sm },
  badgeGap: { marginLeft: spacing.sm },
  empty: { alignItems: 'center', marginTop: 64, gap: spacing.md },
  emptyText: { ...typography.body, textAlign: 'center' },
  loadMoreWrap: { alignItems: 'center', marginVertical: spacing.lg },
  footerSpinner: { margin: spacing.lg },
  noMore: { ...typography.caption, textAlign: 'center', marginVertical: spacing.lg, color: colors.textMuted },
});
