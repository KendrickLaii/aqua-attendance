# 出勤彙總（Attendance Summaries）

> 最後更新：2026-07-21  
> 涵蓋 Summaries 頁面、Payroll 頁面、後端 overview 聚合、Generate 流程、slot 計薪與 seed 測試資料。

本文件為 **Summaries / Payroll 月度流程** 的單一參考來源（SSOT）。資料庫欄位定義見 [database-changes.md](database-changes.md)；前端對齊總覽見 [project-handbook.md](project-handbook.md)。

---

## 1. 資料流總覽

```text
attendance_events（原始打卡）
        │
        │  POST /attendance-summaries/generate?year=&month=  （手動，僅該月）
        ▼
attendance_summaries（每人每天一行，持久化於 DB）
        │
        │  GET /attendance-summaries/overview  （瀏覽月份時讀取）
        │  GET /attendance-summaries         （單人每日明細）
        ▼
Summaries Web UI（總覽 → 明細）
        │
        │  POST /payroll-records/generate?year=&month=
        ▼
payroll_records（每人每月一筆；聚合 slots 並依薪資率計算金額）
```

| 步驟 | 是否持久化 | 何時需要手動觸發 |
|------|------------|------------------|
| 打卡 | ✅ `attendance_events` | 掃碼 / 手動補登 |
| Generate 彙總 | ✅ `attendance_summaries` | 該月有新打卡或需重算時 |
| 瀏覽 Summaries | 只讀 DB | **不需要**每次進頁面都 Generate |
| Generate 薪資 | ✅ `payroll_records` | 彙總更新後、或月結前 |

### 工時計算規則

- 以當日 **首次 check_in** 與 **末次 check_out** 計算
- 時間四捨五入到 **15 分鐘槽**（1 slot = 15 min = 0.25h；&lt;7.5 分捨、≥7.5 分入）
- OT = 超過地點 `business_hours.close` 的部分；未設定營業時間則全部算常規
- **不扣除午休 / Break**（已移除 `total_break_minutes` 與固定 lunch 扣減）
  - ⚠️ 此為已知缺口，會影響薪資正確性，詳見 [known-gaps.md](known-gaps.md) #H6
- `regular_slots` / `ot_slots` 為計薪來源；`regular_hours` / `overtime_hours` = slots × 0.25

---

## 2. 後端 API

### 2.1 `GET /api/attendance-summaries`

每日明細列表（分頁）。

| 參數 | 說明 |
|------|------|
| `unit_id` | 單一 unit |
| `date_from` / `date_to` | 日期區間（含端點） |
| `unit_type` | `staff` / `student` |
| `is_complete` | `true` / `false` |
| `page` / `page_size` | 預設 50，最大 200 |

回應標頭：`X-Total-Count`。排序：`unit_id`, `summary_date` 升序。

回傳含：`regular_slots`、`ot_slots`、`regular_hours`、`overtime_hours`、進出時間與狀態旗標。

### 2.2 `GET /api/attendance-summaries/overview`

依 **unit × 月份** 聚合，供總覽表使用。

| 參數 | 必填 | 說明 |
|------|------|------|
| `date_from` | ✅ | 月初 |
| `date_to` | ✅ | 月末 |
| `unit_type` | | `staff` / `student` |
| `search` | | unit `code` / `full_name` / `english_name`（ILIKE） |
| `page` / `page_size` | | 預設 50，最大 200 |

回傳欄位（`AttendanceSummaryOverviewOut`）：`days_present`, `days_complete`, `days_incomplete`, `total_regular_hours`, `total_overtime_hours`, `total_regular_slots`, `total_ot_slots`, `first_date`, `last_date`。

### 2.3 `POST /api/attendance-summaries/generate`

從 `attendance_events` 計算並 **upsert** `attendance_summaries`（鍵：`unit_id` + `summary_date`）。

| 參數 | 說明 |
|------|------|
| `year` | 例如 2026 |
| `month` | 1–12 |

回傳：`{ created, updated, total_days, year, month }`

- `total_days`：本月有打卡且可計算的天數（有 check_in）
- **僅處理選中月份**；不影響其他月份
- **不篩選** `unit_type`（員工與學生一併處理）
- 已有列 → **覆蓋更新**；無列 → 新建；**不會重複插入**
- 若某天事件已刪除，舊彙總列 **不會自動刪除**
- 寫入 audit log（`DATA_EXPORT`）

實作：`app/services/summary_generator.py`（呼叫 `app/services/overtime.py`）

### 2.4 `GET /api/payroll-records`

薪資記錄列表（分頁）。

| 參數 | 必填 | 說明 |
|------|------|------|
| `year` | ✅ | 4 位數年份 |
| `month` | ✅ | 1–12 |
| `status` | | `draft` / `calculated` / `approved` / `paid` / `cancelled` |
| `unit_type` | | `staff` / `student` |
| `page` / `page_size` | | 預設 50，最大 200 |

回應標頭：`X-Total-Count`。依 `payroll_period_start` 落在該年月區間篩選。

### 2.5 `POST /api/payroll-records/generate`

