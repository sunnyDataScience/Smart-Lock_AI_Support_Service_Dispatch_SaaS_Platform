---
title: 部署指南（Deployment Guide）
version: 1.0
status: active
owner: 平台維運（DevOps / FDE）
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P005_per-brand授權部署_大單體內部容器.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P012_執行債清償排程_cutover_migration_CD.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P003_Casdoor_統一IdP_租戶_License.md
  - smartlock-docs/00_platform/P1/05_platform_architecture_L1.md
  - smartlock-docs/api/P1/05_architecture_and_design.md
  - smartlock-docs/api/P2/04_adr/ADR-002_psycopg3_raw_SQL_與純SQL_migration.md
  - smartlock-docs/agent/P1/05_architecture_and_design.md
  - smartlock-docs/data-pipeline/P2/04_adr/ADR-002_純SQL_forward-only_migration_不用Alembic.md
---

# 23. 部署指南 — Smart Lock AI 客服與派工 SaaS 平台

> 讀者：DevOps / 平台維運 / FDE（品牌上線工程）。
> 本文件回答：平台怎麼部署？本機開發拓撲長怎樣？雲端 per-brand bundle 如何開通？env / secrets 放哪、怎麼注入？migration 怎麼套用、怎麼回滾？部署後怎麼 smoke test？
> 深度架構參考：[12_SAD.md](./12_SAD.md)、平台 L1（../00_platform/P1/05_platform_architecture_L1.md（封存於 git 238f6fce））。

---

## 1. 部署架構總覽 — 雙層：per-brand bundle + 集中共用元件

平台的部署單元設計為**兩層**（依據 ADR-P005）：

### 1.1 per-brand bundle（物理隔離，可完整獨立部署）

每個品牌一套授權部署的「大單體 + 內部容器」，**品牌之間物理隔離**（一品牌一庫）：

| 元件 | 容器 port | 用途 |
|---|---|---|
| web | 8080 | 品牌營運後台（`APP_MODE=dispatch`）；不含師傅端 |
| api | 8080 | FastAPI 派工控制平面（`API_SURFACE=dispatch`）|
| agent | 8080 | LockCore LINE Bot（`POST /callback` 唯一入站門）|
| MCP RAG server | （內部）| `search_product_manual` / `similar_cases` 🔜 規劃中 |
| Redis | 6379 | WS pub/sub fanout + cache 🔜 規劃中（ADR-P007 Phase 1）|
| 品牌庫 pgvector | 5432 | 業務資料 + 唯一事實語料（primary + read replica 🔜 規劃中）|

**師傅端不在 bundle 內**（屬集中共用的 technician-platform），因此品牌不依賴任何共享元件即可獨立上線。

### 1.2 集中共用元件（跨品牌，各一套）

| 元件 | 用途 | 狀態 |
|---|---|---|
| Casdoor | IdP（OIDC）+ 租戶 org + License 訂閱開通 | 🔜 規劃中（ADR-P003 Phase 2）|
| SigNoz | 系統可觀測性（OTel），見 [25_Monitoring_Spec.md](./25_Monitoring_Spec.md) | 🔜 規劃中（ADR-P002 Phase 1）|
| technician-platform | 技師共享池 + 技師庫 `lock_tech` + 獨立師傅 web | 🔜 規劃中（ADR-P004）|
| knowledge-refinery | License 附加系統（知識精煉 + 獨立 web）| 🔜 規劃中（ADR-P001）|
| Kafka | 派工/技師/工單事件骨幹 | 🔜 規劃中（ADR-P007 Phase 3）|
| 平台維運 console | Super Admin web（跨租戶治理）| 現行（platform surface + platform-web）|

> **商業模式接線**：品牌商需經 License 授權才可部署並綁定自己的 LINE channel 與設定；「開通哪些附加模組（如 knowledge-refinery）」由 License 決定。

---

## 2. 本機開發拓撲（docker compose 三 surface bundle）

本機以三份 compose 檔起三個 bundle（`docker-compose.{dispatch,tech,platform}.yml`），同一份 api image 靠 `API_SURFACE` 塑形：

