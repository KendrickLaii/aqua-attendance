import React from 'react';
import { StyleSheet } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import HelpScreen from '../screens/QRDisplayScreen';
import ScannerScreen from '../screens/ScannerScreen';
import HistoryScreen from '../screens/HistoryScreen';
import { useI18n } from '../i18n/I18nContext';
import { canScanAttendance, type User } from '../services/auth';
import { colors, spacing } from '../theme';

const Tab = createBottomTabNavigator();
const TAB_BAR_CONTENT_HEIGHT = 62;

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
        tabBarLabelStyle: styles.tabLabel,
        tabBarStyle: {
          height: TAB_BAR_CONTENT_HEIGHT + tabBarBottom,
          paddingTop: spacing.xs,
          paddingBottom: tabBarBottom,
        },
      }}
    >
      <Tab.Screen
        name="Help"
        options={{
          title: t('tabs.help'),
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="information-circle-outline" size={size} color={color} />
          ),
        }}
      >
        {() => <HelpScreen user={user} onLogout={onLogout} />}
      </Tab.Screen>
      {showScan ? (
        <Tab.Screen
          name="Scanner"
          component={ScannerScreen}
          options={{
            title: t('tabs.scan'),
            tabBarIcon: ({ color, size }) => (
              <Ionicons name="qr-code-outline" size={size} color={color} />
            ),
          }}
        />
      ) : null}
      <Tab.Screen
        name="History"
        component={HistoryScreen}
        options={{
          title: t('tabs.history'),
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="time-outline" size={size} color={color} />
          ),
        }}
      />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  tabLabel: {
    fontSize: 12,
    fontWeight: '600',
    textAlign: 'center',
  },
});
