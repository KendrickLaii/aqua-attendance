# AQUA Attendance — Web App

Vue 3 + Vite 管理後台。出勤相關 UI 位於 `src/pages/attendance/`。其餘為 AQUA 模板範例與示範頁面；生產環境導航僅連結 attendance 頁面。

## 日常開發

每次開發（API + DB 已就緒）：

```bash
# Terminal 1 — repo root（若未執行）
docker compose up -d db

# Terminal 2 — apps/api
python -m uvicorn app.main:app --reload

# Terminal 3 — apps/web
npm run dev
```

完整流程請見根目錄 [README.md](../../README.md#daily-development-recommended)。

## 首次設定

請先確認 API 正在運行（見 [apps/api/README.md](../api/README.md)）。

```bash
cd apps/web
cp .env.example .env
npm install
npm run dev
```

開啟：http://localhost:5173/attendance/login

預設登入：`admin` / `admin123`（API 執行 `python seed.py` 後）。

## 環境變數

| 變數 | 必填 | 說明 |
|------|------|------|
| `VITE_ATTENDANCE_API_URL` | 使用真實 API 時必填 | 例如 `http://localhost:8000/api` |

選用的模板變數（`VITE_MAPBOX_ACCESS_TOKEN` 等）與 attendance 頁面無關。

**生產環境**：`VITE_ATTENDANCE_API_URL` 在 **image build** 時烘焙進 bundle。執行 publish workflow 前，請先在 GitHub Actions Variables 設定 `VITE_ATTENDANCE_API_URL`。

## Attendance 頁面

| 路由 | 用途 |
|------|------|
| `/attendance/login` | 登入 |
| `/attendance/dashboard` | 儀表板 |
| `/attendance/products` | Product CRUD |
| `/attendance/qr-codes` | QR 取得 / 輪替 / 預覽 |
| `/attendance/log` | 事件紀錄、手動校正、CSV 匯出 |
| `/attendance/users` | User CRUD（admin） |

導航設定：`src/navigation/vertical/custom-pages.ts`（生產環境僅使用此列表）。

## API 客戶端

- `src/utils/attendanceApi.ts` — `ofetch`，Bearer token，401 自動 refresh
- `src/api/attendance/` — 型別化的 endpoint
- `src/stores/useAttendanceAuthStore.ts` — session + cookie

Token 儲存在 cookie（`attendanceAccessToken`）。相關注意事項請見 [docs/PROJECT-HANDBOOK.md](../../docs/PROJECT-HANDBOOK.md)。

## 建置

```bash
npm run build      # 輸出：dist/
npm run preview    # 本地預覽生產建置
```

Docker 生產 image：`prod.Dockerfile`（nginx 服務 `dist/`）。

## 停止服務

- 開發伺服器：在 web terminal 按 `Ctrl+C`
- 資料庫（從 repo root）：`docker compose down`

## 更多文件

- 根目錄 [README.md](../../README.md)
- [docs/PROJECT-HANDBOOK.md](../../docs/PROJECT-HANDBOOK.md) — 生產部署與運維手冊