| Bundle | 服務 | Host Port | 說明 |
|---|---|---|---|
| dispatch | web | 3000 | `APP_MODE=dispatch` 品牌營運後台 |
| dispatch | agent | 8000 → 容器 8080 | LockCore `/callback`（LINE 經 ngrok 接入）|
| dispatch | api | 8001 | `API_SURFACE=dispatch`，背景 worker 全開 |
| dispatch | db | 5433 → 容器 5432 | `lock_AI_data`（pgvector/pg17，volume `pgdata`）|
| tech | tech-web | 3001 | `APP_MODE=tech`；**WS 指向品牌 api :8001**（見 §注意）|
| tech | tech-api | 8002 | `API_SURFACE=tech`，背景 worker 停 |
| tech | tech-db | 5434 | `lock_tech` 技師權威庫 |
| platform | platform-web | 3003 | `APP_MODE=platform` 平台 console |
| platform | platform-api | 8003 | `API_SURFACE=platform`，獨立 JWT 密鑰，worker 停 |
| platform | platform-db | 5435 | `lock_platform` 平台庫 |

跨 bundle 連線：dispatch api 對 tech-db 做技師身分雙寫 mirror；tech-api 讀品牌庫投影列；platform-api 跨庫唯讀 dispatch/tech。

```bash
# 一鍵起 dispatch bundle（db/api/agent/web）
docker compose up -d --build
# 對外接 LINE（host 上跑，不入 compose）
ngrok http 8000
# 停止（保留 pgdata）；加 -v 會清空資料庫，平時勿加
docker compose down
```

> **注意**：
> - `NEXT_PUBLIC_*` 是 **build-time 烤入**——web 容器 build 時就要帶對 `NEXT_PUBLIC_API_BASE_URL` / `NEXT_PUBLIC_REALTIME_BASE_URL`。
> - tech-web 的 WS 指向品牌 api（:8001）而非 tech-api（:8002）：WS hub 為單機 in-memory 設計，事件只在動作發生的實例廣播；師傅端即時性以輪詢降級（詳見 [24_Runbook.md](./24_Runbook.md) RB-02）。
> - ngrok free URL 每次重啟都會變，需回 LINE Developers Console 重貼 Webhook URL + Verify。

---

## 3. 雲端部署拓撲（GCP asia-east1）

雲端目前以**集中式三服務**承載品牌面（GCP 專案 `cedar-scope-489604-g3`）；per-brand bundle 為部署設計單元，其 provisioning 自動化屬 🔜 規劃中（§4）：

| Cloud Run 服務 | 內容 | 關鍵配置 |
|---|---|---|
| `smart-lock-api` | FastAPI（`API_SURFACE=all` 預設，全路由 + 背景 worker）| 容器內 :8080 |
| `smart-lock-web` | Next.js 多站前端 | 容器內 :8080 |
| `smart-lock-agent` | LockCore LINE gateway | 2Gi / 2CPU / gen2 / cpu-boost / min=1 max=3 / timeout 300s / `--allow-unauthenticated` / :8080 |

| 基礎設施 | 用途 |
|---|---|
| Cloud SQL（pgvector，實例 `lock-ai`）| 品牌庫 + agent 記憶 schema `agent.*`（`--add-cloudsql-instances` 掛載）；技師庫/平台庫雲端連線 `[待確認]` |
| Secret Manager | `LINE_*` / `POSTGRES_URI` / `OPIK_*` / `INTERNAL_API_TOKEN` 等機密 |
| GCS | 物件儲存（證據/素材；30 天版本保留 + 跨區複寫為 DR 目標，見 24 §5）|
| Vertex AI | LLM 推論（`VERTEX_LOCATION=asia-northeast1`）|

部署一律走部署腳本（目前為手動觸發；CD 自動化見 §7）：

```bash
./scripts/deploy/api.sh      # pre-flight → build → push → deploy → health check
./scripts/deploy/agent.sh    # 同上；BRAND=<name> 載 scripts/deploy/brands/<name>.env
./scripts/deploy/web.sh
```

**品牌參數化**：`BRAND=<name>` 載入 `scripts/deploy/brands/<name>.env`，一品牌一 GCP 專案——此即 per-brand 物理隔離在雲端的落點。

