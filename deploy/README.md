# 生產部署

生產伺服器腳本與 compose 檔案。

詳細部署指南請見 [docs/PROJECT-HANDBOOK.md](../docs/PROJECT-HANDBOOK.md) §3。

## 前置需求

- Ubuntu 22.04+（或任何有 Docker 的 Linux）
- 已登入 GitHub Container Registry（GHCR）以拉取私有 image
- DNS A 記錄將 `APP_DOMAIN` 與 `API_DOMAIN` 指向伺服器 IP

## 首次設定

```bash
cd deploy/
cp .env.example .env
# 編輯 .env — 設定 SECRET_KEY、QR_SECRET、POSTGRES_PASSWORD、域名、image tag
./first-boot.sh
```

## 更新（新版本 image）

```bash
cd deploy/
./update.sh
```

## 備份

### 手動備份

```bash
cd deploy/
./backup.sh
```

備份檔寫入 `./backups/`，自動保留最近 14 份。

### 排程備份（建議）

加入伺服器 crontab，每天 03:00 自動備份：

```bash
0 3 * * * cd /path/to/deploy && ./backup.sh >> ./backups/backup.log 2>&1
```

## 還原

```bash
cd deploy/
./restore.sh backups/attendance_20250604_030000.sql.gz
```

**警告**：還原會先 DROP 既有資料庫，再從備份重建。還原期間 API container 會被停止。

## 檔案說明

| 檔案 | 用途 |
|------|------|
| `docker-compose.prod.yml` | 生產服務（Caddy、web、API、PostgreSQL、Redis） |
| `Caddyfile` | 反向代理 + HTTPS（自動 TLS） |
| `.env` | 密鑰與設定（不在 git 中） |
| `first-boot.sh` | 安裝 Docker、拉取 image、啟動服務 |
| `update.sh` | 拉取最新 image 並重啟 container |
| `backup.sh` | `pg_dump` + gzip + 輪替 |
| `restore.sh` | 從 `.sql.gz` 備份還原 |
