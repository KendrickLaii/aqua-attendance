# Known gaps (docs vs code)

This file tracks intentional MVP limitations and mismatches between **current code** and **desired production behavior**. Use it when planning hardening work.

> **Full project review (2026-06):** see [CODE-REVIEW-2026-06.md](./CODE-REVIEW-2026-06.md) for the detailed pass with severity, code locations, scores, and a checklist. Key open items are summarised in the **Code review 2026-06** section below.

## Code review 2026-06 (full project pass)

New findings from the full backend/web/mobile/deploy audit. All **Open** unless noted.

| Severity | Area | Item | Notes |
|----------|------|------|-------|
| ~~🔴 High~~ | API/data | ~~**`recorded_at` not indexed**~~ | **Done (2026-06)** — migration `013` adds `ix_attendance_events_recorded_at` + composite `ix_attendance_events_product_recorded`; model `__table_args__` kept in sync. |
| ~~🔴 High~~ | Mobile | ~~**Refresh race**~~ | **Done (2026-06)** — `api.ts` `refreshAccessToken()` single-flight: concurrent 401s share one `/auth/refresh`, then retry with the new token. |
| ~~🔴 High~~ | Web | ~~**Refresh race**~~ | **Done (2026-06)** — `attendanceApi.ts` `refreshAttendanceTokens()` wrapped in a shared `attendanceRefreshing` promise (single-flight). |
| 🔴 High | Deploy | **Rate limit in-memory** | `slowapi` default storage is per-process; breaks under multiple API replicas. Use Redis backend if scaling out. |
| 🟡 Med | Deploy | **No API/Web healthcheck** | Only `db` has one; `/api/health` exists but unused. Add healthchecks + Caddy `service_healthy`. |
| 🟡 Med | Deploy | **API image runs as root, no HEALTHCHECK** | Add non-root `USER` + `HEALTHCHECK` in `apps/api/Dockerfile`. |
| 🟡 Med | Web | **Refresh token in non-HttpOnly cookie** | JS-readable; XSS surface from large template tree. Consider backend HttpOnly+Secure+SameSite. |
| 🟡 Med | API | **CSV export not truly streamed** | Loads up to 50k rows into memory before `StreamingResponse`. Yield page-by-page. |
| 🟡 Med | All | **No logging / monitoring / tracing** | No `logging`/`structlog` config, no Sentry, no request IDs. |
| 🟡 Med | API | **Login revokes all refresh tokens** | Single-session only — phone login kills web session. Confirm if intended. |
| 🟡 Med | Tests | **Coverage gaps** | ~53 tests; partial RBAC matrix; no refresh-race test; web/mobile zero tests. |
| 🟢 Low | API | **QR token has no expiry** | By design (printed badge); rotate via version bump. Document lost/leaked flow or add long `exp`. |
| 🟢 Low | Web | **CASL admin == superadmin** | Both get `manage all`; backend enforces correctly, frontend doesn't distinguish. |
| 🟢 Low | Web | **CASL ability lost on hard refresh** | Restored via `watch(immediate)` but timing-fragile; also sync in router guard. |
| 🟢 Low | API | **QR error leaks exception detail** | `detail=f"Invalid QR: {e}"` — return generic message, log details. |
| 🟢 Low | CI | **No mobile CI** | `eas.json` exists; missing GitHub Action for `tsc`/lint/EAS. |
| 🟢 Low | API | **bcrypt 72-byte truncation** | passlib silently truncates; add password max-length validation. |

**Top 3 to do first:** ~~`recorded_at` index~~ **(Done)** → ~~web/mobile refresh single-flight~~ **(Done)** → Redis rate limit (if multi-replica).