> **擴縮約束**：api 的 WS hub 與 11 個 cron worker 為進程內 in-memory 設計，**Cloud Run 須維持單實例（min-instances=1、不開多實例）**，直到 Redis pub/sub + 分散式鎖上線（ADR-P007，🔜 規劃中）。詳見 [24_Runbook.md](./24_Runbook.md) RB-02/RB-03。

---

## 4. per-brand provisioning 流程 🔜 規劃中（Phase 2/3）

品牌開通的標準流程（ADR-P005 §5 + ADR-P003；隨基礎 CD 之後自動化，ADR-P012 優先序 3）：

```
① License 開通（Casdoor subscription 授權 = 開通閘門）
      ↓
② 部署 bundle（web/api/agent/品牌庫/Redis/MCP-RAG，物理隔離）
      ↓
③ 建庫（品牌庫 pgvector：Schema + migrations 全套 fresh-apply）
      ↓
④ 綁定該品牌 LINE channel 與設定（channel secret / access token → Secret Manager）
      ↓
⑤ 健康檢查（api /health = ok；agent webhook 驗簽通；web 首頁 200）→ 登記平台 console 監控目標
```

- 開通哪些附加模組（knowledge-refinery 等）由 License 決定。
- provisioning 自動化（IaC / 腳本）與升級/回滾策略隨 ADR-P005 落地；在此之前品牌上線由 FDE 依上列順序手動執行。

---

## 5. 環境變數與 secrets 管理

### 5.1 原則

- **機密不入 toml / 不入 git**：agent 非機密設定走 `agent/config.toml`（tomllib 載入）；機密（`GEMINI_API_KEY` / `LINE_CHANNEL_*` / `credentials.json`）放 `.env` 或 gitignore 檔，雲端一律 GCP Secret Manager。
- **`POSTGRES_URI` 永不手動構建**：一律 `./scripts/deploy/agent.sh --update-db-uri`（自動 URL-encode + round-trip 驗證）。
- CI 不持密：secrets 於 runtime 由 Secret Manager 注入。

### 5.2 api 關鍵變數

| 變數 | 用途 | 備註 |
|---|---|---|
| `API_SURFACE` | 部署塑形：`all` / `dispatch` / `tech` / `platform` | 塑形非安全邊界；tech/platform 面自動停背景 worker |
| `POSTGRES_URI` | 品牌庫（`lock_AI_data`）懶連線 | 未設 TECH/PLATFORM URI 時的 fallback 主連線 |
| `TECH_POSTGRES_URI` | 技師權威庫（`lock_tech`）| 未設則回主連線（單庫行為不變）|
| `PLATFORM_POSTGRES_URI` | 平台庫（`lock_platform`）| 同上 |
| `PLATFORM_JWT_SECRET_KEY` | platform surface 獨立 JWT 密鑰 | **啟動守衛：≥16 字元**，否則拒絕啟動 |
| `INTERNAL_API_TOKEN` | agent → api `/internal/*` 認證 | api 側 fail-closed（未設回 503）|
| `AGENT_TENANT_ID` | agent 租戶別名 → UUID 映射 | 未設則別名 ingest 回 400 |
| `LINE_CHANNEL_ACCESS_TOKEN` | 客服接管 push 回 LINE | 缺少時 push fail-soft（訊息只進 DB）|
| `CORS_ORIGINS` | CORS 白名單 | |

### 5.3 agent 關鍵變數

| 變數 | 用途 | 備註 |
|---|---|---|
| `LINE_CHANNEL_SECRET` / `LINE_CHANNEL_ACCESS_TOKEN` | webhook 驗簽 / 回覆 | 缺 SECRET 啟動即退出；**讀 `agent/.env`，非專案根 `.env`** |
| `LOCK_API_BASE_URL` + `INTERNAL_API_TOKEN` | 對話/escalation 旁路橋接 | 缺任一 → 橋接停用（fail-soft，LINE 仍回但後台無對話/工單）|
| `POSTGRES_URI` | 記憶後端 `backend="postgres"`（schema `agent.*`）| 生產應為 postgres；sqlite 為本機預設 |
| `credentials.json` | Vertex AI 憑證 | gitignore，容器掛載 |
| `NANOBOT_LLM_TIMEOUT_S` | LLM 逾時 | 預設 300s |
| `OPIK_API_KEY` / `OPIK_WORKSPACE` | agent LLM Ops 觀測 | dev 預設開 / prod 可關（ADR-P002；接線 🔜 規劃中 Phase 1）|

