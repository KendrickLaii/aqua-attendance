# 已知缺口（Known Gaps）

> 最後更新：2026-07-21（已審查：2026-07-21）
> 統合來源：`project-handbook.md` §5、`attendance-summaries.md`、`database-changes.md`
> 本文件為**程式碼層級**已知問題的單一參考來源（SSOT）。文件本身的問題見 [docs-audit.md](docs-audit.md)。

---

## 嚴重度說明

| 標記 | 含義 |
|------|------|
| 🔴 High | 上線前或盡快處理 |
| 🟡 Medium | 上線前應補 |
| 🟢 Low | 可延後 |
| ⚠️ 設計取捨 | 已知但刻意接受的 trade-off |

---

## 1. 🔴 High

| # | 項目 | 狀態 |
|---|------|------|
| H1 | `recorded_at` 無索引 | ✅ 已修（Migration 013） |
| H2 | Mobile refresh 競態 | ✅ 已修（single-flight） |
| H3 | Web refresh 競態 | ✅ 已修（single-flight） |
| H4 | Rate limit 使用記憶體儲存 | ✅ 已修（Redis backend） |
| H5 | 掃描競態保護 | ✅ 已修（`SELECT FOR UPDATE`） |

### #H6 午休（break）未從工時扣除

- **位置**：`apps/api/app/services/overtime.py:calculate_workday`、`apps/api/app/services/summary_generator.py`
- **問題**：`calculate_workday` 只計算 `first_check_in → last_check_out` 總時長，**未扣除午休**；`summary_generator` 雖有 `lunch_minutes` 參數但**從未使用**，`total_break_minutes` 永遠寫入 `0`。
- **影響**：9:00–18:00 出勤會被算成 9 小時 regular（含午休），staff 薪資會**多算**。
- **建議**：在 `calculate_workday` 加入 break 扣除邏輯（例如超過 X 小時自動扣 60 分鐘，或依 `location` 設定），並寫入 `total_break_minutes`。上線前必修。

---

## 2. 🟡 Medium — 部署與維運

### #M1 Compose 無 API/Web healthcheck

- **位置**：`deploy/docker-compose.prod.yml`
- **問題**：僅 `db` 有 healthcheck；`/api/health` 已存在但未使用。
- **建議**：為 api/web 加 healthcheck，Caddy `depends_on` 改 `condition: service_healthy`。

### #M2 API Dockerfile 以 root 執行、無 HEALTHCHECK

- **位置**：`apps/api/Dockerfile`
- **問題**：無 `USER`、無 `HEALTHCHECK`。
- **建議**：加非 root user 與 `HEALTHCHECK` curl `/api/health`。

### #M3 無日誌 / 監控 / 追蹤

- **問題**：無 `logging`/`structlog` 設定、無 Sentry、無 request ID。
- **建議**：加結構化 logging + request ID middleware；接 Sentry（可選）。

### #M4 CSV 匯出非真串流

- **位置**：`apps/api/app/services/attendance.py:271-307`
- **問題**：已改為分頁載入（`CSV_EXPORT_PAGE_SIZE`），但仍將所有事件累積到 `all_events` list 後再一次寫入 `StringIO`，非真正串流。
- **現況**：已改善（分頁讀取 + 上限 `CSV_EXPORT_MAX_ROWS`），但 `StringIO` 仍會佔用與資料量成正比的記憶體。
- **建議**：改為逐頁 yield 寫入 generator，真正串流。

### #M5 無 mobile CI ✅ 已修（2026-07-22）

- **位置**：`.github/workflows/ci.yml`（`mobile-typecheck` job）
- **原問題**：`eas.json` 已存在但無 workflow 觸發任何 mobile 檢查。
- **現況**：已加 `mobile-typecheck` job，於 PR / push main 時跑 `npm run typecheck`（`tsc --noEmit`）。
- **後續（可選）**：mobile 尚無 ESLint 設定；若要 lint 需先建立 eslint config。EAS Build 觸發仍可延後（免費額度有限，非必要）。

