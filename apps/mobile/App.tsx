import React, { useState, useEffect, useCallback } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import { ActivityIndicator, View } from 'react-native';
import LoginScreen from './src/screens/LoginScreen';
import AppNavigator from './src/navigation/AppNavigator';
import { getMe, logout, type User } from './src/services/auth';
import { clearTokens, getToken, setOnUnauthorized } from './src/services/api';
import { setItemAsync } from './src/services/storage';
import { I18nProvider } from './src/i18n/I18nContext';

function AppRoot() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const checkSession = useCallback(async () => {
    const token = await getToken();
    if (!token) {
      setUser(null);
      return;
    }
    try {
      const me = await getMe();
      await setItemAsync('userData', JSON.stringify(me));
      setUser(me);
    } catch {
      await clearTokens();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    setOnUnauthorized(() => {
      void clearTokens().then(() => setUser(null));
    });
    return () => setOnUnauthorized(null);
  }, []);

  useEffect(() => {
    checkSession().finally(() => setLoading(false));
  }, [checkSession]);

  async function handleLogout() {
    await logout();
    setUser(null);
  }

  function handleLoginSuccess(me: User) {
    setUser(me);
  }

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#F4F5FA' }}>
        <ActivityIndicator size="large" color="#160D47" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <StatusBar style="auto" />
      {user ? (
        <AppNavigator user={user} onLogout={handleLogout} />
      ) : (
        <LoginScreen onLoginSuccess={handleLoginSuccess} />
      )}
    </NavigationContainer>
  );
}

export default function App() {
  return (
    <I18nProvider>
      <AppRoot />
    </I18nProvider>
  );
}
