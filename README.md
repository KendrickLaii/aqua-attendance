# Juku Time & Attendance System

Check-in / check-out for a cram school (juku). **Staff and students are not login accounts** — they are **products** with a printed or on-screen QR code. **Admins** (and **superadmins**) log into the web app and mobile app to manage data and scan QRs.

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│  Products (staff / students)                                     │
│  Each has a signed QR (JWT) — same code for every check-in/out   │
└───────────────────────────────┬─────────────────────────────────┘
                                │ scan
                                ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────────────┐
│  Mobile App │────▶│   FastAPI    │◀────│   Vue 3 Web App         │
│  (Expo/RN)  │     │  apps/api    │     │  apps/web/attendance/   │
│  QR scanner │     │              │     │  admin console          │
└─────────────┘     └──────┬───────┘     └─────────────────────────┘
                           │
                    ┌──────┴───────┐
                    │  PostgreSQL  │
                    └──────────────┘
```

| Concept | Description |
|---------|-------------|
| **User** (`users` table) | Someone who logs in: `admin` or `superadmin` only |
| **Product** (`products` table) | Person or entity that checks in: `product_type` = `staff` or `student` |
| **Attendance event** | A `check_in`, `check_out`, or `manual_correction` row for a product |

## Repository layout

| Path | Description |
|------|-------------|
| `apps/api/` | FastAPI — auth, products, QR signing, attendance |
| `apps/web/` | Vue 3 admin UI (`src/pages/attendance/`) on AQUA template |
| `apps/mobile/` | Expo app — QR scanner + history (see mobile README for entry-point note) |
| `docker-compose.yml` | Dev: PostgreSQL + API |
| `deploy/` | Production: Caddy + web + api + db (see `docs/DEPLOY.md`) |
| `docs/` | Deploy guide, CI/CD explainer |

## Daily development (recommended)

**Hybrid mode:** PostgreSQL in Docker; API and web run on your machine (hot reload).

```
┌──────────────────────────────────────────────────────────────┐
│  Your machine                                                 │
│  Terminal 2: uvicorn (apps/api)  ──▶  localhost:5432        │
│  Terminal 3: npm run dev (apps/web)                           │
│  Terminal 1: docker compose up -d db  ──▶  Postgres container │
└──────────────────────────────────────────────────────────────┘
```

| Terminal | Directory | Command | When |
|----------|-----------|---------|------|
| 1 | repo root | `docker compose up -d db` | After reboot or if DB is not running (`docker compose ps db`) |
| 2 | `apps/api` | `python -m uvicorn app.main:app --reload` | Every dev session |
| 3 | `apps/web` | `npm run dev` | Every dev session |

Closing terminals 2–3 stops API/web only. The DB container keeps running until you stop Docker or run `docker compose down`. Data persists in the Docker volume across restarts.

| Task | When |
|------|------|
| `alembic upgrade head` | After pulling new migrations |
| `python seed.py` | Optional — (re)load sample users/products |
| `npm install` / `pip install -r requirements.txt` | After pulling dependency changes |

**URLs:** API http://localhost:8000/docs · Web http://localhost:5173/attendance/login (Vite may use 5174+ if 5173 is busy)

**Alternative — API in Docker too:** from repo root, `docker compose up -d` (runs db + api; migrations on container start). You still run `npm run dev` separately for the web app.

**Inspect the DB (DBeaver, etc.):** only terminal 1 is needed — connect to `127.0.0.1:5432`, database/user/password `attendance` / `attendance` (defaults from `docker-compose.yml`).

## First-time setup — full stack

### 1. Database and API

```bash
# From repo root — requires Docker Desktop running
docker compose up -d db

