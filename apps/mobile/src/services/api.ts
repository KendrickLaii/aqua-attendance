import { Platform } from 'react-native';
import { deleteItemAsync, getItemAsync, setItemAsync } from './storage';

const API_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000/api';

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

async function parseErrorBody(res: Response): Promise<string> {
  const err = await res.json().catch(() => null);
  if (!err) return res.statusText || 'Request failed';
  const detail = err.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail))
    return detail.map((x: { msg?: string }) => x.msg || String(x)).join('; ');
  return 'Request failed';
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
    const hint =
      Platform.OS === 'web'
        ? 'Browser: set EXPO_PUBLIC_API_URL=http://localhost:8000/api in apps/mobile/.env, then npx expo start -c'
        : 'Phone: start API with --host 0.0.0.0 and use your PC LAN IP in .env (ipconfig)';
    throw new Error(`Cannot reach API at ${API_URL}. ${hint}`);
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
          if (!retry.ok) throw new Error(await parseErrorBody(retry));
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
    const detail = await parseErrorBody(res);
    throw new Error(`HTTP ${res.status}: ${detail}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export { apiRequest, setTokens, clearTokens, getToken, API_URL };
