# Release 2026-05 — Web polish + dashboard stats

Ship checklist for **`main`** → GHCR → Lightsail (`deploy/update.sh`).

## Included in this release

### Web (attendance admin)

| Area | Change |
|------|--------|
| P1 | Login `?to=` redirect; `formatApiError` on load errors |
| P1 | Dashboard today event total via `X-Total-Count` |
| P2 | UserProfile attendance menu; Web Scanner (QR dialog entry only) |
| P2 | Shared `DialogFooter`; dialog unification P1–P3 (`AttendanceConfirmDialog`, `AttendanceFormDialog`, `AttendanceInfoDialog`) |
| P3 | Product checked-in/out filter (API + UI) |
| P3 | List pagination — products, users, locations |
| Fix | Dashboard check-in/out counts — `GET /api/attendance/stats` (accurate when >200 events/day) |
| Refactor | `locations.vue` split — `LocationCard`, tab components, `locationHours` / `locationPhotos` utils |
| Fix | Location create when Chinese name empty (`name_zh` defaults from English) |
| Feature | **Staff employment type** — `part_time` / `full_time` on products (API + UI) |
| Feature | **QR Codes** — QR shown on each card; multi-select + **Print selected** |

### API

| Area | Change |
|------|--------|
| New | `GET /api/attendance/stats` — aggregate day counts for dashboard |
| Enhancement | `X-Total-Count` + `attendance_status` filter on products list |
| New | Product `employment_type` (`part_time` \| `full_time`); list filter `?employment_type=` |
| Migration | **`008_product_employment_type`** — adds `products.employment_type` column |

### Not in this release (still open)

See [KNOWN-GAPS.md](./KNOWN-GAPS.md): dual cookies, mobile Scan tab roles, template bloat, location photo upload, etc.

---

## Pre-deploy checklist

Mark before running `update.sh` on the server.

- [ ] **GitHub Actions** — [CI](https://github.com/KendrickLaii/aqua-attendance/actions) green on latest `main` commit
- [ ] **Publish container images** — workflow green; images at `ghcr.io/kendricklaii/aqua-attendance/{api,web}:main`
- [ ] **`VITE_ATTENDANCE_API_URL`** — GitHub Actions variable matches prod API URL (IP-only: `http://<server-ip>/api`)
- [ ] **Server `.env`** — `SECRET_KEY`, `QR_SECRET`, `POSTGRES_PASSWORD` not placeholders (see [DEPLOY.md](./DEPLOY.md))
- [ ] **GHCR login** on server still valid (`docker login ghcr.io`)

## Deploy

```bash
cd ~/aqua-attendance/deploy
sudo ./update.sh
```

**Migration required:** API container runs Alembic on start — `008` adds `employment_type` to `products`. Existing staff rows stay `NULL` until edited in Product Management.

If API fails after pull, check logs: `docker compose -f docker-compose.prod.yml --env-file .env logs api --tail=50`

## Post-deploy verification

- [ ] `curl -s http://<host>/api/health` → `{"status":"ok"}`
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://<host>/api/attendance/stats` → **403** (not 404)
- [ ] Login at `/attendance/login` — dashboard loads without console errors
- [ ] Dashboard — Check-ins / Check-outs Today show numbers; Recent Activity caption correct
- [ ] Products — attendance filter + pagination; staff **Employment** (part/full-time)
- [ ] Locations — create / edit / delete (tabbed form)
- [ ] QR Codes — QR visible on cards; select several → **Print selected** (allow pop-ups)
- [ ] QR Codes — **Rotate / copy** still works from card footer
- [ ] Change default seed passwords if still using `admin123`

## Rollback

```bash
cd ~/aqua-attendance/deploy
# Pin images to previous SHA tag from GHCR, then:
docker compose -f docker-compose.prod.yml --env-file .env pull
docker compose -f docker-compose.prod.yml --env-file .env up -d
```

Or re-run workflow on an earlier commit and `update.sh` again.
