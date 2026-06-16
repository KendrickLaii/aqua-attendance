# 前端對齊計畫（Web + Mobile）

> 制定日期：2026-06-16
> 目的：將前端對齊後端所有 schema 變更（多型 profile、新資料表、新欄位、新端點）
> 後端現況：53 passed, 0 failed，DB 與 API 完全同步（見 `apps/docs/BACKEND_REVIEW.md`）

---

## 1. 背景：後端發生了什麼變化

| 類別 | 變更 | 對前端影響 |
|---|---|---|
| **多型重構** | `products` 瘦身；`school_name`/`grade_class`/`guardian*` → `student_profiles`；`employment_type` 等 → `staff_profiles` | **破壞性**：產品表單/列表欄位全部要改 |
| **新欄位** | products 新增 `photo_url`/`enrollment_date`/`exit_date`；attendance_events 新增 `created_at`/`voided_at`/`source` | 型別與顯示要補 |
| **新資料表** | notifications、attendance_summaries、payroll_records、audit_logs | 需新建頁面 + API client |
| **新端點** | profiles CRUD、作廢、月度彙總生成、auto-checkout、稽核查詢 | 需新增 API 呼叫 |

---

## 2. 現況落差盤點

### 2.1 Web (`apps/web`) — 🔴 嚴重不一致

**`src/api/attendance/products.ts`**

- ❌ `Product` interface 仍含 `employment_type`、`school_name`、`grade_class`、`guardian1_name`…`guardian2_phone`（已搬到 profiles）
- ❌ `createProduct` / `updateProduct` payload 仍送這些扁平欄位
- ❌ 缺 `photo_url`、`enrollment_date`、`exit_date`
- ❌ 缺 `student_profile` / `staff_profile` 巢狀物件

**`src/pages/attendance/products.vue`**

- ❌ 表單「School & guardian」「Employment」區塊綁定扁平欄位
- ❌ 列表 `School / Class` 欄讀 `p.school_name`（將為 undefined）
- ❌ Employment 過濾送 `employment_type` query（後端已移除該 query）

**`src/api/attendance/events.ts`**

- ❌ `AttendanceEvent` 缺 `created_at`、`voided_at`、`source`

**完全缺失的 API client（後端已就緒）**

- ❌ `student-profiles` / `staff-profiles`
- ❌ `notifications`
- ❌ `attendance-summaries`（含 `/generate`）
- ❌ `payroll-records`
- ❌ `audit-logs`
- ❌ `auto-checkout`

### 2.2 Mobile (`apps/mobile`) — 🟡 輕微

- `src/services/attendance.ts` 的 `AttendanceEvent` 缺 `created_at`/`voided_at`/`source`
- Mobile 主要為掃描器，**不顯示** profile/薪資/稽核 → 影響小
- 掃描流程 API（`/attendance/scan`、`/qr/token`）**未變** → 無破壞

---

## 3. 對齊計畫（建議順序）

### 階段一：型別與 API client 修正（解除破壞）🔴

- [ ] **拆分 product 型別**：新增 `StudentProfile` / `StaffProfile` interface
- [ ] 重寫 `Product` interface：移除扁平 profile 欄位，改為巢狀 `student_profile?` / `staff_profile?`
- [ ] 加入 `photo_url` / `enrollment_date` / `exit_date`
- [ ] `createProduct` payload 支援巢狀 `student_profile` / `staff_profile`（後端已支援同交易建立）
- [ ] `events.ts` + mobile `attendance.ts`：`AttendanceEvent` 補 `created_at` / `voided_at` / `source`
- [ ] 移除 `listProducts` 的 `employment_type` query 參數

### 階段二：產品表單與列表重構 🔴

- [ ] `products.vue` 表單：依 `product_type` 動態顯示
  - student → 顯示 `student_profile`（school_name、grade_class、guardians[]）
  - staff → 顯示 `staff_profile`（employment_type、department、position、hire_date…）
- [ ] guardians 改為**動態陣列**（後端 `guardians` 為 JSON list，非固定 guardian1/2）
- [ ] 列表欄位讀巢狀：`p.student_profile?.school_name`
- [ ] Employment 過濾改為前端篩選或移除（後端不再支援該 query）
- [ ] 送出時組裝巢狀 payload

