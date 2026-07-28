# 文件審計 — 問題清單

> 審計日期：2026-07-10；本次更新：2026-07-28
> 目的：列出 `docs/` 中所有過時、缺失、不一致的項目，作為後續更新依據。

---

## 1. project-handbook.md（統合手冊）

### 1.1 全局問題

| # | 問題 | 嚴重度 |
|---|------|--------|
| G1 | ~~最後更新日期仍為 2026-06-16~~ | ✅ 已修（2026-07-10） |
| G2 | ~~缺少 ER 圖~~ | ✅ 已修 — HANDBOOK §10 加入完整 erDiagram |
| G3 | ~~目錄未包含 Summaries / Payroll 相關章節~~ | ✅ 已修 — §8 加入 2026-06/2026-07 release notes |
| G4 | ~~統合來源列表未包含 attendance-summaries.md~~ | ✅ 已修 |

### 1.2 §1.6 API 授權表（L89–103）

| # | 問題 | 狀態 |
|---|------|------|
| A1 | ~~缺少 attendance-summaries 端點~~ | ✅ 已修 |
| A2 | ~~缺少 payroll-records 端點~~ | ✅ 已修 |
| A3 | ~~缺少 notifications 端點~~ | ✅ 已修 |
| A4 | ~~缺少 audit-logs 端點~~ | ✅ 已修 |
| A5 | ~~缺少 auto-checkout 端點~~ | ✅ 已修（**僅手動 API**；排程仍缺 → known-gaps #M14） |
| A6 | ~~缺少 staff-profiles / student-profiles 端點~~ | ✅ 已修 |

### 1.3 §1.7 環境變數（L107–121）

| # | 問題 | 狀態 |
|---|------|------|
| E1 | ~~缺少 REDIS_URL~~ | ✅ 已修 |

### 1.4 §5 已知缺口與代碼審查（L610–655）

| # | 問題 | 狀態 |
|---|------|------|
| K1 | ~~§5.1 #5 狀態不一致~~ | ✅ 已修 — #1–#21 細節已移至 known-gaps.md |
| K2 | ~~§5.2 #6–#14 未更新狀態~~ | ✅ 已修 — 所有項目標註當前狀態 |
| K3 | ~~§5.3 #15–#21 未更新狀態~~ | ✅ 已修 |
| K4 | ~~§5.4 行動計劃過時~~ | ✅ 已修 |
| K5 | ~~§5.5 評分日期過時~~ | ✅ 已修 — 更新至 2026-07，分數調整 |

### 1.5 §6.4 資料庫遷移（L847–867）

| # | 問題 | 狀態 |
|---|------|------|
| M1 | ~~migration 編號過時~~ | ✅ 已修 — 更新至 026 |
| M2 | ~~Migration 編號跳躍未解釋~~ | ✅ 已修 |
| M3 | ~~未列出後續 migration~~ | ✅ 已修 |

### 1.6 §7 Mobile 開發與發布（L977–1135）

| # | 問題 | 狀態 |
|---|------|------|
| MB1 | ~~Phase 3 M3.1 狀態矛盾~~ | ✅ 已修 — 標 ✅ Done |
| MB2 | Phase 3 M3.5「Mobile 顯示 unit QR（admin）」標「待排」，需確認狀態 | 🟡 |
| MB3 | Phase 4 全部標 ⬜，需確認是否有進展 | 🟡 |
| MB4 | ~~§7.2 API 對照表缺少新端點~~ | ✅ 已修 — 保留 Mobile 專用端點 |
| MB5 | ~~§7.3 功能對照缺少 Summaries/Payroll~~ | ✅ 已修 — 加入新列 |
| MB6 | ~~目錄結構過時~~ | ✅ 已修 — 加入 §7.2 現況目錄樹 |
| MB7 | ~~發布檢查清單 migration 編號過時~~ | ✅ 已修 — 更新至 026 |

### 1.7 §8 發布記錄（L1137–1201）

| # | 問題 | 狀態 |
|---|------|------|
| R1 | ~~缺少 2026-06 / 2026-07 release notes~~ | ✅ 已修 — 加入兩個新 release |

