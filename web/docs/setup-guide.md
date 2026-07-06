# SmartLock 工單系統 — 本機建置手冊

對象：第一次接手本專案的工程師（或代為操作的 AI 助手）。
目標：在一台乾淨的 macOS / Linux 機器上，從 0 把整套系統跑起來，並能在瀏覽器登入 Admin Dashboard。

整套系統有三個元件：

| 元件 | 技術 | Port | 啟動方式 |
| :--- | :--- | :--- | :--- |
| **PostgreSQL 資料庫** | pgvector/pgvector:pg17 | 5433 → 5432 | Docker container `lock_AI` |
| **後端 REST API** | FastAPI + Python 3.11 | 8001 → 8080 | Docker container `smart-lock-api` |
| **前端 Admin Dashboard** | Next.js 15 + React 19 | 3000 | `npm run dev` |

啟動順序固定為：**資料庫 → 後端 → 前端**（後端啟動時會連 DB，前端啟動時會打 API）。

---

## 1. 前置需求

請先確認本機已安裝：

| 工具 | 版本 | 驗證指令 |
| :--- | :--- | :--- |
| Docker Desktop | 任何近期版本 | `docker --version` |
| Node.js | v20+（建議 v22 LTS） | `node --version` |
| npm | v10+ | `npm --version` |
| Git | 任意 | `git --version` |