環境切換：`./scripts/env/use-local.sh` / `use-gcp.sh`。

---

## 6. 資料庫 migration（純 SQL、forward-only）

依 api ADR-002 與 data-pipeline ADR-002，本平台**不使用 Alembic / ORM migration**：

### 6.1 規則

1. **格式**：純編號 `SQL/migrations/NNN-<short>.sql`。
2. **forward-only**：無 down migration，不可逆；回滾靠備份還原（見 §9）。
3. **idempotent 手法**（必用，讓 migration 可重跑）：
   - `ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS`
   - `DO $$ ... 查 pg_constraint ... $$`（條件式加約束）
   - `ON CONFLICT DO NOTHING`（seed 資料）
4. **套用真相源 = `public.schema_migrations` 表**；`MIGRATION_REGISTRY.md` 僅為人工編號登記簿（非權威）。
5. **平行開發防撞號**：多 worktree 開發前先在 `MIGRATION_REGISTRY.md` 認領編號。
6. 平台庫走獨立的 `SQL/platform/Schema_platform.sql` 冪等 additive（`CREATE TABLE IF NOT EXISTS`），不佔品牌庫 migration 編號。

### 6.2 prod 套用

```bash
# ① 套用前必先手動備份
gcloud sql backups create --instance=lock-ai
# ② 經 cloud-sql-proxy 套用（Schema.sql → Schema_*.sql → migrations/*.sql → 回填 schema_migrations）
./scripts/db/apply-schema-prod.sh
```

### 6.3 Drift 防護 🔜 規劃中（ADR-P012 優先序 1）

- CI drift-check：對 migration 檔 fresh-apply + 比對 `schema_migrations`，漂移即 fail（`.github/workflows/` 新 job）。
- 一次性 reconcile：028–032 / 036–044 補登 backlog。
- 漂移症狀與診斷見 [24_Runbook.md](./24_Runbook.md) RB-08。

---

## 7. CI/CD pipeline

### 7.1 CI（現行）

`.github/workflows/` 共 13 個 CI workflow，涵蓋 test / lint / smoke / loadtest；主測試入口 `cd agent && pytest` 與 api pytest（203 test 檔）。commit 前防線：pre-commit lint + secret scan。

### 7.2 基礎 CD 🔜 規劃中（ADR-P012 優先序 3）

3 個 Cloud Run（agent/api/web）接 GitHub Actions：tag / merge 觸發 → build → push → deploy，補上 CI→CD 缺口。artifact 版本標記慣例：`{version}-{commit-sha}-{build-number}`，image digest 不可變、可追溯到 commit。

### 7.3 per-brand provisioning 自動化 🔜 規劃中

隨 ADR-P005 落地（§4 流程自動化），非基礎 CD 階段範圍。

---

## 8. 部署策略與 canary 🔜 規劃中（隨基礎 CD 啟用）

CD 上線後的標準發佈流程骨架（工具鏈 = GitHub Actions + Cloud Run traffic split；觀測 = SigNoz）：

```
lint → test → build（SHA tag）→ deploy staging → smoke test
   → canary 5%（觀察 30min）→ 50%（觀察 30min）→ 100%
   → prod gate（人工核准）→ post-deploy 驗證（30min watch）
```

- **Auto-halt 條件**：canary 段 error rate 或 p99 latency 超 baseline（門檻於 SLO 定案後綁定，見 [25_Monitoring_Spec.md](./25_Monitoring_Spec.md) §5）→ 自動停止推進並回前一 revision。
- **prod gate**：人工核准（PM / Tech Lead），release notes 必填。
- migration 與 app 部署解耦：含 migration 的 release 先在 staging dry-run。

---

## 9. Rollback 程序（三層）

