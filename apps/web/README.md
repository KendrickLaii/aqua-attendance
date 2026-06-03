# Juku Attendance — Web App

Vue 3 + Vite admin console for attendance. **Attendance UI** lives under `src/pages/attendance/`. The rest of the repo tree is the AQUA admin template (demos); production navigation only links attendance pages.

## Daily development

Each session (with API + DB already set up):

```bash
# Terminal 1 — repo root (skip if already running)
docker compose up -d db

# Terminal 2 — apps/api
python -m uvicorn app.main:app --reload

# Terminal 3 — apps/web
npm run dev
```

Full workflow: root [README.md](../../README.md#daily-development-recommended).

## First-time setup

Ensure API is running (see [apps/api/README.md](../api/README.md)).

```bash
cd apps/web
cp .env.example .env
npm install
npm run dev
```

Open: http://localhost:5173/attendance/login

Default login: `admin` / `admin123` (after API `python seed.py`).

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_ATTENDANCE_API_URL` | Yes for real API | e.g. `http://localhost:8000/api` |

Optional template vars (`VITE_MAPBOX_ACCESS_TOKEN`, etc.) are unused by attendance pages.

**Production:** `VITE_ATTENDANCE_API_URL` is baked in at **image build** time. Set the GitHub Actions variable `VITE_ATTENDANCE_API_URL` before running the publish workflow.

## Attendance pages

| Route | Purpose |
|-------|---------|
| `/attendance/login` | Login |
| `/attendance/dashboard` | Dashboard |
| `/attendance/products` | Product CRUD |
| `/attendance/qr-codes` | Fetch / rotate / preview QRs |
| `/attendance/log` | Event log, manual correction, CSV |
| `/attendance/users` | User CRUD (admin) |

Navigation: `src/navigation/vertical/custom-pages.ts` (prod uses this list only).

## API client

- `src/utils/attendanceApi.ts` — `ofetch`, Bearer token, 401 refresh
- `src/api/attendance/` — typed endpoints
- `src/stores/useAttendanceAuthStore.ts` — session + cookies

Tokens are stored in cookies (`attendanceAccessToken`). See [docs/KNOWN-GAPS.md](../../docs/KNOWN-GAPS.md) for logout/CSV caveats.

## Build

```bash
npm run build      # output: dist/
npm run preview    # preview production build locally
```

Docker production image: `prod.Dockerfile` (nginx serves `dist/`).

## Stop services

- Dev server: `Ctrl+C` in the web terminal  
- Database (from repo root): `docker compose down`

## More docs

- Root [README.md](../../README.md)  
- [docs/DEPLOY.md](../../docs/DEPLOY.md) — production web image  
