import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useI18n, useLocaleOptions } from '../i18n/I18nContext';
import type { Locale } from '../i18n/types';

const THEME = { primary: '#160D47' };

interface Props {
  /** Smaller chips for navigation header */
  compact?: boolean;
}

export default function LanguagePicker({ compact }: Props) {
  const { locale, setLocale, t } = useI18n();
  const options = useLocaleOptions();

  return (
    <View style={[styles.row, compact && styles.rowCompact]}>
      {!compact ? <Text style={styles.label}>{t('common.language')}</Text> : null}
      <View style={styles.chips}>
        {options.map((opt) => (
          <TouchableOpacity
            key={opt.code}
            style={[
              styles.chip,
              compact && styles.chipCompact,
              locale === opt.code && styles.chipActive,
            ]}
            onPress={() => setLocale(opt.code as Locale)}
            accessibilityRole="button"
            accessibilityState={{ selected: locale === opt.code }}
          >
            <Text
              style={[
                styles.chipText,
                compact && styles.chipTextCompact,
                locale === opt.code && styles.chipTextActive,
              ]}
            >
              {opt.code === 'en' ? 'EN' : '繁中'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { marginBottom: 16 },
  rowCompact: { marginBottom: 0 },
  label: { fontSize: 12, color: '#888', marginBottom: 8, fontWeight: '600' },
  chips: { flexDirection: 'row', gap: 8 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#ccc',
    backgroundColor: '#fff',
  },
  chipCompact: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderColor: 'rgba(255,255,255,0.45)',
  },
  chipActive: {
    backgroundColor: THEME.primary,
    borderColor: THEME.primary,
  },
  chipText: { fontSize: 14, fontWeight: '600', color: THEME.primary },
  chipTextCompact: { fontSize: 12, color: '#fff' },
  chipTextActive: { color: '#fff' },
});
