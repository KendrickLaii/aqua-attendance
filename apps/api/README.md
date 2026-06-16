# AQUA Attendance — API

FastAPI 後端：登入使用者、Product（教職員/學生）、Profile（staff_profiles / student_profiles）、簽名 QR token、出勤事件、場地管理、通知、薪資、稽核。

## 日常開發

推薦模式：**Postgres 跑在 Docker**，**API 在本機**。

| 步驟 | 指令 | 時機 |
|------|------|------|
| 啟動 DB | `docker compose up -d db`（從 repo root）| 重開機後，或 `docker compose ps db` 未運行時 |
| 啟動 API | `python -m uvicorn app.main:app --reload`（從 `apps/api`）| 每次開發 |
| 啟動 API（手機連線）| `python -m uvicorn app.main:app --reload --host 0.0.0.0` | Expo Go 使用 LAN IP 時 |
| 跑 migration | `python -m alembic upgrade head` | 拉取新 migration 後 |
| 種子資料 | `python seed.py` | 選用 — 產生範例 users / products + profiles |

API 預設連線到 `localhost:5432`（`config.py` / `.env.example`）。DBeaver 使用相同 host/port/credentials — 只需 DB container 運行即可。

完整三 terminal 流程請見根目錄 [README.md](../../README.md)。

## 首次設定

```bash
cd apps/api
cp .env.example .env
pip install -r requirements.txt

# PostgreSQL（從 repo root；需 Docker Desktop 運行中）
docker compose up -d db

python -m alembic upgrade head
python seed.py
python -m uvicorn app.main:app --reload
```

- Swagger：http://localhost:8000/docs
- Health：http://localhost:8000/api/health（含 DB 連線檢查）

## 種子資料

```bash
python seed.py
```

產生：

- Users：`admin` / `admin123`、`superadmin` / `super123`
- Products + Profiles：
  - `STAFF-001`（full_time / Math）
  - `STAFF-002`（part_time / English）
  - `STU-001`（Tokyo High / 3-A）
  - `STU-002`（Osaka Middle / 2-B）

## 目錄結構

```
app/
  main.py           # FastAPI app、CORS、routers、/api/health
  config.py         # 從 .env 載入設定
  database.py       # Async SQLAlchemy engine
  deps.py           # get_db、CurrentUser、AdminOnly、SuperAdminOnly
  models/           # User、Product、StaffProfile、StudentProfile、AttendanceEvent、
                    # Location、RefreshToken、Notification、AttendanceSummary、
                    # PayrollRecord、AuditLog
  schemas/          # Pydantic request/response models
  routers/          # auth、users、products、locations、qr、attendance、
                    # student-profiles、staff-profiles
  services/         # auth、qr、attendance、product 業務邏輯
  utils/            # 搜尋輔助（safe ILIKE）
alembic/            # Migrations（使用 DATABASE_URL_SYNC）
tests/              # pytest（SQLite in-memory）
seed.py             # 預設 users + products
```

## Migrations

```bash
python -m alembic upgrade head
python -m alembic revision --autogenerate -m "描述"
python -m alembic downgrade -1
```

Alembic 使用 `DATABASE_URL_SYNC`（`postgresql+psycopg://...`）。App 本身使用 async `DATABASE_URL`。

## 測試

```bash
pip install -r requirements.txt
pytest -v
pytest tests/test_auth.py -v
pytest tests/test_scan.py -v
```

測試覆寫 DB 為 SQLite（`tests/conftest.py`）；不會執行 Alembic。

## Docker

從 repo root：

```bash
docker compose up -d    # db + api（container 啟動時自動跑 migration）
```

環境變數與安全說明請見根目錄 [README.md](../../README.md)。

## 生產部署

API image 由 `Dockerfile` 建置，`.github/workflows/docker-publish.yml` 推送到 GHCR。
伺服器部署請見 [docs/PROJECT-HANDBOOK.md](../../docs/PROJECT-HANDBOOK.md)。

生產 / UAT 部署前：

- 設定 `ENV=production` 與獨立的 `SECRET_KEY` / `QR_SECRET`（各執行 `openssl rand -hex 32`）— 詳見 [docs/PROJECT-HANDBOOK.md](../../docs/PROJECT-HANDBOOK.md)
- API 會在生產密鑰為佔位符或短於 32 字元時**拒絕啟動**
- 部署後執行 `python -m alembic upgrade head`（含 `refresh_tokens`、`locations.name_en` NOT NULL）
- 透過 Web **User Management** 建立額外登入使用者 — 公開的 `/api/auth/register` 回傳 403
- 登出時 client 應呼叫 `POST /api/auth/logout` 並帶 `refresh_token`；過期 refresh row 會在 login、refresh、logout 時自動清理