| 層 | 對象 | RTO 目標 | 機制 |
|---|---|---|---|
| **Layer 1 — Config** | 環境變數 / runtime 設定 | ≤ 1 min | 還原前一組 env（Cloud Run `update-env-vars`）；設定版本化 🔜 規劃中 |
| **Layer 2 — App** | 服務版本 | ≤ 30 min | Cloud Run revision pin：`gcloud run services update-traffic <svc> --to-revisions=<last-green>=100`（保留 ≥ 5 個 green revision）|
| **Layer 3 — DB** | schema / 資料 | ≤ 4 h | **無 down migration（forward-only 不可逆）→ 回滾一律靠備份還原**（Cloud SQL 備份 / PITR）|

**決策鏈**：PM + Tech Lead + DevOps on-call 三人核決（P0 緊急可由 on-call 單人先行 + 事後補審）；rollback 後 24h 內完成事故通報，1 週內出 postmortem（見 [26_Incident_Postmortem.md](./26_Incident_Postmortem.md)）。

**Rollback 觸發門檻（範例，正式值綁 SLO）**：部署後 error rate 超 baseline、可用性跌破合約下限（Uptime < 90% rolling）、AI 紅線 eval 未達標、PII 外洩事件——任一命中即回滾。

**Layer 2 執行步驟**：

```
決策（≤10min）→ 指認上一 green revision（SHA tag）→ revision pin
→ smoke test（§10，5min）→ SLO 恢復觀察 15min → 通報 → postmortem 排程
```

---

## 10. Smoke test 與部署後驗證

### 10.1 api

```bash
curl -s https://<api-url>/health
# 期望 {"status":"ok"}；DB 連線異常時回 degraded（NFR-AVAIL-02）
```

### 10.2 agent（三進程健康鏈）

agent 服務鏈 = Gateway（:8000 本機 / :8080 容器）→ api（:8001）→ Postgres，缺一則「LINE 有回但後台無對話/工單」：

1. **啟動 banner 驗證**：`模型:vertex_ai/gemini-3.1-flash-lite`、`記憶後端:postgres`（生產）、`API 橋接:✅ 啟用`——看到「⚠️ 停用」代表缺 `LOCK_API_BASE_URL` / `INTERNAL_API_TOKEN`。
2. **webhook 存活**：agent 對外僅註冊 `POST /callback`；以無簽章 POST 打 `/callback` 期望 400（驗簽拒絕）即代表存活。`GET /health` 輕量路由 🔜 規劃中（部署腳本 health gate 將對齊此路由）。
3. **ingest 貫通驗證**（不經 LINE 直驗旁路，會真實寫 DB）：

```bash
curl -s -X POST https://<api-url>/api/v1/internal/conversations/ingest \
  -H 'X-Internal-Token: <token>' -H 'Content-Type: application/json' \
  -d '{"tenant_id":"<brand-alias>","line_user_id":"Usmoke","session_id":"<brand>:Usmoke",
       "user_text":"smoke","assistant_text":"ok"}'
# 期望 {"data":{"conversation_id":"…","messages_appended":2},"error":null}
# 503 = api 未設 INTERNAL_API_TOKEN；401 = 兩邊 token 不一致；400 = 缺 AGENT_TENANT_ID 映射
```

4. **escalation 貫通**：`POST /internal/escalations/ingest` 驗 tenant_id UUID 貫通 → 後台 `/problem-cards` 出現 AI 草擬卡。

### 10.3 關鍵路徑清單

- [ ] web 各 portal 首頁 200、登入可用
- [ ] LINE 傳訊息 → AI 回覆（無罐頭訊息蓋掉：LINE Console Auto-reply / Greeting 已關）
- [ ] 轉真人觸發句（如「請安排師傅到府」）→ 後台問題卡出現
- [ ] WS 推播：後台建工單 → 訂閱頁面即時更新（同實例 < 1s）
- [ ] `schema_migrations` 最新編號 = 本次 release 應套用之最大編號
- [ ] 平台 console「維運監控」紅綠燈：本次部署目標全綠

---

*本文件為部署單一入口；故障處置見 [24_Runbook.md](./24_Runbook.md)，監控與 SLO 見 [25_Monitoring_Spec.md](./25_Monitoring_Spec.md)。*
