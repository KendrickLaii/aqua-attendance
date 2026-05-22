# Production Deploy Guide

This stack runs on a single server:

- **web** — Vue admin (nginx) from GHCR
- **api** — FastAPI from GHCR
- **db** — PostgreSQL 16
- **caddy** — HTTPS reverse proxy (`APP_DOMAIN`, `API_DOMAIN`)

Mobile apps are built separately; point them at `https://<API_DOMAIN>/api` (see [apps/mobile/README.md](../apps/mobile/README.md)).

## 1) Prerequisites

- Ubuntu server with public IP
- DNS A records:
  - `app.yourdomain.com` → server IP
  - `api.yourdomain.com` → server IP
- GitHub Actions has published images to GHCR (`docker-publish` workflow on `main`)

## 2) Install Docker on server

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl gnupg lsb-release
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
```

Optional (run docker without sudo):

```bash
sudo usermod -aG docker $USER
newgrp docker
```

## 3) Authenticate to GHCR

Create a GitHub personal access token with `read:packages`.

```bash
echo "YOUR_GITHUB_PAT" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

## 4) Prepare deploy folder

```bash
mkdir -p ~/juku-attendance/deploy
cd ~/juku-attendance/deploy
```

Copy from this repo's `deploy/` folder:

- `docker-compose.prod.yml`
- `Caddyfile`
- `.env.example` → `.env`
- `first-boot.sh`, `update.sh`, `reset-db.sh` (optional but recommended)

```bash
cp .env.example .env
chmod +x first-boot.sh update.sh reset-db.sh
```

Edit `.env`:

| Variable | Set to |
|----------|--------|
| `APP_DOMAIN` | Your app hostname |
| `API_DOMAIN` | Your API hostname |
| `WEB_IMAGE` / `API_IMAGE` | `ghcr.io/<user>/juku-attendance/web:main` etc. |
| `POSTGRES_PASSWORD` | Strong password |
| `SECRET_KEY` / `QR_SECRET` | Strong random values (`openssl rand -hex 32`) |
| `CORS_ORIGINS` | `https://app.yourdomain.com` |

Optional API tuning (if wired through compose env): `SCAN_DEBOUNCE_SECONDS` (default `3` in API code).

## 5) Web image must include your API URL

In GitHub → **Settings → Secrets and variables → Actions → Variables**:

- `VITE_ATTENDANCE_API_URL` = `https://api.yourdomain.com/api`

Re-run the **Publish container images** workflow after changing this so the web bundle calls the correct API.

## 6) Start services

Using scripts (from `deploy/`):

```bash
./first-boot.sh    # first time: Docker install check, pull, up -d
```

Or manually:

```bash
docker compose -f docker-compose.prod.yml --env-file .env pull
docker compose -f docker-compose.prod.yml --env-file .env up -d
docker compose -f docker-compose.prod.yml --env-file .env ps
```

### Seed the database (first install)

`first-boot.sh` does **not** run `seed.py`. After containers are healthy:

```bash
docker compose -f docker-compose.prod.yml --env-file .env exec api python seed.py
```

This creates `admin` / `superadmin` and sample products. **Change passwords immediately** before sharing the system.

For a clean slate with migrations + seed, use `reset-db.sh` (destructive).

## 7) Verify

- App: `https://app.yourdomain.com/attendance/login`
- API health: `https://api.yourdomain.com/api/health`
- Swagger: `https://api.yourdomain.com/docs`

Log in with seeded `admin` / `admin123`, create product QRs under **QR Codes**, then test mobile scan against `https://api.yourdomain.com/api`.

## 8) Update to a new release

After CI pushes new images:

```bash
cd ~/juku-attendance/deploy
./update.sh
```

Or:

```bash
docker compose -f docker-compose.prod.yml --env-file .env pull
docker compose -f docker-compose.prod.yml --env-file .env up -d
```

## 9) Reset database (breaking schema changes)

When a release requires a full schema rebuild:

```bash
cd deploy
./reset-db.sh
```

This will:

1. Stop the API
2. Drop and recreate the database schema
3. Pull latest images
4. Start the API (migrations run on start)
5. Run `seed.py` (default users + sample products)
6. Restart all services

> **Warning:** Deletes **all** data. Use only for breaking upgrades or intentional fresh installs.

## 10) Helper scripts

| Script | Purpose |
|--------|---------|
| `first-boot.sh` | Docker install (if needed), pull images, `up -d` |
| `update.sh` | Pull latest images and restart |
| `reset-db.sh` | Wipe DB, migrate, seed |

## 11) Security before going live

See [KNOWN-GAPS.md](KNOWN-GAPS.md). Minimum checklist:

- [ ] Strong `SECRET_KEY`, `QR_SECRET`, DB password
- [ ] Change seed account passwords
- [ ] Plan to disable public `POST /api/auth/register`
- [ ] HTTPS via Caddy with real domains
- [ ] `CORS_ORIGINS` matches app URL only

## Related

- [CICD-EXPLAINED.md](CICD-EXPLAINED.md) — pipeline overview  
- [README.md](../README.md) — architecture and API reference  
