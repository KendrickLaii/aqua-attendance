#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f ".env" ]]; then
  echo "Missing .env. Copy .env.example to .env and set values first."
  exit 1
fi

echo "==> Updating Juku Attendance containers"
docker compose -f docker-compose.prod.yml --env-file .env pull
docker compose -f docker-compose.prod.yml --env-file .env up -d --remove-orphans
docker image prune -f >/dev/null 2>&1 || true
docker compose -f docker-compose.prod.yml --env-file .env ps

APP_DOMAIN="$(grep -E '^APP_DOMAIN=' .env | cut -d'=' -f2- || true)"
API_DOMAIN="$(grep -E '^API_DOMAIN=' .env | cut -d'=' -f2- || true)"

if [[ -n "${APP_DOMAIN}" ]]; then
  echo "App URL: https://${APP_DOMAIN}"
fi
if [[ -n "${API_DOMAIN}" ]]; then
  echo "API health: https://${API_DOMAIN}/api/health"
  echo "Swagger docs: https://${API_DOMAIN}/docs"
fi

echo "Update completed."
