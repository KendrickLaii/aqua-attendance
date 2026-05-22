# Juku Attendance — Mobile App

Expo (React Native) app for **scanning product QR codes** and viewing attendance history. Login accounts are **admins** (API role `admin` or `superadmin`), not students.

Students and staff **do not log in** — they carry a product QR created in the web app (**QR Codes** / **Product Management**).

## Quick start

```bash
cd apps/mobile
cp .env.example .env
npm install
npx expo start
```

### Environment

| Variable | Example | Notes |
|----------|---------|-------|
| `EXPO_PUBLIC_API_URL` | `http://192.168.1.50:8000/api` | Use your machine's **LAN IP** on a physical device (not `localhost`) |

Ensure the API is running and `CORS_ORIGINS` includes your Expo dev origin if you hit CORS from web tooling; native fetch is not CORS-limited.

### Seed login (after API `python seed.py`)

| Username | Password | Scan tab |
|----------|----------|----------|
| admin | admin123 | Yes (`admin` role) |
| superadmin | super123 | **May be hidden** — app checks `staff` role name; see KNOWN-GAPS |

## Features

| Tab | Description |
|-----|-------------|
| **My QR** | Info placeholder — real QRs are managed on the **web** app per product |
| **Scan** | Camera QR scanner → `POST /api/attendance/scan` (admin login required) |
| **History** | Lists attendance events from API |

## Entry point (important)

The attendance UI is implemented in **`App.tsx`** at the project root.

`package.json` currently sets `"main": "expo-router/entry"`, and `app/index.tsx` is only an Expo Router **stub**. If Expo Go shows "Hello World" instead of the login screen, switch the entry to the classic Expo app entry (or migrate screens into expo-router). Details: [docs/KNOWN-GAPS.md](../../docs/KNOWN-GAPS.md).

## Manual test flow

1. Start API + seed: `admin` / `admin123`, products `STU-001`, etc.
2. Web: log in → **QR Codes** → select **STU-001** → copy QR token or show QR on another screen.
3. Mobile: log in as `admin` → **Scan** → point camera at QR.
4. Confirm modal shows check-in (or check-out on second scan after debounce window).
5. **History** → pull to refresh → event appears.
6. **Debounce:** scan twice within 3 seconds → same event returned (no duplicate row).
7. **Rotate QR:** web **Refresh QR** → old QR should fail with rotation error.

QR tokens **do not expire** by time; they invalidate only when an admin rotates them.

## Project layout

```
App.tsx                 # Root: login vs tabs
src/
  navigation/AppNavigator.tsx
  screens/LoginScreen.tsx, ScannerScreen.tsx, HistoryScreen.tsx, QRDisplayScreen.tsx
  services/api.ts, auth.ts, attendance.ts
app/index.tsx           # Expo Router stub (not the attendance app)
```

## Production builds

Not yet documented in CI. For a physical deployment:

1. Set `EXPO_PUBLIC_API_URL` to your production API, e.g. `https://api.yourdomain.com/api`
2. Build with EAS or `expo prebuild` + native toolchain
3. Distribute via app store or internal MDM

See root [README.md](../../README.md) roadmap for mobile CI.

## More docs

- [docs/KNOWN-GAPS.md](../../docs/KNOWN-GAPS.md) — mobile entry point, role gating  
- [docs/DEPLOY.md](../../docs/DEPLOY.md) — server deploy (API URL for builds)  
