import * as SecureStore from 'expo-secure-store';
import { apiRequest, setTokens, clearTokens } from './api';

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: 'admin' | 'staff' | 'student';
  is_active: boolean;
}

export async function login(username: string, password: string): Promise<User> {
  const tokens = await apiRequest<{ access_token: string; refresh_token: string }>(
    '/auth/login',
    { method: 'POST', body: JSON.stringify({ username, password }) },
  );
  await setTokens(tokens.access_token, tokens.refresh_token);
  const me = await apiRequest<User>('/auth/me');
  await SecureStore.setItemAsync('userData', JSON.stringify(me));
  return me;
}

export async function getMe(): Promise<User> {
  return apiRequest<User>('/auth/me');
}

export async function logout(): Promise<void> {
  await clearTokens();
}

export async function getSavedUser(): Promise<User | null> {
  const raw = await SecureStore.getItemAsync('userData');
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}
