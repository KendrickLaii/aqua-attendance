# Known gaps (docs vs code)

This file tracks intentional MVP limitations and mismatches between **current code** and **desired production behavior**. Use it when planning hardening work.

## Security (high priority)

| Issue | Current behavior | Target |
|-------|------------------|--------|
| Open registration | `POST /api/auth/register` is public; client can set `role` including `superadmin` | Disable in prod or admin-only invite |
| Scan authorization | `POST /api/attendance/scan` requires any Bearer user | Restrict to admin (or dedicated scanner role) |
| List attendance | `GET /api/attendance` requires any Bearer user | Restrict to admin |
| Default secrets | `SECRET_KEY` / `QR_SECRET` have dev placeholders; no startup guard | Fail fast when `ENV=production` |
| Refresh tokens | New pair issued without revoking old refresh token | Optional rotation / token family |

## Web app

| Issue | Notes |
|-------|--------|
| Route guards | Most `/attendance/*` routes rely on `onMounted` redirects, not router `meta` |
| Dual cookies | `attendanceAccessToken` + template `accessToken` can desync |
| Logout | Template `UserProfile` may not clear attendance cookies |
| CSV export | `window.open(url)` does not send `Authorization` header |
| QR preview | Uses third-party `api.qrserver.com` with full token in URL |
| Template bloat | Large AQUA demo tree still in repo; prod nav is trimmed only |

## Mobile app

| Issue | Notes |
|-------|--------|
| Entry point | `package.json` `"main": "expo-router/entry"` but UI lives in `App.tsx`; `app/index.tsx` is a stub |
| Scan tab gating | Code checks `admin \|\| staff`; API roles are `admin \|\| superadmin` — **superadmin may not see Scan** |
| My QR tab | Placeholder screen; products use web **QR Codes** for real tokens |
| Role types | `User.role` typed as `admin \| staff \| student`; does not match API |
| `.env.example` | Was `API_URL`; must be `EXPO_PUBLIC_API_URL` |

## API / data

| Issue | Notes |
|-------|--------|
| Scan race | No row lock on product during debounce window |
| CSV quoting | Commas in names can break CSV rows |
| Migration 003 | Upgrading very old DBs with `user_id` attendance rows may need manual migration |
| Tests | ~12 tests (auth + scan); no full RBAC matrix |

## Documentation

When fixing an item above, update this file and the root README security table.
