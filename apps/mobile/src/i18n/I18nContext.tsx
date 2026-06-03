import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { ActivityIndicator, View } from 'react-native';
import {
  dateLocaleTag,
  loadStoredLocale,
  persistLocale,
  t as translateKey,
} from './index';
import type { Locale } from './types';
import { LOCALES } from './types';

interface I18nContextValue {
  locale: Locale;
  dateLocale: string;
  setLocale: (locale: Locale) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale | null>(null);

  useEffect(() => {
    loadStoredLocale().then(setLocaleState);
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    void persistLocale(next);
  }, []);

  const value = useMemo<I18nContextValue | null>(() => {
    if (!locale) return null;
    const dateLocale = dateLocaleTag(locale);
    return {
      locale,
      dateLocale,
      setLocale,
      t: (key, params) => translateKey(locale, key, params),
    };
  }, [locale, setLocale]);

  if (!value) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#F5F4F8' }}>
        <ActivityIndicator size="large" color="#160D47" />
      </View>
    );
  }

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within I18nProvider');
  return ctx;
}

export function useLocaleOptions() {
  return LOCALES.map((code) => ({
    code,
    label: code === 'en' ? 'English' : '繁體中文',
  }));
}
