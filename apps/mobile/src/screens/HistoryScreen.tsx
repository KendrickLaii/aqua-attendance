import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  RefreshControl,
} from 'react-native';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import { useI18n } from '../i18n/I18nContext';
import { listAttendance, type AttendanceEvent } from '../services/attendance';
import { colors, layout, radius, spacing, typography } from '../theme';

export default function HistoryScreen() {
  const { t, dateLocale } = useI18n();
  const [events, setEvents] = useState<AttendanceEvent[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState('');

  const load = useCallback(async () => {
    setLoadError('');
    try {
      const data = await listAttendance({ page_size: '50' });
      setEvents(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t('history.loadFailed');
      setLoadError(msg);
      setEvents([]);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  function eventTypeLabel(eventType: string): string {
    if (eventType === 'check_in') return t('eventType.check_in');
    if (eventType === 'check_out') return t('eventType.check_out');
    if (eventType === 'manual_correction') return t('eventType.manual_correction');
    return eventType;
  }

  function renderItem({ item }: { item: AttendanceEvent }) {
    const d = new Date(item.recorded_at);
    const isIn = item.event_type === 'check_in';
    return (
      <View style={styles.row}>
        <View style={[styles.strip, { backgroundColor: isIn ? colors.checkIn : colors.checkOut }]} />
        <View style={styles.rowBody}>
          <View style={styles.rowTop}>
            <Badge label={eventTypeLabel(item.event_type)} tone={isIn ? 'success' : 'warning'} />
            <Text style={styles.time}>
              {d.toLocaleTimeString(dateLocale, { hour: '2-digit', minute: '2-digit' })}
            </Text>
          </View>
          <Text style={styles.product}>{item.product_name || item.product_code || t('common.dash')}</Text>
          {item.location ? <Text style={styles.location}>{item.location}</Text> : null}
          <Text style={styles.date}>{d.toLocaleDateString(dateLocale)}</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {loadError ? (
        <View style={styles.errorWrap}>
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{loadError}</Text>
          </View>
          <Button label={t('common.retry')} onPress={load} variant="secondary" />
        </View>
      ) : null}
      <FlatList
        data={events}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />
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
  empty: { alignItems: 'center', marginTop: 64 },
  emptyText: { ...typography.body, textAlign: 'center' },
});
