# Juku Attendance — Mobile App

Expo (React Native) app for students and staff.

## Why Expo?

- Excellent camera/QR scanning via `expo-camera`
- Fast dev iteration with Expo Go
- Cross-platform (iOS + Android) from single codebase
- The rest of the stack is JS/TS, keeping the team in one ecosystem

## Quick Start

```bash
cd apps/mobile
npm install
npx expo start
```

Scan the QR code with Expo Go on your phone, or press `a` for Android emulator / `i` for iOS simulator.

## Environment

Copy `.env.example` to `.env` and set `EXPO_PUBLIC_API_URL` to your API's address (use your machine's LAN IP, not `localhost`, when testing on a physical device).

## Manual Test Steps

1. **Login**: Open app → enter username/password → verify redirect to role-appropriate screen
2. **QR Display (student)**: After login as student → "My QR" tab shows QR code → verify it auto-refreshes
3. **Scanner (staff)**: Login as staff → "Scan" tab → point camera at student QR → verify success/failure modal
4. **History**: Tap "History" tab → pull to refresh → verify attendance records appear
5. **Replay**: Scan same QR twice → second scan should show same event (idempotent)
6. **Expired QR**: Wait >60s without refresh → scan old QR → should show error