---

## 3. 🟡 Medium — 安全與架構

### #M6 Refresh token 存非 HttpOnly cookie

- **位置**：`apps/web/src/utils/attendanceSession.ts`
- **問題**：Web 用 `useCookie('refreshToken')`（JS 可讀），大型模板依賴樹增加 XSS 面。Mobile 用 SecureStore 已 OK。
- **建議**：改後端設 HttpOnly + Secure + SameSite cookie。

### #M7 CORS 設定過寬

- **位置**：`apps/api/app/main.py`
- **問題**：`allow_methods=["*"], allow_headers=["*"]`。
- **建議**：生產環境收斂為白名單。

### #M8 bcrypt 72-byte 截斷

- **位置**：`apps/api/app/services/auth.py`
- **問題**：passlib bcrypt 對 >72 bytes 靜默截斷。
- **建議**：在 schema 加密碼長度上限驗證。

### #M9 測試覆蓋缺口

- **問題**：58 項測試（7 個測試檔案），RBAC 僅部分；無 refresh 競態測試；Web/Mobile 零測試。
- **建議**：補完整 RBAC 矩陣 + 並發 refresh 測試；Web 加 Vitest 關鍵路徑。

---

## 4. 🟡 Medium — Summaries / Payroll

### #M10 統計卡僅加總當前分頁 ✅ 已修（2026-07-22）

- **位置**：`apps/web/src/pages/attendance/summaries.vue`、`payroll.vue`
- **原問題**：統計卡加總**當前分頁**的列，非全月 DB 總計。
- **現況**：兩頁皆改用專用統計端點（全月 DB 聚合，不受分頁影響）：
  - Summaries：`GET /attendance-summaries/overview/stats`（`getSummaryOverviewStats`）
  - Payroll：`GET /payroll-records/stats`（`getPayrollStats`）— gross/net/approved/paid/pending 全月加總

### #M11 Generate orphan 清理（已實作，保留 seed）

- **位置**：`apps/api/app/services/summary_generator.py`
- **現況**：Generate 會刪除當月無可用 check-in 的彙總列；**不刪** `calculation_method=seed`（`python seed.py --summaries`）。若同日後來有真實事件，會被 upsert 成 `standard` 並可再參與 orphan 清理。

### #M12 無 cron 自動月度 Generate

- **問題**：Summaries 與 Payroll 的 Generate 均需手動觸發。
- **建議**：月度 Generate cron + 結構化 logging。

### #M13 Holiday 無獨立 chip

- **位置**：`apps/web/src/pages/attendance/summaries.vue`
- **問題**：Holiday 僅在狀態欄顯示文字，無獨立篩選 chip（如同 Weekend chip）。
- **建議**：新增 Holiday chip 前端篩選。

### #M14b Attendance timezone = Asia/Hong_Kong（已對齊）

- **現況（2026-07-17）**：後端共用 `app/attendance_tz.py`（掃描跨日、OT 關門、日界 23:59、Generate 分日）；Web / Mobile 篩選與顯示用同一時區。舊 Day-end 若曾寫 **UTC 23:59**，在 Log「Today」可能落在隔天早上——用 All time + Source=Auto checkout 可查。
- **勿再假設**：`.date()` on UTC、ISO `slice(0,16)`、或 `date.today()` 等於出勤日。

### #M14 Auto checkout **不是**完整自動版

> ⚠️ 開發者常見誤解：看到 `auto_checkout` 服務、Dashboard「Day-end checkout」、或 Generate 會補 23:59 簽退，就以為「每晚會自動跑完」。**目前沒有排程；上線前不可當成已完成的自動系統。**

