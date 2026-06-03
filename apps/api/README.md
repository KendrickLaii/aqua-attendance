# Juku Attendance — API

FastAPI backend: login users, products (staff/students), signed QR tokens, attendance events, locations.

## Daily development

Recommended: **Postgres in Docker**, **API on your machine**.

| Step | Command | When |
|------|---------|------|
| Start DB | `docker compose up -d db` (from repo root) | After reboot, or if `docker compose ps db` is not running |
| Start API | `python -m uvicorn app.main:app --reload` (from `apps/api`) | Every dev session |
| Start API (mobile on phone) | `python -m uvicorn app.main:app --reload --host 0.0.0.0` | When Expo Go uses your LAN IP in `.env` |
| Migrate | `python -m alembic upgrade head` | After pulling new migrations |
| Seed | `python seed.py` | Optional — sample users/products |

The API connects to `localhost:5432` by default (`config.py` / `.env.example`). DBeaver uses the same host/port/credentials — only the DB container needs to be up.

See root [README.md](../../README.md) for the full three-terminal workflow (db + api + web).

## First-time setup

```bash
cd apps/api
cp .env.example .env
pip install -r requirements.txt

# PostgreSQL (from repo root; Docker Desktop must be running)
docker compose up -d db

python -m alembic upgrade head
python seed.py
python -m uvicorn app.main:app --reload
```

- Swagger: http://localhost:8000/docs  
- Health: http://localhost:8000/api/health (includes DB check)

## Seed data

```bash
python seed.py
```

Creates:

- Users: `admin` / `admin123`, `superadmin` / `super123`
- Products: `STAFF-001`, `STAFF-002`, `STU-001`, `STU-002`

## Layout

```
app/
  main.py           # FastAPI app, CORS, routers, /api/health
  config.py         # Settings from .env
  database.py       # Async SQLAlchemy engine
  deps.py           # get_db, CurrentUser, AdminOnly, SuperAdminOnly
  models/           # User, Product, AttendanceEvent, Location, RefreshToken
  schemas/          # Pydantic request/response models
  routers/          # auth, users, products, locations, qr, attendance
  services/         # auth, qr, attendance business logic
  utils/            # search helpers (safe ILIKE)
alembic/            # Migrations (use DATABASE_URL_SYNC)
tests/              # pytest (SQLite in-memory)
seed.py             # Default users + products
```

## Migrations

```bash
python -m alembic upgrade head
python -m alembic revision --autogenerate -m "description"
python -m alembic downgrade -1
```

Alembic uses `DATABASE_URL_SYNC` (`postgresql+psycopg://...`). The app uses async `DATABASE_URL`.

## Tests

```bash
pip install -r requirements.txt
pytest -v
pytest tests/test_auth.py -v
pytest tests/test_scan.py -v
```

Tests override the DB with SQLite (`tests/conftest.py`); they do not run Alembic.

## Docker

From repo root:

```bash
docker compose up -d    # db + api (migrations on container start)
```

See root [README.md](../../README.md) for env vars and security notes.

## Production

API image is built from `Dockerfile` and published by `.github/workflows/docker-publish.yml`.  
Server deploy: [docs/DEPLOY.md](../../docs/DEPLOY.md).

Before production / UAT deploy:

- Set `ENV=production` and unique `SECRET_KEY` / `QR_SECRET` (each `openssl rand -hex 32`) — see [docs/DEPLOY.md](../../docs/DEPLOY.md)
- API refuses to start if production keys are placeholders or shorter than 32 characters
- Run `python -m alembic upgrade head` after deploy (includes `refresh_tokens`, `locations.name_en` NOT NULL)
- Create additional login users via web **User Management** — public `/api/auth/register` returns 403
- Clients should call `POST /api/auth/logout` with `refresh_token` on sign-out; expired refresh rows are purged on login, refresh, and logout
