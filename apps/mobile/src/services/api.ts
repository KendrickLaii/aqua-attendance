import { Platform } from 'react-native';
import { deleteItemAsync, getItemAsync, setItemAsync } from './storage';

const API_URL = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000/api').trim();

function networkErrorHint(): string {
  const u = API_URL.toLowerCase();
  if (u.includes('localhost') || u.includes('127.0.0.1') || u.includes('10.0.2.2')) {
    return Platform.OS === 'web'
      ? 'Browser: set EXPO_PUBLIC_API_URL=http://localhost:8000/api in apps/mobile/.env, then npx expo start -c'
      : 'Use your PC LAN IP in .env (ipconfig), API: uvicorn --host 0.0.0.0, then npx expo start -c';
  }
  if (u.startsWith('http://')) {
    return 'Cloud API uses HTTP. Use a rebuilt APK (EAS build), not Expo Go. On phone, open the API URL in the browser to test Wi‑Fi.';
  }
  return 'Check phone internet, API URL in .env / eas.json, then rebuild or npx expo start -c';
}

const AUTH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout'];

let onUnauthorized: (() => void) | null = null;

/** Register handler when refresh fails (e.g. return user to login). */
export function setOnUnauthorized(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

function isAuthPath(path: string): boolean {
  return AUTH_PATHS.some((p) => path.startsWith(p));
}

async function getToken(): Promise<string | null> {
  return getItemAsync('accessToken');
}

async function setTokens(access: string, refresh: string): Promise<void> {
  await setItemAsync('accessToken', access);
  await setItemAsync('refreshToken', refresh);
}

async function clearTokens(): Promise<void> {
  await deleteItemAsync('accessToken');
  await deleteItemAsync('refreshToken');
  await deleteItemAsync('userData');
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function parseErrorBody(res: Response): Promise<{ message: string; detail: unknown }> {
  const err = await res.json().catch(() => null);
  if (!err) {
    return { message: res.statusText || 'Request failed', detail: undefined };
  }
  const detail = err.detail;
  if (typeof detail === 'string') return { message: detail, detail };
  if (Array.isArray(detail)) {
    return {
      message: detail.map((x: { msg?: string }) => x.msg || String(x)).join('; '),
      detail,
    };
  }
  if (typeof detail === 'object' && detail !== null) {
    const obj = detail as { message?: string };
    if (typeof obj.message === 'string') return { message: obj.message, detail };
  }
  return { message: 'Request failed', detail };
}

async function apiRequest<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch {
    throw new Error(`Cannot reach API at ${API_URL}. ${networkErrorHint()}`);
  }

  if (res.status === 401 && !isAuthPath(path)) {
    const refreshToken = await getItemAsync('refreshToken');
    if (refreshToken) {
      try {
        const refreshRes = await fetch(`${API_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (refreshRes.ok) {
          const data = await refreshRes.json();
          await setTokens(data.access_token, data.refresh_token);
          headers.Authorization = `Bearer ${data.access_token}`;
          const retry = await fetch(`${API_URL}${path}`, { ...options, headers });
          if (!retry.ok) {
            const parsed = await parseErrorBody(retry);
            throw new ApiError(`HTTP ${retry.status}: ${parsed.message}`, retry.status, parsed.detail);
          }
          if (retry.status === 204) return undefined as T;
          return retry.json();
        }
      } catch {
        await clearTokens();
      }
    }
    onUnauthorized?.();
    throw new Error('Session expired. Please sign in again.');
  }

  if (!res.ok) {
    const parsed = await parseErrorBody(res);
    throw new ApiError(`HTTP ${res.status}: ${parsed.message}`, res.status, parsed.detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export { apiRequest, setTokens, clearTokens, getToken, API_URL };