### 1.8 §9.2 技術債追蹤（L1230–1243）

| # | 問題 | 狀態 |
|---|------|------|
| T1 | ~~多項狀態過時~~ | ✅ 已修 — 加入 Summaries/Payroll/Mobile/API 新項目 |
| T2 | ~~缺少 Summaries/Payroll 技術債~~ | ✅ 已修 — 移至 known-gaps.md |
| T3 | ~~缺少 Mobile 新項目~~ | ✅ 已修 |
| T4 | 「RBAC tests」仍寫 ~53，需確認最新測試數量 | 🟢 |

### 1.9 §9.3 文件評分卡（L1245–1260）

| # | 問題 | 狀態 |
|---|------|------|
| D1 | ~~日期 2026-06~~ | ✅ 已修 — 更新至 2026-07 |
| D2 | ~~操作手冊評分過低~~ | ✅ 已修 — 5→7 |
| D3 | Docs 待補表「可觀測性文件」仍 pending | 🟡 |

---

## 2. attendance-summaries.md

| # | 問題 | 嚴重度 |
|---|------|--------|
| S1 | §5.2 已知限制「金額」項說「Payroll generate 已依 staff_profiles 薪資率…計算」— 此項**已不是限制**，應移至已實作清單 | 🟢 |
| S2 | §5.3「Payroll 薪資率模型（已實作）」放在「後續可選改善」— 應移至已完成的章節 | 🟢 |

---

## 3. known-gaps.md

| # | 問題 | 嚴重度 |
|---|------|--------|
| B1 | 日期 2026-06-16，§4–§7 多項已標完成但分散在各階段，不易一眼看出整體進度 | 🟡 |
| B2 | ~~§5.3 `business_hours` 未被服務層使用~~ | ✅ 已修 — `services/overtime.py:_location_close_time` 已讀取 `location.business_hours` 判斷關門時間，用於 OT 計算 |
| B3 | §5.4 列表端點無排序參數 — 仍為現況（固定排序，未開放 `sort_by`/`sort_order`） | 🟢 |
| B4 | §7 階段四「結構化 logging + request id」仍 pending | 🟡 |
| B5 | §8 測試狀態仍寫 53 passed — 需確認最新測試數量 | 🟡 |

---

## 4. database-changes.md

| # | 問題 | 嚴重度 |
|---|------|--------|
| DB1 | ER 圖完整，但未被 HANDBOOK 引用 | 🟡 |
| DB2 | 需確認是否涵蓋所有最新 migration（001–026）的 schema 變更 | 🟡 |

---

## 5. project-handbook.md

| # | 問題 | 嚴重度 |
|---|------|--------|
| F1 | 日期 2026-06-16，多項對齊任務可能已完成但未標記 | 🟡 |
| F2 | 未涵蓋 Summaries / Payroll 頁面的前端對齊 | 🔴 |

---

## 6. INDEX.md

| # | 問題 | 嚴重度 |
|---|------|--------|
| I1 | ~~未列出新文件~~ | ✅ 已修 — 加入 attendance-summaries.md、docs-audit.md、known-gaps.md |

---

## 7. 後端架構審查補充（2026-07-21）

本次審查後新增/確認的文件缺口：

| # | 問題 | 嚴重度 |
|---|------|--------|
| AR1 | `KNOWN-GAPS.md` 應新增 **午休未扣除**（直接影響薪資） | 🔴 |
| AR2 | `KNOWN-GAPS.md` 應新增 **Payroll 依賴手動 Generate summaries** | 🟡 |
| AR3 | `KNOWN-GAPS.md` 應新增 **Void 後 summary 不自動重算** | 🟡 |
| AR4 | `KNOWN-GAPS.md` 應新增 **Generate 端點無互斥鎖** | 🟡 |
| AR5 | `KNOWN-GAPS.md` 應新增 **`units.attendance_status` 非正規化一致性** | 🟡 |
| AR6 | `attendance-summaries.md`、`database-changes.md` 應補充 break 計算現況 | 🟡 |

---

## 優先級摘要

