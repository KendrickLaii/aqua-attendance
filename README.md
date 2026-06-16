# AQUA Time & Attendance System

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
| **Product** (`products` table) | Person or entity that checks in: `product_type` = `staff`, `student`, `device`, or `goods` |
| **Profile** (`student_profiles` / `staff_profiles`) | Type-specific data: student (school, guardians) / staff (employment, pay) |
| **Attendance event** | A `check_in`, `check_out`, `manual_correction`, or `auto_checkout` row for a product |

## Repository layout

| Path | Description |
|------|-------------|
| `apps/api/` | FastAPI — auth, products, QR signing, attendance |
| `apps/web/` | Vue 3 admin UI (`src/pages/attendance/`) on AQUA template |
| `apps/mobile/` | Expo app — QR scanner + history (see mobile README for entry-point note) |
| `docker-compose.yml` | Dev: PostgreSQL + API |
| `deploy/` | Production: Caddy + web + api + db (see `docs/PROJECT-HANDBOOK.md`) |
| `docs/` | Unified handbook, deploy guide, ops manual, CI/CD explainer |

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
| `ENV` | `development` | `production` enforces key length validation; `development` enables SQL echo |
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

See [deploy/.env.example](deploy/.env.example) and [docs/PROJECT-HANDBOOK.md](docs/PROJECT-HANDBOOK.md).

## Security design (summary)

- **QR tokens** are signed JWTs with `QR_SECRET` (not `SECRET_KEY`), no expiry, versioned via `qr_token_version`. Scanning toggles `check_in` / `check_out`.
- **Debounce**: duplicate scans within `SCAN_DEBOUNCE_SECONDS` return the existing event.
- **Roles**: `admin` or `superadmin`. All product/attendance endpoints require admin; only `DELETE /api/users/:id` requires superadmin.

Details: [docs/PROJECT-HANDBOOK.md](docs/PROJECT-HANDBOOK.md) §1.3–1.6.

## API endpoints (overview)

| Group | Routes | Auth |
|-------|--------|------|
| Auth | `/api/auth/login`, `/refresh`, `/me` | None / Bearer |
| Users | `/api/users` (CRUD) | Admin; `DELETE` = Superadmin |
| Products | `/api/products` (CRUD) | Admin |
| Profiles | `/api/student-profiles/:id`, `/staff-profiles/:id` | Admin |
| QR | `/api/qr/token/:product_id` (get, refresh) | Admin |
| Attendance | `/api/attendance/scan`, `/manual`, `/export/csv`, `/void` | Admin |
| Summaries | `/api/attendance-summaries` (generate, query) | Admin |
| Payroll | `/api/payroll-records` (CRUD, confirm) | Admin |
| Notifications | `/api/notifications` (CRUD, mark read) | Admin |
| Audit | `/api/audit-logs` (query) | Superadmin |
| Auto-checkout | `/api/auto-checkout/run` | Admin |
| Health | `/api/health` | None |

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
- **Server:** `deploy/` + [docs/PROJECT-HANDBOOK.md](docs/PROJECT-HANDBOOK.md)
- **Overview:** [docs/PROJECT-HANDBOOK.md](docs/PROJECT-HANDBOOK.md)

`first-boot.sh` starts containers but does **not** seed the database. After first deploy, run `python seed.py` in the API container or use `deploy/reset-db.sh` for a fresh DB + seed.

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/INDEX.md](docs/INDEX.md) | **Docs entry point** — find the right doc by role |
| [docs/PROJECT-HANDBOOK.md](docs/PROJECT-HANDBOOK.md) | **Unified handbook** — deploy, CI/CD, ops, known gaps, mobile release |
| [apps/api/README.md](apps/api/README.md) | API setup and tests |
| [apps/web/README.md](apps/web/README.md) | Web quick start |
| [apps/mobile/README.md](apps/mobile/README.md) | Mobile scanner setup |

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
