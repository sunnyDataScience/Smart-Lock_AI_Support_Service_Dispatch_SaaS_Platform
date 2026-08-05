# 本機 compose：單一服務啟動速查

> 寫於 2026-08-06。**放在根目錄待歸檔**——內容偏「操作速查」，建議歸到
> `smartlock-docs/enterprise/23_Deployment_Guide.md` §2 之下，或 `docs/` 的維運區。
>
> 為什麼另外寫：`23_Deployment_Guide.md` §2 有本機拓撲，但那段是**舊的根目錄
> `docker-compose.{dispatch,tech,platform}.yml` 結構**（ADR-028 後檔案已搬到
> `web/<站台>/`，該節只補了一行標注），且範例全是整包
> `docker compose up -d --build`，**沒有寫單獨啟動單一服務**。
>
> 本檔所有埠位與依賴關係皆由 compose 檔實地解析取得，非憑印象。

---

## 1. 有哪些 compose 檔（沒有「每服務一支」的檔案）

現有 5 支都是 **stack 級**，一支管一整組服務：

| 檔案 | compose project | 服務 |
|---|---|---|
| `web/brand-portal/docker-compose.yml` | `lock-dispatch-<品牌>` | db · api · agent · web ＋ db-init/refinery/redpanda（profile） |
| `web/tech-portal/docker-compose.yml` | `lock-tech` | tech-db · tech-api · tech-web |
| `web/platform-console/docker-compose.yml` | `lock-platform` | platform-db · platform-api · platform-web ＋ casdoor-db/casdoor（profile） |
| `web/landing/docker-compose.yml` | `lock-landing` | landing-web |
| `api/docker-compose.mock.yml` | （無 name） | prism-openapi（OpenAPI mock server） |

**但單獨啟動不需要另外的檔案**——compose 原生支援在 `up` 後面指定服務名。

---

## 2. 埠位與依賴一覽

| stack | 服務 | host 埠（預設） | 依賴 | profile |
|---|---|---|---|---|
| `lock-dispatch-*` | `db` | 5433 | — | — |
| | `api` | 8001 | db（healthy） | — |
| | `agent` | 8000 | api（healthy） | — |
| | `web` | 3000 | **無** | — |
| | `refinery` | 8004 | api | `refinery` |
| | `redpanda` | 9092 | 無 | `events` |
| | `db-init` | — | db | `init` |
| `lock-tech` | `tech-db` | 5434 | — | — |
| | `tech-api` | 8002 | tech-db | — |
| | `tech-web` | 3001 | **無** | — |
| `lock-platform` | `platform-db` | 5435 | — | — |
| | `platform-api` | 8003 | platform-db | — |
| | `platform-web` | 3003 | **無** | — |
| | `casdoor-db` | 5436 | — | `idp` |
| | `casdoor` | 8005 | casdoor-db | `idp` |
| `lock-landing` | `landing-web` | 3002 | **無** | — |
| （mock） | `prism-openapi` | 4010 | — | — |

埠位可用環境變數覆寫（`DB_PORT` / `API_PORT` / `AGENT_PORT` / `WEB_PORT` /
`TECH_*_PORT` / `PLATFORM_*_PORT` / `LANDING_WEB_PORT` …），開第二個品牌時就是靠這些錯開。

---

## 3. 單獨啟動怎麼下

```bash
# 只起品牌 DB —— 不會拉起 api/agent/web
docker compose -f web/brand-portal/docker-compose.yml up -d db

# 只起 api —— 會連帶起 db（depends_on + healthcheck），這是必要的
docker compose -f web/brand-portal/docker-compose.yml up -d api

# 四個前端零依賴，可以完全單獨起
docker compose -f web/brand-portal/docker-compose.yml     up -d web           # :3000
docker compose -f web/tech-portal/docker-compose.yml      up -d tech-web      # :3001
docker compose -f web/landing/docker-compose.yml          up -d landing-web   # :3002
docker compose -f web/platform-console/docker-compose.yml up -d platform-web  # :3003

# profile 服務要顯式帶 --profile 才起得來
docker compose -f web/brand-portal/docker-compose.yml --profile refinery up -d refinery
docker compose -f web/platform-console/docker-compose.yml --profile idp up -d casdoor

# 停單一服務（保留其他）
docker compose -f web/brand-portal/docker-compose.yml stop agent
```

**依賴鏈很淺**：四個前端零依賴、三個 api 各自只綁自己的 db。
`agent` 是唯一鏈較長的（agent → api → db，起它會連帶三個容器）。

---

## 4. 三個會咬人的地方

### 4.1 四個 stack 的網路是分開的

四個 compose project 各有自己的 network。**師傅 stack 是唯一跨 stack 的**：
`web/tech-portal/docker-compose.yml:119-123` 把 default network 設為
`lock-dispatch-${TECH_DB_BRAND:-locksmart}-net` 且 `external: true`
——也就是**品牌 stack 必須先起**，`tech-api` 才能用 service 名 `db` 解析到品牌庫。

只起師傅 stack 而不起品牌 stack → 技師相關路徑會連線失敗。
那是刻意的 fail-loud（compose 檔頭有寫）：寧可大聲報錯，也不要靜默讀錯庫
造成 split-brain（排班申請寫權威庫、品牌後台審核頁永遠空）。

### 4.2 前端的 `NEXT_PUBLIC_*` 是 build-time 烤進去的

`web/*/Dockerfile` 的 `NEXT_PUBLIC_*` 全是 build ARG → ENV，
`next build` 時就烤進 bundle，**standalone 之後改不了**。

所以改 API base、跨站 URL 這類設定，`up -d` 重啟**沒有用**，要重 build：

```bash
docker compose -f web/brand-portal/docker-compose.yml up -d --build web
```

這個雷 CHANGELOG 記過兩次（0719 C 系列、0723 tech/platform CORS + API base 雙層烤錯）。

例外：CR-0190 導入 server-side proxy 之後，`API_BASE_URL` / `PLATFORM_API_BASE_URL`
是 **runtime** 環境變數（走 `/api-proxy`），那兩個改了重啟即可。

### 4.3 全新的 DB 要先跑 db-init

空的 pgdata volume 起 api 會失敗（無 schema）。第一次要：

```bash
docker compose -f web/brand-portal/docker-compose.yml --profile init run --rm db-init
```

它會依序套 `SQL/Schema.sql` → `Schema_*.sql` → migrations → seeds。

---

## 5. 如果真的需要「只跑一個服務」的獨立 compose

目前沒有現成的。典型情境是**只跑 agent 接 ngrok 給人測**——那需要一支
只含 agent（＋它必要的 DB 連線設定）的 compose，並把 `LOCK_API_BASE_URL`
指向已經在跑的 api（或外部位址）。

要做的話需要先確定兩件事：
1. 那個服務要連到哪裡的 DB（同機 compose 的 db？外部？）
2. 服務間認證怎麼給（`INTERNAL_API_TOKEN` / `AGENT_API_SERVICE_CREDENTIAL`）

---

## 附：目前本機還有一個非 compose 的容器

`lock-scratch-pg`（port **5544**）是 2026-08-05 為了跑測試臨時開的拋棄式
postgres——用 repo 的 schema 從零建，**不掛任何 compose volume、與 5433 的
UAT 庫無關**。跟 compose 的 db 不衝突，但別搞混。

```bash
docker rm -f lock-scratch-pg   # 不需要時收掉
```
