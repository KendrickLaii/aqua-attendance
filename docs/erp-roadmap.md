# 以後做成 ERP 的路線（不在本 repo 實作）

> **狀態**：規劃參考，**已決定不在 `juku-attendance` 這個 repo 裡做**。  
> **寫於**：2026-08-28；**2026-09-04 更新**：確認 ERP／庫存/採購若要做，是**獨立的全新專案**（獨立部署、獨立資料庫，不跟本系統共用 `units`/`course_*`），不是本系統的下一個 Phase。本文件保留作為**未來新專案的參考草稿**（命名、階段拆分、關鍵決策的思路仍然有效），但不會有任何 migration／程式碼在本 repo 落地。  
> **為什麼有這份**：學費月結已經上線。當初曾規劃系統以後可能長成 ERP（庫存、採購、資產、不只補習班收款），但後來確認家具/庫存這類需求應該由獨立系統處理，家具等物料**不要**塞進 `course_skus`／報名／學費 Generate，也**不要**進本系統的 `units`/`attendance_events`。

相關：學費現況見 [PROJECT-HANDBOOK.md](PROJECT-HANDBOOK.md) §1.10；課程缺口 #M22–#M24 見 [known-gaps.md](known-gaps.md)。

---

## 1. 一句話

現在是 **出勤 + 教育營運**（打卡、班次、月結學費、員工薪資）。  
以後 ERP 是 **多套單據、多套主檔**，共用「物料／人／據點」概念，**不共用**課程報名和按月 Generate。

---

## 2. 現在已經像 ERP 的哪些塊

| ERP 模塊 | 現況 | 以後不要拿來硬擴 |
| -------- | ---- | ---------------- |
| 主數據（據點、人員） | `locations`、`units`（能打卡的身份） | 不要把供應商、倉庫管理員全塞進 `units` |
| 出勤／工時 | 掃描、summaries | — |
| 薪酬 | `payroll_records` | — |
| 教育應收 | `course_*` + `tuition_invoices`（一學生一月一張） | 不要把庫存數量寫進堂費 `quantity` |
| 掃碼物品 | schema 預留 `device`／`goods` **unit_type** | **不是**庫存帳；那是「這張桌子有沒有進出大門」 |

Vuexy `/apps/invoice` 仍是模板假資料，**永遠不是**總帳或銷售發票。

---

## 3. 課程 vs 家具（為什麼不能同一張表）

兩邊都可以叫「物料」，但規則不同：

| | 課程 SKU | 庫存物料（家具等） |
| --- | --- | --- |
| 主檔 | `course_skus`（開班、月費／堂費、上課日） | 以後的 `items`（`item_type = inventory`） |
| 怎麼發生 | 報名視窗 + Generate | 採購入庫、調撥、銷售出庫、盤點 |
| quantity | 1 個月，或打卡堂數 | **庫存件數** 與 **單據件數** 是兩回事 |
| 重算 | 每月 Generate **整批替換課程行** | Generate **不得刪** 庫存／銷售行 |

學生買一張書桌 → 銷售單據 →（可選）出現在該月應收上，行類型不是 `course`。  
學校自己買桌椅放課室 → 採購／資產／庫存，**可以不上學生帳單**。

---

## 4. 分階段（按需要開工，不要一次做完）

**現在（Phase 0）** — 不做 ERP。把學費月結用穩；#M22 下學年重報、#M24 發給家長仍按產品優先。提交未提交的「停用學生不出學費／香港月 stale」即可。

**Phase A — 物料主檔**（真的要建家具檔才開）

- 新表 `items`：`code`、`name_zh`、`item_type`（`inventory`／`service`／以後再加）、預設單位、參考價、`is_active`。
- **不**改 `course_skus`。課程繼續只活在課程模塊。
- 可選：`item_type` 以後加 `asset`（課室固定資產，不進出庫存數量）。

**Phase B — 庫存數量**（家具「有幾張」）

- `stock_balances`：`(item_id, location_id)` → on-hand qty。  
- `stock_moves`：入／出／調整，有數量、日期、來源單據。  
- 據點 `locations` 可當倉庫；不夠再加 `warehouses`。

**Phase C — 採購（學校自己買家具）**

