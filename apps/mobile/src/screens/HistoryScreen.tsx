import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, FlatList, StyleSheet, RefreshControl, TouchableOpacity } from 'react-native';
import { useI18n } from '../i18n/I18nContext';
import { listAttendance, type AttendanceEvent } from '../services/attendance';

const THEME = { primary: '#160D47', bg: '#F4F5FA', success: '#56CA00', warning: '#FFB400', error: '#9d1c24' };

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
        <View style={[styles.dot, { backgroundColor: isIn ? THEME.success : THEME.warning }]} />
        <View style={{ flex: 1 }}>
          <Text style={styles.type}>{eventTypeLabel(item.event_type)}</Text>
          <Text style={styles.product}>{item.product_name || item.product_code || t('common.dash')}</Text>
          {item.location ? (
            <Text style={styles.location}>{item.location}</Text>
          ) : null}
          <Text style={styles.time}>
            {d.toLocaleDateString(dateLocale)}{' '}
            {d.toLocaleTimeString(dateLocale, { hour: '2-digit', minute: '2-digit' })}
          </Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {loadError ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{loadError}</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={load}>
            <Text style={styles.retryText}>{t('common.retry')}</Text>
          </TouchableOpacity>
        </View>
      ) : null}
      <FlatList
        data={events}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={
          loadError ? null : (
            <Text style={styles.empty}>{t('history.empty')}</Text>
          )
        }
        contentContainerStyle={{ padding: 16, flexGrow: 1 }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: THEME.bg },
  errorBox: {
    margin: 16,
    marginBottom: 0,
    padding: 14,
    backgroundColor: '#fff0f0',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#f5c2c7',
  },
  errorText: { color: THEME.error, fontSize: 14, marginBottom: 10 },
  retryBtn: {
    alignSelf: 'flex-start',
    backgroundColor: THEME.primary,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  retryText: { color: '#fff', fontWeight: '600' },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    padding: 14,
    borderRadius: 12,
    marginBottom: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  type: { fontSize: 15, fontWeight: '600', color: THEME.primary },
  product: { fontSize: 13, color: '#444', marginTop: 2 },
  location: { fontSize: 12, color: '#666', marginTop: 2 },
  time: { fontSize: 13, color: '#888', marginTop: 2 },
  empty: { textAlign: 'center', color: '#999', marginTop: 40, fontSize: 15 },
});
