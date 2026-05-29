# Known gaps (docs vs code)

This file tracks intentional MVP limitations and mismatches between **current code** and **desired production behavior**. Use it when planning hardening work.

## Web app polish (completed 2026-05)

Review backlog from attendance frontend pass — all **P1–P3** items below are **Done**.

| Priority | Item | Status |
|----------|------|--------|
| P1 | Login `?to=` redirect + `formatApiError` | **Done** |
| P1 | Dashboard today event total via `X-Total-Count` | **Done** |
| P2 | UserProfile — attendance menu (no template 404 links) | **Done** |
| P2 | Web Scanner — sidebar, dashboard CTA, location load error, admin guard | **Done** |
| P2 | Shared `DialogFooter` component | **Done** |
| P3 | Product **Checked in / out** filter (server-side) | **Done** |
| P3 | List pagination — products, users, locations | **Done** |

**Deferred (not in P1–P3):** none from original web polish backlog.

**Suggested next (see tables below):** mobile superadmin Scan tab → dashboard stats accuracy → commit/ship → optional cookie unification / template trim.

## Technical debt (技術債)

Open items — not blocking ship; track here when planning refactors.

| Area | Item | Notes |
|------|------|--------|
| Web | **Dual cookies** | Login mirrors `attendanceAccessToken` → `accessToken` and `attendanceUserData` → `userData` for Materio layout/CASL. Logout clears both (`clearAttendanceSessionCookies`). **Unify:** pick one cookie set; see `login.vue`, `attendanceSession.ts`, `UserProfile.vue`, `guards.ts`. |
| Web | ~~**Dashboard check-in/out stats**~~ | ~~Today event *total* is accurate; check-in/out counts still derived from first 200 events when >200/day.~~ | **Done** — `GET /attendance/stats` aggregate endpoint + dashboard uses it |
| Web | ~~**`locations.vue` split**~~ | ~~`~1.3k lines — candidate for tab/hours/photos sub-components.~~ | **Done** — `LocationCard`, tab components, `locationHours` / `locationPhotos` utils |
| Web | **Template bloat** | Large AQUA demo tree (`pages/apps/`, `dashboards/`, etc.); prod nav trimmed only. |
| Web | ~~**Load errors**~~ | ~~Most pages use fixed strings; API detail via `formatApiError` not used everywhere.~~ | **Done** — load catch blocks use `formatApiError` on all attendance list pages |
| Mobile | **Scan tab + role types** | Gating uses `admin \| staff`; API uses `admin \| superadmin`. Role TS types mismatch. |
| Mobile | **Entry / My QR** | Expo router stub; My QR tab placeholder. |
| API | **Refresh token rotation** | New pair issued without revoking old refresh token. |
| API | **Scan race** | No row lock on product during debounce window. |
| API | **RBAC tests** | ~24 tests; no full permission matrix. |
| Data | **Location photo upload** | v1 URL-only; upload + S3/R2 later — [LOCATIONS.md](./LOCATIONS.md). |

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
| ~~Product attendance filter~~ | ~~Product Management has Type search only; no **Checked in / out** filter~~ | **Done** — `GET /api/products?attendance_status=checked_in|checked_out` + filter on `products.vue` |
| ~~List pagination~~ | ~~Only log had real pagination; products/users/locations capped at 200 rows~~ | **Done** — `X-Total-Count` on list endpoints + prev/next on products, users, locations |
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
| Tests | ~24 tests; no full RBAC matrix |

## Documentation

When fixing an item above, update this file and the root README security table.
