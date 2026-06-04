# CI/CD & Deployment Explained

A complete guide to understanding what the deployment pipeline does, how all pieces fit together, and how to operate it day-to-day.

This is the "why and how" companion to `docs/DEPLOY.md` (which is the "what commands to run").

---

## 1. The Big Picture

You built a 3-stage pipeline:

```
[YOUR LAPTOP] → [GITHUB] → [GHCR REGISTRY] → [CLOUD SERVER] → [USERS]
   write code     test &      store images     run images       use app
                  build
```

Each stage has a specific role:

| Stage | What it does | Tool |
|-------|--------------|------|
| 1. Code | Write features | Cursor / VS Code |
| 2. CI | Test code automatically | GitHub Actions (`ci.yml`) |
| 3. Build | Make Docker images | GitHub Actions (`docker-publish.yml`) |
| 4. Store | Hold images for download | GHCR (GitHub Container Registry) |
| 5. Deploy | Run images on server | Docker Compose on Lightsail |
| 6. Expose | Show to users via internet | Caddy reverse proxy + public IP |

---

## 2. Each Component

### 2.1 Your laptop = source of truth

- Where you write code
- `git push` → triggers everything else
- You don't deploy from your laptop anymore

### 2.2 GitHub repo = central hub

- Stores code (Git)
- Runs GitHub Actions (automation)
- Stores variables/secrets (e.g. `VITE_ATTENDANCE_API_URL`)

### 2.3 GitHub Actions = robot worker

Two workflows in `.github/workflows/`:

**`ci.yml`** — runs on every PR / push to `main`

- Installs Python deps
- Runs `pytest` tests
- Builds web bundle just to confirm it compiles
- Does **not** push images (sanity check only)

**`docker-publish.yml`** — runs on push to `main` and version tags

- Runs tests again as safety
- Builds API Docker image from `apps/api/Dockerfile`
- Builds Web Docker image from `apps/web/prod.Dockerfile`
- Bakes in `VITE_ATTENDANCE_API_URL` at build time
- Pushes both images to GHCR

### 2.4 GHCR = Docker image library

- Free image hosting from GitHub
- Located at `ghcr.io/<owner>/<repo>/<image>:<tag>`
- Your server pulls images from here
- Tag = version label (e.g. `:main`, `:v1.0.0`, `:sha-abc1234`)

### 2.5 Cloud server (Lightsail) = computer running your app

- Always on, public IP, accessible from internet
- Ubuntu Linux machine in AWS data center
- Has Docker installed → runs your images

### 2.6 Docker Compose = orchestrator

- Reads `deploy/docker-compose.prod.yml`
- Starts 4 containers as one stack:
  - `db` (Postgres)
  - `api` (FastAPI from GHCR)
  - `web` (Vue + Nginx from GHCR)
  - `caddy` (reverse proxy)
- Auto-restarts crashed containers (`restart: unless-stopped`)

### 2.7 Caddy = traffic cop

- Listens on port 80 (public)
- Routes:
  - `/` → `web` container
  - `/api/*` → `api` container
- Without Caddy, browser couldn't reach both web + api on same URL

### 2.8 Postgres = database

- Stores **login users** (`admin` / `superadmin`), **products** (staff/student entities with QR versions), and **attendance events**
- Lives in a Docker volume → data persists across restarts
- **Seed** is not automatic on `first-boot.sh` — run `exec api python seed.py` or `reset-db.sh` (see `docs/DEPLOY.md`)

---

## 3. Full lifecycle of a code change

```
1. Edit a Vue file on laptop
   ↓
2. git push origin main
   ↓
3. GitHub receives push → triggers BOTH workflows
   ↓
4. ci.yml: runs pytest + builds web bundle ✅
   ↓
5. docker-publish.yml:
   a. pytest passes
   b. Build API image → push to ghcr.io/.../api:main
   c. Build Web image → push to ghcr.io/.../web:main
   ↓
6. SSH into Lightsail server
   ↓
7. cd ~/aqua-attendance/deploy && sudo ./update.sh
   ↓
8. update.sh runs:
   a. docker compose pull → fetch latest images
   b. docker compose up -d → restart with new images
   ↓
9. Old containers stop, new ones start
   ↓
10. Users see new version at http://<server-ip>
```

---

## 4. Key concepts

| Concept | Meaning | Why it matters |
|---------|---------|----------------|
| **Container** | Isolated mini-OS running one app | Same behavior on any machine |
| **Image** | Frozen template that creates containers | Versioned + portable |
| **Dockerfile** | Recipe for building an image | Defines OS, deps, code, command |
| **docker compose** | Run multiple containers together | Easier than `docker run` for each |
| **Volume** | Disk storage outside container | Data survives container restart |
| **Registry (GHCR)** | Where images live online | Server can fetch them remotely |
| **PAT** | Personal Access Token | Lets server log into GHCR |
| **Reverse proxy** | Routes incoming traffic | Hides multiple services behind 1 URL |
| **Env vars (`.env`)** | Config without code change | Same image, different settings |
| **Build args vs env** | Build-time vs run-time settings | `VITE_*` baked at build; secrets at run |
| **Migration (Alembic)** | Apply schema changes to DB | Code & schema stay in sync |
| **Seed** | Insert initial demo data | Empty DB → usable demo |

---

## 5. My specific setup (current values)

