#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f ".env" ]]; then
  echo "Missing .env. Copy .env.example to .env and set values first."
  exit 1
fi

COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env"

echo "============================================"
echo "  WARNING: This will DELETE ALL data and"
echo "  recreate the database from scratch."
echo "============================================"
read -rp "Are you sure? (type YES to confirm): " confirm
if [[ "$confirm" != "YES" ]]; then
  echo "Aborted."
  exit 0
fi

echo ""
echo "==> Step 1: Stopping API container"
$COMPOSE stop api

echo "==> Step 2: Resetting database schema"
$COMPOSE exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO $POSTGRES_USER;"'

echo "==> Step 3: Pulling latest images"
$COMPOSE pull

echo "==> Step 4: Starting API (runs alembic upgrade head automatically)"
$COMPOSE up -d api
echo "    Waiting for API to be ready..."
sleep 10

echo "==> Step 5: Seeding default data"
$COMPOSE exec -T api python seed.py

echo "==> Step 6: Starting all services"
$COMPOSE up -d
$COMPOSE ps

echo ""
echo "============================================"
echo "  Database reset complete!"
echo ""
echo "  Default login accounts:"
echo "    admin      / admin123  (admin)"
echo "    superadmin / super123  (superadmin)"
echo ""
echo "  Sample products:"
echo "    STAFF-001  Tanaka Sensei   (staff)"
echo "    STAFF-002  Yamamoto Sensei (staff)"
echo "    STU-001    Suzuki Taro     (student)"
echo "    STU-002    Yamada Hanako   (student)"
echo "============================================"
