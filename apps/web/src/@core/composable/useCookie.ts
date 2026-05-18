// Ported from [Nuxt](https://github.com/nuxt/nuxt/blob/main/packages/nuxt/src/app/composables/cookie.ts)

import type { CookieParseOptions, CookieSerializeOptions } from 'cookie-es'
import { parse, serialize } from 'cookie-es'
import { destr } from 'destr'

type _CookieOptions = Omit<CookieSerializeOptions & CookieParseOptions, 'decode' | 'encode'>

export interface CookieOptions<T = any> extends _CookieOptions {
  decode?(value: string): T
  encode?(value: T): string
  default?: () => T | Ref<T>
  watch?: boolean | 'shallow'
}

export type CookieRef<T> = Ref<T>

const CookieDefaults: CookieOptions<any> = {
  path: '/',
  watch: true,
  decode: val => destr(decodeURIComponent(val)),
  encode: val => encodeURIComponent(typeof val === 'string' ? val : JSON.stringify(val)),
}

export const useCookie = <T = string | null | undefined>(name: string, _opts?: CookieOptions<T>): CookieRef<T> => {
  const opts = { ...CookieDefaults, ..._opts || {} }
  const cookies = parse(document.cookie, opts)

  const cookie = ref<T | undefined>(cookies[name] as any ?? opts.default?.())

  // ℹ️ Flush sync so `document.cookie` is updated immediately when `.value` is set.
  // Otherwise, code that calls `useCookie(name)` right after setting will create a
  // new ref that re-reads the (still stale) `document.cookie`, causing race bugs
  // such as the first login attempt failing because the Bearer token isn't visible
  // to the next request's `onRequest` hook.
  watch(cookie, () => {
    document.cookie = serializeCookie(name, cookie.value, opts)
  }, { flush: 'sync' })

  return cookie as CookieRef<T>
}

function serializeCookie(name: string, value: any, opts: CookieSerializeOptions = {}) {
  if (value === null || value === undefined)
    return serialize(name, value, { ...opts, maxAge: -1 })

  return serialize(name, value, { ...opts, maxAge: 60 * 60 * 24 * 30 })
}