- `suppliers`（獨立主檔，不是 Unit）。  
- `purchase_orders` + 行：item、qty、單價。入庫時寫 `stock_moves`。  
- 這是應付（AP）方向，**不是** `tuition_invoices`。

**Phase D — 賣給家長／學生（可選）**

- 銷售單或應收行：`line_kind = product`，qty = 件數。  
- 改學費 Generate：**只替換／刪除 `line_kind = course`（或有 `enrollment_id` 的行）**。product 行留下。  
- 該月沒有學費票時，可以先開一張當月 draft 再加產品行（仍用「一學生一月一張」若產品同意；否則獨立銷售發票）。

**Phase E — 真・ERP 財務（很後面）**

- 抽「應收憑證」：`doc_type = tuition_month | sales | ...`。`tuition_invoices` 當教育月結來源，不要急著改名翻表。  
- 客戶／供應商 `partners`；`units` 繼續只表示能打卡的人。  
- 多組織（multi-tenant）仍未做；做 ERP 前先決定要不要。

---

## 5. 關鍵決定（已拍板，避免以後吵）

| 決定 | 選擇 | 理由 |
| --- | --- | --- |
| 家具進不進 `course_skus` | **不進** | Generate、上課日、報名約束都會錯 |
| 學費 Generate 範圍 | **永遠只產課程行** | 否則一按 Generate 家具行消失 |
| `units.goods` | **不是庫存** | 掃碼身份 ≠ 倉庫結存 |
| 兩種 quantity | **分開** | 庫存 on-hand vs 訂單／發票件數 |
| Vuexy invoice | **不用** | 假資料 |
| 要不要在本 repo 做 | **不做**（2026-09-04 拍板） | ERP／庫存是獨立業務，跟出勤/學費沒有共用資料的必要；硬塞會逼 `units`/`course_skus` 背負不屬於它們的語意 |
| 何時開工（新專案） | **有真實採購或銷售流程，且確定要開新專案時** | 現在做主檔沒人用會爛；本文件下面的階段拆分留給那個新專案參考 |

以下 Phase A–E、§6 表結構草圖、§7 檢查清單，全部改為**未來獨立 ERP 專案**的參考草稿，不會有對應的本 repo migration。待產品再定：賣家具是併進該月學費票，還是獨立銷售發票——這題等新專案啟動時再討論，不影響本 repo。

---

## 6. 以後表長什麼樣子（草圖，不是 migration）

```
items                          # 物料主檔（非課程）
  id, code, name_zh, item_type, uom, default_price, is_active

stock_balances                 # 結存
  item_id, location_id, qty

stock_moves                    # 流水
  item_id, location_id, qty_delta, moved_at, source_type, source_id

suppliers                      # 採購對象
  id, name, ...

purchase_orders / po_lines     # 採購單

# 學費票先不動表名。Phase D 起行上加：
# tuition_invoice_lines.line_kind  = course | product
# tuition_invoice_lines.item_id    nullable  （product 用）
# enrollment_id / sku_id 仍只給 course
```

課程 Generate 偽代碼（Phase D 起）：

```
replace only lines where line_kind == course
keep product lines
recompute invoice.total = sum(all remaining lines)
```

---

## 7. 開工檢查清單（新專案啟動時參考，不是本 repo 的待辦）

- [ ] 確認要開一個獨立的新專案（獨立部署、獨立資料庫），不是在 `juku-attendance` 裡加模塊
- [ ] 產品確認：家具是課室資產、是倉庫買賣、還是賣給家長（可多選，模塊不同）
- [ ] 新專案的 `items` 主檔；一個極簡物料頁
- [ ] 入出庫（`stock_moves`）；倉庫/據點主檔獨立於本系統的 `locations`
- [ ] 若賣給學生：如果新專案要跟本系統的學費票整合，改本系統的 Generate **不刪** 非課程行，再允許加行（這一步才會碰到本 repo，且僅限這一個整合點）
- [ ] 不要從 Vuexy `/apps/invoice` 抄業務

**不要做**：把 `billing_unit` 加一個 `furniture`；用報名表代表「買了桌子」；把家具/庫存塞進本 repo 的 `units`、`course_skus` 或 `attendance_events`。
