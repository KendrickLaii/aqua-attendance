# Production Deploy Guide

This deploy setup runs:

- `web` image from GHCR
- `api` image from GHCR
- `db` (Postgres)
- `caddy` reverse proxy with automatic HTTPS certificates

## 1) Prerequisites

- Ubuntu server with public IP
- DNS records:
  - `app.yourdomain.com` -> server IP
  - `api.yourdomain.com` -> server IP
- GitHub Actions already pushed images to GHCR

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
mkdir -p ~/juku-attendance
cd ~/juku-attendance
```

Copy these files from this repo's `deploy/` folder:

- `docker-compose.prod.yml`
- `Caddyfile`
- `.env.example` (rename to `.env`)

```bash
cp .env.example .env
```

Then edit `.env`:

- set real domains
- set `WEB_IMAGE` and `API_IMAGE`
- set strong secrets
- set `CORS_ORIGINS` to app domain

## 5) Ensure web build uses your API domain

In GitHub repo settings, set Actions variable:

- `VITE_ATTENDANCE_API_URL=https://api.yourdomain.com/api`

Then run the publish workflow again so the web image is rebuilt with that value.

## 6) Start services

```bash
docker compose -f docker-compose.prod.yml --env-file .env pull
docker compose -f docker-compose.prod.yml --env-file .env up -d
docker compose -f docker-compose.prod.yml --env-file .env ps
```

## 7) Verify

- App: `https://app.yourdomain.com`
- API health: `https://api.yourdomain.com/api/health`
- Swagger docs: `https://api.yourdomain.com/docs`

## 8) Update to a new release

After CI pushes a new image tag:

```bash
docker compose -f docker-compose.prod.yml --env-file .env pull
docker compose -f docker-compose.prod.yml --env-file .env up -d
```

## 9) Reset database (breaking schema changes)

When a release has major DB changes (new tables, removed columns, etc.), you need to wipe the old data and start fresh:

```bash
cd deploy
chmod +x reset-db.sh
./reset-db.sh
```

This will:
1. Stop the API
2. Drop and recreate the database schema
3. Pull the latest images
4. Start the API (runs migrations automatically)
5. Seed default admin accounts and sample products
6. Restart all services

> **Warning**: This deletes ALL existing data. Only use for breaking upgrades or fresh installs.

## 10) One-command scripts

Inside `deploy/`, this repo now includes:

- `first-boot.sh` - first-time setup on a fresh server
- `update.sh` - pull latest images and restart services
- `reset-db.sh` - wipe database and re-seed (for breaking schema changes)

Run once on server:

```bash
cd deploy
chmod +x first-boot.sh update.sh
```

First-time deploy:

```bash
./first-boot.sh
```

Regular update after each CI publish:

```bash
./update.sh
```
