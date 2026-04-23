# Juku Attendance — API

FastAPI backend for the Time & Attendance system.

## Quick Start (standalone)

```bash
cd apps/api
cp .env.example .env          # edit as needed
pip install -r requirements.txt
# ensure PostgreSQL is running (see docker-compose at repo root)
alembic upgrade head
python seed.py                # optional: create sample users
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## Tests

```bash
pip install aiosqlite         # needed for SQLite test backend
pytest -v
```
