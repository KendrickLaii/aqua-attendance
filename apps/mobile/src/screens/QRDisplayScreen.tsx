import React, { useEffect, useState, useRef, useCallback } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity } from 'react-native';
import QRCode from 'react-native-qrcode-svg';
import { getQRToken, type QRPayload } from '../services/attendance';
import { getSavedUser, type User } from '../services/auth';

const THEME = { primary: '#160D47', bg: '#F4F5FA', success: '#56CA00', warning: '#FFB400', error: '#9d1c24' };

export default function QRDisplayScreen() {
  const [qrData, setQrData] = useState<QRPayload | null>(null);
  const [countdown, setCountdown] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [user, setUser] = useState<User | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchQR = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getQRToken();
      setQrData(data);
      setCountdown(data.expires_in);
    } catch (e: any) {
      setError(e.message || 'Failed to get QR');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    getSavedUser().then(setUser);
    fetchQR();
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [fetchQR]);

  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (!qrData) return;
    timerRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) { fetchQR(); return 0; }
        return prev - 1;
      });
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [qrData, fetchQR]);

  const progressPct = qrData ? (countdown / qrData.expires_in) * 100 : 0;
  const barColor = countdown > 30 ? THEME.success : countdown > 10 ? THEME.warning : THEME.error;

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        {user && (
          <>
            <Text style={styles.name}>{user.full_name || user.username}</Text>
            <View style={[styles.badge, { backgroundColor: user.role === 'student' ? THEME.success : '#16B1FF' }]}>
              <Text style={styles.badgeText}>{user.role}</Text>
            </View>
          </>
        )}

        {loading ? (
          <ActivityIndicator size="large" color={THEME.primary} style={{ marginVertical: 40 }} />
        ) : error ? (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{error}</Text>
            <TouchableOpacity style={styles.retryBtn} onPress={fetchQR}>
              <Text style={styles.retryText}>Retry</Text>
            </TouchableOpacity>
          </View>
        ) : qrData ? (
          <>
            <View style={styles.qrWrapper}>
              <QRCode value={qrData.qr_token} size={240} backgroundColor="white" color={THEME.primary} />
            </View>
            <View style={styles.progressBarBg}>
              <View style={[styles.progressBarFill, { width: `${progressPct}%`, backgroundColor: barColor }]} />
            </View>
            <Text style={styles.countdown}>
              Refreshes in <Text style={{ fontWeight: '700' }}>{countdown}s</Text>
            </Text>
            <TouchableOpacity style={styles.refreshBtn} onPress={fetchQR}>
              <Text style={styles.refreshBtnText}>Refresh Now</Text>
            </TouchableOpacity>
          </>
        ) : null}
      </View>

      <Text style={styles.hint}>Show this QR code to the scanner at the entrance.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: THEME.bg, padding: 20 },
  card: {
    width: '100%', maxWidth: 360, backgroundColor: '#fff', borderRadius: 20,
    padding: 28, alignItems: 'center',
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.08, shadowRadius: 12, elevation: 4,
  },
  name: { fontSize: 20, fontWeight: '700', color: THEME.primary, marginBottom: 6 },
  badge: { paddingHorizontal: 12, paddingVertical: 3, borderRadius: 12, marginBottom: 20 },
  badgeText: { color: '#fff', fontSize: 12, fontWeight: '600', textTransform: 'uppercase' },
  qrWrapper: {
    padding: 12, borderWidth: 3, borderColor: THEME.primary, borderRadius: 16, marginBottom: 16,
  },
  progressBarBg: { width: '100%', height: 6, backgroundColor: '#eee', borderRadius: 3, marginBottom: 8 },
  progressBarFill: { height: 6, borderRadius: 3 },
  countdown: { fontSize: 13, color: '#888', marginBottom: 12 },
  refreshBtn: { borderWidth: 1, borderColor: THEME.primary, borderRadius: 8, paddingHorizontal: 16, paddingVertical: 8 },
  refreshBtnText: { color: THEME.primary, fontWeight: '600', fontSize: 13 },
  errorContainer: { alignItems: 'center', marginVertical: 30 },
  errorText: { color: THEME.error, fontSize: 14, marginBottom: 12 },
  retryBtn: { backgroundColor: THEME.primary, borderRadius: 8, paddingHorizontal: 20, paddingVertical: 10 },
  retryText: { color: '#fff', fontWeight: '600' },
  hint: { marginTop: 16, fontSize: 12, color: '#999', textAlign: 'center' },
});
