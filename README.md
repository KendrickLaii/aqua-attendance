# Juku Time & Attendance System

A complete check-in / check-out system for a cram school (juku) with three roles: **admin**, **staff**, and **student**. Students present a signed QR code; staff scan it in the mobile app.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Mobile App │────▶│   FastAPI    │◀────│   Vue 3 Web App │
│  (Expo/RN)  │     │  (apps/api)  │     │  (src/pages/    │
│             │     │              │     │   attendance/)   │
└─────────────┘     └──────┬───────┘     └─────────────────┘
                           │
                    ┌──────┴───────┐
                    │  PostgreSQL  │
                    └──────────────┘
```

## Repository Layout

| Path | Description |
|------|-------------|
| `apps/api/` | FastAPI backend — auth, QR signing, attendance CRUD |
| `apps/mobile/` | Expo (React Native) mobile app |
| `apps/web/` | AQUA-based Vue 3 web app for attendance |
| `docker-compose.yml` | PostgreSQL + API containers |

## Quick Start — Full Stack

### 1. Start database and API

```bash
# From repo root
docker compose up -d db        # start PostgreSQL
cd apps/api
cp .env.example .env           # edit if needed
pip install -r requirements.txt
alembic upgrade head           # run migrations
python seed.py                 # create sample users (admin/staff1/student1/student2)
uvicorn app.main:app --reload  # start API on :8000
```

Or run everything via Docker:

```bash
docker compose up -d           # starts db + api
```

### 2. Start web app

```bash
# From repo root
cd apps/web
npm install
npm run dev                    # Vite dev server on :5173 (or next available port)
```

Visit: `http://localhost:5173/attendance/login` (or the port shown in terminal, e.g. `5174`/`5175`)

### 3. Start mobile app

```bash
cd apps/mobile
npm install
npx expo start                 # scan QR with Expo Go
```

Set `EXPO_PUBLIC_API_URL` in `.env` to your machine's LAN IP (e.g. `http://192.168.1.50:8000/api`).

## Default Seed Users

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | admin |
| staff1 | staff123 | staff |
| student1 | student123 | student |
| student2 | student123 | student |

## Environment Variables

### API (`apps/api/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async DB connection string |
| `DATABASE_URL_SYNC` | `postgresql+psycopg://...` | Sync DB URL for Alembic |
| `SECRET_KEY` | — | JWT signing key (change in prod!) |
| `QR_SECRET` | — | QR token signing key (separate from auth) |
| `SCAN_DEBOUNCE_SECONDS` | `3` | Window in which duplicate scans of the same product return the existing event (kiosk double-tap protection) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Auth token expiry |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Allowed CORS origins |

### Web (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_ATTENDANCE_API_URL` | `http://localhost:8000/api` | Attendance API base URL |

### Mobile (`apps/mobile/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `EXPO_PUBLIC_API_URL` | `http://localhost:8000/api` | API URL (use LAN IP for devices) |

## Database Migrations

```bash
cd apps/api
alembic upgrade head           # apply all migrations
alembic revision --autogenerate -m "description"  # create new migration
alembic downgrade -1           # rollback one step
```

## Tests

```bash
cd apps/api
pip install aiosqlite          # test dependency for SQLite backend
pytest -v                      # run all tests
pytest tests/test_auth.py -v   # auth tests only
pytest tests/test_scan.py -v   # scan / QR tests only
```

## Security Design

### QR Token Flow

1. Admin requests `GET /api/qr/token/{product_id}` → receives a signed JWT
2. JWT payload: `{ sub: product_id, ver: token_version, jti, iat, type: "qr" }`
3. QR is signed with `QR_SECRET` (separate from auth `SECRET_KEY`)
4. The token has **no expiry** — it lives on a printed badge / lock screen
   and the same QR is scanned every time the product checks in or out
5. Scanner sends QR token to `POST /api/attendance/scan`
6. Server verifies signature, and verifies `ver` matches the product's
   current `qr_token_version`; a stale version is rejected as "rotated"

### Rotating a QR

