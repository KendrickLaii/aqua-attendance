import React from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import HelpScreen from '../screens/QRDisplayScreen';
import ScannerScreen from '../screens/ScannerScreen';
import HistoryScreen from '../screens/HistoryScreen';
import { useI18n } from '../i18n/I18nContext';
import { canScanAttendance, type User } from '../services/auth';
import { colors, hitSlop, spacing } from '../theme';

const Tab = createBottomTabNavigator();

/** Label area height (safe inset added separately) */
const TAB_BAR_CONTENT_HEIGHT = 58;

interface Props {
  user: User;
  onLogout: () => void;
}

export default function AppNavigator({ user, onLogout }: Props) {
  const { t } = useI18n();
  const insets = useSafeAreaInsets();
  const showScan = canScanAttendance(user.role);
  const tabBarBottom = Math.max(insets.bottom, spacing.md);

  return (
    <Tab.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.primary },
        headerTintColor: colors.headerText,
        headerTitleStyle: { fontWeight: '700', fontSize: 17 },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.tabInactive,
        tabBarIcon: () => null,
        tabBarIconStyle: styles.tabIconHidden,
        tabBarLabelStyle: styles.tabLabel,
        tabBarItemStyle: styles.tabItem,
        tabBarStyle: {
          height: TAB_BAR_CONTENT_HEIGHT + tabBarBottom,
          paddingTop: 0,
          paddingBottom: tabBarBottom,
          justifyContent: 'center',
        },
        headerRight: () => (
          <Pressable
            onPress={onLogout}
            hitSlop={hitSlop(12)}
            style={styles.logoutBtn}
            accessibilityRole="button"
            accessibilityLabel={t('common.logout')}
          >
            <Text style={styles.logoutText}>{t('common.logout')}</Text>
          </Pressable>
        ),
      }}
    >
      <Tab.Screen name="Help" options={{ title: t('tabs.help') }}>
        {() => <HelpScreen user={user} />}
      </Tab.Screen>
      {showScan ? (
        <Tab.Screen
          name="Scanner"
          component={ScannerScreen}
          options={{ title: t('tabs.scan') }}
        />
      ) : null}
      <Tab.Screen
        name="History"
        component={HistoryScreen}
        options={{ title: t('tabs.history') }}
      />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  tabIconHidden: {
    height: 0,
    width: 0,
    margin: 0,
  },
  tabItem: {
    height: TAB_BAR_CONTENT_HEIGHT,
    justifyContent: 'center',
    alignItems: 'center',
  },
  tabLabel: {
    fontSize: 14,
    fontWeight: '600',
    textAlign: 'center',
    marginTop: 0,
    marginBottom: 0,
  },
  logoutBtn: {
    marginRight: spacing.lg,
    paddingVertical: spacing.sm,
  },
  logoutText: {
    color: colors.headerText,
    fontSize: 15,
    fontWeight: '600',
  },
});
