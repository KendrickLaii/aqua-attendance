# Operations Runbook — AQUA Attendance

故障排查與日常維運手冊。所有指令在 **生產主機** 的 `deploy/` 目錄執行(該目錄需有 `.env` 與 `docker-compose.prod.yml`)。

> 相關文件:[DEPLOY.md](./DEPLOY.md)(首次部署)、[KNOWN-GAPS.md](./KNOWN-GAPS.md)(已知缺口)。

---

## 0. 快速健康檢查

```bash
cd deploy

# 服務狀態
docker compose -f docker-compose.prod.yml ps

# API 健康(含 DB 連線檢查)
curl -fsS http://localhost:8000/api/health        # 容器網路內
curl -fsS https://<API_DOMAIN>/api/health         # 經 Caddy 對外

# 即時日誌(最後 100 行 + 跟隨)
docker compose -f docker-compose.prod.yml logs -n 100 -f api
```

`/api/health` 回傳:
- `{"status":"ok","database":"ok"}` → 正常
- HTTP 503 `Database unavailable: ...` → API 起來了但連不到 DB(見 §2)

---

## 1. API 容器起不來 / 一直重啟

**症狀**:`docker compose ps` 顯示 `api` 為 `restarting` 或 `exited`。

```bash
docker compose -f docker-compose.prod.yml logs -n 200 api
```

| 日誌訊息 | 原因 | 處理 |
|----------|------|------|
| `SECRET_KEY must be at least 32 characters...` / `must not use the example placeholder` | `ENV=production` 但 `SECRET_KEY`/`QR_SECRET` 是佔位符或太短 | 在 `.env` 設真實值:`openssl rand -hex 32`,各自獨立,然後 `docker compose ... up -d api` |
| `Can't connect to ...:5432` / `Connection refused` | DB 尚未就緒或連線字串錯 | 見 §2 |
| `alembic ... Target database is not up to date` / migration 報錯 | 遷移失敗 | 見 §3 |
| `Address already in use` | 連接埠衝突 | `docker compose ... down` 後重起;確認無其他服務佔 8000 |

啟動指令會先跑 `alembic upgrade head` 再起 uvicorn(見 `docker-compose.prod.yml` api `command`)。migration 失敗會導致容器退出。

**重啟單一服務**:
```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate api
```

---

## 2. 資料庫連不上 (`/api/health` 回 503)

```bash
# DB 容器是否健康
docker compose -f docker-compose.prod.yml ps db

# DB 內部就緒檢查
docker compose -f docker-compose.prod.yml exec db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"

# DB 日誌
docker compose -f docker-compose.prod.yml logs -n 100 db
```

檢查清單:
1. `.env` 的 `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` 與 API 的 `DATABASE_URL` 一致。
2. DB healthcheck 是否 `healthy`(api `depends_on: condition: service_healthy`,DB 不健康 API 不會起)。
3. 磁碟是否滿(見 §6)— Postgres 寫不進會拒絕連線。
4. `pgdata` volume 未損壞:`docker volume inspect deploy_pgdata`。

---

## 3. 資料庫遷移 (migration) 問題

```bash
# 目前 DB 版本
docker compose -f docker-compose.prod.yml exec api alembic current

# 最新可用版本(應為 013 或更新)
docker compose -f docker-compose.prod.yml exec api alembic heads

# 手動升級到最新
docker compose -f docker-compose.prod.yml exec api alembic upgrade head

# 升級時看詳細 SQL
docker compose -f docker-compose.prod.yml exec api alembic upgrade head --sql
```

| 情境 | 處理 |
|------|------|
| `current` 落後於 `heads` | 跑 `alembic upgrade head` |
| 升級中途失敗 | 先看錯誤;**升級前務必有備份**(§4)。必要時 `alembic downgrade -1` 回退一步後修正 |
| 很舊的 DB(含 003 之前 `user_id` attendance 列) | 可能需手動遷移,見 [KNOWN-GAPS.md](./KNOWN-GAPS.md) API/data 段 |

> 註:`013_attendance_recorded_at_indexes` 在大表上建索引可能花數秒~數分鐘;期間查詢仍可用(Postgres 預設鎖較輕,但避開尖峰執行)。

---

## 4. 備份與還原

