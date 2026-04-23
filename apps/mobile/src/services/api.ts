import * as SecureStore from 'expo-secure-store';

const API_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000/api';

async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync('accessToken');
}

async function setTokens(access: string, refresh: string): Promise<void> {
  await SecureStore.setItemAsync('accessToken', access);
  await SecureStore.setItemAsync('refreshToken', refresh);
}

async function clearTokens(): Promise<void> {
  await SecureStore.deleteItemAsync('accessToken');
  await SecureStore.deleteItemAsync('refreshToken');
  await SecureStore.deleteItemAsync('userData');
}

async function apiRequest<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    const refreshToken = await SecureStore.getItemAsync('refreshToken');
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
          headers['Authorization'] = `Bearer ${data.access_token}`;
          const retry = await fetch(`${API_URL}${path}`, { ...options, headers });
          if (!retry.ok) throw new Error(await retry.text());
          return retry.json();
        }
      } catch {
        await clearTokens();
      }
    }
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export { apiRequest, setTokens, clearTokens, getToken, API_URL };
