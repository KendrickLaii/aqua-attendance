# Location photos (v1 — URL only)

This document describes how **location images** work today and what is planned for a later release.

## Current behavior (v1)

Locations store **image URLs only**. The admin UI does **not** upload files to our server.

| Field | Purpose |
|-------|---------|
| `icon_url` | Small icon for lists / map pins |
| `main_photo_url` | Main cover / hero image |
| `detail_photos` | Gallery array: `[{ "url", "caption", "sort_order" }]` |

Images must already be hosted somewhere reachable by URL (e.g. company CDN, S3 public URL, Google Drive public link).

**Database:** `locations.icon_url`, `locations.main_photo_url`, `locations.detail_photos` (JSON).

**Migration note:** Legacy single `photo_url` was migrated to `main_photo_url` in migration `007`.

## Admin UI

**Location Management** (`/attendance/locations`):

- Icon URL
- Main photo URL
- Detail photos — add multiple rows (URL + optional caption)

Scanner and attendance log use the **location record** (name), not the photos.

## Deferred — admin file upload (later)

Planned for a future release; **not implemented yet**.

| Item | Plan |
|------|------|
| Upload from admin | File picker in Location Management instead of pasting URLs |
| Storage (dev) | Optional local `uploads/locations/{id}/` + static serve |
| Storage (prod) | S3 or Cloudflare R2 + signed URLs |
| API | e.g. `POST /api/locations/{id}/photos` with `multipart/form-data` |
| Migration path | Uploaded files get URLs stored in the same `icon_url` / `main_photo_url` / `detail_photos` fields |

Until upload ships, continue using external URLs in v1.

## Deploy

After pulling API changes, migration runs automatically on container start:

```bash
alembic upgrade head   # includes 007_location_multi_photos
```

Or on server: `sudo ./update.sh` (API entrypoint runs migrations).

See also [KNOWN-GAPS.md](./KNOWN-GAPS.md) — **Location photo upload**.
