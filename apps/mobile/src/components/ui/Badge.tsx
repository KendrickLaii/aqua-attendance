import React from 'react';
import { StyleSheet, Text, View, ViewStyle } from 'react-native';
import { colors, radius, spacing } from '../../theme';

type Tone = 'primary' | 'success' | 'warning' | 'info' | 'neutral';

interface Props {
  label: string;
  tone?: Tone;
  style?: ViewStyle;
}

const toneStyles: Record<Tone, { bg: string; text: string }> = {
  primary: { bg: colors.primaryMuted, text: colors.primary },
  success: { bg: colors.checkInSoft, text: colors.checkIn },
  warning: { bg: colors.checkOutSoft, text: colors.checkOut },
  info: { bg: colors.infoSoft, text: colors.info },
  neutral: { bg: colors.background, text: colors.textSecondary },
};

export default function Badge({ label, tone = 'neutral', style }: Props) {
  const t = toneStyles[tone];
  return (
    <View style={[styles.badge, { backgroundColor: t.bg }, style]}>
      <Text style={[styles.text, { color: t.text }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderRadius: radius.pill,
    alignSelf: 'flex-start',
  },
  text: { fontSize: 12, fontWeight: '600' },
});