> macOS 建議用 `brew install node` 或 [nvm](https://github.com/nvm-sh/nvm) 裝 Node。Docker Desktop 從官網下載即可。

不需要安裝：Python、Postgres client、conda — 後端跑在 container 內，這份手冊不會用到 host 的 Python。

---

## 2. 取得程式碼

```bash
git clone git@github.com:Zenobia0000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform.git
cd Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform
git checkout dev
```

> 主要開發分支是 `dev`，不是 `main`。所有最新程式都在 `dev` 上。

---

## 3. 啟動資料庫（Docker）

### 3.1 拉映像並建立 container

```bash
docker run -d \
  --name lock_AI \
  -e POSTGRES_USER=lock \
  -e POSTGRES_PASSWORD=0000 \
  -e POSTGRES_DB=lock_AI_data \
  -p 5433:5432 \
  -v lock_AI_data:/var/lib/postgresql/data \
  pgvector/pgvector:pg17
```

固定參數（**不要改**，後端 container 是用 `db:5432` 連線並 hard-code `lock/0000`）：

| 參數 | 值 | 為何不可改 |
| :--- | :--- | :--- |
| Container name | `lock_AI` | 後端 container 用 `--link lock_AI:db` 解析 hostname |
| User | `lock` | 後端 `POSTGRES_URI` 寫死此值 |
| Password | `0000` | 同上 |
| DB name | `lock_AI_data` | 同上 |
| Host port | `5433` | 5432 通常被 host 上其他 Postgres 占用 |

驗證：

```bash
docker ps | grep lock_AI
# 應看到 STATUS = Up X seconds，PORTS = 0.0.0.0:5433->5432/tcp

docker exec lock_AI psql -U lock -d lock_AI_data -c "SELECT 1;"
# 應回 ?column? = 1
```

### 3.2 建表（schema）

從 host 把 SQL 檔複製進 container，再用 `psql` 跑：

```bash
# Schema（依序跑，後者依賴前者）
docker cp SQL/Schema.sql lock_AI:/tmp/
docker cp SQL/Schema_harness_migration.sql lock_AI:/tmp/
docker cp SQL/Schema_v2_extensions.sql lock_AI:/tmp/
docker cp SQL/Schema_api_phase1.sql lock_AI:/tmp/

docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/Schema.sql
docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/Schema_harness_migration.sql
docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/Schema_v2_extensions.sql
docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/Schema_api_phase1.sql
```

> Schema_v2_extensions.sql 內可能有 `trg_roles_updated_at already exists` 之類的 NOTICE — **可以忽略**，所有 CREATE 都是 `IF NOT EXISTS` 寫法，整體 idempotent。

完成後只是建好空表，**還沒有任何資料**。下一步必跑 3.3 灌 seeds。

### 3.3 灌種子假資料（**必做，否則前端各頁全空白**）

`SQL/seeds/` 內每張表都有對應的種子檔，前端 dashboard、列表、詳情頁的示範資料都靠這些。**沒灌就什麼都看不到，連登入帳號都不存在**。

執行（按字母順序，`_admin_user.sql` 因前綴 `_` 會最先跑，確保 admin 帳號先建立）：

```bash
for f in $(ls SQL/seeds/*.sql | sort); do
  echo "=== $f ==="
  docker cp "$f" lock_AI:/tmp/seed.sql
  docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/seed.sql
done
```

> 部分 seeds 之間有 FK 依賴（例：`work_orders` 引用 `problem_cards`、`vouchers` 引用 `settlements`），**請完整跑完整個資料夾，不要只跑單檔**。檔案以字母順序排序，依賴順序已對齊。

#### 驗證 seed 灌成功

```bash
# 1. 登入帳號存在（沒這個前端登入會 401）
docker exec lock_AI psql -U lock -d lock_AI_data -c \
  "SELECT email, role, is_active FROM users WHERE email='test@lock-ai.com';"
# 預期：test@lock-ai.com | admin | t

# 2. 各表都有資料（部分例子，前端直接吃）
docker exec lock_AI psql -U lock -d lock_AI_data -c "
  SELECT 'conversations' AS t, COUNT(*) FROM conversations UNION ALL
  SELECT 'problem_cards', COUNT(*) FROM problem_cards UNION ALL
  SELECT 'work_orders', COUNT(*) FROM work_orders UNION ALL
  SELECT 'technicians', COUNT(*) FROM technicians UNION ALL
  SELECT 'manuals', COUNT(*) FROM manuals UNION ALL
  SELECT 'vouchers', COUNT(*) FROM vouchers;
"
# 每行 count 都應 > 0，全 0 = 灌失敗，回 3.2 / 3.3 重跑
```

如果 count 全 0，可能原因：

| 症狀 | 原因 | 修法 |
| :--- | :--- | :--- |
| 跑 seed 報 `relation "xxx" does not exist` | 3.2 沒先建 schema | 回 3.2 跑完 4 個 Schema 後重跑 3.3 |
| 跑 seed 報 `violates foreign key constraint` | 順序錯（單獨跑某檔） | 一定要照 `for f in ...` 整批跑 |
| 跑完還是 0 筆 | 上次跑到一半失敗，留了髒狀態 | 看下方「重灌」 |

#### 砍掉重灌（清空資料但保留 schema）

```bash
docker exec lock_AI psql -U lock -d lock_AI_data -c "
  TRUNCATE
    family_reviews, vouchers, settlements, invoices,
    disputes, refund_requests, warranty_claims,
    inventory_items, dispatch_logs, sentiment_alerts,
    work_orders, problem_cards, sop_drafts, manual_chunks, manuals,
    pricing_rules, technicians,
    messages, conversations, user_facts, audit_logs,
    users
  RESTART IDENTITY CASCADE;
"
# 然後重跑 3.3 的 for-loop
```

完全砍掉 container 從零來：

```bash
docker rm -f lock_AI && docker volume rm lock_AI_data
# 然後從 3.1 重跑
```

---

### 3.4 已灌資料一覽（看到這些前端才會有東西）

| Seed 檔 | 對應前端頁面 |
| :--- | :--- |
| `_admin_user.sql` | `/login`（admin 帳號） |
| `conversations.sql` | `/conversations`、`/conversations/[id]` |
| `problem_cards.sql` | `/problem-cards`、`/problem-cards/[id]` |
| `work_orders.sql` | `/work-orders`、`/work-orders/[id]`、dashboard 工單 KPI |
| `technicians.sql` | `/technicians`、`/technicians/[id]`、dashboard 在線技師 |
| `manuals.sql` | `/knowledge-base/manuals` |
| `sop_drafts.sql` | `/knowledge-base/sop-drafts` |
| `family_reviews.sql` | `/knowledge-base/family-reviews` |
| `pricing_rules.sql` | `/settings`（計價規則 tab） |
| `invoices.sql` | `/accounting/invoices` |
| `vouchers.sql` | `/accounting/vouchers` |
| `settlements.sql` | `/accounting`（月結算） |
| `refund_requests.sql` | `/admin/refunds` |
| `warranty_claims.sql` | `/admin/warranty-claims` |
| `disputes.sql` | `/admin/disputes` |
| `inventory_items.sql` | `/admin/inventory` |
| `dispatch_logs.sql` | `/admin/dispatch-queue` |
| `sentiment_alerts.sql` | `/admin/sentiment-alerts` |

**沒灌 seeds 直接啟動前端 → 登入會失敗（admin 帳號不存在），就算手動建帳號各列表頁也會全空白**。3.3 是必做步驟。

---

## 4. 啟動後端 API（Docker）

### 4.1 建 Docker image

```bash
cd api
docker build -t smart-lock-api:local .
cd ..
```

第一次 build 約 1–3 分鐘（pip install）。後續修改程式重 build 約 30 秒。

### 4.2 跑 container

```bash
docker rm -f smart-lock-api 2>/dev/null

docker run -d \
  --name smart-lock-api \
  --link lock_AI:db \
  -p 8001:8080 \
  -e POSTGRES_URI="postgresql://lock:0000@db:5432/lock_AI_data" \
  -e API_JWT_SECRET_KEY="dev-secret-key" \
  smart-lock-api:local
```

關鍵點：

- `--link lock_AI:db` — 讓 container 內的 `db` hostname 指向資料庫 container。`POSTGRES_URI` 必須用 `db:5432` 不是 `localhost`。
- `-p 8001:8080` — 容器內 uvicorn 跑在 8080，host 對外 8001。前端會打 `http://localhost:8001`。
- `API_JWT_SECRET_KEY` — 簽發 JWT 用，本機隨意給，**不要 commit 進 repo**。

驗證：

```bash
curl http://localhost:8001/health
# 預期：{"status":"ok","version":"0.2.0","checks":{"db":"ok"}}
```

如果回 `503` 或 `db: degraded`，看 4.4 排查。

### 4.3 後端 logs

```bash
docker logs -f smart-lock-api
```

Ctrl+C 只是離開 follow，container 仍在跑。

### 4.4 常見後端問題

| 症狀 | 原因 | 修法 |
| :--- | :--- | :--- |
| `health` 回 `db: degraded` | DB container 沒起，或 `--link` 沒設 | `docker ps` 確認 lock_AI 在跑；重跑 4.2 加 `--link` |
| `relation "users" does not exist` | Schema 沒灌 | 回 3.2 跑 Schema.sql |
| port 8001 already in use | 已有舊 container | `docker rm -f smart-lock-api` 後重跑 |
| 改了 api/ 程式碼沒生效 | image 是舊的 | `cd api && docker build -t smart-lock-api:local . && docker rm -f smart-lock-api` 後重跑 |

---

## 5. 啟動前端（Next.js）

### 5.1 設定環境變數

```bash
cd web
cp .env.local.example .env.local
```

`.env.local` 內容應為：

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001
```

> 變數名以 `NEXT_PUBLIC_` 開頭才會被 inline 到 client-side bundle。改完要重啟 `npm run dev`。

### 5.2 安裝依賴

```bash
npm install
```

第一次跑約 1–2 分鐘。

### 5.3 啟動 dev server

```bash
npm run dev
```

預期輸出：

```
▲ Next.js 15.x.x
- Local: http://localhost:3000
✓ Ready in 1.5s
```

開瀏覽器到 [http://localhost:3000](http://localhost:3000) — 第一次進會被導到 `/login`。

### 5.4 登入

| 欄位 | 值 |
| :--- | :--- |
| Email | `test@lock-ai.com` |
| 密碼 | `changeme123` |

登入成功會跳到 `/dashboard`。詳細登入測試流程見 [`login-testing-guide.md`](./login-testing-guide.md)。

---

## 6. 完整冷啟動檢查清單

每天開機後，按順序執行：

```bash
# 1. DB（如果 container 已存在，只需 start；首次才 run）
docker start lock_AI

# 2. API
docker start smart-lock-api

# 3. 健康檢查
curl http://localhost:8001/health

# 4. 前端
cd web && npm run dev
```

關機時：

```bash
# 前端：Ctrl+C 終止 npm run dev
# Container 不一定要停（重啟很快），要停就：
docker stop smart-lock-api lock_AI
```

---

## 7. 系統架構速覽

```
┌──────────────────────┐         ┌──────────────────────┐         ┌──────────────────────┐
│  Browser             │         │  Next.js Dev Server  │         │  FastAPI Container   │
│  http://localhost    │ ──────► │  localhost:3000      │ ──────► │  localhost:8001      │
│  :3000               │         │  (npm run dev)       │   REST  │  (smart-lock-api)    │
└──────────────────────┘         └──────────────────────┘         └──────────┬───────────┘
                                                                              │
                                                                       --link │ db:5432
                                                                              ▼
                                                                  ┌──────────────────────┐
                                                                  │  Postgres Container  │
                                                                  │  localhost:5433      │
                                                                  │  (lock_AI)           │
                                                                  └──────────────────────┘
```

- 前端 client component 透過 `web/src/lib/api.ts` 統一呼叫後端，自動帶 `Authorization: Bearer <jwt>` 與 `X-Tenant-ID` headers。
- 後端用 JWT 驗 token，所有 `/api/v1/*` endpoint 都需登入（除了 `/auth/login`、`/auth/refresh`、`/health`）。
- 後端到 DB 的連線在 container 內走 `db` 這個 alias hostname（不是 `localhost`）。

---

## 8. 主要程式碼進入點

| 路徑 | 用途 |
| :--- | :--- |
| `web/src/app/` | Next.js App Router 頁面（檔案路由 = URL） |
| `web/src/components/` | 共用元件，依領域分子目錄 |
| `web/src/lib/api.ts` | API client + token 管理（auth helper） |
| `web/types/api.generated.ts` | OpenAPI 自動產生的 TS 型別 — **手動勿動** |
| `api/main.py` | FastAPI app 進入點，掛載所有 router |
| `api/routers/` | 各領域 endpoint 群（依資源拆檔） |
| `api/services/` | 業務邏輯 + DB queries |
| `api/core/` | 共用模組（DB、auth、errors、pagination 等） |
| `api/models/generated.py` | OpenAPI 自動產生的 Pydantic 型別 — **手動勿動** |
| `SQL/Schema*.sql` | DB schema（建表） |
| `SQL/seeds/*.sql` | DB seeds（示範資料） |
| `docs/02-design/specs/openapi.yaml` | API 契約 SSOT，前後端型別都從這生 |

---

## 9. 常用驗證指令

```bash
# 後端 smoke test（取 access token、打一個受保護的 endpoint）
TOKEN=$(curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@lock-ai.com","password":"changeme123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

curl -s http://localhost:8001/api/v1/dashboard/stats?period=today \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: 00000000-0000-0000-0000-000000000001" \
  | python3 -m json.tool
```

```bash
# 前端 TypeScript 檢查（不啟動 dev server）
cd web && npx tsc --noEmit
```

```bash
# DB 連線進去看
docker exec -it lock_AI psql -U lock -d lock_AI_data
# 進去後 \dt 列所有 table，\q 離開
```

---

## 10. 排錯總表

| 症狀 | 排查順序 |
| :--- | :--- |
| 前端白屏 / 一直 loading | DevTools Console 看紅字；Network 看 8001 是否通 |
| 登入按鈕無反應 | DevTools Network → `/api/v1/auth/login` 是否發出，回什麼 status |
| `/dashboard` 一直跳回 `/login` | Application → Local Storage → 確認 `smartlock.access_token` 有值 |
| `curl :8001/health` 不通 | `docker ps` 看 smart-lock-api 是否在跑；`docker logs smart-lock-api` 看錯誤 |
| `health` 回 db degraded | `docker ps` 看 lock_AI 是否在跑；4.2 重啟 API container 加 `--link` |
| 改 api/ 程式碼沒效果 | 4.4 表格最後一列：rebuild + 重起 container |
| 改 web/src/ 程式碼沒效果 | dev server 預設熱更新；偶爾要 `rm -rf web/.next` 後重啟 `npm run dev` |
| `npm install` 報 peer dep | Node 版本太舊；切到 v20+ |
| Cannot find module 'next' | 沒跑 `npm install`，或 `node_modules` 損壞，刪掉重裝 |

---

## 11. 不在這份文件範圍

以下功能要跑得動需要更多前置條件，**接手前不一定要弄**：

- **LINE Bot agent**（`agent/`）— 需要 LINE Channel 金鑰、Vertex AI、Cloud SQL，僅在開發 LINE 對話流程時才用
- **資料管線**（`data/`）— 需要 Vertex AI / Whisper / yt-dlp，僅在補知識庫時才用
- **Cloud Run 部署**（`scripts/deploy/api.sh`）— 需要 GCP 權限與 Secret Manager
- **API 契約變更**（`docs/02-design/specs/openapi.yaml`）— 改完要跑 `./scripts/ci/generate-api-types.sh`

只要做 Admin Dashboard 的功能開發，**第 1–6 節就夠了**。

---

## 12. 補充參考文件

| 文件 | 用途 |
| :--- | :--- |
| [`./login-testing-guide.md`](./login-testing-guide.md) | 登入流程的瀏覽器手動測試步驟 |
| `../../CLAUDE.md` | 專案總覽（架構、慣例、命令參考） |
| `../../README.md` | 專案介紹 |
| `../../docs/HOME.md` | 設計文件入口 |
| `../../docs/02-design/specs/openapi.yaml` | REST API 契約 SSOT |