| Item | Value |
|------|-------|
| Cloud provider | AWS Lightsail |
| Region | `ap-northeast-1` (Tokyo) |
| OS | Ubuntu 24.04 LTS |
| Plan | $7/mo (1 GB RAM) — first 90 days free |
| Static IP | `<your-server-ip>` |
| Domain | (none yet — using IP only) |
| HTTPS | Not yet (no domain) |
| GHCR images | `ghcr.io/kendricklaii/aqua-attendance/api:main` and `/web:main` |
| Reverse proxy | Caddy (HTTP-only path mode) |
| Public URL | `http://<your-server-ip>` |
| API docs | `http://<your-server-ip>/api/docs` |

---

## 6. Day-to-day operation

### Push a new code change

On laptop:

```bash
git add .
git commit -m "your message"
git push origin main
```

Wait for **Publish container images** workflow → green ✅

### Deploy the new version to server

SSH into Lightsail → run:

```bash
cd ~/aqua-attendance/deploy
sudo ./update.sh
```

### Check server status

```bash
sudo docker compose -f docker-compose.prod.yml --env-file .env ps
```

All 4 containers should show `Up`.

### See logs (when something is wrong)

```bash
sudo docker compose -f docker-compose.prod.yml --env-file .env logs api --tail=50
sudo docker compose -f docker-compose.prod.yml --env-file .env logs web --tail=50
sudo docker compose -f docker-compose.prod.yml --env-file .env logs caddy --tail=50
sudo docker compose -f docker-compose.prod.yml --env-file .env logs db --tail=50
```

### Restart everything

```bash
cd ~/aqua-attendance/deploy
sudo docker compose -f docker-compose.prod.yml --env-file .env restart
```

### Seed users + sample products (empty or reset DB)

```bash
sudo docker compose -f docker-compose.prod.yml --env-file .env exec api python seed.py
```

Creates `admin`, `superadmin`, and products `STAFF-001`, `STU-001`, etc. Change passwords after seeding.

---

## 7. Files I created / matter

```
aqua-attendance/
├── .github/
│   └── workflows/
│       ├── ci.yml                # Run tests on PR/main
│       └── docker-publish.yml    # Build & push images to GHCR
├── apps/
│   ├── api/Dockerfile            # How to build API image
│   └── web/prod.Dockerfile       # How to build web image
├── deploy/
│   ├── docker-compose.prod.yml   # Run stack on server
│   ├── Caddyfile                 # Reverse proxy config
│   ├── .env.example              # Template for server env vars
│   ├── first-boot.sh             # First-time server setup
│   └── update.sh                 # Pull + restart on new release
└── docs/
    ├── DEPLOY.md                 # Step-by-step deploy commands
    └── CICD-EXPLAINED.md         # This file
```

---

## 8. Common problems & fixes

### API container keeps restarting → `ModuleNotFoundError: No module named 'app'`

Add `PYTHONPATH: /app` under `api.environment:` in `deploy/docker-compose.prod.yml`.

### Alembic tries `127.0.0.1:5432` instead of `db`

Add a sync URL alongside the async one:

```yaml
DATABASE_URL_SYNC: postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
```

### Login returns "Invalid email or password" (MSW intercepts)

In `apps/web/src/plugins/fake-api/index.ts` skip MSW in production:

```ts
if (import.meta.env.PROD || import.meta.env.VITE_USE_MSW === 'false')
  return
```

Then commit, wait for publish, and `sudo ./update.sh`. Hard refresh browser (`Ctrl+Shift+R`).

### Login still fails after fix → service worker cached

Browser DevTools → Application → Service Workers → Unregister, then refresh.

### "permission denied" on `docker compose ps`

Either use `sudo docker compose ...` or:

```bash
sudo usermod -aG docker $USER
exit  # then SSH back in
```

### Image pull fails with `your-org-or-user/aqua-attendance/...: not found`

`.env` still has the placeholder. Set:

```env
WEB_IMAGE=ghcr.io/<your-username-lowercase>/aqua-attendance/web:main
API_IMAGE=ghcr.io/<your-username-lowercase>/aqua-attendance/api:main
```

### SSH disconnects randomly during long commands

Out of memory. Add swap:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 9. Why this setup is professional

What you built mirrors how real companies deploy:

- Automated tests = catch bugs before deploy
- Image-based deploy = reproducible
- Versioned releases = can roll back
- Single-command deploy (`./update.sh`)
- Reverse proxy ready for HTTPS
- Persistent volumes = data safety
- Secrets in env, not code

Common next-level additions:

- Multi-stage envs (staging + production)
- Auto-deploy on push (SSH webhook in workflow)
- Monitoring (logs, metrics, alerts)
- Backups (DB snapshots)
- Real domain + HTTPS via Caddy auto-TLS
- CDN for static assets

---

## 10. What to do next (suggestions)

1. **Add a real domain** — Caddy auto-issues HTTPS certs (free)
2. **Auto-deploy** — workflow SSH-es into server, runs `./update.sh`
3. **DB backups** — daily Postgres dump to S3 or local
4. **Monitoring** — install something like `dozzle` to view logs in browser
5. **Staging environment** — same setup on a 2nd VM for testing before prod
6. **Strong passwords** — change all seeded demo passwords before sharing
7. **Harden API** — disable open `/api/auth/register` before public launch ([KNOWN-GAPS.md](KNOWN-GAPS.md))
8. **Mobile** — set `EXPO_PUBLIC_API_URL` to production API when building the Expo app (not part of this compose stack)

---

## TL;DR mental model

> GitHub builds images → server runs them.
> CI/CD = automation. Docker = packaging. Caddy = routing.
> You just connected the dots.

The pipeline you built is the same flow used by Netflix, Spotify, GitHub itself (smaller scale, same shape).
