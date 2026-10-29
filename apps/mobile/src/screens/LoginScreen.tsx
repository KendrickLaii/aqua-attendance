import React, { useRef, useState } from 'react';
import {
  View,
  Text,
  Image,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  TextInput,
  Pressable,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import LanguagePicker from '../components/LanguagePicker';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import Field from '../components/ui/Field';
import { useI18n } from '../i18n/I18nContext';
import { login, loginStaff, type Session } from '../services/auth';
import { colors, layout, radius, spacing, typography } from '../theme';

interface Props {
  onLoginSuccess: (session: Session) => void;
}

type LoginMode = 'admin' | 'staff';

export default function LoginScreen({ onLoginSuccess }: Props) {
  const { t } = useI18n();
  const insets = useSafeAreaInsets();
  const passwordRef = useRef<TextInput>(null);
  const [mode, setMode] = useState<LoginMode>('admin');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [staffCode, setStaffCode] = useState('');
  const [pin, setPin] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function switchMode(next: LoginMode) {
    setMode(next);
    setError('');
  }

  async function handleLogin() {
    if (mode === 'staff') {
      if (!staffCode.trim() || !/^\d{6}$/.test(pin)) {
        setError(t('login.staffEmptyFields'));
        return;
      }
      setLoading(true);
      setError('');
      try {
        const session = await loginStaff(staffCode.trim(), pin);
        onLoginSuccess(session);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : t('login.failed'));
      } finally {
        setLoading(false);
      }
      return;
    }
    if (!username.trim() || !password.trim()) {
      setError(t('login.emptyFields'));
      return;
    }
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
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <View style={[styles.hero, { paddingTop: insets.top + spacing.xxl }]}>
        <Image
          source={require('../../assets/logo.png')}
          style={styles.logo}
          resizeMode="contain"
          accessibilityLabel={t('login.title')}
        />
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
            <View style={styles.errorBox} accessibilityLiveRegion="polite">
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}
          <View style={styles.modeTrack}>
            <Pressable
              style={[styles.modeSegment, mode === 'admin' && styles.modeSegmentActive]}
              onPress={() => switchMode('admin')}
              accessibilityRole="button"
              accessibilityState={{ selected: mode === 'admin' }}
            >
              <Text style={[styles.modeText, mode === 'admin' && styles.modeTextActive]}>
                {t('login.adminTab')}
              </Text>
            </Pressable>
            <Pressable
              style={[styles.modeSegment, mode === 'staff' && styles.modeSegmentActive]}
              onPress={() => switchMode('staff')}
              accessibilityRole="button"
              accessibilityState={{ selected: mode === 'staff' }}
            >
              <Text style={[styles.modeText, mode === 'staff' && styles.modeTextActive]}>
                {t('login.staffTab')}
              </Text>
            </Pressable>
          </View>
          {mode === 'admin' ? (
            <>
              <Field
                label={t('login.username')}
                placeholder={t('login.username')}
                value={username}
                onChangeText={setUsername}
                autoCapitalize="none"
                autoCorrect={false}
                spellCheck={false}
                autoComplete="username"
                textContentType="username"
                returnKeyType="next"
                onSubmitEditing={() => passwordRef.current?.focus()}
              />
              <Field
                ref={passwordRef}
                label={t('login.password')}
                placeholder={t('login.password')}
                value={password}
                onChangeText={setPassword}
                secureTextEntry
                autoComplete="password"
                textContentType="password"
                returnKeyType="go"
                onSubmitEditing={handleLogin}
              />
            </>
          ) : (
            <>
              <Field
                label={t('login.staffCode')}
                placeholder={t('login.staffCode')}
                value={staffCode}
                onChangeText={setStaffCode}
                autoCapitalize="characters"
                autoCorrect={false}
                spellCheck={false}
                returnKeyType="next"
                onSubmitEditing={() => passwordRef.current?.focus()}
              />
              <Field
                ref={passwordRef}
                label={t('login.pin')}
                placeholder={t('login.pin')}
                value={pin}
                onChangeText={setPin}
                secureTextEntry
                keyboardType="number-pad"
                maxLength={6}
                returnKeyType="go"
                onSubmitEditing={handleLogin}
              />
            </>
          )}
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
  logo: {
    width: 80,
    height: 80,
    marginBottom: spacing.lg,
    borderRadius: 16,
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
  modeTrack: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 4,
    marginBottom: spacing.lg,
    gap: 4,
  },
  modeSegment: {
    flex: 1,
    minHeight: 40,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modeSegmentActive: { backgroundColor: colors.primaryMuted },
  modeText: { fontSize: 14, fontWeight: '600', color: colors.textSecondary },
  modeTextActive: { color: colors.primary },
  errorBox: {
    backgroundColor: colors.errorSoft,
    borderRadius: 12,
    padding: spacing.md,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: colors.errorSoft,
  },
  errorText: { color: colors.error, fontSize: 14, textAlign: 'center' },
});
