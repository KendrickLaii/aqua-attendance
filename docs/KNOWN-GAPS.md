# Known gaps (docs vs code)

This file tracks intentional MVP limitations and mismatches between **current code** and **desired production behavior**. Use it when planning hardening work.

## Security (high priority)

| Issue | Current behavior | Target |
|-------|------------------|--------|
| ~~Open registration~~ | ~~Public `/api/auth/register`~~ | **Done** — returns 403; use User Management / `POST /api/users` |
| ~~Scan authorization~~ | ~~Any Bearer user~~ | **Done** — `AdminOnly` |
| ~~List attendance~~ | ~~Any Bearer user~~ | **Done** — `AdminOnly` |
| ~~Default secrets~~ | ~~No startup guard~~ | **Done** — API fails fast when `ENV=production` and keys are weak/placeholder |
| Refresh tokens | New pair issued without revoking old refresh token | Optional rotation / token family |

## Web app

| Issue | Notes |
|-------|--------|
| ~~Route guards~~ | ~~`onMounted` only~~ | **Done** — `/attendance/*` guarded in `guards.ts` |
| Dual cookies | `attendanceAccessToken` + template `accessToken` still mirrored on login | Logout clears both; could unify to one cookie later |
| ~~Logout~~ | ~~Template logout missed attendance cookies~~ | **Done** — `UserProfile` + store clear all session cookies |
| ~~CSV export~~ | ~~`window.open` without auth~~ | **Done** — `exportAttendanceCSV` blob download with Bearer |
| ~~QR preview~~ | ~~`api.qrserver.com` leaked token~~ | **Done** — local `qrcode` data URL in browser |
| Product attendance filter | Product Management has Type search only; no **Checked in / out** filter | **Later** — add `attendance_status` (and optional `has_scans`) to `GET /api/products`, then a filter on `products.vue`. Use Dashboard for “who is here now”; client-only filter on 200 rows is not accurate enough |
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
| ~~CSV quoting~~ | ~~Commas in names can break CSV rows~~ | **Done** — `csv.writer` in export endpoint |
| Location photos | v1: URL fields only (`icon_url`, `main_photo_url`, `detail_photos`) | **Later** — admin file upload + S3/R2; see [LOCATIONS.md](./LOCATIONS.md) |
| Migration 003 | Upgrading very old DBs with `user_id` attendance rows may need manual migration |
| Tests | ~21 tests; no full RBAC matrix |

## Documentation

When fixing an item above, update this file and the root README security table.
