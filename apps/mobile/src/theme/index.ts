import { Platform, TextStyle, ViewStyle } from 'react-native';

export const colors = {
  primary: '#160D47',
  primarySoft: '#2A2068',
  primaryMuted: '#EEEDF8',
  background: '#F5F4F8',
  surface: '#FFFFFF',
  border: '#E4E2EB',
  borderLight: '#F0EEF5',
  text: '#12121F',
  textSecondary: '#4E4E63',
  textMuted: '#88889C',
  checkIn: '#157A52',
  checkInSoft: '#E8F5EF',
  checkOut: '#B85C14',
  checkOutSoft: '#FFF4E8',
  info: '#3B6FD9',
  infoSoft: '#EDF3FC',
  error: '#B42318',
  errorSoft: '#FEF3F2',
  headerText: '#FFFFFF',
  tabInactive: '#9A98A8',
  cameraOverlay: 'rgba(18, 14, 40, 0.72)',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
};

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 22,
  pill: 999,
};

export const typography = {
  hero: { fontSize: 26, fontWeight: '700' as const, letterSpacing: -0.6, color: colors.text },
  title: { fontSize: 20, fontWeight: '700' as const, letterSpacing: -0.3, color: colors.text },
  subtitle: { fontSize: 15, fontWeight: '400' as const, lineHeight: 22, color: colors.textSecondary },
  label: {
    fontSize: 12,
    fontWeight: '600' as const,
    letterSpacing: 0.6,
    textTransform: 'uppercase' as const,
    color: colors.textMuted,
  },
  body: { fontSize: 15, fontWeight: '400' as const, lineHeight: 22, color: colors.textSecondary },
  bodyStrong: { fontSize: 15, fontWeight: '600' as const, color: colors.text },
  caption: { fontSize: 13, fontWeight: '400' as const, color: colors.textMuted },
  button: { fontSize: 16, fontWeight: '600' as const, letterSpacing: 0.2 },
};

export const shadow = {
  card: Platform.select<ViewStyle>({
    ios: {
      shadowColor: '#160D47',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.06,
      shadowRadius: 12,
    },
    android: { elevation: 3 },
    default: {},
  }),
  soft: Platform.select<ViewStyle>({
    ios: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.04,
      shadowRadius: 8,
    },
    android: { elevation: 2 },
    default: {},
  }),
};

export const layout = {
  screenPadding: spacing.xxl,
  cardPadding: spacing.xxl,
  maxContentWidth: 440,
};

/** @deprecated Use `colors` — kept for gradual migration */
export const THEME = {
  primary: colors.primary,
  bg: colors.background,
  success: colors.checkIn,
  warning: colors.checkOut,
  error: colors.error,
};

export function hitSlop(size = 8) {
  return { top: size, bottom: size, left: size, right: size };
}

export type TextVariant = keyof typeof typography;

export function textStyle(variant: TextVariant): TextStyle {
  return typography[variant];
}
