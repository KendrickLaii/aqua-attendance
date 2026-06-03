import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Pressable,
  Modal,
  Platform,
  FlatList,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import Button from '../components/ui/Button';
import { colors, layout, radius, spacing, typography } from '../theme';
import { previewScanQR, scanQR, type AttendanceEvent, type ScanPreview } from '../services/attendance';
import { normalizeQrToken } from '../utils/qrToken';
import { listLocations, locationDisplayName, type LocationItem } from '../services/locations';
import { useI18n } from '../i18n/I18nContext';
import {
  allowedLocationLabel,
  getLocationNotAllowedDetail,
  isLocationNotAllowedError,
  type AllowedLocationRef,
} from '../utils/scanErrors';
import {
  clearDefaultLocation,
  loadScanPrefs,
  resolveDefaultLocationId,
  saveDefaultLocation,
  type ScanEventType,
} from '../services/scanPrefs';

type Phase = 'setup' | 'camera';

export default function ScannerScreen() {
  const { t, dateLocale } = useI18n();
  const [permission, requestPermission] = useCameraPermissions();
  const [phase, setPhase] = useState<Phase>('setup');
  const [scanning, setScanning] = useState(true);
  const [selectedEventType, setSelectedEventType] = useState<ScanEventType>('check_in');
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [locationsLoading, setLocationsLoading] = useState(true);
  const [locationsError, setLocationsError] = useState('');
  const [prefsLoaded, setPrefsLoaded] = useState(false);
  const [hasDefaultLocation, setHasDefaultLocation] = useState(false);
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(null);
  const [locationPickerOpen, setLocationPickerOpen] = useState(false);
  const [pendingToken, setPendingToken] = useState<string | null>(null);
  const [pendingPreview, setPendingPreview] = useState<ScanPreview | null>(null);
  const [confirmVisible, setConfirmVisible] = useState(false);
  const [result, setResult] = useState<AttendanceEvent | null>(null);
  const [error, setError] = useState('');
  const [errorAllowedLocations, setErrorAllowedLocations] = useState<AllowedLocationRef[]>([]);
  const [errorProductName, setErrorProductName] = useState<string | null>(null);
  const [resultVisible, setResultVisible] = useState(false);
  const [processing, setProcessing] = useState(false);

  const selectedLocation = locations.find((l) => l.id === selectedLocationId) ?? null;
  const canStartCamera = Boolean(selectedLocationId) && !locationsLoading && !locationsError;

  const loadLocations = useCallback(async () => {
    setLocationsLoading(true);
    setLocationsError('');
    try {
      const prefs = await loadScanPrefs();
      const data = await listLocations({ is_active: true, page_size: 200 });
      setLocations(data);

      const validId = resolveDefaultLocationId(
        prefs.locationId,
        data.map((l) => l.id),
      );
      if (prefs.locationId && !validId) {
        await clearDefaultLocation();
      }
      setSelectedLocationId(validId);
      setHasDefaultLocation(Boolean(validId));
      // Check-in/out is chosen each session on the setup screen (not auto-skipped).
      setSelectedEventType('check_in');
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t('scanner.loadLocationsFailed');
      setLocationsError(msg);
    } finally {
      setLocationsLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadLocations();
  }, [loadLocations]);

  async function selectLocation(id: string | null) {
    setSelectedLocationId(id);
    setLocationPickerOpen(false);
    if (id) {
      await saveDefaultLocation(id);
      setHasDefaultLocation(true);
    } else {
      await clearDefaultLocation();
      setHasDefaultLocation(false);
    }
  }

  async function clearDefault() {
    await clearDefaultLocation();
    setSelectedLocationId(null);
    setHasDefaultLocation(false);
    setPhase('setup');
  }

  function selectEventType(type: ScanEventType) {
    setSelectedEventType(type);
  }

  function clearScanError() {
    setError('');
    setErrorAllowedLocations([]);
    setErrorProductName(null);
  }

  function applyScanError(e: unknown) {
    if (isLocationNotAllowedError(e)) {
      const info = getLocationNotAllowedDetail(e);
      setError(info.message);
      setErrorAllowedLocations(info.allowedLocations);
      setErrorProductName(info.productName);
      return;
    }
    setError(e instanceof Error ? e.message : t('scanner.scanFailed'));
    setErrorAllowedLocations([]);
    setErrorProductName(null);
  }

  function handleStartCamera() {
    if (!canStartCamera) return;
    setPhase('camera');
    setScanning(true);
    setPendingToken(null);
    setPendingPreview(null);
    setConfirmVisible(false);
    clearScanError();
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
    clearScanError();

    try {
      const preview = await previewScanQR(token, {
        locationId: selectedLocationId ?? undefined,
      });
      setPendingPreview(preview);
      setConfirmVisible(true);
    } catch (e: unknown) {
      applyScanError(e);
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
    clearScanError();
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
        <ScrollView
          contentContainerStyle={styles.setupScroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.setupTitle}>{t('scanner.setupTitle')}</Text>
          <Text style={styles.setupSubtitle}>
            {hasDefaultLocation ? t('scanner.setupSubtitleWithDefault') : t('scanner.setupSubtitle')}
          </Text>

          <Text style={styles.sectionLabel}>{t('scanner.sectionType')}</Text>
          <Text style={styles.sectionHint}>{t('scanner.eventTypeRequired')}</Text>
          <View style={styles.segmentTrack}>
            <Pressable
              style={[styles.segment, selectedEventType === 'check_in' && styles.segmentInActive]}
              onPress={() => selectEventType('check_in')}
            >
              <Text
                style={[
                  styles.segmentText,
                  selectedEventType === 'check_in' && styles.segmentTextActive,
                ]}
              >
                {t('scanner.checkIn')}
              </Text>
            </Pressable>
            <Pressable
              style={[styles.segment, selectedEventType === 'check_out' && styles.segmentOutActive]}
              onPress={() => selectEventType('check_out')}
            >
              <Text
                style={[
                  styles.segmentText,
                  selectedEventType === 'check_out' && styles.segmentTextActive,
                ]}
              >
                {t('scanner.checkOut')}
              </Text>
            </Pressable>
          </View>

          <Text style={[styles.sectionLabel, { marginTop: spacing.xl }]}>
            {t('scanner.defaultLocationLabel')}
          </Text>
          {selectedLocation ? (
            <View style={styles.defaultBanner}>
              <Text style={styles.defaultBannerText}>
                {t('scanner.defaultLocationActive', {
                  name: locationDisplayName(selectedLocation),
                })}
              </Text>
            </View>
          ) : null}
          <Pressable
            style={styles.setupLocationBtn}
            onPress={() => setLocationPickerOpen(true)}
            disabled={locationsLoading}
          >
            <View style={styles.locationBtnInner}>
              <View style={styles.locationBtnText}>
                <Text style={styles.setupLocationBtnLabel}>
                  {selectedLocation ? t('scanner.changeDefaultLocation') : t('scanner.selectLocation')}
                </Text>
                <Text style={styles.setupLocationValue} numberOfLines={2}>
                  {selectedLocation
                    ? locationDisplayName(selectedLocation)
                    : locationsLoading
                      ? t('common.loading')
                      : t('scanner.selectLocation')}
                </Text>
              </View>
              <Text style={styles.chevron}>›</Text>
            </View>
          </Pressable>
          <Text style={styles.defaultHint}>{t('scanner.defaultLocationHint')}</Text>
          {locationsError ? <Text style={styles.setupError}>{locationsError}</Text> : null}
          {!selectedLocationId && !locationsLoading && !locationsError ? (
            <Text style={styles.setupHint}>{t('scanner.selectLocationRequired')}</Text>
          ) : null}
          {hasDefaultLocation && selectedLocation ? (
            <Pressable style={styles.clearDefaultBtn} onPress={clearDefault}>
              <Text style={styles.clearDefaultText}>{t('scanner.clearDefaultLocation')}</Text>
            </Pressable>
          ) : null}
        </ScrollView>

        <View style={styles.setupFooter}>
          <Button
            label={t('scanner.startScan')}
            onPress={handleStartCamera}
            disabled={!canStartCamera}
          />
        </View>

        {locationPickerModal}
      </View>
    );
  }

  if (!permission) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary} />
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
            <Text style={styles.confirmTitle}>{t('scanner.confirmTitle', { action: eventLabel })}</Text>
            {pendingPreview ? (
              <>
                <Text style={styles.confirmName}>
                  {pendingPreview.product_name || pendingPreview.product_code || t('common.dash')}
                </Text>
                {pendingPreview.product_type ? (
                  <Text style={styles.confirmType}>
                    {labelProductType(pendingPreview.product_type)}
                  </Text>
                ) : null}
                {pendingPreview.product_code ? (
                  <Text style={styles.confirmCode}>
                    {t('scanner.codeLabel', { code: pendingPreview.product_code })}
                  </Text>
                ) : null}
              </>
            ) : null}
            <Text style={styles.confirmBody}>{t('scanner.confirmRecord', { action: eventLabel })}</Text>
            {selectedLocation ? (
              <Text style={styles.confirmDetail}>
                {t('scanner.locationLabel', { name: locationDisplayName(selectedLocation) })}
              </Text>
            ) : null}
            <View style={styles.confirmRow}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={handleCancelConfirm}
                disabled={processing}
              >
                <Text style={styles.cancelBtnText}>{t('common.cancel')}</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.confirmBtn, selectedEventType === 'check_in' ? styles.confirmBtnIn : styles.confirmBtnOut]}
                onPress={handleConfirmScan}
                disabled={processing}
              >
                {processing ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.confirmBtnText}>{t('scanner.confirmAction', { action: eventLabel })}</Text>
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
                <View
                  style={[
                    styles.resultIconWrap,
                    {
                      backgroundColor:
                        result.event_type === 'check_in' ? colors.checkInSoft : colors.checkOutSoft,
                    },
                  ]}
                >
                  <Text
                    style={[
                      styles.resultGlyph,
                      { color: result.event_type === 'check_in' ? colors.checkIn : colors.checkOut },
                    ]}
                  >
                    {result.event_type === 'check_in' ? '✓' : '↩'}
                  </Text>
                </View>
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
                <View style={[styles.resultIconWrap, { backgroundColor: colors.errorSoft }]}>
                  <Text style={[styles.resultGlyph, { color: colors.error }]}>✕</Text>
                </View>
                <Text style={styles.resultType}>
                  {errorAllowedLocations.length > 0
                    ? t('scanner.locationNotAllowedTitle')
                    : t('scanner.scanFailed')}
                </Text>
                <Text style={styles.errorMsg}>{error}</Text>
                {errorAllowedLocations.length > 0 ? (
                  <View style={styles.allowedBox}>
                    <Text style={styles.allowedTitle}>
                      {errorProductName
                        ? t('scanner.allowedLocationsForProduct', { name: errorProductName })
                        : t('scanner.allowedLocationsTitle')}
                    </Text>
                    {errorAllowedLocations.map((loc) => (
                      <Text key={loc.id} style={styles.allowedItem}>
                        • {allowedLocationLabel(loc)}
                      </Text>
                    ))}
                  </View>
                ) : null}
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
  setupContainer: { flex: 1, backgroundColor: colors.background },
  setupScroll: {
    padding: layout.screenPadding,
    paddingBottom: spacing.xl,
  },
  setupFooter: {
    padding: layout.screenPadding,
    paddingTop: spacing.md,
    paddingBottom: Platform.OS === 'ios' ? spacing.xxl : spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
  },
  setupTitle: { ...typography.hero, fontSize: 22, marginBottom: spacing.sm },
  setupSubtitle: { ...typography.subtitle, marginBottom: spacing.xxl },
  sectionLabel: { ...typography.label, marginBottom: spacing.sm },
  sectionHint: { ...typography.caption, marginBottom: spacing.md },
  segmentTrack: {
    flexDirection: 'row',
    gap: spacing.md,
    marginBottom: spacing.sm,
  },
  segment: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.lg,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  segmentInActive: { backgroundColor: colors.checkIn, borderColor: colors.checkIn },
  segmentOutActive: { backgroundColor: colors.checkOut, borderColor: colors.checkOut },
  segmentText: { fontSize: 15, fontWeight: '600', color: colors.text },
  segmentTextActive: { color: '#fff' },
  defaultBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.primaryMuted,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  defaultBannerText: { ...typography.bodyStrong, color: colors.primary, flex: 1 },
  defaultHint: { ...typography.caption, marginBottom: spacing.md, lineHeight: 18 },
  setupLocationBtn: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    marginBottom: spacing.sm,
  },
  locationBtnInner: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.lg,
    gap: spacing.md,
  },
  locationBtnText: { flex: 1 },
  chevron: { fontSize: 22, color: colors.textMuted, fontWeight: '300' },
  setupLocationBtnLabel: { ...typography.label, marginBottom: spacing.xs, textTransform: 'none' as const, letterSpacing: 0 },
  setupLocationValue: { ...typography.bodyStrong },
  clearDefaultBtn: { alignSelf: 'flex-start', marginBottom: spacing.sm, paddingVertical: spacing.xs },
  clearDefaultText: { fontSize: 13, color: colors.error, fontWeight: '600' },
  setupError: { color: colors.error, fontSize: 13, marginBottom: spacing.sm },
  setupHint: { ...typography.caption, marginBottom: spacing.lg },
  container: { flex: 1, backgroundColor: '#000' },
  centered: { flex: 1, backgroundColor: colors.background, justifyContent: 'center', alignItems: 'center', padding: layout.screenPadding },
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
    backgroundColor: colors.cameraOverlay,
    borderRadius: radius.md,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  backBtnText: { color: '#fff', fontWeight: '600', fontSize: 14 },
  cameraSummary: {
    flex: 1,
    backgroundColor: colors.cameraOverlay,
    borderRadius: radius.md,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  cameraSummaryLine: { color: '#fff', fontSize: 14, fontWeight: '600' },
  scanFrame: {
    width: 248,
    height: 248,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.9)',
    borderRadius: radius.xl,
  },
  hint: { color: '#fff', fontSize: 14, marginTop: 20, textAlign: 'center', paddingHorizontal: 24 },
  backLink: { position: 'absolute', top: Platform.OS === 'ios' ? 56 : 24, left: 24 },
  backLinkText: { color: colors.primary, fontSize: 15, fontWeight: '600' },
  permText: { color: colors.primary, fontSize: 16, textAlign: 'center', marginBottom: 16 },
  permBtn: { backgroundColor: colors.primary, borderRadius: 10, paddingHorizontal: 24, paddingVertical: 12 },
  permBtnText: { color: '#fff', fontWeight: '600', fontSize: 15 },
  modalBg: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: 'rgba(0,0,0,0.5)' },
  modalCard: {
    width: '88%',
    maxWidth: 380,
    backgroundColor: colors.surface,
    borderRadius: radius.xl,
    padding: spacing.xxl,
    alignItems: 'center',
  },
  pickerCard: { maxHeight: '70%', width: '90%' },
  pickerTitle: { fontSize: 18, fontWeight: '700', color: colors.primary, marginBottom: 12, alignSelf: 'flex-start' },
  pickerRow: {
    paddingVertical: 12,
    paddingHorizontal: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#eee',
    width: '100%',
  },
  pickerRowSelected: { backgroundColor: colors.primaryMuted },
  pickerRowText: { fontSize: 16, color: '#333' },
  pickerRowSub: { fontSize: 12, color: '#888', marginTop: 2 },
  pickerEmpty: { textAlign: 'center', color: '#999', padding: 16 },
  confirmTitle: { fontSize: 22, fontWeight: '700', color: colors.primary, marginBottom: 12 },
  confirmName: { fontSize: 20, fontWeight: '700', color: '#333', textAlign: 'center', marginBottom: 4 },
  confirmType: { fontSize: 15, color: colors.primary, fontWeight: '600', marginBottom: 4 },
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
  confirmBtnIn: { backgroundColor: colors.checkIn },
  confirmBtnOut: { backgroundColor: colors.checkOut },
  confirmBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  resultIconWrap: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.lg,
  },
  resultGlyph: { fontSize: 36, fontWeight: '700' },
  resultType: { fontSize: 22, fontWeight: '700', color: colors.primary, marginBottom: 8 },
  resultName: { fontSize: 18, color: '#333', marginBottom: 4 },
  resultLocation: { fontSize: 14, color: '#555', marginBottom: 6 },
  resultStatus: { fontSize: 13, color: '#555', marginBottom: 6, fontWeight: '600' },
  resultTime: { fontSize: 14, color: '#888', marginBottom: 20 },
  errorMsg: { fontSize: 14, color: colors.error, textAlign: 'center', marginBottom: 12 },
  allowedBox: {
    width: '100%',
    backgroundColor: colors.background,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.lg,
    alignSelf: 'stretch',
    borderWidth: 1,
    borderColor: colors.border,
  },
  allowedTitle: { fontSize: 13, fontWeight: '600', color: colors.primary, marginBottom: 8 },
  allowedItem: { fontSize: 14, color: '#444', marginBottom: 4, textAlign: 'left' },
  okBtn: { backgroundColor: colors.primary, borderRadius: 10, paddingHorizontal: 32, paddingVertical: 12 },
  okBtnText: { color: '#fff', fontWeight: '600', fontSize: 15 },
});
