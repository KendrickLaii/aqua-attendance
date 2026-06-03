import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useI18n } from '../i18n/I18nContext';
import type { User } from '../services/auth';

const THEME = { primary: '#160D47', bg: '#F4F5FA', warning: '#FFB400' };

interface Props {
  user: User;
}

/** Help tab — product QRs are managed on the web admin. */
export default function HelpScreen({ user }: Props) {
  const { t } = useI18n();

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.name}>{user.full_name || user.username}</Text>
        <View
          style={[
            styles.badge,
            { backgroundColor: user.role === 'superadmin' ? THEME.warning : '#16B1FF' },
          ]}
        >
          <Text style={styles.badgeText}>{user.role}</Text>
        </View>
        <Text style={styles.iconBig}>📖</Text>
        <Text style={styles.heading}>{t('help.qrWebTitle')}</Text>
        <Text style={styles.body}>
          {t('help.qrWebBody', { qrCodes: t('help.qrCodes') })}
          {'\n\n'}
          {t('help.qrWebBodyScan', { scanTab: t('help.scanTab') })}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: THEME.bg, padding: 20 },
  card: {
    width: '100%',
    maxWidth: 360,
    backgroundColor: '#fff',
    borderRadius: 20,
    padding: 28,
    alignItems: 'center',
  },
  name: { fontSize: 18, fontWeight: '600', color: THEME.primary, marginBottom: 8 },
  badge: { paddingHorizontal: 12, paddingVertical: 4, borderRadius: 12, marginBottom: 16 },
  badgeText: { color: '#fff', fontSize: 12, fontWeight: '600', textTransform: 'capitalize' },
  iconBig: { fontSize: 48, marginBottom: 12 },
  heading: { fontSize: 18, fontWeight: '700', color: THEME.primary, textAlign: 'center', marginBottom: 12 },
  body: { fontSize: 15, color: '#555', textAlign: 'center', lineHeight: 22 },
});