| 已實作 | 未實作 |
|--------|--------|
| 共用 helper：`make_day_boundary_checkout_event`（23:59、`source=auto_checkout`） | **無** 23:59 cron / scheduler / worker |
| 手動 `POST /api/auto-checkout/run`（Dashboard Day-end） | **無** 00:00 自動把 `attendance_status` 重設為 `checked_out` |
| Generate 對**過去日期**缺簽退時補日界 `check_out` | 關門時間（`business_hours.close`）**不會**觸發簽退（只用於 OT / UI 標籤） |
| `GET /api/auto-checkout/status` + 仍 checked_in 清單 | 隔夜仍 `checked_in` 會一直掛著，直到手動 Day-end 或隔日 Generate 回填 |

- **位置**：`apps/api/app/services/auto_checkout.py`、`routers/auto_checkout.py`、Dashboard Day-end、`summary_generator.py`
- **設計意圖**（見 [database-changes.md](database-changes.md)）：日界 23:59 兜底，非關門時間；避免忘記簽退造成 OT 虛高。
- **現況**：邏輯與手動／Generate 路徑已對齊，但**不會自己跑**。Router 註解裡「Normally run by a scheduled job」是目標態，不是現況。
- **建議**：部署後加排程（例如每天 23:59 呼叫 `POST /api/auto-checkout/run`，或獨立 worker）；可選再補 00:00 status 重置 job。文件與 UI 文案應持續標明「手動／回填」，避免當成完整自動。

### #M15 Payroll 必須先手動 Generate summaries

- **位置**：`apps/api/app/services/payroll_generator.py`
- **問題**：Payroll generate 只讀 `attendance_summaries`。如果 admin 忘記先 Generate summaries，Payroll 會用**過期彙總**算薪水，且沒有警告。
- **建議**：Payroll generate 前先自動觸發 summary generate（同交易），或比對 events 最新時間 vs summaries `updated_at`，過期回傳警告。

### #M16 Void 事件後 summary 不會自動重算

- **位置**：`apps/api/app/routers/attendance.py`（`POST /api/attendance/{event_id}/void`）
- **問題**：作廢 event 只寫 audit log 與 `voided_at`；該 product 該日的 `attendance_summaries` 要等到下次手動 Generate 才更新。期間 UI 顯示舊數字。
- **建議**：void endpoint 順便重算該 product 該日的 summary（單日重算很便宜）。

### #M17 Generate 端點無互斥鎖

