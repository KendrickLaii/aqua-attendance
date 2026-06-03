import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, FlatList, StyleSheet, RefreshControl } from 'react-native';
import { listAttendance, type AttendanceEvent } from '../services/attendance';

const THEME = { primary: '#160D47', bg: '#F4F5FA', success: '#56CA00', warning: '#FFB400' };

export default function HistoryScreen() {
  const [events, setEvents] = useState<AttendanceEvent[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await listAttendance({ page_size: '50' });
      setEvents(data);
    } catch (e) {
      console.warn('Failed to load history', e);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  function renderItem({ item }: { item: AttendanceEvent }) {
    const d = new Date(item.recorded_at);
    const isIn = item.event_type === 'check_in';
    return (
      <View style={styles.row}>
        <View style={[styles.dot, { backgroundColor: isIn ? THEME.success : THEME.warning }]} />
        <View style={{ flex: 1 }}>
          <Text style={styles.type}>{item.event_type.replace('_', ' ')}</Text>
          <Text style={styles.product}>{item.product_name || item.product_code || '—'}</Text>
          {item.location ? (
            <Text style={styles.location}>{item.location}</Text>
          ) : null}
          <Text style={styles.time}>{d.toLocaleDateString()} {d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={events}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={
          <Text style={styles.empty}>No attendance records yet</Text>
        }
        contentContainerStyle={{ padding: 16 }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: THEME.bg },
  row: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff',
    padding: 14, borderRadius: 12, marginBottom: 8,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 4, elevation: 1,
  },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  type: { fontSize: 15, fontWeight: '600', color: THEME.primary, textTransform: 'capitalize' },
  product: { fontSize: 13, color: '#444', marginTop: 2 },
  location: { fontSize: 12, color: '#666', marginTop: 2 },
  time: { fontSize: 13, color: '#888', marginTop: 2 },
  empty: { textAlign: 'center', color: '#999', marginTop: 40, fontSize: 15 },
});