cd apps/api
cp .env.example .env
pip install -r requirements.txt
alembic upgrade head
python seed.py
python -m uvicorn app.main:app --reload
```

API: http://localhost:8000/docs  
Health: http://localhost:8000/api/health

### 2. Web app

```bash
cd apps/web
cp .env.example .env   # set VITE_ATTENDANCE_API_URL if needed
npm install
npm run dev
```

Open: http://localhost:5173/attendance/login

### 3. Mobile app

```bash
cd apps/mobile
cp .env.example .env
# Set EXPO_PUBLIC_API_URL to your LAN IP on a physical device, e.g.:
# EXPO_PUBLIC_API_URL=http://192.168.1.50:8000/api
npm install
npx expo start
```

See [apps/mobile/README.md](apps/mobile/README.md) for scanner setup and known entry-point limitations.

## Seed data

After `python seed.py`:

### Login users

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | admin |
| superadmin | super123 | superadmin |

### Sample products (QR issued from web)

| Code | Name | Type |
|------|------|------|
| STAFF-001 | Tanaka Sensei | staff |
| STAFF-002 | Yamamoto Sensei | staff |
| STU-001 | Suzuki Taro | student |
| STU-002 | Yamada Hanako | student |

**Get a QR:** log in as `admin` → **QR Codes** or **Product Management** → fetch token → print or display.  
**Scan:** mobile **Scan** tab or web **Scanner** (paste token) while logged in as admin/superadmin.

Change all seed passwords before any shared or production use.

## Environment variables

### API (`apps/api/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async app connection |
| `DATABASE_URL_SYNC` | `postgresql+psycopg://...` | Sync URL for Alembic |
| `SECRET_KEY` | (required in prod) | JWT auth signing |
| `QR_SECRET` | (required in prod) | QR token signing (separate from auth) |
| `SCAN_DEBOUNCE_SECONDS` | `3` | Same product: duplicate scan within window returns existing event |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `CORS_ORIGINS` | localhost dev URLs | Comma-separated allowed origins |
| `ENV` | `development` | `development` enables SQL echo |
| `LOGIN_RATE_LIMIT` | `5/minute` | Per-IP login attempts |
| `SCAN_RATE_LIMIT` | `30/minute` | Per-IP QR scan attempts |

### Web (`apps/web/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_ATTENDANCE_API_URL` | `http://localhost:8000/api` | API base URL (baked at **build** time for prod images) |

### Mobile (`apps/mobile/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `EXPO_PUBLIC_API_URL` | `http://localhost:8000/api` | API base URL; use LAN IP on real devices |

### Production server (`deploy/.env`)

See [deploy/.env.example](deploy/.env.example) and [docs/DEPLOY.md](docs/DEPLOY.md).

## Security design

### QR token flow

1. Admin calls `GET /api/qr/token/{product_id}` → signed JWT
2. Payload: `{ sub: product_id, ver: qr_token_version, jti, iat, type: "qr" }`
3. Signed with `QR_SECRET` (not `SECRET_KEY`)
4. **No expiry** — same QR on badge/lock screen; each scan toggles check-in/out
5. Scanner posts token to `POST /api/attendance/scan`
6. Server checks signature and `ver` matches product; stale version → "rotated"

**Rotate:** `POST /api/qr/token/{product_id}/refresh` bumps `qr_token_version` and invalidates old QRs.

### Check-in / check-out toggle

- `attendance_status`: `checked_out` → scan → `check_in`; `checked_in` → scan → `check_out`
- If last event was on a **previous UTC day**, next scan always starts with `check_in` (overnight gap handling)
- Admins: `POST /api/attendance/manual` for corrections

### Debounce

Same product scanned twice within `SCAN_DEBOUNCE_SECONDS` (default 3) returns the **existing** event (kiosk double-tap), not a duplicate row.

### API authorization (current behavior)

Roles on **users**: `admin`, `superadmin`.  
`AdminOnly` = admin or superadmin. `SuperAdminOnly` = superadmin only.

| Endpoint | Auth required |
|----------|----------------|
| `POST /api/auth/register` | None (always **403** — use User Management) |
| `POST /api/auth/login`, `/refresh` | None |
| `GET /api/auth/me` | Bearer |
| `GET/PATCH /api/users` | Admin |
| `POST /api/users` | Admin (create user — web User Management) |
| `DELETE /api/users/:id` | Superadmin |
| `DELETE /api/users/:id` | Superadmin |
| `GET/POST/PATCH/DELETE /api/products` | Admin |
| `GET/POST /api/qr/token/...` | Admin |
| `POST /api/attendance/scan` | Admin |
| `GET /api/attendance` | Admin |
| `POST /api/attendance/manual` | Admin |
| `GET /api/attendance/export/csv` | Admin |

> See [docs/KNOWN-GAPS.md](docs/KNOWN-GAPS.md) for remaining web/mobile hardening.

### Audit fields (`attendance_events`)

- `recorded_by_user_id` — logged-in user who performed the scan or manual entry
- `client_device_id` — kiosk/mobile identifier from scan request
- `qr_jti` — QR token id at scan time
- `recorded_at` — server timestamp (UTC)

