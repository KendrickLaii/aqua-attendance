import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text } from 'react-native';
import QRDisplayScreen from '../screens/QRDisplayScreen';
import ScannerScreen from '../screens/ScannerScreen';
import HistoryScreen from '../screens/HistoryScreen';
import type { User } from '../services/auth';

const Tab = createBottomTabNavigator();

const THEME = { primary: '#160D47' };

interface Props {
  user: User;
  onLogout: () => void;
}

export default function AppNavigator({ user, onLogout }: Props) {
  const canScan = user.role === 'admin' || user.role === 'superadmin';

  return (
    <Tab.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: THEME.primary },
        headerTintColor: '#fff',
        tabBarActiveTintColor: THEME.primary,
        tabBarInactiveTintColor: '#999',
        headerRight: () => (
          <Text onPress={onLogout} style={{ color: '#fff', marginRight: 16, fontSize: 14 }}>
            Logout
          </Text>
        ),
      }}
    >
      <Tab.Screen
        name="MyQR"
        component={QRDisplayScreen}
        options={{
          title: 'My QR',
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 22, color }}>📱</Text>,
        }}
      />
      {canScan && (
        <Tab.Screen
          name="Scanner"
          component={ScannerScreen}
          options={{
            title: 'Scan',
            tabBarIcon: ({ color }) => <Text style={{ fontSize: 22, color }}>📷</Text>,
          }}
        />
      )}
      <Tab.Screen
        name="History"
        component={HistoryScreen}
        options={{
          title: 'History',
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 22, color }}>📋</Text>,
        }}
      />
    </Tab.Navigator>
  );
}
