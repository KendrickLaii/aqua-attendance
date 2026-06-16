# FastAPI 後端審查與修復計畫

> 審查日期：2026-06-16　範圍：`apps/api`（不含資料庫 schema 設計，聚焦 API/應用層）
> 測試現況：`pytest` → **53 passed, 0 failed**（全部同步完成）

---

## 1. 總體評價

後端架構整體**健康且專業**，採用清晰的分層設計：

```
routers/   → HTTP 層（驗證輸入、權限、回應）
services/  → 商業邏輯（attendance、auth、product、qr）
schemas/   → Pydantic I/O 契約
models/    → SQLAlchemy ORM
deps.py    → 依賴注入（DB、CurrentUser、角色守衛）
```

**優點：**

- **100% ORM**（非 raw SQL，唯一例外是 health check 的 `SELECT 1`）
- JWT access/refresh token 輪換 + jti 撤銷機制完善
- 角色階層守衛（`AdminOnly` / `SuperAdminOnly`）正確
- 掃碼防重放：debounce window + PostgreSQL `with_for_update()` 行鎖
- 速率限制（slowapi）套用在 login / scan
- 生產環境密鑰驗證（`validate_production_secrets`）
- CSV 匯出分頁 + 上限保護

---

## 2. 嚴重問題（已修復）

### 2.1 ✅ StaffProfile 多重外鍵歧義（CRITICAL，已修）

`StaffProfile` 有兩個指向 `products` 的外鍵（`id` 與 `supervisor_id`），導致
`Product.staff_profile` 關係無法判定 join 條件，**整個 ORM 映射在啟動時崩潰**。

- 修復：在 `StaffProfile.product` 與 `Product.staff_profile` 上明確指定
  `foreign_keys`。

### 2.2 ✅ profile 關係未設 `uselist=False`（已修）

`student_profile` / `staff_profile` 是一對一，但預設會被當成 list，使
`ProductOut.model_validate` 對單一物件的轉換出錯。

- 修復：兩個關係加上 `uselist=False`。

---

## 3. 已解決問題（RESOLVED）

### 3.1 ✅ `employment_type` 遷移至 `staff_profiles`（已完成）

**決策：** 採 **B**（符合多型設計目標）。

**執行內容：**

- Alembic migration `e350a1e954db`：
  1. `staff_profiles` 新增 `employment_type` 欄位
  2. 資料遷移：`UPDATE staff_profiles SET employment_type = products.employment_type`
  3. `products` 刪除 `employment_type` 舊欄位
- `models/product.py` 移除 `employment_type`
- `models/staff_profile.py` 新增 `employment_type`
- `schemas/staff_profile.py`：`Create/Update/Out` 新增 `employment_type`
- 測試 `test_staff_profile_employment_type`：改為測試 `/api/staff-profiles/{id}` CRUD
- `seed.py`：改為建立 product 後建立對應 profile（含 employment_type）

**結果：** 測試 53 passed, 0 failed。

---

## 4. 中優先級問題

### 4.1 建立 student/staff 時無法一次帶入 profile 資料

`POST /api/products` 只建立核心 `products`，profile 需另外呼叫
`POST /api/student-profiles/{id}` 或 `/staff-profiles/{id}`。

- 風險：前端需兩段式呼叫，中途失敗會產生「無 profile 的孤兒 product」。
- 建議：在 `create_product` 內以同一交易選擇性建立對應 profile，或提供
  組合式端點。

### 4.2 新表缺少 router / service

已建立 model + schema，但尚無端點：

- ❌ `/api/notifications`
- ❌ `/api/attendance-summaries`
- ❌ `/api/payroll-records`
- ❌ `/api/audit-logs`

audit_logs 目前**沒有任何寫入點** — 稽核需求尚未真正啟用。

### 4.3 audit_log 尚未接線

需在關鍵操作（建立/修改/刪除 product、user、手動補打卡、薪資審核）寫入
`audit_logs`。建議用 service helper 或 SQLAlchemy event 統一處理。

