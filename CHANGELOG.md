# Changelog

本檔案以 [Keep a Changelog](https://keepachangelog.com/) 格式記錄發布內容。

## [2026-10-29]

### 變更

- **Courses 名冊「Join a student」**：揀咗已經喺班嘅學生唔再顯示「This student is already in the class.」鎖掣。堂費（per_session）班個掣變 **Top up sessions**：新增一筆 `enrollment_purchases` 記錄（表單結束日遲過現有結束日時順便延長 `end_date`；ongoing 唔郁；開始日唔改）。月費（monthly）班個掣變 **Update**：自動填返現有開始／結束日同價錢，撳落去 PATCH 日期同價錢。已在班學生唔佔新位，容量滿都頂得。
- **API**：`POST /course-enrollments/{id}/purchases` 而家會寫 audit log（`enrollment_purchases` / `CREATE`）。

## [main-f7bec86] - 2026-10-27（後續）

### 新增

- **Inventory 商品副圖**：每件商品 1 張主圖（`image_url`）+ 最多 2 張副圖（`sub_image_urls`，JSON，Migration **049**）；上傳流程同 Location 照片（`POST /api/uploads` → `uploads` volume）。列表縮圖仍只顯示主圖。

### 修正

- **收條列印冇 logo**（`b368a8d`）：之前寫完列印頁即刻 `print()`，logo 未載入就印咗空白。改用發票同一套流程：logo 轉 data URL 嵌入 → 等圖片 decode → 喺列印視窗內呼叫 `print()`。共用 helper 搬去 `utils/printWindow.ts`。

### 文件

- 文件整併：只留 README、CHANGELOG、`docs/PROJECT-HANDBOOK.md`；舊設計／審查紀錄移到 `docs/archive/`。
- 手冊 §5 新增 **#M25**：上傳圖片未納入 `backup.sh` 備份（待做）。

### 部署

- 兩台伺服器跑 `sudo ./update.sh` 即可（compose／`.env` 冇改）；API 啟動會自動跑 Migration 049（只加一個可空欄位）。

## [main-279495c] - 2026-10-27

推翻 2026-09-04「ERP／庫存唔喺本 repo 做」決定（~~#F1~~）：**Inventory 模組**喺本 repo 落地，runtime feature flag `INVENTORY_ENABLED` 把關（預設 `false`）。已部署（2026-10-27）：測試伺服器（Lightsail `Ubuntu-testing-deploy`）`INVENTORY_ENABLED=true`；生產（`Ubuntu-Aqua-Attendance`）保持關。

### 新增

- **API — Inventory 模組**（全部喺 `/api/inventory/*`，flag 關時全部回 404）：
  - Stock core：categories、items（單圖）、stocks、movements、transfers、stocktakes、CSV 匯出
  - Purchasing：suppliers、purchase orders、goods receipts、purchase returns
  - Sales：customers、sales orders（可出 proforma）、delivery orders
  - Invoicing：inventory invoices、receipts、credit notes；發出 invoice 時扣庫存；DO 係 invoice 嘅子單；流程 SO → invoice → DO
  - Reports、dashboard、低庫存提示（alerts loop；要 `INVENTORY_ENABLED` 同 `INVENTORY_ALERTS_ENABLED` 都係 true 先跑）
- **API — `GET /api/features`**：公開、免登入，回 `{"inventory": bool}`。Web image 兩邊伺服器共用，所以 flag 係 runtime 問 API，唔係 build-time 烘焙。
- **Web — `useFeatureFlags` composable**：單飛 fetch `/api/features`；`filterNavByFeatures()` 喺 flag 關時收埋側欄 Inventory 群組；router guard 將 `/attendance/inventory/*` 導返 dashboard。
- **Web — `GlobalConfirmDialog`** 掛喺 App.vue（inventory 頁用）。
- **測試**：`tests/test_feature_flags.py`（features endpoint + flag 關時 404）。

### 變更

- `AttendanceConfirmDialog`（全站共用）標題左邊加咗 tone icon，行為不變。
- Router `beforeEach` 轉 async（等 feature flags 載入）。

### 部署

- `deploy/docker-compose.prod.yml`：`api.environment` 加 `INVENTORY_ENABLED: ${INVENTORY_ENABLED:-false}`。`deploy/` 檔案係手工複製上伺服器——要開 flag 嗰台機需手加 compose 行 + `.env` 設 `INVENTORY_ENABLED=true`；生產唔使郁（預設關）。
- Migration **042–048**（Alembic head **048**）：全部新表，冇改現有表；FK 只指 `users`／`locations`／`units`；獨立派號表 `inventory_counters`。
- 驗證：`curl -s http://localhost/api/features` → `{"inventory":true|false}`。
- 回滾：image tag `sha-16b8856`（上一個 main）。
- API 測試：**430 passed**。

### 已部署（2026-10-27）

- CI 同 Publish container images（279495c）兩邊都 green。
- Testing（`Ubuntu-testing-deploy`）：`git pull` 更新 compose（該機係 `~/juku-attendance` 嘅 git clone）+ `.env` 設 `INVENTORY_ENABLED=true` → `/api/features` 回 `{"inventory":true}`，側欄見 Inventory。
- Production（`Ubuntu-Aqua-Attendance`）：部署前 backup、`update.sh` → `/api/features` 回 `{"inventory":false}`、`/api/inventory/items` 回 404、`alembic current` = `048 (head)`。瀏覽器抽查已確認：側欄無 Inventory，Courses／Invoices／Receipts／Credit Notes／Payroll 頁正常。

---

## [2026-10-02]

- **#M22 已做**：同一學生同一 SKU 改為只鎖一筆 `active`（partial unique `uq_course_enrollment_unit_sku_active`，Migration `a4e8c1d9b6f2`）；離開後再 Join 開新報名，Back in class 重開舊報名。
- Courses 名冊：**Renew**（月費有結束日）／**Set end**（月費 Ongoing）；結束日過後自動 Leave（`completed`）。
- 員工**自助報更**（Migration `b7c1e9a4d2f6`）：員工編號 + 6 位 PIN 登入 `/staff/shifts` 交申請，admin 批准先入正式 `shifts`；`shift_requests` 表＋`staff_profiles.shift_pin_hash`。
- Alembic head：**b7c1e9a4d2f6**。

## [2026-09-24]

- Credit Notes 獨立頁（`total < 0` 發票）；退款單列印（REFUND REQUEST + REFUND ACKNOWLEDGEMENT）。
- `tuition_invoices.payable_to_name`／`payee_name`（d4b8e2a1c7f0，Paid 後仍可改）。
- 收條編號改手打（`receipt_no` 由職員輸入）；`GET /api/uploads/{key}` 改公開讀取。
- Alembic head：**d4b8e2a1c7f0**。

## [2026-09-22]

- 未收款發票可 Edit 且保留報名連結；Paid 之後用 credit note；作廢單／作廢收條 Remove 後可重用編號。
- Courses 班次表顯示 In class 人數。

## [2026-09-17]

- 手動發票不再受「一人一期一單」限制（`(unit_id, period_start, period_end)` 改 partial unique index，僅 `kind='tuition'`；b8f2c4d6a1e9）。
- 發票 PATCH 至 `void` 即時清 `enrollment_purchases.billed_invoice_line_id`（「未出單」只有一個判斷式）。
- drop `course_enrollments.purchased_quantity`（c3e7a95b2d10）；堂數單一來源 = `enrollment_purchases`。
- 測試：全套 **164 passed**。Alembic head：**c3e7a95b2d10**。

## [2026-09-15]

- 手動發票落庫（`kind=manual`、可結算堂費 `purchase_ids`）；發票編號改每中心系列（`location_id` + `invoice_counters`，f5d44789754d）。
- 堂費改由 `enrollment_purchases` 追蹤（7d340d0ce7de），Generate 出未出單購買；購買價可空、出單時先定（a1c9e4d7f2b3）。
- 發票行 `staff_name` 快照（bfb6cd4eb3b9）；發票列印已做。
- Alembic head：**a1c9e4d7f2b3**。

## [2026-09-04]

- 堂費（per_session）改為報名時輸入 `purchased_quantity` 一次性收費（Migration 038），不再按出勤∩上課日計算；#M23 失效。
- ~~ERP／庫存確認不在本 repo 做，是獨立新專案（#F1）~~——2026-10-27 已推翻（見 `[main-279495c]`）。
- Alembic head：**038**。

## [2026-08-28]

- SKU `meeting_weekdays` 上線（Migration 037）；堂費 Generate 按上課日∩出勤計堂（後於 2026-09-04 改一次性收費）。
- Alembic head：**037**。

## [2026-08-27]

- SKU `billing_unit`（035）與學費發票（036）上線：`tuition_invoices`／`tuition_invoice_lines`，按月從有效報名產生草稿，行項目快照價錢。
- 後端測試約 95 個 `test_*`。Alembic head：**036**。

## [2026-08-04]

- 課程資料模型上線：`course_spus`／`course_skus`／`course_enrollments`（Migration 034）。
- 修正產品定位（非僅補習班；多據點已上線）。

## [2026-08-03]

- 出勤端點 `unit_type` 白名單檢查（#M19）：`ATTENDANCE_ELIGIBLE_TYPES = {"staff","student"}` defense-in-depth。

## [2026-07-28]

- product → unit 重構審計完成；#M20 個人資料欄位搬移至 profiles 完成（`f8e65b7cf82b` + `033`）；#M21 legacy constraint/index 名稱待清理。

## [2026-07-21]

- 後端架構審查：**午休未扣除**列為新 High 缺口（#H6）；新增 #M15–#M18（Summaries/Payroll 相依、Generate 競態、`attendance_status` 一致性）。

## [2026-07-17]

- 釐清 **auto checkout 非完整自動版**（有手動 Day-end + Generate 回填，**無** 23:59 cron／無 00:00 status 重置）— #M14。

## [2026-07-10]

- Summaries / Payroll 重構完成（主從式 UI、overview 聚合、Generate upsert、薪資率計算、seed bulk 測試資料）；多項 Medium/Low 問題修復。

---

## Release 2026-07 — Summaries / Payroll 重構

### API（2026-07）

| 區域 | 變更 |
| ------ | ------ |
| New | `POST /api/attendance-summaries/generate` — 從 events 計算並 upsert 每日彙總 |
| New | `GET /api/attendance-summaries/overview` — unit × 月份聚合（含工時、天數） |
| New | `POST /api/payroll-records/generate` — 從 summaries 聚合薪資記錄 |
| Enhancement | `GET /api/payroll-records` — 新增 `year`/`month`/`unit_type`/`status` 篩選 |
| Enhancement | Payroll generate 依 `staff_profiles` 薪資率計算 `base_salary`/`overtime_pay`/`gross_pay`/`net_pay` |
| Enhancement | 員工可設定 `commission_rate`（0–100%）；Generate 按發票級 Tutor 匹配（`tutor_unit_id` 優先，舊單 fallback 名字）**收款月**內已收發票，扣除 credit note 後將分成寫入 `commission_pay`；比例由 `commission_rate_snapshot` 凍結；`GET /payroll-records/{id}/commission-detail` 提供明細 |
| Enhancement | `payroll_records` 凍結 `hourly_rate_snapshot`/`ot_multiplier_snapshot`（防歷史污染） |
| Enhancement | Generate 寫入 audit log（`DATA_EXPORT`） |
| Migration | `026_add_slots_and_pay_rates.py` — slots + 薪資率欄位；`032_rename_products_to_units.py` — product → unit 重新命名 |

### Web（2026-07）

| 區域 | 變更 |
| ------ | ------ |
| New | `/attendance/summaries` — 主從式頁面（總覽 → 每日明細） |
| New | `/attendance/payroll` — 主從式頁面（月度薪資 → 明細） |
| Enhancement | Unit 表單 Compensation 區新增 `Commission / sharing` 開關與可編輯比例（開啟時預設 70%） |
| Enhancement | Payroll Generate 提示 Tutor 找不到員工或同名不唯一的 commission warnings |
| Enhancement | Summaries：月份切換、Type 篩選（預設 Staff）、Generate、統計卡 |
| Enhancement | Payroll：狀態流程（draft → calculated → approved → paid）、Approve/Pay 動作 |
| Enhancement | Generate 成功提示（區分首次/重算/無事件/seed 既有資料） |
| Enhancement | Payroll 明細直接讀取 `attendance_summaries`（與 Summaries 同資料源） |

### Seed 資料（2026-07）

| 資料集 | 月份 | 說明 |
| -------- | ------ | ------ |
| `SEED_SUMMARIES` | 2026-05 | 固定少數列 |
| `build_bulk_summary_rows` | 2026-06、2026-07 | 大量隨機模式（`calculation_method = "seed"`） |

---

## Release 2026-06 — 後端大量修復 + 多型 Profile

### API（2026-06）

| 區域 | 變更 |
| ------ | ------ |
| Critical | StaffProfile 多重外鍵歧義修復（`foreign_keys` 明確指定） |
| Critical | profile 關係 `uselist=False`（一對一映射修正） |
| Migration | `employment_type` 從 `units` 遷移至 `staff_profiles`（`e350a1e954db`） |
| New | `staff_profiles` / `student_profiles` CRUD 端點 |
| New | `notifications` CRUD + 標記已讀 |
| New | `audit_logs` 查詢端點（superadmin） |
| New | `auto_checkout` **手動**觸發端點（`POST /api/auto-checkout/run`；**非**已上線排程，見 [docs/PROJECT-HANDBOOK.md](docs/PROJECT-HANDBOOK.md) §5 #M14） |
| New | OT 計算服務（`services/overtime.py` — 15 分鐘槽） |
| Enhancement | Rate limit 改用 Redis backend（多副本安全） |
| Enhancement | `notification.extra_data` 改 JSON 型別 |
| Enhancement | attendance 作廢端點（`voided_at`） |
| Enhancement | audit_log 寫入 helper，接線關鍵操作 |
| Migration | 001–033（含 `attendance_summaries`、`payroll_records`、slots、薪資率；032/033 於 7 月完成 product→unit 與 profile 欄位對齊） |

### Web（2026-06）

| 區域 | 變更 |
| ------ | ------ |
| New | Notifications 頁面 |
| New | Audit Logs 頁面（superadmin） |
| Enhancement | Staff/Student profile 編輯整合進 Unit 頁面 |

---

## Release 2026-05 — Web polish + dashboard stats

Ship checklist for `main` → GHCR → Lightsail（`deploy/update.sh`）。

### Web（attendance admin）（2026-05）

| 區域 | 變更 |
| ------ | ------ |
| P1 | Login `?to=` redirect；`formatApiError` on load errors |
| P1 | Dashboard today event total via `X-Total-Count` |
| P2 | UserProfile attendance menu；Web Scanner（QR dialog entry only） |
| P2 | Shared `DialogFooter`；dialog 統一 P1–P3 |
| P3 | Unit checked-in/out filter（API + UI） |
| P3 | List pagination — units, users, locations |
| Fix | Dashboard check-in/out counts — `GET /api/attendance/stats` |
| Refactor | `locations.vue` split |
| Fix | Location create when Chinese name empty |
| Feature | **Staff employment type** — `part_time` / `full_time` on units |
| Feature | **QR Codes** — QR shown on each card；multi-select + **Print selected** |

### API（2026-05）

| 區域 | 變更 |
| ------ | ------ |
| New | `GET /api/attendance/stats` — aggregate day counts for dashboard |
| Enhancement | `X-Total-Count` + `attendance_status` filter on units list |
| New | Unit `employment_type`（`part_time` \| `full_time`）；list filter `?employment_type=` |
| Migration | `008_product_employment_type` — adds `units.employment_type` column |

### 部署（當時清單）（2026-05）

- CI green → Publish container images green → server `.env` 密鑰非佔位符 → GHCR login 有效 → `update.sh`。
- 部署後驗證：`/api/health` → `{"status":"ok"}`；`/api/attendance/stats` 無登入 → 403；dashboard／units／locations／QR print 抽查。
- Migration：API 啟動自動 `alembic upgrade head`（008 新增 `units.employment_type`）。
- 回滾：`.env` 將 `API_IMAGE`/`WEB_IMAGE` 指去舊 SHA tag → `pull` + `up -d`。