### 階段三：新功能頁面（補齊後端能力）🟢

- [ ] **Notifications**：通知中心頁 + 鈴鐺未讀數（`GET /notifications`、`PATCH` 標記已讀）
- [ ] **Attendance Summaries**：月度彙總頁
  - 選年月 → `POST /attendance-summaries/generate?year=&month=`
  - 表格顯示每日 regular/OT 工時
- [ ] **Payroll Records**：薪資列表 + 審核按鈕（PATCH status → approved/paid）
- [ ] **Audit Logs**：稽核查詢頁（superadmin only，多維度過濾）
- [ ] **Attendance 作廢**：log 頁每列加「作廢」按鈕（`POST /attendance/{id}/void`）
- [ ] **Auto-checkout**：dashboard 顯示「仍簽到中」人數 + 手動觸發按鈕

### 階段四：選單與權限 🟢

- [ ] 導航選單新增：Notifications、Summaries、Payroll、Audit Logs
- [ ] Audit Logs / Payroll delete 限 superadmin（前端守衛 + 後端已強制）
- [ ] 新頁面加入路由與麵包屑

### 階段五：Mobile 補強（低優先）🟡

- [ ] `attendance.ts` 型別補新欄位
- [ ] 掃描歷史顯示 `source`（scan/manual/auto_checkout）標記
- [ ] （選用）作廢事件在 mobile 歷史中標示

---

## 4. 受影響檔案清單

### Web — 需修改

| 檔案 | 動作 |
|---|---|
| `src/api/attendance/products.ts` | 重寫型別 + payload |
| `src/api/attendance/events.ts` | 補欄位 |
| `src/pages/attendance/products.vue` | 表單/列表重構 |
| `src/pages/attendance/log.vue` | 加作廢按鈕 + source 顯示 |
| `src/pages/attendance/dashboard.vue` | auto-checkout 狀態 |

### Web — 需新建

| 檔案 | 用途 |
|---|---|
| `src/api/attendance/profiles.ts` | student/staff profile CRUD |
| `src/api/attendance/notifications.ts` | 通知 |
| `src/api/attendance/summaries.ts` | 月度彙總 |
| `src/api/attendance/payroll.ts` | 薪資 |
| `src/api/attendance/auditLogs.ts` | 稽核 |
| `src/pages/attendance/notifications.vue` | 通知中心 |
| `src/pages/attendance/summaries.vue` | 彙總報表 |
| `src/pages/attendance/payroll.vue` | 薪資管理 |
| `src/pages/attendance/audit-logs.vue` | 稽核查詢 |

### Mobile — 需修改

| 檔案 | 動作 |
|---|---|
| `src/services/attendance.ts` | 補 `created_at`/`voided_at`/`source` |

---

## 5. 風險與注意事項

- **破壞性變更**：階段一/二完成前，產品頁的 school/guardian/employment 會顯示空白 → 建議**一次性合併**階段一+二
- **guardians 結構**：後端用 JSON 陣列（`[{name, relationship, phone}]`），前端不能再假設固定 2 位
- **Employment 過濾**：後端已移除 query，前端若需要請改用 staff_profile 前端篩選
- **權限**：audit-logs、payroll delete 為 superadmin；前端要隱藏按鈕避免 403
- **向後相容**：掃描核心流程未變，mobile 掃描功能不受影響可延後

---

## 6. 建議執行批次

| 批次 | 內容 | 阻塞性 |
|---|---|---|
| **Batch 1** | 階段一 + 階段二（產品多型對齊） | 🔴 必做，否則產品頁壞 |
| **Batch 2** | 階段三 Summaries + Payroll（核心業務報表） | 🟢 高價值 |
| **Batch 3** | 階段三 Notifications + Audit + 作廢 | 🟢 中價值 |
| **Batch 4** | 階段四選單權限 + 階段五 mobile | 🟡 收尾 |

---

## 7. 一句話總結

後端已完整就緒；前端最緊要的是 **Batch 1（產品多型對齊）**，因為 schema 重構使現有產品頁的
school/guardian/employment 欄位失效。其餘為**新增頁面**以解鎖後端已建好的
通知、薪資、彙總、稽核能力。
