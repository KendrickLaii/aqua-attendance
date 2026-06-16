# AQUA 文件索引

本目錄 (`docs/`) 存放部署、運維與專案治理相關文件。程式碼層級的開發說明（API、Web、Mobile 的啟動指令、環境變數、元件說明）位於各 `apps/<層級>/README.md`。

---

## 按角色快速導航

| 你是誰 | 先讀這裡 | 下一步 |
|--------|----------|--------|
| **新進開發者** | [../README.md](../README.md) | 針對你負責的層級讀對應 App README |
| **後端開發者** | [../apps/api/README.md](../apps/api/README.md) | [PROJECT-HANDBOOK.md](PROJECT-HANDBOOK.md) §2 本地開發 |
| **前端開發者** | [../apps/web/README.md](../apps/web/README.md) | [PROJECT-HANDBOOK.md](PROJECT-HANDBOOK.md) §5 已知缺口 |
| **Mobile 開發者** | [../apps/mobile/README.md](../apps/mobile/README.md) | [PROJECT-HANDBOOK.md](PROJECT-HANDBOOK.md) §7 Mobile 開發與發布 |
| **DevOps / 部署** | [PROJECT-HANDBOOK.md](PROJECT-HANDBOOK.md) §3 生產部署 | [PROJECT-HANDBOOK.md](PROJECT-HANDBOOK.md) §6 運維手冊 |
| **維運值班** | [PROJECT-HANDBOOK.md](PROJECT-HANDBOOK.md) §6 運維手冊 | 本頁下方的「常見問題對照表」 |

---

## 文件總覽

| 文件 | 類型 | 內容 | 更新頻率 |
|------|------|------|----------|
| [../README.md](../README.md) | 總覽 | 系統架構、概念對照表（Product vs User）、QR 流程、快速開始、倉庫結構 | 架構變更時 |
| [PROJECT-HANDBOOK.md](PROJECT-HANDBOOK.md) | 手冊 | 本地開發、生產部署（Docker/Caddy）、CI/CD 流程、運維手冊、已知缺口與評分、Mobile 發布、發布紀錄 | 持續累積 |
| [../apps/api/README.md](../apps/api/README.md) | 開發 | FastAPI 啟動、測試、環境變數、Alembic、seed 資料 | API 變更時 |
| [../apps/web/README.md](../apps/web/README.md) | 開發 | Vue 3 開發伺服器、Vite 設定、出勤頁面路由、AQUA 模板注意事項 | Web 變更時 |
| [../apps/mobile/README.md](../apps/mobile/README.md) | 開發 | Expo 啟動、QR Scanner 設定、實體裝置 LAN IP 設定、entry-point 限制 | Mobile 變更時 |
| [../REVIEW-PROMPT.md](../REVIEW-PROMPT.md) | 流程 | 合併前檢查清單與 Code Review 提示 | 流程調整時 |
| [../deploy/README.md](../deploy/README.md) | 部署 | 生產主機目錄結構、輔助腳本說明（`first-boot.sh`、`update.sh`、`reset-db.sh`） | 部署腳本變更時 |
| [BACKEND_REVIEW.md](BACKEND_REVIEW.md) | 審查 | FastAPI 後端審查與修復計畫 — 架構評價、已修問題、待補缺口 | 後端重大變更時 |
| [DATABASE_CHANGES.md](DATABASE_CHANGES.md) | 設計 | 資料庫設計 Single Source of Truth — ER 圖、欄位搬遷、OT 計算 | Schema 變更時 |

---

## 常見問題對照表（快速查閱）

> 以下問題在 [PROJECT-HANDBOOK.md](PROJECT-HANDBOOK.md) §6 均有詳細指令，此表僅供快速定位章節。

| 問題 | 章節 |
|------|------|
| API container 不斷重啟 | §6.2 |
| `/api/health` 回 503 | §6.3 |
| Migration 失敗 / 版本不對 | §6.4 |
| 如何備份 / 還原資料庫 | §6.5 |
| 登入後馬上 401 / 被登出 | §6.6 |
| 磁碟滿 / Docker 日誌膨脹 | §6.7 |
| CI 流程說明 | §4 |
| 上線前安全檢查清單 | §3.14 |
| 已知缺口與優先順序 | §5 |

---

## 閱讀順序建議

1. **理解系統**：Root README（`Product` 與 `User` 的區別、QR 簽到流程）
2. **針對層級**：開啟你正在修改的 `apps/<層級>/README.md`
3. **部署或維運**：翻開 `PROJECT-HANDBOOK.md`，依角色看對應章節
4. **合併前**：確認 `REVIEW-PROMPT.md` 的檢查清單
