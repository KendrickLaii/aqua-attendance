import { apiRequest, setTokens, clearTokens } from './api';
import { deleteItemAsync, getItemAsync, setItemAsync } from './storage';

export type UserRole = 'admin' | 'superadmin';

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
}

export function canScanAttendance(role: string): boolean {
  return role === 'admin' || role === 'superadmin';
}

export async function login(username: string, password: string): Promise<User> {
  const tokens = await apiRequest<{ access_token: string; refresh_token: string }>(
    '/auth/login',
    { method: 'POST', body: JSON.stringify({ username, password }) },
  );
  await setTokens(tokens.access_token, tokens.refresh_token);
  const me = await apiRequest<User>('/auth/me');
  await setItemAsync('userData', JSON.stringify(me));
  return me;
}

export async function getMe(): Promise<User> {
  return apiRequest<User>('/auth/me');
}

export async function logout(): Promise<void> {
  const refreshToken = await getItemAsync('refreshToken');
  if (refreshToken) {
    try {
      await apiRequest('/auth/logout', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch {
      // still clear local session if API unreachable or token already invalid
    }
  }
  await clearTokens();
}

export async function getSavedUser(): Promise<User | null> {
  const raw = await getItemAsync('userData');
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}
