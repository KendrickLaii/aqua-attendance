# Mobile App — Release Checklist (Phase 4)

Use before internal pilot or store submission. Assumes API and Web are already deployed per [DEPLOY.md](./DEPLOY.md).

---

## 1. Backend ready

- [ ] `python -m alembic upgrade head` on production DB (migrations through `010`)
- [ ] `ENV=production` with strong `SECRET_KEY` and `QR_SECRET` (≥ 32 chars, not placeholders)
- [ ] Seed or create admin users via Web **User Management**
- [ ] Health check: `GET https://<api-host>/api/health` → `{"status":"ok","database":"ok"}`
- [ ] At least one **active** location in **Location Management** (for scan tests)

---

## 2. API URL for mobile builds

- [ ] Production API base ends with `/api`, e.g. `https://attendance.example.com/api`
- [ ] HTTPS only (no mixed content on physical devices)
- [ ] `CORS_ORIGINS` includes web origin; native apps do not use CORS but API must be reachable on device network

Set in EAS / build env:

```bash
EXPO_PUBLIC_API_URL=https://your-api.example.com/api
```

---

## 3. Build configuration

- [ ] `apps/mobile/package.json` → `"main": "expo/AppEntry.js"` (not expo-router stub)
- [ ] Run `npm install` in `apps/mobile` after dependency changes
- [ ] Configure `app.json` / `app.config` — `name`, `slug`, `ios.bundleIdentifier`, `android.package`
- [ ] Add EAS project (`eas.json`) if using EAS Build — *not yet in repo*

Suggested commands (when EAS is set up):

```bash
cd apps/mobile
eas build --platform android --profile preview
eas build --platform ios --profile preview
```

---

## 4. Pre-release manual test matrix

| # | Case | admin | superadmin | Expected |
|---|------|-------|------------|----------|
| 1 | Login | ✅ | ✅ | Tabs: My QR, Scan, History |
| 2 | Scan + location + 簽到 | ✅ | ✅ | 201 event, location in modal |
| 3 | Scan 簽退 same product | ✅ | ✅ | Second event, status OUT |
| 4 | Debounce double scan (<3s, same action) | ✅ | ✅ | Same event id returned |
| 5 | Rotated QR (web Refresh QR) | ✅ | ✅ | Error: token rotated |
| 6 | Logout | ✅ | ✅ | Refresh reuse → 401 |
| 7 | History pull refresh | ✅ | ✅ | Latest events, location shown |
| 8 | Wrong password | ✅ | — | Clear error |
| 9 | API offline | ✅ | — | Login/scan error message |

Test on:

- [ ] Android physical device (Wi‑Fi → API host)
- [ ] iOS physical device (if applicable)
- [ ] Optional: Expo Go on same LAN

---

## 5. Security review

- [ ] No API secrets in mobile bundle (only public API URL)
- [ ] Tokens in `expo-secure-store`, not AsyncStorage
- [ ] Logout revokes refresh token server-side
- [ ] Scan requires admin JWT (students never log in)

---

## 6. Distribution

- [ ] Internal APK / TestFlight build shared with pilot users
- [ ] Short user guide: Web for QR sheets + user setup; Mobile for floor scanning
- [ ] Support contact / rollback plan if API URL wrong

---

## 7. Post-release

- [ ] Monitor API logs for scan 400/401 spikes
- [ ] Confirm `refresh_tokens` table size stable (purge on login/logout)
- [ ] Update [MOBILE-SPRINT.md](./MOBILE-SPRINT.md) Phase 3/4 status
- [ ] File issues for Phase 3 backlog (history filters, etc.)

---

## Quick dev smoke (before any build)

```bash
# Terminal 1 — repo root
docker compose up -d db

# Terminal 2
cd apps/api && python -m uvicorn app.main:app --reload

# Terminal 3
cd apps/mobile && cp .env.example .env
# Edit EXPO_PUBLIC_API_URL to LAN IP
npx expo start
```

Login: `admin` / `admin123` (after `python seed.py`).
