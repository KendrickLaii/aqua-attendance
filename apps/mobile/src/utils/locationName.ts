export type LocationNameLocale = 'en' | 'zh-Hant';

export interface LocationNameParts {
  id?: string | null;
  code?: string | null;
  name_en?: string | null;
  name_zh?: string | null;
}

export function locationDisplayName(
  loc: LocationNameParts,
  locale: LocationNameLocale = 'en',
): string {
  const zh = loc.name_zh?.trim() || '';
  const en = loc.name_en?.trim() || '';
  const preferred = locale === 'zh-Hant' ? zh || en : en || zh;
  return preferred || loc.code || loc.id || '';
}
