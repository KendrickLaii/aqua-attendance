import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Modal, Platform } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { scanQR, type AttendanceEvent } from '../services/attendance';

const THEME = { primary: '#160D47', bg: '#F4F5FA', success: '#56CA00', warning: '#FFB400', error: '#9d1c24' };

export default function ScannerScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanning, setScanning] = useState(true);
  const [selectedEventType, setSelectedEventType] = useState<'check_in' | 'check_out'>('check_in');
  const [result, setResult] = useState<AttendanceEvent | null>(null);
  const [error, setError] = useState('');
  const [modalVisible, setModalVisible] = useState(false);
  const [processing, setProcessing] = useState(false);

  async function handleBarCodeScanned({ data }: { data: string }) {
    if (!scanning || processing) return;
    setScanning(false);
    setProcessing(true);
    setError('');
    setResult(null);

    try {
      const evt = await scanQR(data, `mobile-${Platform.OS}`, selectedEventType);
      setResult(evt);
    } catch (e: any) {
      setError(e.message || 'Scan failed');
    } finally {
      setProcessing(false);
      setModalVisible(true);
    }
  }

  function handleDismiss() {
    setModalVisible(false);
    setResult(null);
    setError('');
    setTimeout(() => setScanning(true), 500);
  }

  if (!permission) return <View style={styles.container}><Text>Loading...</Text></View>;

  if (!permission.granted) {
    return (
      <View style={styles.container}>
        <Text style={styles.permText}>Camera permission is needed to scan QR codes.</Text>
        <TouchableOpacity style={styles.permBtn} onPress={requestPermission}>
          <Text style={styles.permBtnText}>Grant Permission</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView
        style={StyleSheet.absoluteFill}
        facing="back"
        barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
        onBarcodeScanned={scanning ? handleBarCodeScanned : undefined}
      />

      {/* Overlay */}
      <View style={styles.overlay}>
        <View style={styles.scanFrame} />
        <Text style={styles.hint}>
          {processing ? 'Processing...' : 'Point camera at student QR code'}
        </Text>
        <View style={styles.actionRow}>
          <TouchableOpacity
            style={[styles.actionBtn, selectedEventType === 'check_in' && styles.actionBtnActiveIn]}
            onPress={() => setSelectedEventType('check_in')}
            disabled={processing}
          >
            <Text style={[styles.actionBtnText, selectedEventType === 'check_in' && styles.actionBtnTextActive]}>
              Check In
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionBtn, selectedEventType === 'check_out' && styles.actionBtnActiveOut]}
            onPress={() => setSelectedEventType('check_out')}
            disabled={processing}
          >
            <Text style={[styles.actionBtnText, selectedEventType === 'check_out' && styles.actionBtnTextActive]}>
              Check Out
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Result modal */}
      <Modal visible={modalVisible} transparent animationType="slide">
        <View style={styles.modalBg}>
          <View style={styles.modalCard}>
            {result ? (
              <>
                <Text style={[styles.resultIcon, { color: result.event_type === 'check_in' ? THEME.success : THEME.warning }]}>
                  {result.event_type === 'check_in' ? '✓' : '↩'}
                </Text>
                <Text style={styles.resultType}>
                  {result.event_type.replace('_', ' ').toUpperCase()}
                </Text>
                <Text style={styles.resultName}>
                  {result.product_name || result.product_code || '—'}
                </Text>
                {result.attendance_status ? (
                  <Text style={styles.resultStatus}>
                    Now: {result.attendance_status === 'checked_in' ? 'IN' : 'OUT'}
                  </Text>
                ) : null}
                <Text style={styles.resultTime}>
                  {new Date(result.recorded_at).toLocaleTimeString()}
                </Text>
              </>
            ) : error ? (
              <>
                <Text style={[styles.resultIcon, { color: THEME.error }]}>✗</Text>
                <Text style={styles.resultType}>SCAN FAILED</Text>
                <Text style={styles.errorMsg}>{error}</Text>
              </>
            ) : null}
            <TouchableOpacity style={styles.okBtn} onPress={handleDismiss}>
              <Text style={styles.okBtnText}>OK — Next Scan</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000', justifyContent: 'center', alignItems: 'center' },
  overlay: { ...StyleSheet.absoluteFillObject, justifyContent: 'center', alignItems: 'center' },
  scanFrame: { width: 260, height: 260, borderWidth: 3, borderColor: '#fff', borderRadius: 20, opacity: 0.7 },
  hint: { color: '#fff', fontSize: 14, marginTop: 20, textAlign: 'center' },
  actionRow: { flexDirection: 'row', marginTop: 24, gap: 12 },
  actionBtn: {
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.6)',
    backgroundColor: 'rgba(0,0,0,0.35)',
  },
  actionBtnActiveIn: { borderColor: THEME.success, backgroundColor: THEME.success },
  actionBtnActiveOut: { borderColor: THEME.warning, backgroundColor: THEME.warning },
  actionBtnText: { color: '#fff', fontWeight: '600', fontSize: 15 },
  actionBtnTextActive: { color: '#fff' },
  permText: { color: THEME.primary, fontSize: 16, textAlign: 'center', marginBottom: 16, paddingHorizontal: 30 },
  permBtn: { backgroundColor: THEME.primary, borderRadius: 10, paddingHorizontal: 24, paddingVertical: 12 },
  permBtnText: { color: '#fff', fontWeight: '600', fontSize: 15 },
  modalBg: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: 'rgba(0,0,0,0.5)' },
  modalCard: {
    width: '80%', maxWidth: 340, backgroundColor: '#fff', borderRadius: 20,
    padding: 32, alignItems: 'center',
  },
  resultIcon: { fontSize: 72, fontWeight: '700', marginBottom: 8 },
  resultType: { fontSize: 22, fontWeight: '700', color: THEME.primary, marginBottom: 8 },
  resultName: { fontSize: 18, color: '#333', marginBottom: 4 },
  resultStatus: { fontSize: 13, color: '#555', marginBottom: 6, fontWeight: '600' },
  resultTime: { fontSize: 14, color: '#888', marginBottom: 20 },
  errorMsg: { fontSize: 14, color: THEME.error, textAlign: 'center', marginBottom: 20 },
  okBtn: { backgroundColor: THEME.primary, borderRadius: 10, paddingHorizontal: 32, paddingVertical: 12 },
  okBtnText: { color: '#fff', fontWeight: '600', fontSize: 15 },
});
