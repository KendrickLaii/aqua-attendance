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

export interface StaffMe {
  id: string;
  code: string;
  full_name: string;
  can_take_attendance: boolean;
}

export type Session =
  | { kind: 'admin'; user: User }
  | { kind: 'staff'; staff: StaffMe };

export function canScanAttendance(role: string): boolean {
  return role === 'admin' || role === 'superadmin';
}

export async function login(username: string, password: string): Promise<Session> {
  const tokens = await apiRequest<{ access_token: string; refresh_token: string }>(
    '/auth/login',
    { method: 'POST', body: JSON.stringify({ username, password }) },
  );
  await setTokens(tokens.access_token, tokens.refresh_token);
  const me = await apiRequest<User>('/auth/me');
  const session: Session = { kind: 'admin', user: me };
  await setItemAsync('userData', JSON.stringify(session));
  return session;
}

export async function loginStaff(code: string, pin: string): Promise<Session> {
  const res = await apiRequest<{ access_token: string; unit: StaffMe }>(
    '/staff-shifts/login',
    { method: 'POST', body: JSON.stringify({ code, pin }) },
  );
  // Staff tokens are 12h, no refresh — drop any stale admin refresh token.
  await setItemAsync('accessToken', res.access_token);
  await deleteItemAsync('refreshToken');
  const session: Session = { kind: 'staff', staff: res.unit };
  await setItemAsync('userData', JSON.stringify(session));
  return session;
}

export async function fetchSession(saved: Session | null): Promise<Session> {
  if (saved?.kind === 'staff') {
    const staff = await apiRequest<StaffMe>('/staff-shifts/me');
    return { kind: 'staff', staff };
  }
  const user = await apiRequest<User>('/auth/me');
  return { kind: 'admin', user };
}

export async function logout(session: Session | null): Promise<void> {
  if (session?.kind === 'staff') {
    try {
      await apiRequest('/staff-shifts/logout', { method: 'POST' });
    } catch {
      // still clear local session if API unreachable or token already invalid
    }
  } else {
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
  }
  await clearTokens();
}

export async function getSavedSession(): Promise<Session | null> {
  const raw = await getItemAsync('userData');
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Session | User;
    // Legacy saved sessions stored the bare admin User object (no `kind`).
    if (parsed && typeof parsed === 'object' && 'kind' in parsed) {
      return parsed as Session;
    }
    return { kind: 'admin', user: parsed as User };
  } catch {
    return null;
  }
}
