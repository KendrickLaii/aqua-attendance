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
import { previewScanQR, scanQR, type AttendanceEvent, type ScanPreview } from '../services/attendance';
import { normalizeQrToken } from '../utils/qrToken';
import { listLocations, locationDisplayName, type LocationItem } from '../services/locations';
import { useI18n } from '../i18n/I18nContext';

const THEME = { primary: '#160D47', bg: '#F4F5FA', success: '#56CA00', warning: '#FFB400', error: '#9d1c24' };

const SCAN_LOCATION_KEY = 'attendance-scan-location-id';
const SCAN_EVENT_TYPE_KEY = 'attendance-scan-event-type';

type Phase = 'setup' | 'camera';

export default function ScannerScreen() {
  const { t, dateLocale } = useI18n();
  const [permission, requestPermission] = useCameraPermissions();
  const [phase, setPhase] = useState<Phase>('setup');
  const [scanning, setScanning] = useState(true);
  const [selectedEventType, setSelectedEventType] = useState<'check_in' | 'check_out'>('check_in');
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [locationsLoading, setLocationsLoading] = useState(true);
  const [locationsError, setLocationsError] = useState('');
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(null);
  const [locationPickerOpen, setLocationPickerOpen] = useState(false);
  const [pendingToken, setPendingToken] = useState<string | null>(null);
  const [pendingPreview, setPendingPreview] = useState<ScanPreview | null>(null);
  const [confirmVisible, setConfirmVisible] = useState(false);
  const [result, setResult] = useState<AttendanceEvent | null>(null);
  const [error, setError] = useState('');
  const [resultVisible, setResultVisible] = useState(false);
  const [processing, setProcessing] = useState(false);

  const selectedLocation = locations.find((l) => l.id === selectedLocationId) ?? null;
  const canStartCamera = Boolean(selectedLocationId) && !locationsLoading && !locationsError;

  const loadLocations = useCallback(async () => {
    setLocationsLoading(true);
    setLocationsError('');
    try {
      const data = await listLocations({ is_active: true, page_size: 200 });
      setLocations(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t('scanner.loadLocationsFailed');
      setLocationsError(msg);
    } finally {
      setLocationsLoading(false);
    }
  }, [t]);

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

  function handleStartCamera() {
    if (!canStartCamera) return;
    setPhase('camera');
    setScanning(true);
    setPendingToken(null);
    setPendingPreview(null);
    setConfirmVisible(false);
    setError('');
    setResult(null);
  }

  function handleBackToSetup() {
    setPhase('setup');
    setScanning(false);
    setPendingToken(null);
    setPendingPreview(null);
    setConfirmVisible(false);
    setProcessing(false);
  }

  async function handleBarCodeScanned({ data }: { data: string }) {
    if (phase !== 'camera' || !scanning || processing || confirmVisible) return;

    const token = normalizeQrToken(data);
    if (!token) {
      setError(t('scanner.qrEmpty'));
      setResultVisible(true);
      setScanning(false);
      return;
    }

    setScanning(false);
    setProcessing(true);
    setPendingToken(token);
    setPendingPreview(null);
    setError('');

    try {
      const preview = await previewScanQR(token, {
        locationId: selectedLocationId ?? undefined,
      });
      setPendingPreview(preview);
      setConfirmVisible(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('scanner.qrUnrecognized'));
      setResultVisible(true);
      setPendingToken(null);
    } finally {
      setProcessing(false);
    }
  }

  function handleCancelConfirm() {
    setConfirmVisible(false);
    setPendingToken(null);
    setPendingPreview(null);
    setTimeout(() => setScanning(true), 300);
  }

  async function handleConfirmScan() {
    if (!pendingToken || processing) return;
    setProcessing(true);
    setConfirmVisible(false);
    setError('');
    setResult(null);

    try {
      const evt = await scanQR(pendingToken, {
        deviceId: `mobile-${Platform.OS}`,
        eventType: selectedEventType,
        locationId: selectedLocationId ?? undefined,
      });
      setResult(evt);
      setResultVisible(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '掃描失敗');
      setResultVisible(true);
    } finally {
      setProcessing(false);
      setPendingToken(null);
      setPendingPreview(null);
    }
  }

  function handleDismissResult() {
    setResultVisible(false);
    setResult(null);
    setError('');
    if (phase === 'camera') {
      setTimeout(() => setScanning(true), 500);
    }
  }

  const eventLabel =
    selectedEventType === 'check_in' ? t('scanner.checkIn') : t('scanner.checkOut');

  function labelProductType(productType: string | null): string {
    if (productType === 'student') return t('productType.student');
    if (productType === 'staff') return t('productType.staff');
    return productType ?? '';
  }

  const locationPickerModal = (
    <Modal visible={locationPickerOpen} transparent animationType="slide">
      <View style={styles.modalBg}>
        <View style={[styles.modalCard, styles.pickerCard]}>
          <Text style={styles.pickerTitle}>{t('scanner.pickLocationTitle')}</Text>
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
                {locationsLoading ? t('common.loading') : t('scanner.noLocations')}
              </Text>
            }
          />
          <TouchableOpacity style={styles.okBtn} onPress={() => setLocationPickerOpen(false)}>
            <Text style={styles.okBtnText}>{t('common.close')}</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );

  if (phase === 'setup') {
    return (
      <View style={styles.setupContainer}>
        <Text style={styles.setupTitle}>掃描設定</Text>
        <Text style={styles.setupSubtitle}>請先選擇簽到／簽退與地點，再進入相機掃描</Text>

        <Text style={styles.sectionLabel}>類型</Text>
        <View style={styles.setupActionRow}>
          <TouchableOpacity
            style={[styles.setupActionBtn, selectedEventType === 'check_in' && styles.setupActionBtnIn]}
            onPress={() => selectEventType('check_in')}
          >
            <Text
              style={[
                styles.setupActionBtnText,
                selectedEventType === 'check_in' && styles.setupActionBtnTextActive,
              ]}
            >
              {t('scanner.checkIn')}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.setupActionBtn, selectedEventType === 'check_out' && styles.setupActionBtnOut]}
            onPress={() => selectEventType('check_out')}
          >
            <Text
              style={[
                styles.setupActionBtnText,
                selectedEventType === 'check_out' && styles.setupActionBtnTextActive,
              ]}
            >
              {t('scanner.checkOut')}
            </Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.sectionLabel}>{t('scanner.sectionLocation')}</Text>
        <TouchableOpacity
          style={styles.setupLocationBtn}
          onPress={() => setLocationPickerOpen(true)}
          disabled={locationsLoading}
        >
          <Text style={styles.setupLocationValue} numberOfLines={2}>
            {selectedLocation
              ? locationDisplayName(selectedLocation)
              : locationsLoading
                ? t('common.loading')
                : t('scanner.selectLocation')}
          </Text>
        </TouchableOpacity>
        {locationsError ? <Text style={styles.setupError}>{locationsError}</Text> : null}
        {!selectedLocationId && !locationsLoading && !locationsError ? (
          <Text style={styles.setupHint}>{t('scanner.selectLocationRequired')}</Text>
        ) : null}

        <TouchableOpacity
          style={[styles.startBtn, !canStartCamera && styles.startBtnDisabled]}
          onPress={handleStartCamera}
          disabled={!canStartCamera}
        >
          <Text style={styles.startBtnText}>{t('scanner.startScan')}</Text>
        </TouchableOpacity>

        {locationPickerModal}
      </View>
    );
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
        <TouchableOpacity style={styles.backLink} onPress={handleBackToSetup}>
          <Text style={styles.backLinkText}>{t('scanner.backToSetup')}</Text>
        </TouchableOpacity>
        <Text style={styles.permText}>{t('scanner.cameraPermission')}</Text>
        <TouchableOpacity style={styles.permBtn} onPress={requestPermission}>
          <Text style={styles.permBtnText}>{t('scanner.grantPermission')}</Text>
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
        onBarcodeScanned={scanning && !confirmVisible && !processing ? handleBarCodeScanned : undefined}
      />

      <View style={styles.overlay}>
        <View style={styles.cameraTopBar}>
          <TouchableOpacity style={styles.backBtn} onPress={handleBackToSetup} disabled={processing}>
            <Text style={styles.backBtnText}>{t('scanner.backSetupShort')}</Text>
          </TouchableOpacity>
          <View style={styles.cameraSummary}>
            <Text style={styles.cameraSummaryLine}>
              {eventLabel} · {selectedLocation ? locationDisplayName(selectedLocation) : t('common.dash')}
            </Text>
          </View>
        </View>

        <View style={styles.scanFrame} />
        <Text style={styles.hint}>
          {processing && !confirmVisible
            ? t('scanner.hintRecognizing')
            : processing
              ? t('scanner.hintSubmitting')
              : confirmVisible
                ? t('scanner.hintConfirmInModal')
                : t('scanner.hintAimQr')}
        </Text>
      </View>

      <Modal visible={confirmVisible} transparent animationType="fade">
        <View style={styles.modalBg}>
          <View style={styles.modalCard}>
            <Text style={styles.confirmTitle}>確認{eventLabel}？</Text>
            {pendingPreview ? (
              <>
                <Text style={styles.confirmName}>
                  {pendingPreview.product_name || pendingPreview.product_code || '—'}
                </Text>
                {pendingPreview.product_type ? (
                  <Text style={styles.confirmType}>
                    {labelProductType(pendingPreview.product_type)}
                  </Text>
                ) : null}
                {pendingPreview.product_code ? (
                  <Text style={styles.confirmCode}>編號：{pendingPreview.product_code}</Text>
                ) : null}
              </>
            ) : null}
            <Text style={styles.confirmBody}>即將記錄「{eventLabel}」</Text>
            {selectedLocation ? (
              <Text style={styles.confirmDetail}>
                地點：{locationDisplayName(selectedLocation)}
              </Text>
            ) : null}
            <View style={styles.confirmRow}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={handleCancelConfirm}
                disabled={processing}
              >
                <Text style={styles.cancelBtnText}>取消</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.confirmBtn, selectedEventType === 'check_in' ? styles.confirmBtnIn : styles.confirmBtnOut]}
                onPress={handleConfirmScan}
                disabled={processing}
              >
                {processing ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.confirmBtnText}>確認{eventLabel}</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      <Modal visible={resultVisible} transparent animationType="slide">
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
                  {result.event_type === 'check_in'
                    ? t('scanner.checkInSuccess')
                    : t('scanner.checkOutSuccess')}
                </Text>
                <Text style={styles.resultName}>
                  {result.product_name || result.product_code || t('common.dash')}
                </Text>
                {result.location ? (
                  <Text style={styles.resultLocation}>
                    {t('scanner.locationLabel', { name: result.location })}
                  </Text>
                ) : null}
                {result.attendance_status ? (
                  <Text style={styles.resultStatus}>
                    {t('scanner.statusLabel', {
                      status:
                        result.attendance_status === 'checked_in'
                          ? t('attendanceStatus.checked_in')
                          : t('attendanceStatus.checked_out'),
                    })}
                  </Text>
                ) : null}
                <Text style={styles.resultTime}>
                  {new Date(result.recorded_at).toLocaleTimeString(dateLocale)}
                </Text>
              </>
            ) : error ? (
              <>
                <Text style={[styles.resultIcon, { color: THEME.error }]}>✗</Text>
                <Text style={styles.resultType}>{t('scanner.scanFailed')}</Text>
                <Text style={styles.errorMsg}>{error}</Text>
              </>
            ) : null}
            <TouchableOpacity style={styles.okBtn} onPress={handleDismissResult}>
              <Text style={styles.okBtnText}>{t('scanner.continueScan')}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {locationPickerModal}
    </View>
  );
}

