# Mobile App Sprint Plan

Attendance Expo app (`apps/mobile`). Tracks work by phase; update status when items ship.

**Last updated:** 2026-06-03

---

## Phase 1 — 基礎修復 ✅ Done

| ID | Task | Screen / file | API | Status |
|----|------|---------------|-----|--------|
| M1.1 | Scan tab: `admin` + `superadmin` (not `staff`) | `AppNavigator.tsx` | `GET /auth/me` → `role` | ✅ |
| M1.2 | `User.role` type = `admin \| superadmin` | `services/auth.ts` | — | ✅ |
| M1.3 | Logout calls `POST /auth/logout` | `services/auth.ts`, `App.tsx` | `/auth/logout` | ✅ |
| M1.4 | Entry point `expo/AppEntry.js` → `App.tsx` | `package.json` | — | ✅ |
| M1.5 | 401 refresh; skip refresh on auth paths | `services/api.ts` | `/auth/refresh` | ✅ |
| M1.6 | FastAPI error `detail` parsing | `services/api.ts` | — | ✅ |

### Phase 1 manual test

- [ ] `npx expo start` opens **Login**, not Hello World stub
- [ ] Login `admin` / `admin123` → Scan tab visible
- [ ] Login `superadmin` / `super123` → Scan tab visible
- [ ] Logout → refresh token cannot reuse (`POST /auth/refresh` → 401)

---

## Phase 2 — 與 Web 掃描對齊 ✅ Done

| ID | Task | Screen / file | API | Status |
|----|------|---------------|-----|--------|
| M2.1 | `listLocations` client | `services/locations.ts` | `GET /locations?is_active=true` | ✅ |
| M2.2 | Scan: location picker + persist | `ScannerScreen.tsx` | `POST /attendance/scan` + `location_id` | ✅ |
| M2.3 | Scan: 簽到/簽退 + persist | `ScannerScreen.tsx` | `event_type` on scan | ✅ |
| M2.4 | Result modal shows location | `ScannerScreen.tsx` | `AttendanceOut.location` | ✅ |
| M2.5 | History shows location | `HistoryScreen.tsx` | `GET /attendance` | ✅ |
| M2.6 | `scanQR` options object | `services/attendance.ts` | — | ✅ |

### Phase 2 manual test

- [ ] Web: create active location with English name
- [ ] Mobile Scan: pick location → scan STU-001 QR → result shows location name
- [ ] History row shows same location
- [ ] Kill app, reopen → last location + check in/out still selected

---

## Phase 3 — 體驗與功能（待排）

| ID | Task | Priority | Notes |
|----|------|----------|-------|
| M3.1 | History: date filter + pagination | P2 | Use `date_from` / `date_to`, `X-Total-Count` |
| M3.2 | History: pull-to-refresh error toast | P3 | Show message instead of `console.warn` only |
| M3.3 | My QR tab: remove or rename to help | P3 | Products use **Web → QR Codes** |
| M3.4 | Login: show API connection hint on failure | P3 | LAN IP / `EXPO_PUBLIC_API_URL` |
| M3.5 | Optional: display product QR on mobile (admin) | P4 | `GET /qr/token/{id}` + `react-native-qrcode-svg` |
| M3.6 | Username login trim (API already case-insensitive) | P3 | Trim input on `LoginScreen` |
| M3.7 | Dark status bar on scanner | P4 | Polish |

---

## Phase 4 — 上線前

See **[MOBILE-RELEASE-CHECKLIST.md](./MOBILE-RELEASE-CHECKLIST.md)** for deploy steps.

| ID | Task | Owner | Status |
|----|------|-------|--------|
| M4.1 | Production `EXPO_PUBLIC_API_URL` in EAS secrets | DevOps | ⬜ |
| M4.2 | EAS build profile (preview / production) | DevOps | ⬜ |
| M4.3 | API `alembic upgrade head` on server | DevOps | ⬜ |
| M4.4 | CORS / HTTPS API URL for builds | DevOps | ⬜ |
| M4.5 | End-to-end test matrix (devices) | QA | ⬜ |
| M4.6 | Internal distribution (TestFlight / APK) | Ops | ⬜ |

---

## API ↔ Mobile endpoint map

| Feature | Method | Path | Auth |
|---------|--------|------|------|
| Login | POST | `/auth/login` | Public |
| Logout | POST | `/auth/logout` | Public (body: refresh_token) |
| Refresh | POST | `/auth/refresh` | Public |
| Me | GET | `/auth/me` | Bearer |
| Locations list | GET | `/locations` | Admin |
| Scan | POST | `/attendance/scan` | Admin |
| History | GET | `/attendance` | Admin |
| QR token | GET | `/qr/token/{product_id}` | Admin |

---

## Web parity matrix

| Feature | Web (`attendance/`) | Mobile |
|---------|---------------------|--------|
| Login | ✅ | ✅ |
| Logout revokes refresh | ✅ | ✅ |
| Scan check in/out toggle | ✅ | ✅ |
| Scan location select | ✅ | ✅ |
| Scan manual token paste | ✅ | ❌ (camera only) |
| QR display per product | ✅ | ❌ (web only) |
| Product / user / location CRUD | ✅ | ❌ |
| CSV export | ✅ | ❌ |
| Dashboard stats | ✅ | ❌ |

---

## Related docs

- [apps/mobile/README.md](../apps/mobile/README.md) — dev setup
- [KNOWN-GAPS.md](./KNOWN-GAPS.md) — debt tracker
- [MOBILE-RELEASE-CHECKLIST.md](./MOBILE-RELEASE-CHECKLIST.md) — Phase 4
- [DEPLOY.md](./DEPLOY.md) — server deploy