## API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | — | Disabled (403) — use `POST /api/users` |
| POST | `/api/auth/login` | — | Login → JWT pair |
| POST | `/api/auth/refresh` | — | Refresh tokens |
| GET | `/api/auth/me` | Bearer | Current user |
| GET | `/api/users` | Admin | List users |
| POST | `/api/users` | Admin | Create user |
| GET | `/api/users/:id` | Admin | Get user |
| PATCH | `/api/users/:id` | Admin | Update user |
| DELETE | `/api/users/:id` | Superadmin | Delete user |
| GET | `/api/products` | Admin | List products (filters: type, `employment_type`, active, search, `attendance_status`, pagination) |
| POST | `/api/products` | Admin | Create product |
| GET | `/api/products/:id` | Admin | Get product |
| PATCH | `/api/products/:id` | Admin | Update product |
| DELETE | `/api/products/:id` | Admin | Delete product |
| GET | `/api/qr/token/:product_id` | Admin | Current QR JWT |
| POST | `/api/qr/token/:product_id/refresh` | Admin | Rotate QR |
| POST | `/api/attendance/scan` | Admin | Process QR scan |
| GET | `/api/attendance` | Admin | List events (filters: product, dates, type) |
| POST | `/api/attendance/manual` | Admin | Manual correction |
| GET | `/api/attendance/export/csv` | Admin | CSV export |
| GET | `/api/health` | — | Health check |

Full OpenAPI: http://localhost:8000/docs

## Web routes (attendance)

| Path | Access | Description |
|------|--------|-------------|
| `/attendance/login` | Public | Login |
| `/attendance` | Public | Redirect to dashboard or login |
| `/attendance/dashboard` | Logged in | Today's stats |
| `/attendance/products` | Admin | Product CRUD |
| `/attendance/qr-codes` | Logged in | Browse/fetch/rotate QRs |
| `/attendance/log` | Logged in | Event log, manual correction, CSV export |
| `/attendance/users` | Admin (CASL) | User CRUD |

Prod navigation is trimmed to these pages via `src/navigation/vertical/custom-pages.ts`. The rest of `apps/web` is AQUA template demos (not used in production nav).

## Tests

```bash
cd apps/api
pip install -r requirements.txt   # includes aiosqlite for tests
pytest -v
pytest tests/test_auth.py -v
pytest tests/test_scan.py -v
```

CI also runs API tests and web `npm run build` on every PR and push to `main`.

## Deployment and CI/CD

- **CI:** `.github/workflows/ci.yml` — pytest + web build
- **Images:** `.github/workflows/docker-publish.yml` — push API + web to GHCR on `main` / tags
- **Server:** `deploy/` + [docs/DEPLOY.md](docs/DEPLOY.md)
- **Overview:** [docs/CICD-EXPLAINED.md](docs/CICD-EXPLAINED.md)

`first-boot.sh` starts containers but does **not** seed the database. After first deploy, run `python seed.py` in the API container or use `deploy/reset-db.sh` for a fresh DB + seed.

## Documentation index

| Doc | Purpose |
|-----|---------|
| [docs/README.md](docs/README.md) | Doc index |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Production server setup |
| [docs/CICD-EXPLAINED.md](docs/CICD-EXPLAINED.md) | Pipeline mental model |
| [docs/KNOWN-GAPS.md](docs/KNOWN-GAPS.md) | Doc/code mismatches and planned fixes |
| [docs/RELEASE-2026-05.md](docs/RELEASE-2026-05.md) | **Current release** — deploy checklist |
| [apps/api/README.md](apps/api/README.md) | API-only quick start |
| [apps/web/README.md](apps/web/README.md) | Web-only quick start |
| [apps/mobile/README.md](apps/mobile/README.md) | Mobile scanner app |

## Roadmap (not in v1)

- [ ] Password reset / email verification
- [ ] Push notifications
- [ ] Multi-location / multi-organization
- [ ] Offline mode
- [ ] Biometric auth on mobile
- [ ] Advanced analytics
- [ ] Class scheduling integration
- [ ] Parent portal
- [ ] Geofencing
- [ ] Bulk CSV import for products
- [ ] Rate limiting / Redis throttling
- [ ] E2E tests (Playwright / Detox)
- [ ] Mobile CI and EAS build docs
- [ ] WebSocket live feed
- [ ] Trim AQUA template dead code from web app

**Partially done (update checklist as you go):**

- [x] CI (pytest + web build on PR/main)
- [x] Container images to GHCR
- [x] Production compose + Caddy + deploy scripts
- [x] Disable public registration (use User Management)
- [x] Scan and attendance list restricted to admin/superadmin
- [x] CSV export auth on web (Bearer blob download)
- [ ] Fix mobile Expo entry point
- [ ] HttpOnly session cookies
