# Juku Attendance — Mobile App

Expo (React Native) app for **scanning product QR codes** and viewing attendance history. Login accounts are **admins** (`admin` or `superadmin`), not students.

Students and staff **do not log in** — they carry a product QR created in the web app (**QR Codes** / **Product Management**).

## API URL by platform

| How you run the app | `EXPO_PUBLIC_API_URL` |
|---------------------|------------------------|
| **Android emulator** (press `a`) | `http://10.0.2.2:8000/api` |
| **Expo web** (press `w`) | `http://localhost:8000/api` |
| **Physical phone** (Expo Go QR) | `http://<PC-LAN-IP>:8000/api` + API `--host 0.0.0.0` |

`10.0.2.2` is the emulator’s alias for your PC’s `127.0.0.1`.

## Web vs phone

Pressing **`w`** opens the app in a **browser**. Tokens use `localStorage` on web (`src/services/storage.ts`).

For **QR camera scanning**, use the **Android emulator** (`a`) or a **physical device** — not the browser.

## Languages

The app supports **English** and **繁體中文**. Use the **EN / 繁中** switch on the login screen or in the top bar after sign-in. Your choice is saved on the device; first launch follows the phone language (Chinese → 繁中, otherwise English).

Translation files: `src/i18n/locales/en.ts`, `src/i18n/locales/zh-Hant.ts`.

## Quick start

```bash
cd apps/mobile
cp .env.example .env
npm install
npx expo start
```

### Expo Go: `Failed to download remote update`

The phone could not reach Metro on your PC (firewall, VPN, or Wi‑Fi isolation). Try in order:

1. **Tunnel mode** (most reliable): `npm run start:tunnel` — scan the new QR code in Expo Go.
2. Turn off **VPN** on PC and phone (e.g. Surfshark).
3. Same **Wi‑Fi**; Windows Firewall: allow **Node.js** on private networks (ports **8081**, **8000**).
4. Update **Expo Go** from the store (project uses **Expo SDK 54** — must match phone app).
5. Expo Go app menu → clear cache, or `npx expo start -c` on PC.

API URL in `.env` must stay your PC LAN IP (not `localhost`) when using Expo Go on a phone.

### Environment

| Variable | Example | Notes |
|----------|---------|-------|
| `EXPO_PUBLIC_API_URL` | `http://192.168.1.50:8000/api` | Use your machine's **LAN IP** on a physical device (not `localhost`) |

Ensure the API is running. Native fetch is not CORS-limited; web tooling may still need `CORS_ORIGINS` if applicable.

### Seed login (after API `python seed.py`)

| Username | Password | Scan tab |
|----------|----------|----------|
| admin | admin123 | Yes |
| superadmin | super123 | Yes |

## Features

| Tab | Description |
|-----|-------------|
| **My QR** | Help text — product QRs are managed on the **web** app |
| **Scan** | Camera QR → `POST /api/attendance/scan` with optional **location** and **check in/out** |
| **History** | Recent attendance events (pull to refresh) |

## Entry point

The app loads from **`App.tsx`** via `"main": "expo/AppEntry.js"` in `package.json`.

`app/index.tsx` is an Expo Router stub only — do not use `expo-router/entry` as `main` or Expo Go may show the wrong screen.

## Manual test flow

1. Start API + DB + seed: `admin` / `admin123`, products `STU-001`, etc.
2. Web: create an active **location** (English name required).
3. Web: **QR Codes** → **STU-001** → show QR on another screen.
4. Mobile: log in → **Scan** → pick a **default location** (saved on device) → choose **簽到/簽退** each time → **Start scanning** → scan QR.
5. Confirm modal shows name + location.
6. **History** → event appears with location.
7. **Logout** → server refresh token revoked.
8. **Debounce:** same action twice within 3s → no duplicate row.
9. **Rotate QR:** web **Refresh QR** → old QR fails.

## Project layout

```
App.tsx                 # Root: login vs tabs
src/
  navigation/AppNavigator.tsx
  screens/LoginScreen.tsx, ScannerScreen.tsx, HistoryScreen.tsx, QRDisplayScreen.tsx
  services/api.ts, auth.ts, attendance.ts, locations.ts
app/index.tsx           # Expo Router stub (not the attendance app)
```

## Sprint & release docs

- [docs/MOBILE-SPRINT.md](../../docs/MOBILE-SPRINT.md) — phased backlog (Phase 1–4)
- [docs/MOBILE-RELEASE-CHECKLIST.md](../../docs/MOBILE-RELEASE-CHECKLIST.md) — pre-launch checklist
- [docs/KNOWN-GAPS.md](../../docs/KNOWN-GAPS.md) — remaining debt

## Production builds

1. Set `EXPO_PUBLIC_API_URL` to production API, e.g. `https://api.yourdomain.com/api`
2. Build with EAS or `expo prebuild` + native toolchain
3. Follow [MOBILE-RELEASE-CHECKLIST.md](../../docs/MOBILE-RELEASE-CHECKLIST.md)

See root [README.md](../../README.md) and [docs/DEPLOY.md](../../docs/DEPLOY.md).
