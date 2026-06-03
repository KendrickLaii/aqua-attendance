import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Modal,
  Platform,
  FlatList,
  ActivityIndicator,
} from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { deleteItemAsync, getItemAsync, setItemAsync } from '../services/storage';
import { scanQR, type AttendanceEvent } from '../services/attendance';
import { listLocations, locationDisplayName, type LocationItem } from '../services/locations';

const THEME = { primary: '#160D47', bg: '#F4F5FA', success: '#56CA00', warning: '#FFB400', error: '#9d1c24' };

const SCAN_LOCATION_KEY = 'attendance-scan-location-id';
const SCAN_EVENT_TYPE_KEY = 'attendance-scan-event-type';

export default function ScannerScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanning, setScanning] = useState(true);
  const [selectedEventType, setSelectedEventType] = useState<'check_in' | 'check_out'>('check_in');
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [locationsLoading, setLocationsLoading] = useState(true);
  const [locationsError, setLocationsError] = useState('');
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(null);
  const [locationPickerOpen, setLocationPickerOpen] = useState(false);
  const [result, setResult] = useState<AttendanceEvent | null>(null);
  const [error, setError] = useState('');
  const [modalVisible, setModalVisible] = useState(false);
  const [processing, setProcessing] = useState(false);

  const selectedLocation = locations.find((l) => l.id === selectedLocationId) ?? null;

  const loadLocations = useCallback(async () => {
    setLocationsLoading(true);
    setLocationsError('');
    try {
      const data = await listLocations({ is_active: true, page_size: 200 });
      setLocations(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to load locations';
      setLocationsError(msg);
    } finally {
      setLocationsLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      const [storedLoc, storedType] = await Promise.all([
        getItemAsync(SCAN_LOCATION_KEY),
        getItemAsync(SCAN_EVENT_TYPE_KEY),
      ]);
      if (storedLoc) setSelectedLocationId(storedLoc);
      if (storedType === 'check_out' || storedType === 'check_in')
        setSelectedEventType(storedType);
      await loadLocations();
    })();
  }, [loadLocations]);

  async function selectLocation(id: string | null) {
    setSelectedLocationId(id);
    setLocationPickerOpen(false);
    if (id) await setItemAsync(SCAN_LOCATION_KEY, id);
    else await deleteItemAsync(SCAN_LOCATION_KEY);
  }

  async function selectEventType(type: 'check_in' | 'check_out') {
    setSelectedEventType(type);
    await setItemAsync(SCAN_EVENT_TYPE_KEY, type);
  }

  async function handleBarCodeScanned({ data }: { data: string }) {
    if (!scanning || processing) return;
    setScanning(false);
    setProcessing(true);
    setError('');
    setResult(null);

    try {
      const evt = await scanQR(data, {
        deviceId: `mobile-${Platform.OS}`,
        eventType: selectedEventType,
        locationId: selectedLocationId ?? undefined,
      });
      setResult(evt);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Scan failed');
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

  if (!permission) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={THEME.primary} />
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={styles.centered}>
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

      <View style={styles.overlay}>
        <View style={styles.topPanel}>
          <TouchableOpacity
            style={styles.locationBtn}
            onPress={() => setLocationPickerOpen(true)}
            disabled={processing}
          >
            <Text style={styles.locationLabel}>地點</Text>
            <Text style={styles.locationValue} numberOfLines={1}>
              {selectedLocation
                ? locationDisplayName(selectedLocation)
                : locationsLoading
                  ? '載入中…'
                  : '（可選）點此選擇'}
            </Text>
          </TouchableOpacity>
          {locationsError ? (
            <Text style={styles.locError}>{locationsError}</Text>
          ) : null}
        </View>

        <View style={styles.scanFrame} />
        <Text style={styles.hint}>
          {processing
            ? '處理中…'
            : `請對準 QR · 將記錄為 ${selectedEventType === 'check_in' ? '簽到' : '簽退'}`}
        </Text>
        <View style={styles.actionRow}>
          <TouchableOpacity
            style={[styles.actionBtn, selectedEventType === 'check_in' && styles.actionBtnActiveIn]}
            onPress={() => selectEventType('check_in')}
            disabled={processing}
          >
            <Text style={[styles.actionBtnText, selectedEventType === 'check_in' && styles.actionBtnTextActive]}>
              簽到
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionBtn, selectedEventType === 'check_out' && styles.actionBtnActiveOut]}
            onPress={() => selectEventType('check_out')}
            disabled={processing}
          >
            <Text style={[styles.actionBtnText, selectedEventType === 'check_out' && styles.actionBtnTextActive]}>
              簽退
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      <Modal visible={locationPickerOpen} transparent animationType="slide">
        <View style={styles.modalBg}>
          <View style={[styles.modalCard, styles.pickerCard]}>
            <Text style={styles.pickerTitle}>選擇地點</Text>
            <TouchableOpacity style={styles.pickerRow} onPress={() => selectLocation(null)}>
              <Text style={styles.pickerRowText}>不指定地點</Text>
            </TouchableOpacity>
            <FlatList
              data={locations}
              keyExtractor={(item) => item.id}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[
                    styles.pickerRow,
                    item.id === selectedLocationId && styles.pickerRowSelected,
                  ]}
                  onPress={() => selectLocation(item.id)}
                >
                  <Text style={styles.pickerRowText}>{locationDisplayName(item)}</Text>
                  {item.region ? (
                    <Text style={styles.pickerRowSub}>{item.region}</Text>
                  ) : null}
                </TouchableOpacity>
              )}
              ListEmptyComponent={
                <Text style={styles.pickerEmpty}>
                  {locationsLoading ? '載入中…' : '沒有可用地點'}
                </Text>
              }
            />
            <TouchableOpacity style={styles.okBtn} onPress={() => setLocationPickerOpen(false)}>
              <Text style={styles.okBtnText}>關閉</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      <Modal visible={modalVisible} transparent animationType="slide">
        <View style={styles.modalBg}>
          <View style={styles.modalCard}>
            {result ? (
              <>
                <Text
                  style={[
                    styles.resultIcon,
                    { color: result.event_type === 'check_in' ? THEME.success : THEME.warning },
                  ]}
                >
                  {result.event_type === 'check_in' ? '✓' : '↩'}
                </Text>
                <Text style={styles.resultType}>
                  {result.event_type === 'check_in' ? '簽到成功' : '簽退成功'}
                </Text>
                <Text style={styles.resultName}>
                  {result.product_name || result.product_code || '—'}
                </Text>
                {result.location ? (
                  <Text style={styles.resultLocation}>地點：{result.location}</Text>
                ) : null}
                {result.attendance_status ? (
                  <Text style={styles.resultStatus}>
                    狀態：{result.attendance_status === 'checked_in' ? '已簽到' : '已簽退'}
                  </Text>
                ) : null}
                <Text style={styles.resultTime}>
                  {new Date(result.recorded_at).toLocaleTimeString()}
                </Text>
              </>
            ) : error ? (
              <>
                <Text style={[styles.resultIcon, { color: THEME.error }]}>✗</Text>
                <Text style={styles.resultType}>掃描失敗</Text>
                <Text style={styles.errorMsg}>{error}</Text>
              </>
            ) : null}
            <TouchableOpacity style={styles.okBtn} onPress={handleDismiss}>
              <Text style={styles.okBtnText}>確定 — 繼續掃描</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  centered: { flex: 1, backgroundColor: THEME.bg, justifyContent: 'center', alignItems: 'center', padding: 24 },
  overlay: { ...StyleSheet.absoluteFillObject, justifyContent: 'center', alignItems: 'center' },
  topPanel: {
    position: 'absolute',
    top: Platform.OS === 'ios' ? 56 : 16,
    left: 16,
    right: 16,
  },
  locationBtn: {
    backgroundColor: 'rgba(0,0,0,0.55)',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.35)',
  },
  locationLabel: { color: 'rgba(255,255,255,0.75)', fontSize: 11, marginBottom: 2 },
  locationValue: { color: '#fff', fontSize: 15, fontWeight: '600' },
  locError: { color: '#ffb4b4', fontSize: 12, marginTop: 6 },
  scanFrame: { width: 260, height: 260, borderWidth: 3, borderColor: '#fff', borderRadius: 20, opacity: 0.7 },
  hint: { color: '#fff', fontSize: 14, marginTop: 20, textAlign: 'center', paddingHorizontal: 24 },
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
  permText: { color: THEME.primary, fontSize: 16, textAlign: 'center', marginBottom: 16 },
  permBtn: { backgroundColor: THEME.primary, borderRadius: 10, paddingHorizontal: 24, paddingVertical: 12 },
  permBtnText: { color: '#fff', fontWeight: '600', fontSize: 15 },
  modalBg: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: 'rgba(0,0,0,0.5)' },
  modalCard: {
    width: '85%',
    maxWidth: 360,
    backgroundColor: '#fff',
    borderRadius: 20,
    padding: 24,
    alignItems: 'center',
  },
  pickerCard: { maxHeight: '70%', width: '90%' },
  pickerTitle: { fontSize: 18, fontWeight: '700', color: THEME.primary, marginBottom: 12, alignSelf: 'flex-start' },
  pickerRow: { paddingVertical: 12, paddingHorizontal: 8, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#eee', width: '100%' },
  pickerRowSelected: { backgroundColor: '#f0eeff' },
  pickerRowText: { fontSize: 16, color: '#333' },
  pickerRowSub: { fontSize: 12, color: '#888', marginTop: 2 },
  pickerEmpty: { textAlign: 'center', color: '#999', padding: 16 },
  resultIcon: { fontSize: 72, fontWeight: '700', marginBottom: 8 },
  resultType: { fontSize: 22, fontWeight: '700', color: THEME.primary, marginBottom: 8 },
  resultName: { fontSize: 18, color: '#333', marginBottom: 4 },
  resultLocation: { fontSize: 14, color: '#555', marginBottom: 6 },
  resultStatus: { fontSize: 13, color: '#555', marginBottom: 6, fontWeight: '600' },
  resultTime: { fontSize: 14, color: '#888', marginBottom: 20 },
  errorMsg: { fontSize: 14, color: THEME.error, textAlign: 'center', marginBottom: 20 },
  okBtn: { backgroundColor: THEME.primary, borderRadius: 10, paddingHorizontal: 32, paddingVertical: 12 },
  okBtnText: { color: '#fff', fontWeight: '600', fontSize: 15 },
});