const styles = StyleSheet.create({
  setupContainer: {
    flex: 1,
    backgroundColor: THEME.bg,
    padding: 24,
    paddingTop: Platform.OS === 'ios' ? 56 : 24,
  },
  setupTitle: { fontSize: 24, fontWeight: '700', color: THEME.primary, marginBottom: 8 },
  setupSubtitle: { fontSize: 14, color: '#666', marginBottom: 28 },
  sectionLabel: { fontSize: 13, fontWeight: '600', color: '#888', marginBottom: 8, marginTop: 8 },
  setupActionRow: { flexDirection: 'row', gap: 12, marginBottom: 8 },
  setupActionBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#ccc',
    backgroundColor: '#fff',
    alignItems: 'center',
  },
  setupActionBtnIn: { borderColor: THEME.success, backgroundColor: THEME.success },
  setupActionBtnOut: { borderColor: THEME.warning, backgroundColor: THEME.warning },
  setupActionBtnText: { fontSize: 17, fontWeight: '600', color: THEME.primary },
  setupActionBtnTextActive: { color: '#fff' },
  setupLocationBtn: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#ddd',
    marginBottom: 8,
  },
  setupLocationValue: { fontSize: 16, fontWeight: '600', color: THEME.primary },
  setupError: { color: THEME.error, fontSize: 13, marginBottom: 8 },
  setupHint: { color: '#888', fontSize: 13, marginBottom: 16 },
  startBtn: {
    marginTop: 32,
    backgroundColor: THEME.primary,
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
  },
  startBtnDisabled: { opacity: 0.45 },
  startBtnText: { color: '#fff', fontSize: 17, fontWeight: '700' },
  container: { flex: 1, backgroundColor: '#000' },
  centered: { flex: 1, backgroundColor: THEME.bg, justifyContent: 'center', alignItems: 'center', padding: 24 },
  overlay: { ...StyleSheet.absoluteFillObject, justifyContent: 'center', alignItems: 'center' },
  cameraTopBar: {
    position: 'absolute',
    top: Platform.OS === 'ios' ? 56 : 16,
    left: 16,
    right: 16,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
  },
  backBtn: {
    backgroundColor: 'rgba(0,0,0,0.55)',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  backBtnText: { color: '#fff', fontWeight: '600', fontSize: 14 },
  cameraSummary: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  cameraSummaryLine: { color: '#fff', fontSize: 14, fontWeight: '600' },
  scanFrame: { width: 260, height: 260, borderWidth: 3, borderColor: '#fff', borderRadius: 20, opacity: 0.7 },
  hint: { color: '#fff', fontSize: 14, marginTop: 20, textAlign: 'center', paddingHorizontal: 24 },
  backLink: { position: 'absolute', top: Platform.OS === 'ios' ? 56 : 24, left: 24 },
  backLinkText: { color: THEME.primary, fontSize: 15, fontWeight: '600' },
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
  pickerRow: {
    paddingVertical: 12,
    paddingHorizontal: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#eee',
    width: '100%',
  },
  pickerRowSelected: { backgroundColor: '#f0eeff' },
  pickerRowText: { fontSize: 16, color: '#333' },
  pickerRowSub: { fontSize: 12, color: '#888', marginTop: 2 },
  pickerEmpty: { textAlign: 'center', color: '#999', padding: 16 },
  confirmTitle: { fontSize: 22, fontWeight: '700', color: THEME.primary, marginBottom: 12 },
  confirmName: { fontSize: 20, fontWeight: '700', color: '#333', textAlign: 'center', marginBottom: 4 },
  confirmType: { fontSize: 15, color: THEME.primary, fontWeight: '600', marginBottom: 4 },
  confirmCode: { fontSize: 13, color: '#888', marginBottom: 12 },
  confirmBody: { fontSize: 15, color: '#555', textAlign: 'center', marginBottom: 8 },
  confirmDetail: { fontSize: 14, color: '#555', marginBottom: 24, textAlign: 'center' },
  confirmRow: { flexDirection: 'row', gap: 12, width: '100%' },
  cancelBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#ccc',
    alignItems: 'center',
  },
  cancelBtnText: { color: '#666', fontWeight: '600', fontSize: 15 },
  confirmBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
  },
  confirmBtnIn: { backgroundColor: THEME.success },
  confirmBtnOut: { backgroundColor: THEME.warning },
  confirmBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
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