### 手動備份
```bash
cd deploy
./backup.sh
# 產出 ./backups/<DB>_<timestamp>.sql.gz,自動保留最近 14 份
```

### 還原(會先停 API、DROP 並重建 DB)
```bash
cd deploy
./restore.sh ./backups/<DB>_<timestamp>.sql.gz
# 無參數列出可用備份
```

⚠️ 還原是 **破壞性** 操作:會 `DROP DATABASE` 後重建。執行前確認選對檔案,並建議先跑一次 `./backup.sh` 留現況。

### 排程備份(建議)
```bash
# crontab -e — 每天 03:00 備份
0 3 * * * cd /path/to/deploy && ./backup.sh >> ./backups/backup.log 2>&1
```

### 驗證備份可用
定期在非生產環境跑一次 `restore.sh`,確認備份檔可成功還原(備份未經還原測試不算備份)。

---

## 5. 認證 / 登入相關

| 症狀 | 可能原因 | 處理 |
|------|----------|------|
| 全部使用者一直被登出 | refresh 競態(Web/Mobile 並發 401)— 見 KNOWN-GAPS Code review #2/#3 | 待修;暫時避免同時開多分頁狂點 |
| 登入後馬上 401 | access token 30 分過期 + refresh 失敗;或前後端時鐘偏移 | 確認主機時間 `date -u`,NTP 同步 |
| 手機登入後 Web 被踢 | 設計上 `login` 撤銷該用戶所有 refresh token(單一 session)| 預期行為,見 KNOWN-GAPS #11 |
| 429 Too many requests | 命中限流(login 5/min、scan 30/min)| 正常防護;可在 `.env` 調 `LOGIN_RATE_LIMIT` / `SCAN_RATE_LIMIT` |
| 掃 QR 回 `Invalid QR: token has been rotated` | QR 已被輪替(版本不符)| 在 Web 重新產生該 product 的 QR |

重設某用戶密碼(無自助流程):由 superadmin 在 Web User Management,或直接改 DB(最後手段)。

---

## 6. 磁碟 / volume / 日誌膨脹

```bash
# 容器與 volume 用量
docker system df

# Docker 容器日誌大小(JSON file driver 預設無上限)
du -sh /var/lib/docker/containers/*/*-json.log 2>/dev/null | sort -h | tail
```

**日誌輪替(建議設定)** — 在 `docker-compose.prod.yml` 每個服務加:
```yaml
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
```
(目前 compose 未設,屬已知缺口 — 見 KNOWN-GAPS。)

**清理**:
```bash
docker image prune -f          # 移除無用 image
docker builder prune -f        # 清 build cache(若主機有 build)
# 舊備份已由 backup.sh 自動保留最近 14 份
```

⚠️ 不要 `docker volume prune`,以免誤刪 `pgdata`。

---

## 7. TLS / 域名 / Caddy

```bash
docker compose -f docker-compose.prod.yml logs -n 100 caddy
```

| 症狀 | 處理 |
|------|------|
| 憑證取得失敗 | 確認 `APP_DOMAIN`/`API_DOMAIN` DNS 已指向本機 IP、80/443 對外開放;Caddy 需 80 做 ACME |
| 502 Bad Gateway | 後端 `web`/`api` 未健康;見 §0/§1 |
| 改了 Caddyfile 沒生效 | `docker compose ... up -d --force-recreate caddy` |

---

## 8. 完整重啟 / 緊急回滾

```bash
cd deploy

# 平滑重啟全部
docker compose -f docker-compose.prod.yml up -d

# 回滾到先前的 image tag(GHCR)— 改 .env 的 API_IMAGE / WEB_IMAGE 指向舊 tag
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# 完整停機(保留資料 volume)
docker compose -f docker-compose.prod.yml down
```

⚠️ `down -v` 會刪除 volumes(含資料庫)— **絕不要在生產用 `-v`**。

---

## 升級前檢查清單(SOP)

1. `./backup.sh` 並確認備份檔產生。
2. `docker compose ... pull` 拉新 image。
3. `docker compose ... up -d`(會自動跑 `alembic upgrade head`)。
4. `curl .../api/health` 確認 `database: ok`。
5. 抽測:登入、掃一筆、看歷史、匯出 CSV。
6. 觀察 `logs -f api` 幾分鐘無異常。
7. 出問題 → §8 回滾 + 必要時 `./restore.sh`。
