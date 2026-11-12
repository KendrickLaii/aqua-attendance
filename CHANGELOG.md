# Changelog

本檔案以 [Keep a Changelog](https://keepachangelog.com/) 格式記錄發布內容。

## [2026-11-12]（Inventory 名稱、地點卡片、金額欄）

### 變更

- **中文名唔再必填**（Inventory 主檔：倉庫、品牌、分類、貨品、產品、供應商、客戶）：`name_zh`、`name_en` 至少填一個；`name_zh` 留空時伺服器用 `name_en`（trim 後）填入，所以所有顯示、單據快照、報表、列印照舊讀 `name_zh`，冇 migration。更新時 `name_zh` 傳空字串會用同一請求嘅 `name_en`，兩個都空回 422（`Enter a Chinese or English name.`）。Items CSV 匯入只有 `name_en` 嘅行亦可以。表單移除中文名必填，打開舊資料時若 `name_zh` 等於 `name_en` 會顯示為空。
- 地點卡片封面 logo 背景改白色，並加底邊線。
- 單據明細表（採購單／銷售單／發票／貸項單等）金額欄闊度 100px → 130px 並不斷行。

### 修正

- 有標題嘅彈窗（全站）第一個欄位嘅浮動標籤被裁走：`styles.scss` 蓋過 Vuetify `.v-dialog > … > .v-card-item + .v-card-text { padding-top: 0 }`，改為 8px。
- 分類與品牌頁「New category」打開時 Parent category 顯示 `[object PointerEvent]`（點擊事件被當成上層分類 id）。
- 品牌／分類彈窗移除 Name (English) 嘅「Optional. 選填」提示（中英文名填一個即可）。

## [2026-11-10]（Inventory 貨品頁改版）

- 庫存異動 **effective date**（Migration **055**）：`inventory_movements.effective_date`（DATE 可空，有索引）。GRN Confirm 寫入 `receipt_date`，補舊收貨單喺異動紀錄同報表（`GET /movements`、`/reports/movements-summary`、`/reports/write-offs` 日期篩選）跟實際收貨日；排序同 `balance_after` 仍用 `created_at`。`InventoryMovementOut` 加 `effective_date`；Postgres 升級時回填舊 GRN 入庫異動；異動頁日期格顯示「Received DD/MM/YYYY」。新增 API 測試。

- 收貨單（GRN）日期更正：Draft 收貨單詳情 ⋮ 選單新增 **Edit date & notes**（用現有 `PATCH /goods-receipts/{id}`），詳情顯示 notes；建立表單 Receipt date 加提示（補舊單填實際日期）；Void 選項說明加「日期錯咗可以作廢再開過」。新增 API 測試：draft 可改 `receipt_date`、已確認 409。

- 貨品彈窗規格編輯器：Option name／Values 會建議其他貨品用過嘅規格同選項（大小寫自動對齊，可「Add all」，仍可輸入新嘅）；純前端，由現有產品 `options` 推算（`utils/inventoryGoods.ts` `buildOptionSuggestions`，附單元測試）。

- Inventory **Start Here**（`/attendance/inventory/workflow`）改為中英並列（英文為主，中文在下）：開始前加到 4 步（加入分類與品牌）、新增「Items and variants 貨品與規格」說明區（附新圖 `public/inventory-variants.svg`、要記住清單、開發人員面板）、新增「Maintain items」工作、新增 FAQ；`public/inventory-workflow.svg` 頂部加「0. Item setup」帶。

- 貨品頁、分類與品牌頁、貨品彈窗改為英文介面（提示可附粵語）；`seed_inventory.py` 新增 `--catalog`（品牌／子分類／多規格貨品 demo 資料，`--reset-demo` 會一併清除）。

### 新增（Inventory 品牌、子分類、多規格貨品）

- **品牌同兩層分類**（Migration **054**）：新表 `inventory_brands`（`name_zh`／`name_en`／`is_active`，名稱 trim 後唔分大小寫唔可重複，409）；`inventory_categories` 加 `parent_id`（自我 FK，RESTRICT，有索引，最多兩層）；`inventory_products`、`inventory_items` 加 `brand_id`（FK RESTRICT，可空，有索引）。品牌同分類互相獨立。新 API `GET/POST /api/inventory/brands`、`PATCH /api/inventory/brands/{id}`（Admin，無 DELETE）；分類規則：上層要存在且係頂層、有子分類嘅分類唔可以掛上層、同層重名 409。`GET /items`、`GET /products` 加 `?brand_id=`，`?category_id=` 會包含子分類。
- **產品（多規格貨品）一次過儲存**：`POST/PATCH /api/inventory/products` 可帶 `skus`（每行有 `id`＝更新、冇 `id`＝新增；編號、規格值、售價、入貨價、其他成本、條碼、安全庫存、啟用）。全部喺同一個 transaction，驗證失敗就乜都唔寫入。SKU 名稱一律由產品名＋規格值計出；產品改名稱／分類／品牌／單位會同步到所有 SKU。加新規格 key 時要喺同一次請求為所有現有 SKU 補值，否則 422。`generate-skus` 端點保留但頁面唔再用。Options 組合數上限 200。
- **庫存總數 `on_hand`**：`InventoryItemOut` 加 `on_hand`（所有倉庫 `quantity` 總和），列表同產品內嵌 `skus` 都係分組一次查詢，冇 N+1。
- **CSV**：Items 匯出加 `brand` 欄，`category` 欄子分類輸出為 `上層 > 子分類`；匯入接受路徑或單一名稱（單一名稱撞多個分類時報錯，要用路徑），未知品牌報錯（唔會自動建立）；舊 CSV（冇 brand 欄）照樣入到。

### 變更（Inventory 貨品頁）

- `/attendance/inventory/items` 改版：一行一件貨（多規格貨品可展開睇規格），新增貨品用單一彈窗（可開「多個規格」並喺表格填各規格價錢），搜尋／品牌／分類篩選，顯示售價、庫存同狀態。分類同品牌移到新頁 `/attendance/inventory/categories`，貨品彈窗內亦可即時新增。

## [2026-11-10]（Inventory SPU／SKU）

### 新增（Inventory 產品 SPU）

- **SPU 層**（Migration **053**）：新表 `inventory_products`（`code` unique、名稱、類別、單位、圖、`options` JSON、`is_active`）；`inventory_items` 加 `product_id`（FK `inventory_products.id`，RESTRICT，可空，有索引）同 `variant_attrs`（JSON，可空）。1 個 SPU 對 N 個 SKU，SKU 仍然係 `inventory_items` 嘅真實 row，庫存、流水、單據 FK 不變。新 API `GET/POST /api/inventory/products`、`GET/PATCH /api/inventory/products/{id}`、`POST /api/inventory/products/{id}/generate-skus`（Admin）；`GET /api/inventory/items` 加 `?product_id=`。`skus` 同 `sku_count` 係計出嚟嘅回應欄位，唔入庫。Options 組合數上限 200；已有 SKU 缺新 option key 時產生 SKU 回 409，要先補值。Items 頁加「Add Product (SPU)」、按產品分組顯示 SKU、一鍵產生 SKU 彈窗；Item 彈窗可揀 Product 同規格值。

## [2026-11-05]（Inventory 開始頁）

### 變更（Inventory）

- **Start Here** 改成倉庫流程：先開倉庫、品項、期初數量，再進貨、銷售、調撥、盤點、客戶退貨和採購退貨。Quick Fulfill 寫明出貨單和收據是可勾選。盤點、異動、估值報表裡的「分校」改為「倉庫」。

## [2026-11-04]（Inventory 倉庫脫鉤）

### 新增（Inventory 倉庫）

- **Inventory 倉庫同打卡中心脫鉤**（Migration **052**）：新表 `inventory_warehouses`。庫存、流水、盤點、單據嘅 `location_id` 改為 `warehouse_id`，指向倉庫；升級時沿用已被引用嘅中心 id，所以現有數量同單號系列不變。單號改用倉庫 code。新頁 `/attendance/inventory/warehouses`（Admin）可以新增、編輯、停用；有庫存或單據嘅倉庫不能刪（409）。

## [2026-11-04]（Inventory 商品欄位）

### 新增（Inventory 商品欄位）

- **Inventory 商品新欄位**（Migration **051**）：`inventory_items` 加 `barcode`（String(100)，可空、有索引、非 unique；API trim 後空白存 NULL）同 `other_cost`（Numeric(10,2)，可空、≥0）。Item dialog 加 Barcode 同 Other cost 兩格；Items CSV export／import 加 `barcode`、`other_cost` 欄（舊 CSV 冇呢兩欄照樣入到）。

### 修正（Inventory）

- **New Invoice 打開即報錯**：`@click="openCreate"` 將點擊事件當成銷售單 id（`path.so_id` 錯誤、選單顯示 `undefined`）；而家打開時選單為空，錯誤顯示喺 dialog 內，從銷售單跳過嚟會預選並顯示正確標題，銷售單選單改用 server 搜尋（`GET /inventory/sales-orders?search=`）。
- **Paid by 下拉顯示 `[object Object]`**：選項改用 `title`。
- **Stocktake apply** 改為按差異調整（即時庫存 + 點數差異），唔再覆蓋開單後嘅出入貨。
- 取消銷售單會刪除其 draft 發票；已取消銷售單嘅發票不能 Issue。
- 折讓單按比例攤分發票整單折扣，有折扣發票可全數折讓；已全數收款發票嘅 Create Credit Note 停用。
- Items 搜尋（API／頁面）包含 barcode；CSV import 舊格式（冇 barcode／other_cost 欄）唔再清空呢兩欄，`NaN`／`Infinity` 當錯誤行；庫存移動日期篩選按香港日；Delivery Order confirm 鎖定發票行。

### 變更（Inventory 商品欄位）

- **加品項合併規則**：`useInventoryLinePicker` 只喺同品項**而且單價相同**（`unit_cost`／`unit_price`，空值當 0）先合併數量；單價唔同就保留兩行，唔彈提示。
- **效能（內部）**：銷售單、出貨單、採購單、收貨單、退貨單列表由逐行查詢改為批次載入（`_so/_do/_po/_grn/_prt_details_batch`，單張 detail 共用同一段程式，輸出不變）；新增 `tests/test_inventory_list_batching.py` 比對列表同單張輸出，並斷言 1 張同 5 張單嘅 SELECT 數量相同。
- **修正**：`PATCH /inventory/goods-receipts/{id}` 改行時按 PO＋品項解析 `po_line_id`（同建立時一樣，並驗證屬於該 PO），確認後 PO `received_qty`／狀態會正確更新；新增測試。

- **Inventory 全模組操作提示**：`AppToastStack` 掛到 `App.vue`（移除 units／tax 頁各自掛載）；所有 inventory 成功操作改用 `useToast`，移除頁面 `actionSuccess`／`actionError` 橫額；彈窗內出錯顯示喺彈窗內（dialog-local VAlert），頁面層級操作出錯用 error toast。
- **加品項回饋**：新 composable `useInventoryLinePicker`（PO／SO／GRN／PR 行）——重複品項合併數量（info toast「Qty +n for SKU」）、停用品項拒絕（warning toast）；SO 無可用庫存時提示。
- **彈窗統一**：分段標題（`text-overline`）、闊度 560／900、手機全螢幕（`useDisplay`）、`VDivider` 分隔動作列；GRN／PR 行表加 Line total 同 Subtotal；Payment／Customer／Supplier 彈窗分段排版。
- **格式**：新 `utils/inventoryDisplay.ts` `formatMoney()`（`HK$1,234.50`，空值 `—`）取代各頁 `fmtMoney`／`toFixed`（列印版面不變）；movements／stocktakes 日期用 `formatAttendanceDateTime`（香港時間）。
- **空白狀態**：新 `InventoryEmptyState` 組件（圖示＋文字＋新增按鈕）。
- `GET /inventory/dashboard` 加 `overdue_days`（`INVENTORY_INVOICE_OVERDUE_DAYS`），Dashboard 逾期說明不再寫死 30 天；Reports 逾期欄位改標示「31 天以上」（對應固定賬齡分檔）。

- **「Cost price」改名「Purchase price」**：Item dialog label 同 Items 表頭（「Cost」→「Purchase price」，列表加埋「Other cost」欄）改名；DB／API 欄名 `cost_price` 不變。

## [2026-10-29]（員工掃碼）

### 新增（員工掃碼）

- **Mobile 員工掃碼打卡**：員工可以用員工編號 + 6 位 shift PIN 登入 mobile app（`POST /api/staff-shifts/login`，token type `staff_shift`，12 小時，無 refresh），喺自己允許嘅地點掃**其他人**嘅 QR 簽到／簽退，並睇返今日自己掃嘅紀錄。
  - 新端點（staff token 專用，admin token 會 401）：`POST /api/staff-shifts/attendance/scan`、`POST /api/staff-shifts/attendance/scan/preview`、`GET /api/staff-shifts/attendance`（伺服器強制今日香港日＋`recorded_by_unit_id`＝登入員工）。員工冇手動更正／作廢權限。
  - Migration **050**：`staff_profiles.can_take_attendance`（NOT NULL，預設 true，舊員工自動有權；Admin 喺員工資料嘅「Can take attendance (mobile scanner)」取消權限）＋ `attendance_events.recorded_by_unit_id`（FK `units.id` ON DELETE SET NULL，有索引）。
  - 員工掃嘅事件 `recorded_by_unit_id`＝掃碼員工、`recorded_by_user_id`＝空；CSV export 加 `recorded_by_unit_id` 欄（喺 `recorded_by_user_id` 之後）。
  - `/api/staff-shifts/login`、`/me` 回 `can_take_attendance`；`/api/staff-shifts/locations` 加 `code`／`region`／`is_active` 欄位。
  - 掃碼共用邏輯搬到 `app/services/attendance_scan.py`；`record_scan`／`list_events` 支援 `recorded_by_unit_id`。
- **Mobile app**：登入頁加 Admin / Staff 切換（staff 用員工編號 + PIN）；staff session 只有 Help tab，`can_take_attendance=true` 先有 Scanner 同 History（History 只顯示今日自己掃嘅紀錄）。
- **Web**：員工編輯框 Staff profile 區加「Can take attendance (mobile scanner)」checkbox，新員工預設勾選。

### 修正（員工掃碼）

- `POST /api/attendance/{id}/void` 漏 import `selectinload`，作廢打卡會 500（CI pytest 3 個失敗，image 未 build）。

## [2026-10-29]

### 變更（Join a student）

- **Courses 名冊「Join a student」**：揀咗已經喺班嘅學生唔再顯示「This student is already in the class.」鎖掣。堂費（per_session）班個掣變 **Top up sessions**：新增一筆 `enrollment_purchases` 記錄（表單結束日遲過現有結束日時順便延長 `end_date`；ongoing 唔郁；開始日唔改）。月費（monthly）班個掣變 **Update**：自動填返現有開始／結束日同價錢，撳落去 PATCH 日期同價錢。已在班學生唔佔新位，容量滿都頂得。
- **API**：`POST /course-enrollments/{id}/purchases` 而家會寫 audit log（`enrollment_purchases` / `CREATE`）。
- **Top up 日期檢查**：開始日（即 `purchased_at`）早過該筆報名嘅 `start_date` 會鎖掣；留空就用今日，今日早過開始日則用開始日。表單下面預覽計費窗會延長定唔變（結束日早過現有唔會縮短）。同一日同堂數已有購買時彈確認框，防重複撳。後端 `POST /course-enrollments/{id}/purchases` 對 `purchased_at < start_date` 回 422。
- **購買紀錄顯示**：Sessions 欄唔再用 tooltip，改為撳一下喺該行下面展開「Purchase history」表（日期／堂數／價錢／billed 狀態／備註＋總數）；堂費班 **Edit** 對話框都有同一個表（共用 `EnrollmentPurchaseHistory.vue`）。
- **Join a student 提示精簡**：表單下面最多一行狀態（例如 `In class · 37 sessions · 2026-10-01 → 2026-11-30 · extends to …`）加一行真正阻擋嘅錯誤；「請填堂數」之類提示只放喺掣嘅 title。

## [main-f7bec86] - 2026-10-27（後續）

### 新增（10-27 後續）

- **Inventory 商品副圖**：每件商品 1 張主圖（`image_url`）+ 最多 2 張副圖（`sub_image_urls`，JSON，Migration **049**）；上傳流程同 Location 照片（`POST /api/uploads` → `uploads` volume）。列表縮圖仍只顯示主圖。

### 修正（10-27 後續）

- **收條列印冇 logo**（`b368a8d`）：之前寫完列印頁即刻 `print()`，logo 未載入就印咗空白。改用發票同一套流程：logo 轉 data URL 嵌入 → 等圖片 decode → 喺列印視窗內呼叫 `print()`。共用 helper 搬去 `utils/printWindow.ts`。

### 文件（10-27 後續）

- 文件整併：只留 README、CHANGELOG、`docs/PROJECT-HANDBOOK.md`；舊設計／審查紀錄移到 `docs/archive/`。
- 手冊 §5 新增 **#M25**：上傳圖片未納入 `backup.sh` 備份（待做）。

### 部署（10-27 後續）

- 兩台伺服器跑 `sudo ./update.sh` 即可（compose／`.env` 冇改）；API 啟動會自動跑 Migration 049（只加一個可空欄位）。

## [main-279495c] - 2026-10-27

推翻 2026-09-04「ERP／庫存唔喺本 repo 做」決定（~~#F1~~）：**Inventory 模組**喺本 repo 落地，runtime feature flag `INVENTORY_ENABLED` 把關（預設 `false`）。已部署（2026-10-27）：測試伺服器（Lightsail `Ubuntu-testing-deploy`）`INVENTORY_ENABLED=true`；生產（`Ubuntu-Aqua-Attendance`）保持關。

### 新增（Inventory）

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

### 變更（Inventory）

- `AttendanceConfirmDialog`（全站共用）標題左邊加咗 tone icon，行為不變。
- Router `beforeEach` 轉 async（等 feature flags 載入）。

### 部署（Inventory）

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