從當月 `attendance_summaries` 聚合為 `payroll_records`（鍵：`unit_id` + `payroll_period_start/end`）。

回傳：`{ created, updated, skipped, year, month }`

- 狀態為 `approved` / `paid` 的記錄 → **skipped**，不覆寫
- 聚合 `regular_slots` / `ot_slots`，依 `staff_profiles` 薪資率計算 `base_salary` / `overtime_pay` / `gross_pay` / `net_pay`
- 凍結 `hourly_rate_snapshot` / `ot_multiplier_snapshot`，避免之後調薪影響歷史
- 手動調整欄位 `adjustment_1` / `adjustment_2`（及 remark）在重算時會保留；`gross_pay = base + OT + adj1`，`net_pay = gross + adj2`

實作：`app/services/payroll_generator.py`

---

## 3. Web UI — `/attendance/summaries`

### 3.1 版面（主從式）

| 層級 | 內容 |
|------|------|
| **工具列** | 月份箭頭、`Type` 篩選（預設 **Staff**）、Generate、Refresh |
| **統計卡** | 人數、日次數、完整率、總工時（見 §6 已知限制） |
| **總覽** | 每人一行月度彙總（含 Regular / Reg slots / OT / OT slots）；搜尋（300ms debounce）；分頁 |
| **明細** | 點列進入；狀態 chips（All / Complete / Incomplete / Weekend）；每日表含 Regular / Reg slots / OT / OT slots / 狀態 + Total 列 |

### 3.2 Generate 成功提示

`src/utils/formatGenerateResult.ts` — 標題 + 說明，避免 `0 created, 8 updated` 等技術用語。

| 情況 | 標題示例 |
|------|----------|
| 有事件、首次 | `Generated N daily summaries for YYYY-MM` |
| 有事件、重算 | `Refreshed N daily summaries for YYYY-MM` |
| 無事件、但有舊彙總（seed） | `No check-in events for YYYY-MM` + 說明下方 N 列為既有資料 |
| 無事件、無彙總 | 提示先新增打卡再 Generate |

### 3.3 相關檔案

| 檔案 | 用途 |
|------|------|
| `apps/web/src/pages/attendance/summaries.vue` | 頁面 |
| `apps/web/src/api/attendance/summaries.ts` | API client |
| `apps/web/src/utils/formatGenerateResult.ts` | Generate 提示文案 |
| `apps/web/src/pages/attendance/payroll.vue` | 薪資頁面（同套提示） |

---

## 4. Web UI — `/attendance/payroll`

### 4.1 版面（主從式）

| 層級 | 內容 |
|------|------|
| **工具列** | 月份箭頭、`Type` 篩選（預設 **Staff**）、`Status` 篩選、Generate、Refresh |
| **統計卡** | 本月記錄數、總常規工時、總 OT 工時、總 Net pay（當前頁加總） |
| **總覽** | 每個 unit 當月一筆薪資；點列進入明細；分頁；亦有 Generate wizard 卡片檢視 |
| **明細** | 該 unit 當月 `attendance_summaries`：日期、上下班、Regular / Reg slots / OT / OT slots、狀態與 Total；可編輯 Adjustment 1/2 與 remark |

### 4.2 狀態流程

| 目前狀態 | 可執行動作 |
|----------|------------|
| `draft` / `calculated` | Approve → `approved` |
| `approved` | Pay → `paid` |
| `paid` | 不可刪除、不可重算（Generate 會 skipped） |

Superadmin 可刪除 `draft` / `calculated` / `approved` 狀態的記錄。

### 4.3 與 Summaries 的關聯

Payroll 明細直接呼叫 `GET /api/attendance-summaries?unit_id=&date_from=&date_to=`，
展示「這筆薪資是由哪些每日彙總計算而來」。這與 Summaries 的單人每日明細使用同一資料源。

### 4.4 相關檔案

| 檔案 | 用途 |
|------|------|
| `apps/web/src/pages/attendance/payroll.vue` | 頁面（主從式） |
| `apps/web/src/api/attendance/payroll.ts` | API client |
| `apps/web/src/api/attendance/summaries.ts` | 明細讀取每日彙總 |
| `apps/api/app/routers/payroll_records.py` | 後端列表篩選與 Generate |
| `apps/api/app/services/payroll_generator.py` | 從彙總生成/更新 payroll_records |

---

## 5. Seed 測試資料

```bash
cd apps/api
python seed.py              # users + units + summaries（完整 seed 末尾會跑 summaries）
python seed.py --summaries  # 僅寫入彙總（需已有 units）
```

| 資料集 | 月份 | 來源 |
|--------|------|------|
| `SEED_SUMMARIES` | 2026-05 | 固定少數列 |
| `build_bulk_summary_rows` | 2026-06、2026-07 | 大量隨機模式 |
| 打卡事件 | — | **未**為 bulk 月份建立 |

Bulk 彙總的 `calculation_method = "seed"`，**沒有**對應 `attendance_events`。因此：

