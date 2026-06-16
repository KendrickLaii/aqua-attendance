import React, { useEffect, useState, useCallback } from 'react';
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

type EventTypeFilter = '' | 'check_in' | 'check_out';
type DateRangeFilter = 'today' | 'yesterday' | '7d' | '30d';

const PAGE_SIZE = 25;

function toISODate(date: Date): string {
  return date.toISOString().split('T')[0];
}

function getDateRange(filter: DateRangeFilter): { from: string; to: string } {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  let from = today;
  let to = today;

  switch (filter) {
    case 'today':
      from = today;
      to = today;
      break;
    case 'yesterday': {
      const y = new Date(today);
      y.setDate(y.getDate() - 1);
      from = y;
      to = y;
      break;
    }
    case '7d': {
      const d7 = new Date(today);
      d7.setDate(d7.getDate() - 6);
      from = d7;
      to = today;
      break;
    }
    case '30d': {
      const d30 = new Date(today);
      d30.setDate(d30.getDate() - 29);
      from = d30;
      to = today;
      break;
    }
  }

  return {
    from: `${toISODate(from)}T00:00:00`,
    to: `${toISODate(to)}T23:59:59`,
  };
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
      style={[
        styles.chip,
        active && styles.chipActive,
      ]}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

export default function HistoryScreen() {
  const { t, dateLocale } = useI18n();
  const [events, setEvents] = useState<AttendanceEvent[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
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
      };
      if (eventFilter) params.event_type = eventFilter;
      return params;
    },
    [eventFilter, dateFilter]
  );

  const load = useCallback(
    async (targetPage: number, append = false) => {
      setLoadError('');
      try {
        const { events: data, total: totalCount } = await listAttendance(buildParams(targetPage));
        setEvents((prev) => (append ? [...prev, ...data] : data));
        setTotal(totalCount);
        setPage(targetPage);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : t('history.loadFailed');
        setLoadError(msg);
        if (!append) setEvents([]);
      }
    },
    [buildParams, t]
  );

  useEffect(() => {
    load(1, false);
  }, [load, eventFilter, dateFilter]);

  async function onRefresh() {
    setRefreshing(true);
    await load(1, false);
    setRefreshing(false);
  }

  async function onLoadMore() {
    if (loadingMore || events.length >= total) return;
    setLoadingMore(true);
    await load(page + 1, true);
    setLoadingMore(false);
  }

  function eventTypeLabel(eventType: string): string {
    if (eventType === 'check_in') return t('eventType.check_in');
    if (eventType === 'check_out') return t('eventType.check_out');
    if (eventType === 'manual_correction') return t('eventType.manual_correction');
    return eventType;
  }

  function sourceLabel(source: string): string {
    if (!source) return '';
    return source.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase());
  }

  function renderItem({ item }: { item: AttendanceEvent }) {
    const d = new Date(item.recorded_at);
    const isIn = item.event_type === 'check_in';
    const isVoided = !!item.voided_at;
    return (
      <View style={[styles.row, isVoided && styles.rowVoided]}>
        <View style={[styles.strip, { backgroundColor: isIn ? colors.checkIn : colors.checkOut }]} />
        <View style={styles.rowBody}>
          <View style={styles.rowTop}>
            <View style={styles.badgeGroup}>
              <Badge label={eventTypeLabel(item.event_type)} tone={isIn ? 'success' : 'warning'} />
              {item.source ? <Badge label={sourceLabel(item.source)} tone="neutral" style={{ marginLeft: spacing.sm }} /> : null}
              {isVoided ? <Badge label="VOIDED" tone="error" style={{ marginLeft: spacing.sm }} /> : null}
            </View>
            <Text style={styles.time}>
              {d.toLocaleTimeString(dateLocale, { hour: '2-digit', minute: '2-digit' })}
            </Text>
          </View>
          <Text style={[styles.product, isVoided && styles.textVoided]}>{item.product_name || item.product_code || t('common.dash')}</Text>
          {item.location ? <Text style={[styles.location, isVoided && styles.textVoided]}>{item.location}</Text> : null}
          <Text style={[styles.date, isVoided && styles.textVoided]}>{d.toLocaleDateString(dateLocale)}</Text>
        </View>
      </View>
    );
  }

  const canLoadMore = events.length < total && !loadingMore;

  return (
    <View style={styles.container}>
      {/* Filters */}
      <View style={styles.filterWrap}>
        <Text style={styles.filterTitle}>{t('history.filterTitle')}</Text>

        {/* Event type chips */}
        <View style={styles.chipRow}>
          <Chip label={t('history.all')} active={eventFilter === ''} onPress={() => setEventFilter('')} />
          <Chip label={t('eventType.check_in')} active={eventFilter === 'check_in'} onPress={() => setEventFilter('check_in')} />
          <Chip label={t('eventType.check_out')} active={eventFilter === 'check_out'} onPress={() => setEventFilter('check_out')} />
        </View>

        {/* Date range chips */}
        <View style={styles.chipRow}>
          <Chip label={t('history.today')} active={dateFilter === 'today'} onPress={() => setDateFilter('today')} />
          <Chip label={t('history.yesterday')} active={dateFilter === 'yesterday'} onPress={() => setDateFilter('yesterday')} />
          <Chip label={t('history.last7Days')} active={dateFilter === '7d'} onPress={() => setDateFilter('7d')} />
          <Chip label={t('history.last30Days')} active={dateFilter === '30d'} onPress={() => setDateFilter('30d')} />
        </View>
      </View>

      {loadError ? (
        <View style={styles.errorWrap}>
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{loadError}</Text>
          </View>
          <Button label={t('common.retry')} onPress={() => load(1, false)} variant="secondary" />
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
            <ActivityIndicator style={{ margin: spacing.lg }} color={colors.primary} />
          ) : canLoadMore ? (
            <View style={styles.loadMoreWrap}>
              <Button label={t('history.loadMore')} onPress={onLoadMore} variant="secondary" />
            </View>
          ) : events.length > 0 ? (
            <Text style={styles.noMore}>{t('history.noMore')}</Text>
          ) : null
        }
        ListEmptyComponent={
          loadError ? null : (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>{t('history.empty')}</Text>
            </View>
          )
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
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: {
    backgroundColor: colors.primaryMuted,
    borderColor: colors.primarySoft,
  },
  chipText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  chipTextActive: { color: colors.primary },
  listContent: { padding: layout.screenPadding, flexGrow: 1, paddingBottom: spacing.xxxl },
  errorWrap: { padding: layout.screenPadding, paddingBottom: 0, gap: spacing.md },
  errorBox: {
    backgroundColor: colors.errorSoft,
    borderRadius: radius.md,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: '#F5C2C0',
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
  product: { ...typography.bodyStrong, marginBottom: spacing.xs },
  location: { ...typography.caption, marginBottom: spacing.xs },
  date: { ...typography.caption },
  rowVoided: { opacity: 0.6 },
  textVoided: { textDecorationLine: 'line-through' as const },
  badgeGroup: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap' },
  empty: { alignItems: 'center', marginTop: 64 },
  emptyText: { ...typography.body, textAlign: 'center' },
  loadMoreWrap: { alignItems: 'center', marginVertical: spacing.lg },
  noMore: { ...typography.caption, textAlign: 'center', marginVertical: spacing.lg, color: colors.textMuted },
});
