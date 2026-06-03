import React from 'react';
import { View } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text } from 'react-native';
import HelpScreen from '../screens/QRDisplayScreen';
import ScannerScreen from '../screens/ScannerScreen';
import HistoryScreen from '../screens/HistoryScreen';
import LanguagePicker from '../components/LanguagePicker';
import { useI18n } from '../i18n/I18nContext';
import { canScanAttendance, type User } from '../services/auth';

const Tab = createBottomTabNavigator();

const THEME = { primary: '#160D47' };

interface Props {
  user: User;
  onLogout: () => void;
}

export default function AppNavigator({ user, onLogout }: Props) {
  const { t } = useI18n();
  const showScan = canScanAttendance(user.role);

  return (
    <Tab.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: THEME.primary },
        headerTintColor: '#fff',
        tabBarActiveTintColor: THEME.primary,
        tabBarInactiveTintColor: '#999',
        headerRight: () => (
          <View style={{ flexDirection: 'row', alignItems: 'center', marginRight: 12, gap: 10 }}>
            <LanguagePicker compact />
            <Text onPress={onLogout} style={{ color: '#fff', fontSize: 14, fontWeight: '600' }}>
              {t('common.logout')}
            </Text>
          </View>
        ),
      }}
    >
      <Tab.Screen
        name="Help"
        options={{
          title: t('tabs.help'),
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 22, color }}>📖</Text>,
        }}
      >
        {() => <HelpScreen user={user} />}
      </Tab.Screen>
      {showScan ? (
        <Tab.Screen
          name="Scanner"
          component={ScannerScreen}
          options={{
            title: t('tabs.scan'),
            tabBarIcon: ({ color }) => <Text style={{ fontSize: 22, color }}>📷</Text>,
          }}
        />
      ) : null}
      <Tab.Screen
        name="History"
        component={HistoryScreen}
        options={{
          title: t('tabs.history'),
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 22, color }}>📋</Text>,
        }}
      />
    </Tab.Navigator>
  );
}