### 🔴 立即處理（全部完成 ✅）
1. ~~HANDBOOK 全域日期更新~~ ✅
2. ~~HANDBOOK §5 已知缺口 — 標記所有已修項目~~ ✅（細節移至 known-gaps.md）
3. ~~HANDBOOK §7 Mobile — 更新 Phase 3/4 狀態、目錄結構~~ ✅
4. ~~HANDBOOK §9.2 技術債 — 更新狀態、加入新項目~~ ✅
5. ~~`project-handbook.md` — 加入 Summaries/Payroll 對齊~~ ✅（已涵蓋）

### 🟡 近期處理（全部完成 ✅）
6. ~~HANDBOOK 加入 ER 圖~~ ✅（§10）
7. ~~HANDBOOK §1.6 API 授權表補全~~ ✅
8. ~~HANDBOOK §1.7 環境變數加入 REDIS_URL~~ ✅
9. ~~HANDBOOK §6.4 migration 編號更新~~ ✅
10. ~~HANDBOOK §8 加入 2026-06 / 2026-07 release notes~~ ✅
11. known-gaps.md 更新過時項目 — 部分完成：2026-07-17 已加 **#M14 auto checkout 非完整自動版**；M10/M11 等仍待對照程式碼更新 ⬜

### 🟢 可延後
12. attendance-summaries.md 微調（S1、S2）— FAQ／限制已補 auto checkout 現況 ✅（其餘 S1/S2 另審）⬜
13. ~~INDEX.md 更新文件列表~~ ✅
14. ~~釐清 auto checkout「設計 vs 實作」~~ ✅（known-gaps #M14、database-changes、handbook、API docstring）

---

## 8. 全面審計補充（2026-07-28）

本次審計涵蓋 product → unit 重構後的完整系統審查（ORM、routers、services、web、mobile、docs）。

### 8.1 database-changes.md

| # | 問題 | 狀態 |
|---|------|------|
| DB3 | ~~ER 圖未反映實際 DB 狀態~~ | ✅ 已修 — ER 圖已更新為 2026-07-28 實際 DB 狀態 |
| DB4 | ~~Migration 歷史未包含 032~~ | ✅ 已修 — 已更新至 032 |
| DB5 | ~~缺少 Legacy constraint/index 名稱清單~~ | ✅ 已修 — 新增 § Legacy 約束與索引名稱 |
| DB6 | ~~缺少個人資料搬移狀態追蹤~~ | ✅ 已修 — 新增 § 個人資料欄位搬移狀態；migration `f8e65b7cf82b` 已於 2026-07-28 執行完畢 |

### 8.2 known-gaps.md

| # | 問題 | 狀態 |
|---|------|------|
| B6 | ~~缺少 product → unit 重構記錄~~ | ✅ 已修 — 已加入已完成區 |
| B7 | ~~缺少個人資料搬移未執行缺口~~ | ✅ 已修 — 新增 #M20 |
| B8 | ~~缺少 legacy constraint/index 名稱缺口~~ | ✅ 已修 — 新增 #M21 |

### 8.3 project-handbook.md

| # | 問題 | 狀態 |
|---|------|------|
| F3 | Migration 編號仍為 026，應更新至 032 | ✅ 已修 — 已更新至 032，並補上 `f8e65b7cf82b` 個人資料欄位調整 migration |
| F4 | §10 ER 圖可能與 database-changes.md 不一致（需同步更新） | ✅ 已修 — 兩份文件 ER 圖已同步，且與實際 DB 一致 |

### 8.4 程式碼審計結果

| # | 項目 | 結果 |
|---|------|------|
| CA1 | 後端 `apps/api/app/` product 殘留 | ✅ 零殘留 |
| CA2 | Web `apps/web/src/` product 殘留 | ✅ 僅模板/demo 檔案（非業務代碼） |
| CA3 | Mobile `apps/mobile/src/` product 殘留 | ✅ 零殘留 |
| CA4 | ORM 模型 vs DB schema 對齊 | ✅ 全部對齊 |
| CA5 | API schema 欄位名稱 | ✅ 全部使用 unit 命名 |
| CA6 | 前端 API 呼叫欄位名稱 | ✅ 全部使用 unit 命名 |
| CA7 | `seed.py` 欄位名稱 | ✅ 全部使用 unit 命名 |
