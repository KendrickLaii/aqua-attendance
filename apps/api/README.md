# AQUA Attendance — API

FastAPI 後端：登入使用者、Unit（教職員/學生）、Profile（staff_profiles / student_profiles）、簽名 QR token、出勤事件、據點（locations）、通知、薪資、稽核、課程目錄、學費發票。

## 日常開發

推薦模式：**Postgres 跑在 Docker**，**API 在本機**。

| 步驟 | 指令 | 時機 |
| ------ | ------ | ------ |
| 啟動 DB | `docker compose up -d db`（從 repo root） | 重開機後，或 `docker compose ps db` 未運行時 |
| 啟動 API | `python -m uvicorn app.main:app --reload`（從 `apps/api`） | 每次開發 |
| 啟動 API（手機連線） | `python -m uvicorn app.main:app --reload --host 0.0.0.0` | Expo Go 使用 LAN IP 時 |
| 跑 migration | `python -m alembic upgrade head` | 拉取新 migration 後 |
| 種子資料 | `python seed.py` | 選用 — 範例 users / units / profiles；完整 seed 含 **彙總測試資料** |
| 僅彙總 seed | `python seed.py --summaries` | 選用 — 2026-05 固定 + 2026-06/07 bulk（需已有 units） |

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

- Swagger：<http://localhost:8000/docs>
- Health：<http://localhost:8000/api/health>（含 DB 連線檢查）

## 種子資料

```bash
python seed.py              # users + locations + units + profiles + summaries
python seed.py --users-only # 僅 users
python seed.py --summaries  # 僅 attendance_summaries（需已有 units）
```

產生：

- Users：帳密見 `seed.py`（角色 `admin`、`superadmin`）。**勿將預設密碼寫入公開文件；生產環境請立即修改。**
- Locations：`HK-CWB` / `HK-MK`（結構化 `business_hours`，平日 09:00–18:00，供 OT 判斷）
- Units + Profiles：
  - Staff 含薪資欄位 `pay_type` / `hourly_rate` / `monthly_salary` / `ot_multiplier`（供 Payroll Generate）
    - full_time（如 `STAFF-001`）：`monthly` + 時薪（供 OT）
    - part_time（如 `STAFF-002`）：`hourly`
  - Students：學校 / 班級 / `student_id`
  - 以及 `STAFF-003`–`006`、`STU-003`–`008`（bulk 測試用）
- **Attendance summaries**（測試用）：
  - 2026-05：固定少數列（含 `regular_slots` / `ot_slots`）
  - 2026-06、2026-07：大量 bulk 列（**無**對應打卡事件；slots = hours × 4）

彙總與 Generate 行為見 [docs/attendance-summaries.md](../../docs/attendance-summaries.md)。學費發票見 [docs/PROJECT-HANDBOOK.md](../../docs/PROJECT-HANDBOOK.md) §1.10。

## 目錄結構

```text
app/
  main.py           # FastAPI app、CORS、routers、/api/health
  config.py         # 從 .env 載入設定
  database.py       # Async SQLAlchemy engine
  deps.py           # get_db、CurrentUser、AdminOnly、SuperAdminOnly
  models/           # User、Unit、StaffProfile、StudentProfile、AttendanceEvent、
                    # Location、RefreshToken、Notification、AttendanceSummary、
                    # PayrollRecord、AuditLog、CourseSpu、CourseSku、CourseEnrollment、
                    # TuitionInvoice、TuitionInvoiceLine
  schemas/          # Pydantic request/response models
  routers/          # auth、users、units、locations、qr、attendance、
                    # student-profiles、staff-profiles、notifications、
                    # attendance-summaries、payroll-records、audit-logs、auto-checkout、
                    # course-spus、course-skus、course-enrollments、tuition-invoices
  services/         # auth、qr、attendance、unit、overtime、auto_checkout、
                    # summary_generator、payroll_generator、tuition_invoice_generator
  utils/            # 搜尋輔助（safe ILIKE）
alembic/            # Migrations（使用 DATABASE_URL_SYNC）
tests/              # pytest（SQLite in-memory）
seed.py             # 預設 users + units + locations
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

## 相關文件

- [docs/attendance-summaries.md](../../docs/attendance-summaries.md) — 彙總 / 薪資月度流程、Generate、seed FAQ
- [docs/database-changes.md](../../docs/database-changes.md) — 資料庫設計 SSOT（ER 圖、課程、學費發票）
- [docs/known-gaps.md](../../docs/known-gaps.md) — 後端審查與修復計畫（架構評價、已知缺口）
- [docs/PROJECT-HANDBOOK.md](../../docs/PROJECT-HANDBOOK.md) — 部署、CI/CD、運維、課程與學費發票

---

生產 / UAT 部署前：

- 設定 `ENV=production` 與獨立的 `SECRET_KEY` / `QR_SECRET`（各執行 `openssl rand -hex 32`）— 詳見 [docs/PROJECT-HANDBOOK.md](../../docs/PROJECT-HANDBOOK.md)
- API 會在生產密鑰為佔位符或短於 32 字元時**拒絕啟動**
- 部署後執行 `python -m alembic upgrade head`（目前 head **036**：課程、SKU `billing_unit`、學費發票）
- 透過 Web **User Management** 建立額外登入使用者 — 公開的 `/api/auth/register` 回傳 403
- 登出時 client 應呼叫 `POST /api/auth/logout` 並帶 `refresh_token`；過期 refresh row 會在 login、refresh、logout 時自動清理
