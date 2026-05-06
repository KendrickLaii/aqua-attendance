# AQUA-Attendance

## Quick Start

Run these commands from the repository root:

```bash
# 1) Start database
docker compose up -d db

# 2) Start API (new terminal)
cd apps/api
python -m uvicorn app.main:app --reload

# 3) Start Web (new terminal)
cd apps/web
npm run dev
```

## URLs

- API Health: `http://127.0.0.1:8000/api/health`
- Web Login: `http://localhost:5173/attendance/login`
  - If `5173` is occupied, Vite may use `5174`/`5175`/etc.

## First-Time Setup

```bash
# API setup
cd apps/api
pip install -r requirements.txt
python -m alembic upgrade head
python seed.py

# Web setup
cd ../web
npm install
```

## Stop Services

- In API/Web terminals: press `Ctrl + C`
- Stop database:

```bash
docker compose down
```
