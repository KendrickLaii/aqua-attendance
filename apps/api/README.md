# Juku Attendance — API

FastAPI backend: login users, products (staff/students), signed QR tokens, attendance events.

## Quick start

```bash
cd apps/api
cp .env.example .env
pip install -r requirements.txt

# PostgreSQL (from repo root)
docker compose up -d db

alembic upgrade head
python seed.py
uvicorn app.main:app --reload
```

- Swagger: http://localhost:8000/docs  
- Health: http://localhost:8000/api/health  

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
  main.py           # FastAPI app, CORS, routers
  config.py         # Settings from .env
  database.py       # Async SQLAlchemy engine
  deps.py           # get_db, CurrentUser, AdminOnly, SuperAdminOnly
  models/           # User, Product, AttendanceEvent
  schemas/          # Pydantic request/response models
  routers/          # auth, users, products, qr, attendance
  services/         # auth, qr, attendance business logic
alembic/            # Migrations (use DATABASE_URL_SYNC)
tests/              # pytest (SQLite in-memory)
seed.py             # Default users + products
```

## Migrations

```bash
alembic upgrade head
alembic revision --autogenerate -m "description"
alembic downgrade -1
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

Before production:

- Set strong `SECRET_KEY` and `QR_SECRET`
- Create additional login users via web **User Management** (`POST /api/users`) — public `/api/auth/register` returns 403
