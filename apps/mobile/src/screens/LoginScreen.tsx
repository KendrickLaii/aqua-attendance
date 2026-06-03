import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import LanguagePicker from '../components/LanguagePicker';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import Field from '../components/ui/Field';
import { useI18n } from '../i18n/I18nContext';
import { login, type User } from '../services/auth';
import { colors, layout, spacing, typography } from '../theme';

interface Props {
  onLoginSuccess: (user: User) => void;
}

export default function LoginScreen({ onLoginSuccess }: Props) {
  const { t } = useI18n();
  const insets = useSafeAreaInsets();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleLogin() {
    if (!username.trim() || !password.trim()) return;
    setLoading(true);
    setError('');
    try {
      const me = await login(username.trim(), password);
      onLoginSuccess(me);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('login.failed'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={[styles.hero, { paddingTop: insets.top + spacing.xxl }]}>
        <Text style={styles.heroTitle}>{t('login.title')}</Text>
        <Text style={styles.heroSubtitle}>{t('login.subtitle')}</Text>
      </View>

      <ScrollView
        style={styles.sheetScroll}
        contentContainerStyle={[
          styles.sheetContent,
          { paddingBottom: insets.bottom + spacing.xxl },
        ]}
        keyboardShouldPersistTaps="handled"
      >
        <Card style={styles.formCard}>
          <LanguagePicker />
          {error ? (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}
          <Field
            label={t('login.username')}
            placeholder={t('login.username')}
            value={username}
            onChangeText={setUsername}
            autoCapitalize="none"
            autoCorrect={false}
          />
          <Field
            label={t('login.password')}
            placeholder={t('login.password')}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />
          <Button label={t('login.signIn')} onPress={handleLogin} loading={loading} />
        </Card>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.primary },
  hero: {
    paddingHorizontal: layout.screenPadding,
    paddingBottom: spacing.xxxl + 8,
    alignItems: 'flex-start',
  },
  heroTitle: {
    ...typography.hero,
    color: colors.headerText,
  },
  heroSubtitle: {
    ...typography.subtitle,
    color: 'rgba(255,255,255,0.82)',
    marginTop: spacing.sm,
  },
  sheetScroll: {
    flex: 1,
    backgroundColor: colors.background,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    marginTop: -20,
  },
  sheetContent: {
    paddingHorizontal: layout.screenPadding,
    paddingTop: spacing.xxl,
  },
  formCard: { width: '100%' },
  errorBox: {
    backgroundColor: colors.errorSoft,
    borderRadius: 12,
    padding: spacing.md,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: '#F5C2C0',
  },
  errorText: { color: colors.error, fontSize: 14, textAlign: 'center' },
});
