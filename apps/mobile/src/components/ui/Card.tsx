import React from 'react';
import { StyleSheet, View, ViewStyle } from 'react-native';
import { colors, layout, radius, shadow, spacing } from '../../theme';

interface Props {
  children: React.ReactNode;
  style?: ViewStyle;
  padded?: boolean;
}

export default function Card({ children, style, padded = true }: Props) {
  return (
    <View style={[styles.card, padded && styles.padded, style]}>{children}</View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    maxWidth: layout.maxContentWidth,
    alignSelf: 'stretch',
    ...shadow.card,
  },
  padded: { padding: layout.cardPadding },
});
