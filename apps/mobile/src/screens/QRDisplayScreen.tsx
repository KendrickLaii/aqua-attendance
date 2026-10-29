import React from 'react';
import { Alert, View, Text, StyleSheet, ScrollView } from 'react-native';
import LanguagePicker from '../components/LanguagePicker';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import { useI18n } from '../i18n/I18nContext';
import { APP_DIAGNOSTICS } from '../services/api';
import type { Session } from '../services/auth';
import { colors, layout, spacing, typography } from '../theme';

interface Props {
  session: Session;
  onLogout: () => void;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

export default function HelpScreen({ session, onLogout }: Props) {
  const { t } = useI18n();
  const displayName =
    session.kind === 'staff'
      ? session.staff.full_name || session.staff.code
      : session.user.full_name || session.user.username;
  const badgeLabel = session.kind === 'staff' ? 'staff' : session.user.role;
  const roleTone =
    session.kind === 'admin' && session.user.role === 'superadmin' ? 'warning' : 'info';

  function confirmLogout() {
    Alert.alert(t('common.logoutConfirmTitle'), t('common.logoutConfirmBody'), [
      { text: t('common.cancel'), style: 'cancel' },
      { text: t('common.logout'), style: 'destructive', onPress: onLogout },
    ]);
  }

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
      <Card style={styles.profileCard}>
        <View style={styles.profileRow}>
          <View style={styles.avatar} accessibilityLabel={displayName}>
            <Text style={styles.avatarText}>{initials(displayName)}</Text>
          </View>
          <View style={styles.profileMeta}>
            <Text style={styles.name}>{displayName}</Text>
            <Badge label={badgeLabel} tone={roleTone} />
          </View>
        </View>
      </Card>

      <Text style={styles.sectionTitle}>{t('help.qrWebTitle')}</Text>

      <Card padded style={styles.stepCard}>
        <View style={styles.stepRow}>
          <View style={styles.stepNum}>
            <Text style={styles.stepNumText}>1</Text>
          </View>
          <Text style={styles.stepBody}>
            {t('help.qrWebBody', { qrCodes: t('help.qrCodes') })}
          </Text>
        </View>
      </Card>

      <Card padded style={styles.stepCard}>
        <View style={styles.stepRow}>
          <View style={[styles.stepNum, styles.stepNumAlt]}>
            <Text style={styles.stepNumText}>2</Text>
          </View>
          <Text style={styles.stepBody}>
            {t('help.qrWebBodyScan', { scanTab: t('help.scanTab') })}
          </Text>
        </View>
      </Card>

      <Card style={styles.langCard}>
        <LanguagePicker />
      </Card>

      <Text style={styles.sectionTitle}>{t('diagnostics.title')}</Text>
      <Card padded>
        <Text style={styles.diagnosticText} selectable>
          {t('diagnostics.version', { version: APP_DIAGNOSTICS.version, build: APP_DIAGNOSTICS.build })}
        </Text>
        <Text style={styles.diagnosticText} selectable>
          {t('diagnostics.environment', { environment: APP_DIAGNOSTICS.environment })}
        </Text>
        <Text style={styles.diagnosticText} selectable>
          {t('diagnostics.api', { api: APP_DIAGNOSTICS.apiHost })}
        </Text>
      </Card>

      <View style={styles.logoutWrap}>
        <Button label={t('common.logout')} onPress={confirmLogout} variant="danger" />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.background },
  content: {
    padding: layout.screenPadding,
    paddingBottom: spacing.xxxl,
    maxWidth: layout.maxContentWidth,
    width: '100%',
    alignSelf: 'center',
  },
  profileCard: { marginBottom: spacing.xxl },
  profileRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { fontSize: 18, fontWeight: '700', color: colors.primary },
  profileMeta: { flex: 1, gap: spacing.sm },
  name: { ...typography.title, fontSize: 18 },
  sectionTitle: { ...typography.title, fontSize: 17, marginBottom: spacing.lg },
  stepCard: { marginBottom: spacing.md },
  stepRow: { flexDirection: 'row', gap: spacing.lg, alignItems: 'flex-start' },
  stepNum: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.infoSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepNumAlt: { backgroundColor: colors.primaryMuted },
  stepNumText: { fontSize: 14, fontWeight: '700', color: colors.primary },
  stepBody: { ...typography.body, flex: 1, paddingTop: 2 },
  langCard: { marginTop: spacing.md, marginBottom: spacing.xxl },
  diagnosticText: { ...typography.body, color: colors.textSecondary, marginBottom: spacing.xs },
  logoutWrap: { marginTop: spacing.xxl },
});