- **位置**：`apps/api/app/routers/attendance_summaries.py`、`routers/payroll_records.py`
- **問題**：Summaries / Payroll generate 都是「select 再 upsert」；兩個 admin 同時按會競態，可能噴 `IntegrityError` 或重複計算。
- **建議**：改用 PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`，或以 Redis/advisory lock 互斥。單一塾使用下機率低，但修法便宜。

### #M18 `products.attendance_status` 非正規化狀態可能與 events 不一致

- **位置**：`apps/api/app/services/attendance.py:_next_event_type`、`models/product.py`
- **問題**：scan 的 check_in/check_out 推斷依賴 `products.attendance_status`。void、manual correction、隔夜未簽退後，此欄位可能與實際 events 不一致（雖有 `recompute_product_attendance_status` 但不是所有路徑都會觸發）。
- **建議**：確保所有寫入/作廢 events 的路徑都呼叫 recompute，或改用「查最近一筆非作廢 event」來決定下一個動作。

---

## 5. 🟢 Low — 前端改善

### #L1 CASL admin 與 superadmin 權限相同

- **位置**：`apps/web/src/utils/attendanceCasl.ts`
- **問題**：兩者都回 `manage all`，前端無區分（後端已正確強制）。
- **建議**：前端區分 superadmin-only 功能（如刪除用戶）。

### #L2 硬刷新 CASL ability 短暫遺失

- **位置**：`apps/web/src/composables/useAttendanceCaslSync.ts`
- **問題**：靠 `watch(immediate)` 修復，但時序脆弱。
- **建議**：在 router guard 或 app 啟動時也同步一次。

### #L3 AQUA 模板死代碼

- **位置**：`apps/web/src/pages/apps/`、`src/views/demos/`
- **問題**：大量未使用 demo 路由與元件殘留。
- **建議**：逐步刪除未使用路由（tree-shaking 已處理打包體積，非緊急）。

### #L4 列表端點無排序參數

- **位置**：多個 list endpoint
- **問題**：固定排序（如 `created_at desc`），未開放 client 控制。
- **建議**：加入 `sort_by` / `sort_order` query 參數。

---

## 6. 🟢 Low — API 改善

### #L5 QR 錯誤訊息洩漏例外細節

- **位置**：`apps/api/app/routers/attendance.py`
- **問題**：`detail=f"Invalid QR: {e}"` 回傳例外內容。
- **建議**：回傳通用訊息，細節只記 log。

### #L6 `recorded_by_user_id` 無 FK 載入

- **位置**：CSV/列表查詢
- **問題**：只存 UUID，未 join user 顯示姓名。
- **建議**：查詢時 eager load user 關係。

### #L7 Seed 可選 `--no-summaries`

- **位置**：`apps/api/seed.py`
- **問題**：`python seed.py` 預設寫入 summaries。已有 `--summaries` flag（僅 summaries），但無反向的 `--no-summaries` flag（完整 seed 但跳過 summaries）。
- **建議**：加 `--no-summaries` flag。

---

## 7. ⚠️ 設計取捨（已知且接受）

| # | 項目 | 說明 |
|---|------|------|
| D1 | QR token 無過期 | 設計上無 `exp`，靠 `qr_token_version` 手動輪替。洩漏後在輪替前一直有效。 |
| D2 | 登入撤銷所有 refresh token | `login` 呼叫 `revoke_all_refresh_tokens_for_user` → 單一 session，手機登入會踢掉 Web。 |
| D3 | Mobile 無離線處理 | 所有網路失敗直接顯示 "Cannot reach API"。除非有實際斷網需求，否則不優先。 |
| D4 | Weekend 篩選為前端 | 明細層 Weekend chip 為前端篩選已載入列；Complete/Incomplete 走 API `is_complete`。 |

---

## 8. 已完成（從各文件移出）

以下項目原列於各文件的已知缺口，現已修復完成，保留以供追溯：

| 來源 | 項目 | 完成日期 |
|------|------|----------|
| project-handbook §5 | #1–#5 High（索引、refresh 競態、rate limit、掃描競態） | 2026-06 |
| project-handbook §5 | #13 API 錯誤格式不一致 | 2026-07 |
| 後端審查 | StaffProfile 多 FK 歧義 | 2026-06 |
| 後端審查 | profile `uselist=False` | 2026-06 |
| 後端審查 | `employment_type` 遷移至 `staff_profiles` | 2026-06 |
| 後端審查 | notifications / summaries / payroll / audit_logs 端點 | 2026-06 |
| 後端審查 | OT 計算（15 分鐘槽） | 2026-06 |
| 後端審查 | auto_checkout **helper + 手動 API + Generate 回填**（**非** cron；見 #M14） | 2026-06 / 2026-07 |
| 後端審查 | `notification.extra_data` 改 JSON | 2026-06 |
| attendance-summaries | Payroll 薪資率模型（slots + 薪資率計算 + 快照凍結） | 2026-07 |
| 前端對齊計畫 | Batch 1–4 全部（產品多型、Summaries、Payroll、Notifications、Audit、Mobile） | 2026-07 |
| API | `POST /api/attendance/{event_id}/void` 作廢端點 | 2026-07 |

---

> **關聯文件**：[project-handbook.md](project-handbook.md) §5（摘要 + 評分）、[docs-audit.md](docs-audit.md)（文件本身問題）、[attendance-summaries.md](attendance-summaries.md)（Summaries/Payroll 設計）、[database-changes.md](database-changes.md)（Schema 設計）
