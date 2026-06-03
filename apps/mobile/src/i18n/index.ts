import * as Localization from 'expo-localization';
import { getItemAsync, setItemAsync } from '../services/storage';
import { en, type TranslationMessages } from './locales/en';
import { zhHant } from './locales/zh-Hant';
import { translate } from './translate';
import type { Locale } from './types';
import { LOCALE_STORAGE_KEY, LOCALES } from './types';

export type { Locale } from './types';
export { LOCALES, LOCALE_STORAGE_KEY } from './types';

const catalogs: Record<Locale, TranslationMessages> = {
  en,
  'zh-Hant': zhHant,
};

export function resolveDeviceLocale(): Locale {
  const tag = Localization.getLocales()[0]?.languageTag ?? 'en';
  return tag.toLowerCase().startsWith('zh') ? 'zh-Hant' : 'en';
}

export function dateLocaleTag(locale: Locale): string {
  return locale === 'zh-Hant' ? 'zh-HK' : 'en-US';
}

export async function loadStoredLocale(): Promise<Locale> {
  const stored = await getItemAsync(LOCALE_STORAGE_KEY);
  if (stored === 'en' || stored === 'zh-Hant') return stored;
  return resolveDeviceLocale();
}

export async function persistLocale(locale: Locale): Promise<void> {
  await setItemAsync(LOCALE_STORAGE_KEY, locale);
}

export function getMessages(locale: Locale): TranslationMessages {
  return catalogs[locale];
}

export function t(
  locale: Locale,
  key: string,
  params?: Record<string, string | number>,
): string {
  return translate(getMessages(locale), key, params);
}
