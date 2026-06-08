# AQUA Attendance — Mobile App

Expo（React Native）QR 掃描與出勤紀錄查詢 App。登入帳號為 **admin**（`admin` 或 `superadmin`），非學生。

學生與教職員**不需登入** — 他們攜帶在 Web App 建立的 Product QR（**QR Codes** / **Product Management**）。

## 各平台的 API URL

| 執行方式 | `EXPO_PUBLIC_API_URL` |
|----------|----------------------|
| **Android 模擬器**（按 `a`）| `http://10.0.2.2:8000/api` |
| **Expo web**（按 `w`）| `http://localhost:8000/api` |
| **實體手機**（Expo Go QR）| `http://<PC-LAN-IP>:8000/api` + API `--host 0.0.0.0` |

`10.0.2.2` 是模擬器連回 PC `127.0.0.1` 的別名。

## Web 與手機

按 **`w`** 會在**瀏覽器**開啟 App。Web 模式下 token 使用 `localStorage`（`src/services/storage.ts`）。

**QR 相機掃描**請使用 **Android 模擬器**（`a`）或**實體裝置** — 瀏覽器無法掃描。

## 語言

App 支援 **English** 與 **繁體中文**。登入畫面或登入後頂部可切換 **EN / 繁中**。選擇會儲存在裝置上；首次啟動依手機語言（中文 → 繁中，其餘 → English）。

翻譯檔：`src/i18n/locales/en.ts`、`src/i18n/locales/zh-Hant.ts`。

## 快速開始

```bash
cd apps/mobile
cp .env.example .env
npm install
npx expo start
```

### Expo Go：`Failed to download remote update`

手機無法連線到 PC 的 Metro（防火牆、VPN 或 Wi-Fi 隔離）。依序嘗試：

1. **Tunnel 模式**（最穩定）：`npm run start:tunnel` — 在 Expo Go 掃描新的 QR code。
2. 關閉 PC 與手機的 **VPN**（例如 Surfshark）。
3. 確認同一 **Wi-Fi**；Windows 防火牆：允許 **Node.js** 在私人網路（port **8081**、**8000**）。
4. 從商店更新 **Expo Go**（專案使用 **Expo SDK 54** — 需與手機 App 版本匹配）。
5. Expo Go App 選單 → 清除快取，或在 PC 執行 `npx expo start -c`。

使用 Expo Go 時，`.env` 中的 API URL 必須是 PC 的 LAN IP（不可使用 `localhost`）。

### 環境變數

| 變數 | 範例 | 說明 |
|------|------|------|
| `EXPO_PUBLIC_API_URL` | `http://192.168.1.50:8000/api` | 實體裝置請使用 PC 的 **LAN IP**（非 `localhost`）|

請確認 API 正在運行。Native fetch 不受 CORS 限制；web 模式可能仍需設定 `CORS_ORIGINS`。

### 種子登入（API 執行 `python seed.py` 後）

| Username | Password | Scan tab |
|----------|----------|----------|
| admin | admin123 | Yes |
| superadmin | super123 | Yes |

## 功能

| Tab | 說明 |
|-----|------|
| **My QR** | 說明文字 — Product QR 在 **Web App** 管理 |
| **Scan** | 相機掃 QR → `POST /api/attendance/scan`，可選 **location** 與 **簽到/簽退** |
| **History** | 最近出勤事件（下拉重新整理） |

## 進入點

App 透過 `package.json` 的 `"main": "expo/AppEntry.js"` 載入 **`App.tsx`**。

`app/index.tsx` 僅為 Expo Router stub — 請勿將 `expo-router/entry` 設為 `main`，否則 Expo Go 可能顯示錯誤畫面。

## 手動測試流程

1. 啟動 API + DB + seed：`admin` / `admin123`，products `STU-001` 等。
2. Web：建立一個 active **location**（需填英文名稱）。
3. Web：**QR Codes** → **STU-001** → 在另一個畫面顯示 QR。
4. Mobile：登入 → **Scan** → 選擇**預設 location**（儲存在裝置上）→ 每次選擇**簽到/簽退** → **Start scanning** → 掃描 QR。
5. 確認 modal 顯示姓名 + location。
6. **History** → 事件出現並顯示 location。
7. **Logout** → server 端 refresh token 被撤銷。
8. **Debounce：** 同一動作 3 秒內重複 → 不產生重複 row。
9. **Rotate QR：** Web 點 **Refresh QR** → 舊 QR 失效。

## 專案結構

```
App.tsx                 # Root：login vs tabs
src/
  navigation/AppNavigator.tsx
  screens/LoginScreen.tsx, ScannerScreen.tsx, HistoryScreen.tsx, QRDisplayScreen.tsx
  services/api.ts, auth.ts, attendance.ts, locations.ts
app/index.tsx           # Expo Router stub（非 attendance app）
```

## Sprint 與發布文件

- [docs/PROJECT-HANDBOOK.md](../../docs/PROJECT-HANDBOOK.md) — Mobile 開發與發布檢查清單（§7）

## 生產建置

1. 將 `EXPO_PUBLIC_API_URL` 設為生產 API，例如 `https://api.yourdomain.com/api`
2. 使用 EAS 或 `expo prebuild` + native toolchain 建置
3. 遵循 [docs/PROJECT-HANDBOOK.md](../../docs/PROJECT-HANDBOOK.md) 中的發布檢查清單

詳見根目錄 [README.md](../../README.md) 與 [docs/PROJECT-HANDBOOK.md](../../docs/PROJECT-HANDBOOK.md)。
