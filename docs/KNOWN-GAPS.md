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
| P3 | Dialog unification — Confirm / Form / Info shells | **Done** |
| Post-P3 | Dashboard check-in/out stats (`GET /attendance/stats`) | **Done** |
| Post-P3 | `locations.vue` component split | **Done** |
| Post-P3 | Location create — `name_zh` default from English | **Done** |
| Post-P3 | Load errors — `formatApiError` on all attendance list pages | **Done** |

**Deferred (not in P1–P3):** none from original web polish backlog.

**Ship:** [RELEASE-2026-05.md](./RELEASE-2026-05.md) — pre/post deploy checklist for this release.

**Suggested next (see tables below):** mobile Phase 3 (history filters) → optional cookie unification / template trim.

## Technical debt (技術債)

Open items — not blocking ship; track here when planning refactors.

| Area | Item | Notes |
|------|------|--------|
| Web | **Dual cookies** | Login mirrors `attendanceAccessToken` → `accessToken` and `attendanceUserData` → `userData` for Materio layout/CASL. Logout clears both (`clearAttendanceSessionCookies`). **Unify:** pick one cookie set; see `login.vue`, `attendanceSession.ts`, `UserProfile.vue`, `guards.ts`. |
| Web | **Template bloat** | Large AQUA demo tree (`pages/apps/`, `dashboards/`, etc.); prod nav trimmed only. |
| Mobile | **History filters** | List capped at 50 rows; no date range UI. See [MOBILE-SPRINT.md](./MOBILE-SPRINT.md) M3.1. |
| Mobile | **My QR tab** | Help placeholder only; product QRs on web. |
| Mobile | **EAS / store build** | No `eas.json` in repo yet — [MOBILE-RELEASE-CHECKLIST.md](./MOBILE-RELEASE-CHECKLIST.md). |
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
| ~~Refresh tokens~~ | ~~No rotation~~ | **Done** — DB-backed rotation + logout revoke |

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
| ~~Dashboard check-in/out stats~~ | ~~Counts capped at first 200 events/day~~ | **Done** — `GET /api/attendance/stats` |
| ~~Dialog unification~~ | ~~Mixed VDialog patterns~~ | **Done** — `AttendanceConfirmDialog`, `AttendanceFormDialog`, `AttendanceInfoDialog` |
| ~~`locations.vue` split~~ | ~~1.3k line monolith~~ | **Done** — `components/attendance/locations/*` |
| Template bloat | Large AQUA demo tree still in repo; prod nav is trimmed only |

## Mobile app

| Issue | Notes |
|-------|--------|
| ~~Entry point~~ | ~~expo-router entry~~ | **Done** — `expo/AppEntry.js` → `App.tsx` |
| ~~Scan tab gating~~ | ~~staff role~~ | **Done** — `admin \| superadmin` |
| ~~Logout~~ | ~~local only~~ | **Done** — `POST /auth/logout` |
| ~~Scan location~~ | ~~missing~~ | **Done** — location picker + `location_id` (2026-06) |
| My QR tab | Help placeholder; product QRs on web **QR Codes** |
| History | No date filter / pagination UI — Phase 3 in [MOBILE-SPRINT.md](./MOBILE-SPRINT.md) |
| Production build | EAS not configured — [MOBILE-RELEASE-CHECKLIST.md](./MOBILE-RELEASE-CHECKLIST.md) |

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
