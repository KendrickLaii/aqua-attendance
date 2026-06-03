import React from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { useI18n, useLocaleOptions } from '../i18n/I18nContext';
import type { Locale } from '../i18n/types';
import { colors, radius, spacing, typography } from '../theme';

interface Props {
  compact?: boolean;
}

export default function LanguagePicker({ compact }: Props) {
  const { locale, setLocale, t } = useI18n();
  const options = useLocaleOptions();

  return (
    <View style={[styles.row, compact && styles.rowCompact]}>
      {!compact ? <Text style={styles.label}>{t('common.language')}</Text> : null}
      <View style={[styles.track, compact && styles.trackCompact]}>
        {options.map((opt) => {
          const active = locale === opt.code;
          return (
            <Pressable
              key={opt.code}
              style={[styles.segment, active && (compact ? styles.segmentActiveCompact : styles.segmentActive)]}
              onPress={() => setLocale(opt.code as Locale)}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
            >
              <Text
                style={[
                  styles.segmentText,
                  compact && styles.segmentTextCompact,
                  active && styles.segmentTextActive,
                ]}
              >
                {opt.code === 'en' ? 'EN' : '繁中'}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { marginBottom: spacing.xl },
  rowCompact: { marginBottom: 0 },
  label: { ...typography.label, marginBottom: spacing.sm },
  track: {
    flexDirection: 'row',
    backgroundColor: colors.background,
    borderRadius: radius.md,
    padding: 3,
    borderWidth: 1,
    borderColor: colors.border,
  },
  trackCompact: {
    backgroundColor: 'rgba(255,255,255,0.12)',
    borderColor: 'rgba(255,255,255,0.2)',
  },
  segment: {
    flex: 1,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm + 2,
    alignItems: 'center',
  },
  segmentActive: {
    backgroundColor: colors.surface,
    ...{
      shadowColor: '#160D47',
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.08,
      shadowRadius: 3,
      elevation: 2,
    },
  },
  segmentActiveCompact: { backgroundColor: 'rgba(255,255,255,0.95)' },
  segmentText: { fontSize: 14, fontWeight: '600', color: colors.textMuted },
  segmentTextCompact: { color: 'rgba(255,255,255,0.75)' },
  segmentTextActive: { color: colors.primary },
});