### 4.4 `notification.extra_data` 型別

model 定義為 `Text` 但語意是 JSON。建議改為 `JSON`/`JSONB` 以利查詢與驗證。

---

## 5. 低優先級 / 體質改善

| # | 項目 | 說明 |
|---|---|---|
| 5.1 | `recorded_by_user_id` 無 FK 載入 | CSV/列表只存 UUID，未 join user 顯示姓名 |
| 5.2 | 缺 voided 流程 | 已有 `voided_at` 欄位，但無「作廢事件」端點/邏輯 |
| 5.3 | `business_hours` 未被服務層使用 | OT 計算邏輯（15 分鐘槽）尚未實作於 service |
| 5.4 | 列表端點無排序參數 | 固定 `created_at desc`，未開放 client 控制 |
| 5.5 | 統一錯誤格式 | 多數用 `HTTPException(detail=str)`，可導入標準錯誤 schema |
| 5.6 | `print`/logging | 缺結構化 logging（request id、層級） |

---

## 6. 安全檢查

- ✅ 密碼 bcrypt 雜湊
- ✅ refresh token 輪換 + 撤銷 + 過期清理
- ✅ 角色權限（admin 不可管理 superadmin）
- ✅ 生產密鑰長度/placeholder 驗證
- ⚠️ CORS `allow_methods=["*"], allow_headers=["*"]` — 生產建議收斂白名單
- ⚠️ 無 audit log 寫入 — 合規追蹤未啟用（見 4.3）
- ⚠️ scan 端點要求 `AdminOnly`，若未來有 kiosk 裝置需檢視權限模型

---

## 7. 修復計畫（建議順序）

### 階段一：解除阻塞（已完成）

- [x] 修復 StaffProfile 多 FK 歧義
- [x] profile 關係 `uselist=False`
- [x] `employment_type` 遷移至 `staff_profiles`（§3.1）

### 階段二：資料一致性

- [x] `employment_type` → `staff_profiles` 遷移 + 資料搬遷
- [x] `create_product` 支援同交易建立 profile（避免孤兒）
- [x] `notification.extra_data` 改 JSON

### 階段三：補齊功能端點

- [x] notifications CRUD + 標記已讀
- [x] attendance_summaries 產生 + 查詢
- [x] payroll_records CRUD + 審核流程
- [x] attendance 作廢端點（寫 `voided_at`）

### 階段四：稽核與可觀測性

- [x] audit_log 寫入 helper，接線關鍵操作（products create、users CRUD、attendance manual/void）
- [x] audit_logs 查詢端點（superadmin）
- [ ] 結構化 logging + request id（保留為持續改善）

### 階段五：商業邏輯

- [x] OT 計算服務（`services/overtime.py` — 15 分鐘槽、lunch 扣除、business_hours close 判定）
- [x] auto_checkout 排程（`services/auto_checkout.py` + `/api/auto-checkout/run` 端點）
- [x] 月度彙總計算填入 attendance_summaries（`POST /api/attendance-summaries/generate?year=&month=` 手動觸發）

---

## 8. 測試狀態

```
53 passed, 0 failed
```

全部測試通過，資料庫 schema 與 FastAPI 後端完全同步。

其餘測試（auth、scan、locations、products CRUD、review fixes）全數通過，
確認 §2 的關鍵修復未破壞既有行為。

---

## 9. 一句話總結

架構紮實、安全機制完善；**資料庫與 FastAPI 後端已完全同步**。

已完成的同步工作：

- ✅ 18 項資料庫 schema 變更全部落地
- ✅ 後端 schemas / models / routers / services 同步更新
- ✅ `employment_type` 正確遷移至 `staff_profiles`
- ✅ 新建資料表（notifications、attendance_summaries、payroll_records、audit_logs）模型 + schema 就緒

接下來的優先工作：**月度彙總 cron job + 結構化 logging**。主要功能已全部就緒。
