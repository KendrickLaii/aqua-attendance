import type { TranslationMessages } from './locales/en';

export function translate(
  messages: TranslationMessages,
  key: string,
  params?: Record<string, string | number>,
): string {
  const parts = key.split('.');
  let node: unknown = messages;
  for (const part of parts) {
    if (node && typeof node === 'object' && part in (node as object)) {
      node = (node as Record<string, unknown>)[part];
    } else {
      return key;
    }
  }
  if (typeof node !== 'string') return key;
  let text = node;
  if (params) {
    for (const [name, value] of Object.entries(params)) {
      text = text.replaceAll(`{{${name}}}`, String(value));
    }
  }
  return text;
}