If a QR is lost or shared with someone who shouldn't have it, an admin can
call `POST /api/qr/token/{product_id}/refresh`. This bumps the product's
`qr_token_version`, invalidating any previously-issued QR for that product.
Normal check-in / check-out **never** needs a refresh.

### Check-in / Check-out Toggle

Each `Product` has an `attendance_status` (`checked_in` / `checked_out`,
default `checked_out`). Every scan toggles it:

- Status `checked_out` → scan creates a `check_in` event, status becomes `checked_in`
- Status `checked_in` → scan creates a `check_out` event, status becomes `checked_out`

If the last event was on a previous UTC day, the next scan starts a fresh
session with `check_in` regardless of stored status (handles overnight gaps).

Admins can override via `POST /api/attendance/manual` with an explicit
`event_type`; manual `check_in` / `check_out` corrections also update the
product's `attendance_status`.

### Replay / Double-tap Protection

Rapid duplicate scans of the **same product** within
`SCAN_DEBOUNCE_SECONDS` (default `3`) return the existing event instead of
creating a duplicate row. This protects kiosks from double-taps without
preventing the legitimate "scan again to check out" flow.

### RBAC

| Endpoint | admin | staff | student |
|----------|-------|-------|---------|
| User CRUD | ✅ | ❌ | ❌ |
| Scan QR | ✅ | ✅ | ❌ |
| View all attendance | ✅ | ✅ | ❌ |
| View own attendance | ✅ | ✅ | ✅ |
| Manual correction | ✅ | ❌ | ❌ |
| Export CSV | ✅ | ✅ | ❌ |
| Get QR token | ✅ | ✅ | ✅ |

### Audit Trail

Every `AttendanceEvent` records:
- `scanner_user_id` — who performed the scan
- `client_device_id` — which device/kiosk
- `qr_jti` — links back to the exact QR token used
- `recorded_at` — server-side timestamp

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | — | Register a new user |
| POST | `/api/auth/login` | — | Login, returns JWT pair |
| POST | `/api/auth/refresh` | — | Refresh access token |
| GET | `/api/auth/me` | Bearer | Get current user |
| GET | `/api/users` | Admin | List users |
| POST | `/api/users` | Admin | Create user |
| GET | `/api/users/:id` | Admin | Get user |
| PATCH | `/api/users/:id` | Admin | Update user |
| DELETE | `/api/users/:id` | Admin | Delete user |
| GET | `/api/qr/token/:product_id` | Admin | Get product's current QR token |
| POST | `/api/qr/token/:product_id/refresh` | Admin | Rotate product's QR (invalidates the old one) |
| POST | `/api/attendance/scan` | Staff+ | Process QR scan |
| GET | `/api/attendance` | Bearer | List attendance events |
| POST | `/api/attendance/manual` | Admin | Manual correction |
| GET | `/api/attendance/export/csv` | Staff+ | Export CSV |
| GET | `/api/health` | — | Health check |

## Web Routes

| Path | Role | Description |
|------|------|-------------|
| `/attendance/login` | All | Attendance login page |
| `/attendance/dashboard` | Admin/Staff | Dashboard with today's stats |
| `/attendance/my-qr` | All | Show personal QR code |
| `/attendance/log` | All | Attendance log (filtered for students) |
| `/attendance/users` | Admin | User management CRUD |

## Not in v1

The following features are explicitly **out of scope** for this MVP:

- [ ] Password reset / email verification
- [ ] Push notifications for attendance reminders
- [ ] Multi-location / multi-organization support
- [ ] Offline mode / local-first sync
- [ ] Biometric authentication (Face ID / fingerprint)
- [ ] Advanced reporting / analytics dashboards
- [ ] Class/course scheduling integration
- [ ] Parent portal / notifications
- [ ] Geofencing for attendance validation
- [ ] Bulk user import (CSV upload)
- [ ] Rate limiting / Redis-backed throttling
- [ ] E2E tests (Playwright / Detox)
- [ ] Production deployment (CI/CD, container registry, secrets management)
- [ ] Internationalization (i18n) for mobile app
- [ ] Dark mode for mobile app
- [ ] WebSocket real-time attendance feed
