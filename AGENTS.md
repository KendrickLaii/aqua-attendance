# AGENTS.md — juku-attendance 專案規則

給 AI 助手與開發者的專案規則。詳細內容見 [docs/PROJECT-HANDBOOK.md](docs/PROJECT-HANDBOOK.md)。

## 文件結構（只維護這幾份）

| 檔案 | 用途 |
| ------ | ------ |
| `README.md` | 專案入口、快速開始（英文） |
| `CHANGELOG.md` | 版本歷史（Keep a Changelog，最新在上） |
| `USER-UPDATES.md` | 用戶版更新公告（粵語、無技術細節，標明【正式機】／【測試機】，可直接貼 WhatsApp） |
| `docs/PROJECT-HANDBOOK.md` | 唯一詳細文件：架構、各功能規則、部署、運維、已知缺口（§5）、資料庫設計與 ER 圖（§10） |
| `docs/archive/` | 舊工作紀錄，只讀，不再更新 |
| `apps/*/README.md`、`deploy/README.md` | 只放該資料夾的常用指令，細節連去手冊 |

不要在 `docs/` 新增其他文件；新內容寫進手冊對應章節。

## 每次改動必須同步的文件

| 改了什麼 | 要更新 |
| ------ | ------ |
| 任何會 push 到 `main` 的功能／修正 | `CHANGELOG.md` 最上面加一筆（新增／變更／修正／部署） |
| 用戶看得到的變化（新功能、畫面、列印、操作流程） | `USER-UPDATES.md` 最上面加一筆：日期（DD/MM/YYYY）、【正式機】或【測試機】、頁面網址、重點與使用方法；純內部改動（重構、文件、測試）不用寫 |
| 業務規則、API、頁面行為 | 手冊 §1 對應功能章節（§1.9 課程 … §1.14 Inventory） |
| 新 API 端點或權限 | 手冊 §1.6 授權表 |
| 新環境變數 | 手冊 §1.7（及 §3.7 如影響部署）、`apps/api/.env.example` |
| 新 migration | 手冊 §6.4 與 §10.1 的 Alembic head、§10.2／§10.3 ER 圖欄位 |
| 發現但暫不修的問題 | 手冊 §5 加一條 `#M<n>`／`#L<n>`（位置／問題／建議） |
| 修好 §5 的問題 | 從 §5 移除，記入 CHANGELOG |

歷史紀錄（「YYYY-MM-DD 更新」）只寫進 CHANGELOG，不要疊在手冊裡。

## 部署要點

- 兩台 Lightsail 都拉同一個 `:main` image。**push 到 `main` = 兩台下次跑 `update.sh` 都會拿到**。
- 測試機 `Ubuntu-testing-deploy`：git clone 在 `~/juku-attendance`，`git pull` 更新 compose，`INVENTORY_ENABLED=true`。
- 正式機 `Ubuntu-Aqua-Attendance`：手動複製在 `~/aqua-attendance/deploy`，compose 不會自動更新，`INVENTORY_ENABLED` 不設（預設 false）。
- 只給測試機的功能用 runtime flag（見 `/api/features`、`useFeatureFlags`），不要用 build-time `VITE_*` 變數。
- 先更新測試機確認，再更新正式機；正式機更新前跑 `./backup.sh`。

## 驗證指令

- API：`cd apps/api && python -m pytest -q`（全套約 15 分鐘；改動小時先跑相關測試檔）。
- Web：`cd apps/web && npm run typecheck`；改過的檔案跑 `npx eslint <files>`。
  - 已知既有錯誤：`src/api/attendance/staffShifts.ts` 一個型別錯誤，非新增。
- Migration：`cd apps/api && python -m alembic upgrade head`（PATH 上通常沒有裸 `alembic`）。

## Git

- Conventional Commits：`<type>(<scope>): <subject>`，一個 commit 一個邏輯變更。
- 程式碼和文件分開 commit（例如 `feat(...)` 再 `docs: ...`）。
- 不要 commit `apps/api/uvicorn_inv.log`、`.env`、`test.db`。
