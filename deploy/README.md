# Production Deploy

Scripts and compose file for the production server.

## Prerequisites

- Ubuntu 22.04+ (or any Linux with Docker)
- GitHub Container Registry (GHCR) login for pulling private images
- DNS A records pointing `APP_DOMAIN` and `API_DOMAIN` to the server IP

## Initial setup

```bash
cd deploy/
cp .env.example .env
# Edit .env — set SECRET_KEY, QR_SECRET, POSTGRES_PASSWORD, domains, image tags
./first-boot.sh
```

## Update (new image version)

```bash
cd deploy/
./update.sh
```

## Backup

### Manual

```bash
cd deploy/
./backup.sh
```

Backups are written to `./backups/` and automatically rotated (last 14 kept).

### Cron (recommended)

Add to the server crontab for daily backups at 03:00:

```bash
0 3 * * * cd /path/to/deploy && ./backup.sh >> ./backups/backup.log 2>&1
```

## Restore

```bash
cd deploy/
./restore.sh backups/attendance_20250604_030000.sql.gz
```

**Warning**: restore drops the existing database and recreates it from the backup. The API container is stopped during the operation.

## File reference

| File | Purpose |
|------|---------|
| `docker-compose.prod.yml` | Production services (Caddy, web, API, PostgreSQL) |
| `Caddyfile` | Reverse proxy + HTTPS (auto-TLS) |
| `.env` | Secrets and configuration (not in git) |
| `first-boot.sh` | Install Docker, pull images, start services |
| `update.sh` | Pull latest images and restart containers |
| `backup.sh` | `pg_dump` with gzip + rotation |
| `restore.sh` | Restore from `.sql.gz` backup |
