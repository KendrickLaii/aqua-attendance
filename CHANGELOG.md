# Changelog

本檔案以 [Keep a Changelog](https://keepachangelog.com/) 格式記錄發布內容。更早期嘅 release 記錄喺 [docs/PROJECT-HANDBOOK.md](docs/PROJECT-HANDBOOK.md) §8 發布記錄。

## [main-279495c] - 2026-10-27

推翻 2026-09-04「ERP／庫存唔喺本 repo 做」決定（~~#F1~~）：**Inventory 模組**喺本 repo 落地，runtime feature flag `INVENTORY_ENABLED` 把關（預設 `false`）。計劃只喺測試伺服器（Lightsail `Ubuntu-testing-deploy`）開；生產（`Ubuntu-Aqua-Attendance`）保持關。

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