**Remaining High:** Redis-backed rate limit — only needed before scaling to multiple API replicas; single-replica in-memory limiting is correct today.

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
|------|------|-------|
| Web | ~~**Dual cookies**~~ | ~~Login mirrors `attendanceAccessToken` → `accessToken` and `attendanceUserData` → `userData` for Materio layout/CASL.~~ | **Done** — unified to canonical `accessToken`/`refreshToken`/`userData` cookies |
| Web | **Template bloat** | Large AQUA demo tree (`pages/apps/`, `dashboards/`, etc.); prod nav trimmed only. **Deferred** — may need demo pages later. |
| Mobile | ~~**History filters**~~ | ~~List capped at 50 rows; no date range UI.~~ | **Done** — date range chips (today/yesterday/7d/30d) + event type filter + pagination |
| Mobile | **My QR tab** | Help placeholder only; product QRs on web. **Deferred** — only needed if app is opened to students. |
| Mobile | **EAS / store build** | `eas.json` present (preview/production APK). Missing: mobile CI workflow — [MOBILE-RELEASE-CHECKLIST.md](./MOBILE-RELEASE-CHECKLIST.md). |
| API | ~~**Scan race**~~ | ~~No row lock on product during debounce window.~~ | **Done** — `SELECT FOR UPDATE` on PostgreSQL (`_resolve_product_for_scan`) |
| API | ~~**python-jose**~~ | ~~Unmaintained, known CVEs.~~ | **Done** — migrated to `PyJWT` 2.10.1 |
| API | ~~**Rate limiting**~~ | ~~No throttling on login/scan.~~ | **Done** — `slowapi` on `/auth/login` (5/min) and `/attendance/scan` (30/min) |
| API | **RBAC tests** | ~53 tests; no full permission matrix. |
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
| Production build | `eas.json` configured (APK build); no mobile CI workflow yet — [MOBILE-RELEASE-CHECKLIST.md](./MOBILE-RELEASE-CHECKLIST.md) |

## API / data

| Issue | Notes |
|-------|--------|
| ~~Scan race~~ | ~~No row lock on product during debounce window~~ | **Done** — `SELECT FOR UPDATE` in `_resolve_product_for_scan` |
| ~~CSV quoting~~ | ~~Commas in names can break CSV rows~~ | **Done** — `csv.writer` in export endpoint |
| Location photos | v1: URL fields only (`icon_url`, `main_photo_url`, `detail_photos`) | **Later** — admin file upload + S3/R2; see [LOCATIONS.md](./LOCATIONS.md) |
| Migration 003 | Upgrading very old DBs with `user_id` attendance rows may need manual migration |
| Tests | ~53 tests; partial RBAC matrix (admin↔superadmin checks); no full permission matrix; no refresh-race test |

## Documentation

When fixing an item above, update this file and the root README security table.

### Docs review scorecard (2026-06)

| 項目 | 評分 | 說明 |
|------|------|------|
| README 清晰度 | 9/10 | Root README 非常詳細,架構圖、seed data、env var 表齊全 |
| 部署文檔 | 8/10 | DEPLOY.md 覆蓋從 Docker 安裝到域名配置的完整流程 |
| API Docs | 7/10 | OpenAPI 自動生成 ✅,但缺少版本策略說明 |
| 操作手冊 | 5/10 | 有 backup/restore 腳本,但沒有故障排查 runbook |

**Docs 待補(對應上方評分扣分點):**

| 項目 | 對應評分 | 建議 |
|------|----------|------|
| API 版本策略 | API Docs 7/10 | 在 DEPLOY/README 說明 API 版本化策略(目前 `version="2.0.0"`,但無 breaking-change / deprecation 政策) |
| 故障排查 runbook | 操作手冊 5/10 | **Done (2026-06)** — 新增 [RUNBOOK.md](./RUNBOOK.md):健康檢查、API/DB 故障、migration、備份還原、認證、磁碟/日誌、TLS、回滾 SOP |
| 可觀測性文檔 | 操作手冊 5/10 | logging/監控導入後(見 Code review #9),補日誌查看與告警設定說明 |
