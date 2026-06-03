import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import LanguagePicker from '../components/LanguagePicker';
import Badge from '../components/ui/Badge';
import Card from '../components/ui/Card';
import { useI18n } from '../i18n/I18nContext';
import type { User } from '../services/auth';
import { colors, layout, spacing, typography } from '../theme';

interface Props {
  user: User;
}

function initials(user: User): string {
  const name = user.full_name || user.username;
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

export default function HelpScreen({ user }: Props) {
  const { t } = useI18n();
  const roleTone = user.role === 'superadmin' ? 'warning' : 'info';

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
      <Card style={styles.profileCard}>
        <View style={styles.profileRow}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initials(user)}</Text>
          </View>
          <View style={styles.profileMeta}>
            <Text style={styles.name}>{user.full_name || user.username}</Text>
            <Badge label={user.role} tone={roleTone} />
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
  langCard: { marginTop: spacing.md },
});