- 瀏覽 6、7 月 → 列表有資料（讀 `attendance_summaries`）
- Generate 6、7 月 → 常顯示「No check-in events」（讀 `attendance_events` 為空）

---

## 6. 程式審查摘要（2026-07-17）

### 6.1 做得好的地方

- **主從 UI** 符合「先選月、看人、再看日」的業務流程
- **`/overview` 聚合** 避免 N+1 查詢與前端自行加總
- **Generate upsert** 可安全重複執行，不產生重複列
- **提示文案** 區分「從事件重算」vs「seed 既有資料」
- **Payroll generate** 保護已審批／已發放記錄
- **Slot 計薪** `regular_slots` / `ot_slots` 為來源，金額與費率快照寫入 `payroll_records`
- **Type 預設 staff** 符合管理員主要使用情境

### 6.2 已知限制（非阻斷）

| 項目 | 說明 |
|------|------|
| 統計卡範圍 | Overview Stat 卡改為 **整月 filtered 合計**（`/overview/stats`）；不受分頁影響 |
| Generate orphan 清理 | Generate 會刪除當月不再有可用 check-in 事件的彙總列；**保留** `calculation_method=seed` 的 demo 列 |
| Seed vs 事件 | 測試環境易出現「列表有資料但 Generate 無事件」；無事件時 Generate 也會清掉 orphan 列 |
| Weekend 篩選 | 明細層 Weekend chip 為 **前端篩選**已載入列；Complete/Incomplete 走 API `is_complete` |
| Holiday | 僅在狀態欄顯示，無獨立 chip |
| Overview 無 slots | ✅ 已補 `total_regular_slots` / `total_ot_slots` |
| 唯一約束 | `(unit_id, summary_date)` / payroll `(unit_id, period_start, period_end)` |
| 自動化 | 尚無 cron 自動月度 Generate |
| Auto checkout | **非完整自動版**：有 23:59 日界 helper、手動 Day-end、Generate 過去日回填；**無** 23:59 cron、**無** 00:00 status 重置（見 [known-gaps.md](known-gaps.md) #M14） |

### 6.3 後續可選改善

- Seed 可選 `--no-summaries` 避免與真實流程混淆
- 月度 Generate cron + 結構化 logging
- Auto checkout 排程（每晚呼叫 `POST /api/auto-checkout/run`）+ 可選 00:00 status 重置
- Payroll 狀態機已收緊（draft/calculated → approved → paid；paid/cancelled 不可回退）

### 6.4 本次文件對照修正（相對 2026-07-08 版）

| 舊描述 | 現況 |
|--------|------|
| 固定 lunch / `total_break_minutes` | **已移除**（欄位、計算、UI） |
| Payroll 金額暫為 0 | 已依 slots × 薪資率計算 |
| 明細只顯示小時 | 明細顯示 **小時 + slots** |
| 文件有兩個「§5」 | 已重編為 §5 Seed、§6 審查 |

---

## 7. 常見問題

**Q：為什麼沒按 Generate 就有資料？**  
A：多為 `python seed.py` 寫入的測試彙總，或先前已 Generate 過。瀏覽只讀 DB。

**Q：為什麼第二次 Generate 還是顯示 Refreshed 8？**  
A：每次都重算同一 8 天；`updated` 計數不代表數值有變化。

**Q：Generate 會處理 Type 篩選嗎？**  
A：不會。Type 只影響列表顯示；Generate 處理該月所有有打卡的 unit。

**Q：切換月份要再 Generate 嗎？**  
A：不需要，除非該月打卡有變動且尚未重算。

**Q：Payroll 頁面的明細從哪裡來？**  
A：點擊 unit 的薪資列後，會讀取該 unit 在當月的 `attendance_summaries`，展示這筆薪資的計算來源。

**Q：Payroll 列表為什麼只顯示單一月份？**  
A：列表依頂部選中的月份篩選，與 Summaries 的「按月聚焦」模型一致。

**Q：為什麼還有 Incomplete？**  
A：Incomplete 只表示「當天還缺簽退、且尚未到日界」。過去日期若只有 check_in，**Generate** 會補 `auto_checkout`（23:59）並標為 Complete；Dashboard **Day-end checkout** 可手動對仍 checked_in 的人補日界簽退。兩者都不是「系統每晚自動跑」——目前**沒有** 23:59 cron（見 known-gaps #M14）。Seed 測試資料不再大量產生 Incomplete。

**Q：Auto checkout / Day-end 算不算做完了？**  
A：**不算完整自動版。** 已完成：共用日界事件、手動 API、Generate 回填過去日。未完成：排程、00:00 `attendance_status` 重置。關門時間只影響 OT／UI「Past closing」標籤，不會觸發簽退。

---

## 8. 相關文件

- [database-changes.md](database-changes.md) — ER、`attendance_summaries` 欄位
- [known-gaps.md](known-gaps.md) — 已知問題追蹤
- [project-handbook.md](project-handbook.md) — 前端對齊狀態
- [../apps/api/README.md](../apps/api/README.md) — seed 與 API 啟動
- [../apps/web/README.md](../apps/web/README.md) — Web 路由
