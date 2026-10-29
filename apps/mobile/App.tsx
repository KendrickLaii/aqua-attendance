import React, { useState, useEffect, useCallback } from 'react';

import { NavigationContainer } from '@react-navigation/native';

import { StatusBar } from 'expo-status-bar';

import { ActivityIndicator, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import LoginScreen from './src/screens/LoginScreen';

import AppNavigator from './src/navigation/AppNavigator';

import { fetchSession, getSavedSession, logout, type Session } from './src/services/auth';

import { clearTokens, getToken, SessionExpiredError, setOnUnauthorized } from './src/services/api';

import { setItemAsync } from './src/services/storage';

import { I18nProvider } from './src/i18n/I18nContext';
import { colors } from './src/theme';



function AppRoot() {

  const [session, setSession] = useState<Session | null>(null);

  const [loading, setLoading] = useState(true);



  const checkSession = useCallback(async () => {

    const token = await getToken();

    if (!token) {

      setSession(null);

      return;

    }

    const saved = await getSavedSession();

    try {

      const me = await fetchSession(saved);

      await setItemAsync('userData', JSON.stringify(me));

      setSession(me);

    } catch (error: unknown) {

      if (error instanceof SessionExpiredError) {

        await clearTokens();

        setSession(null);

        return;

      }

      setSession(saved);

    }

  }, []);



  useEffect(() => {

    setOnUnauthorized(() => {

      void clearTokens().then(() => setSession(null));

    });

    return () => setOnUnauthorized(null);

  }, []);



  useEffect(() => {

    checkSession().finally(() => setLoading(false));

  }, [checkSession]);



  async function handleLogout() {

    await logout(session);

    setSession(null);

  }



  function handleLoginSuccess(me: Session) {

    setSession(me);

  }



  if (loading) {

    return (

      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background }}>

        <ActivityIndicator size="large" color={colors.primary} />

      </View>

    );

  }



  return (

    <NavigationContainer>

      <StatusBar style="auto" />

      {session ? (

        <AppNavigator session={session} onLogout={handleLogout} />

      ) : (

        <LoginScreen onLoginSuccess={handleLoginSuccess} />

      )}

    </NavigationContainer>

  );

}



export default function App() {

  return (

    <SafeAreaProvider>

      <I18nProvider>

        <AppRoot />

      </I18nProvider>

    </SafeAreaProvider>

  );

}

