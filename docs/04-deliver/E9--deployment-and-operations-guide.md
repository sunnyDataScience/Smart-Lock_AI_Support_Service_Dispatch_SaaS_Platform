# 部署與運維指南 - 電子鎖智能客服與派工平台

# Deployment and Operations Guide - Smart Lock AI Support & Service Dispatch SaaS Platform

> **部署現況更新（2026-04-21）**
> - 部署平台已確定：**Google Cloud Run**（GCP, Docker 容器化）
> - V1.0 拓撲：FastAPI (port 8080) + PostgreSQL + GCS，**無 Next.js 前端**
> - V1.0 未使用 Redis（對話狀態由 PostgreSQL checkpoint 管理）
> - LLM 觀測：**OPIK**（已整合至 agent）
> - 本文件中的 Next.js、多 Worker 拓撲為 V2.0 規劃

---

> ## 遷移備註：uv workspace（2026-05）
>
> 本指南已從 conda + pip + requirements.txt 遷移到 **uv workspace**，並把實際生產部署統一到 **Cloud Run + `scripts/deploy/*.sh`**：
>
> | 場景 | 舊指令 | 新指令 |
> |------|--------|--------|
> | 安裝依賴 | `pip install -r agent/requirements.txt` | `uv sync` |
> | Agent CLI | `cd agent && python main.py` | `cd agent && uv run python main.py` |
> | API 啟動 | `cd api && uvicorn main:app --reload --port 8001` | `cd api && uv run uvicorn main:app --reload --port 8001` |
> | 部署（V1.0 生產） | `./scripts/deploy.sh`（已不存在） | `./scripts/deploy/agent.sh` 或 `./scripts/deploy/api.sh` |
> | 本機 DB 切換 | （無集中位置） | `./scripts/env/use-local.sh` / `./scripts/env/use-gcp.sh` |
> | 開發環境啟動 | `./scripts/dev-up.sh` | `./scripts/dev/dev-up.sh` |
>
> **本文件章節定位**：
> - 第 1 部分（拓撲）、第 7 部分（docker-compose / nginx）、第 9 部分中以 `docker compose ...` 起始的指令：**僅供 local dev 多服務一鍵起、或自行架設 self-hosted VPS 時參考**。生產環境一律走 Cloud Run。
> - 第 2 部分（CI/CD）已更新為 `astral-sh/setup-uv@v3` + `uv sync --frozen`；deploy 流水線改為呼叫 `scripts/deploy/agent.sh` / `scripts/deploy/api.sh`。
> - 第 9 部分中提到的 `alembic` 指令：本專案目前未啟用 Alembic（schema 演進透過 `SQL/*.sql` 手動套用），僅作為日後啟用 migration 框架時的參考模板。
>
> **回滾路徑**：若需回到 pip，移除根目錄 `pyproject.toml` / `uv.lock`、恢復各模組 `requirements.txt`。但本專案 CI/CD 已釘 uv，回滾代價高。
>
> 完整新舊對照見專案根 `CLAUDE.md` 的 Common Commands 段。

---

**文件版本 (Document Version):** `v1.1`
**最後更新 (Last Updated):** `2026-04-04`
**主要作者 (Lead Author):** `DevOps / 技術負責人`
**審核者 (Reviewers):** `架構委員會, 核心開發團隊`
**狀態 (Status):** `草稿 (Draft)`

---

## 目錄 (Table of Contents)

- [第 1 部分：部署架構總覽](#第-1-部分部署架構總覽)
  - [1.1 環境策略](#11-環境策略)
  - [1.2 部署拓撲圖](#12-部署拓撲圖)
  - [1.3 容器服務清單](#13-容器服務清單)
  - [1.4 網路與端口規劃](#14-網路與端口規劃)
- [第 2 部分：CI/CD 流水線](#第-2-部分cicd-流水線)
  - [2.1 流水線概覽](#21-流水線概覽)
  - [2.2 ci.yml - 持續整合](#22-ciyml---持續整合)
  - [2.3 deploy.yml - 持續部署](#23-deployyml---持續部署)
  - [2.4 CI/CD 步驟詳細說明](#24-cicd-步驟詳細說明)
- [第 3 部分：部署檢查清單](#第-3-部分部署檢查清單)
  - [3.1 部署前檢查](#31-部署前檢查)
  - [3.2 部署中監控](#32-部署中監控)
  - [3.3 部署後驗證](#33-部署後驗證)
- [第 4 部分：部署策略](#第-4-部分部署策略)
  - [4.1 Blue-Green 部署 (生產環境)](#41-blue-green-部署-生產環境)
  - [4.2 滾動部署 (Staging 環境)](#42-滾動部署-staging-環境)
  - [4.3 首次部署流程](#43-首次部署流程)
- [第 5 部分：監控與告警](#第-5-部分監控與告警)
  - [5.1 應用程式指標](#51-應用程式指標)
  - [5.2 基礎設施指標](#52-基礎設施指標)
  - [5.3 業務指標](#53-業務指標)
  - [5.4 告警配置](#54-告警配置)
  - [5.5 日誌管理](#55-日誌管理)
- [第 6 部分：回滾程序](#第-6-部分回滾程序)
  - [6.1 自動回滾觸發條件](#61-自動回滾觸發條件)
  - [6.2 手動回滾流程](#62-手動回滾流程)
  - [6.3 資料庫回滾](#63-資料庫回滾)
- [第 7 部分：基礎設施即程式碼](#第-7-部分基礎設施即程式碼)
  - [7.1 Docker Compose 配置](#71-docker-compose-配置)
  - [7.2 Nginx 反向代理配置](#72-nginx-反向代理配置)
  - [7.3 Dockerfile 配置](#73-dockerfile-配置)
- [第 8 部分：部署安全性](#第-8-部分部署安全性)
  - [8.1 密鑰管理](#81-密鑰管理)
  - [8.2 網路安全](#82-網路安全)
  - [8.3 容器安全](#83-容器安全)
  - [8.4 外部服務安全](#84-外部服務安全)
- [第 9 部分：運維手冊 (Runbook)](#第-9-部分運維手冊-runbook)
  - [9.1 資料庫遷移](#91-資料庫遷移)
  - [9.2 手動備份](#92-手動備份)
  - [9.3 服務重啟](#93-服務重啟)
  - [9.4 水平擴展](#94-水平擴展)
  - [9.5 日誌查詢](#95-日誌查詢)
  - [9.6 SSL 憑證更新](#96-ssl-憑證更新)
  - [9.7 密鑰輪替](#97-密鑰輪替)
  - [9.8 災難復原](#98-災難復原)
- [第 10 部分：環境專屬配置](#第-10-部分環境專屬配置)
  - [10.1 Development 環境](#101-development-環境)
  - [10.2 Staging 環境](#102-staging-環境)
  - [10.3 Production 環境](#103-production-環境)
  - [10.4 環境變數完整清單](#104-環境變數完整清單)

---

**目的**: 本文件為「電子鎖智能客服與派工 SaaS 平台」提供完整的部署流程、基礎設施管理與日常運維操作指南。涵蓋從開發環境到生產環境的部署架構、CI/CD 流水線、監控告警、回滾策略及常見運維操作手冊，確保系統可靠、穩定地運行於生產環境中。

**參考文件：**
- `docs/05_architecture_and_design_document.md` — 第 6 部分：部署與基礎設施、第 7 部分：跨領域考量
- `docs/08_project_structure_guide.md` — 第 6 節：Docker 與部署結構、第 7 節：設定檔結構
- `docs/06_api_design_specification.md` — API 端點與健康檢查規範

---

## 第 1 部分：部署架構總覽

### 1.1 環境策略

系統採用三環境策略，從開發到生產逐步推進：

```
Development (localhost)  →  Staging (VPS)  →  Production (VPS/Cloud)
        ↓                       ↓                    ↓
    功能開發                 整合測試              正式運行
    單元測試                UAT 驗收             對外服務
    Hot Reload             模擬生產              每日備份
```

| 環境 | 用途 | 基礎設施 | 資料 | 外部服務 |
| :--- | :--- | :--- | :--- | :--- |
| **Development** | 本地開發與除錯 | `scripts/dev/dev-up.sh`（uvicorn + Docker PostgreSQL + ngrok） | 本機 PostgreSQL 16 + pgvector（Docker），可選擇透過 `cloud-sql-proxy` 連 GCP Staging DB（`./scripts/env/use-gcp.sh`） | LINE Bot: ngrok 暫時隧道。Google AI: 開發帳號（設定用量上限） |
| **Staging** | 整合測試、UAT 驗收 | Cloud Run（獨立 service：`agent-staging` / `api-staging`） | Cloud SQL (staging)，匿名化生產資料副本 | LINE Bot: 獨立的 Staging Channel。Google AI: 開發帳號 |
| **Production** | 正式運行環境 | Cloud Run（`agent` / `api`） | Cloud SQL (production)，自動備份（PITR + 每日 dump 保留 30 天） | LINE Bot: 正式 Channel。Google AI: 正式帳號 |

**環境隔離原則：**
- 每個環境使用獨立的 `.env` 檔案，絕不共享密鑰
- Staging 與 Production 使用獨立的 LINE Channel
- 生產 API Key 僅存在於生產環境的密鑰管理中
- 開發環境使用 Google AI 帳號的用量上限 (usage cap) 防止誤用

### 1.2 部署拓撲圖

#### 1.2.1 生產拓撲（Cloud Run，V1.0 實際部署）

```mermaid
graph TB
    subgraph "External"
        LINE_USER["LINE Users"]
        LINE_SRV["LINE Messaging API"]
        ADMIN["Admin Web (V2.0)"]
        GOOGLE_AI["Google Vertex AI<br/>(Gemini)"]
        OPIK["Opik<br/>(LLM observability)"]
    end

    subgraph "GCP Project"
        subgraph "Cloud Run Services"
            AGENT["agent service<br/>---<br/>FastAPI + LangGraph<br/>Port 8080<br/>Image: agent/Dockerfile"]
            API["api service<br/>---<br/>FastAPI backend<br/>Port 8080<br/>Image: api/Dockerfile"]
        end

        subgraph "Cloud SQL"
            PG["PostgreSQL 16 + pgvector<br/>---<br/>checkpoints / facts / audit / vectors<br/>連線：Unix socket（生產） / cloud-sql-proxy（local dev）"]
        end

        subgraph "Secret Manager"
            SECRETS["LINE_CHANNEL_SECRET<br/>LINE_CHANNEL_ACCESS_TOKEN<br/>DB_PASSWORD<br/>POSTGRES_URI<br/>OPIK_API_KEY"]
        end

        AR["Artifact Registry<br/>(agent + api images)"]
    end

    LINE_USER -- "HTTPS message" --> LINE_SRV
    LINE_SRV -- "Webhook POST /webhook" --> AGENT
    ADMIN -- "REST /api/v1/*" --> API
    AGENT -- "Cloud SQL (Unix socket)" --> PG
    API -- "Cloud SQL (Unix socket)" --> PG
    AGENT -- "secrets injected at deploy" -.- SECRETS
    API -- "secrets injected at deploy" -.- SECRETS
    AGENT -- "Vertex SDK" --> GOOGLE_AI
    AGENT -- "trace export" --> OPIK
    AR -. "image pull" .-> AGENT
    AR -. "image pull" .-> API
```

**特點：**
- 兩個獨立 Cloud Run service（`agent` / `api`），分別由 `scripts/deploy/agent.sh` / `scripts/deploy/api.sh` 部署
- DB 連線走 **Cloud SQL Unix socket**（無需開放公網 IP），本機開發時改走 `cloud-sql-proxy`（見 `scripts/dev/proxy-up.sh`）
- 無 nginx / 無 Redis / 無 docker-compose — 邊緣代理為 GCP Load Balancer + Cloud Run 內建 HTTPS

#### 1.2.2 Local Dev 拓撲（Docker Compose 多服務一鍵起，僅參考）

下圖描述早期單機 self-host 的 docker-compose 拓撲，**目前僅作為自架 VPS 場景的參考**，生產環境已遷至 Cloud Run。本機開發推薦走 `scripts/dev/dev-up.sh`（uvicorn + Docker PostgreSQL + ngrok），不需要起整個 docker-compose stack。

```mermaid
graph TB
    subgraph "Host Machine (VPS / Cloud VM)"
        subgraph "Docker Network: smartlock-net"

            subgraph "Reverse Proxy"
                NGINX["Nginx<br/>---<br/>SSL Termination<br/>Reverse Proxy<br/>Static File Serving<br/>Rate Limiting<br/>---<br/>Port: 80, 443"]
            end

            subgraph "Application Tier"
                API1["FastAPI App<br/>(Worker 1)<br/>---<br/>Python 3.11 + Uvicorn<br/>Port: 8000"]
                API2["FastAPI App<br/>(Worker 2)<br/>---<br/>Python 3.11 + Uvicorn<br/>Port: 8001"]
            end

            subgraph "Frontend Tier (V2.0)"
                NEXT["Next.js 14+ App<br/>---<br/>SSR / Static<br/>Port: 3000"]
            end

            subgraph "Data Tier"
                PG["PostgreSQL 16<br/>+ pgvector 0.7+<br/>---<br/>Port: 5432<br/>Volume: pg_data"]
                RD["Redis 7<br/>---<br/>Port: 6379<br/>Volume: redis_data"]
            end

            subgraph "Utility"
                BACKUP["Backup CronJob<br/>---<br/>Daily pg_dump<br/>Volume: backup_data<br/>保留 30 天"]
            end
        end
    end

    subgraph "External"
        INTERNET["Internet<br/>(LINE Users / Admins / Technicians)"]
        LINE_SRV["LINE Messaging API"]
        GOOGLE_AI_SRV["Google AI API<br/>(Gemini 3 Pro + Embeddings)"]
        GOOGLE_MAPS["Google Maps API<br/>(V2.0)"]
    end

    INTERNET -- "HTTPS :443" --> NGINX
    LINE_SRV -- "Webhook POST :443" --> NGINX
    NGINX -- "Proxy Pass /api/* :8000" --> API1
    NGINX -- "Proxy Pass /api/* :8001" --> API2
    NGINX -- "Proxy Pass /* :3000" --> NEXT
    NEXT -- "API Call :8000" --> API1
    API1 -- "SQL :5432" --> PG
    API2 -- "SQL :5432" --> PG
    API1 -- "Cache :6379" --> RD
    API2 -- "Cache :6379" --> RD
    API1 -- "HTTPS" --> GOOGLE_AI_SRV
    API2 -- "HTTPS" --> GOOGLE_AI_SRV
    API1 -- "HTTPS" --> LINE_SRV
    API1 -- "HTTPS" --> GOOGLE_MAPS
    BACKUP -- "pg_dump :5432" --> PG
```

### 1.3 容器服務清單（self-host 參考；生產走 Cloud Run）

> 以下表格描述 self-host docker-compose 拓撲下的容器組成。**生產實際只有兩個 Cloud Run service（`agent` / `api`）**，無 nginx / 無 Redis，DB 由 Cloud SQL 託管。

| 服務名稱 | Image | 端口 | 環境變數 | Volume | 備註 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `nginx` | nginx:alpine | 80, 443 (external) | - | `./nginx/conf.d`, `./certs` | SSL 終止、反向代理、Rate Limiting |
| `api` (backend) | 自建 Dockerfile | 8000 (internal) | `DATABASE_URL`, `REDIS_URL`, `GOOGLE_API_KEY`, `LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN`, `JWT_SECRET` | `./uploads` | 可用 `--scale api=2` 水平擴展 |
| `web` (frontend, V2.0) | 自建 Dockerfile | 3000 (internal) | `NEXT_PUBLIC_API_URL` | - | Next.js SSR |
| `postgres` | pgvector/pgvector:pg16 | 5432 (internal) | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | `pg_data` | 啟用 pgvector extension |
| `redis` | redis:7-alpine | 6379 (internal) | - | `redis_data` | 持久化 appendonly |
| `backup` | postgres:16-alpine | - | - | `backup_data` | cron 排程 pg_dump，每日執行 |

### 1.4 網路與端口規劃（self-host 參考）

> 生產 Cloud Run 沒有「Docker network」概念 — 兩個 service 各自有獨立 HTTPS endpoint（`https://agent-xxx.a.run.app`），透過 Cloud SQL Unix socket 連 DB，不暴露任何 PostgreSQL / Redis 端口至公網。下表描述 self-host 拓撲。

**Docker Network:** `smartlock-net` (bridge mode)

| 服務 | 內部端口 | 外部端口 | 說明 |
| :--- | :--- | :--- | :--- |
| Nginx | 80, 443 | 80, 443 | 唯一對外暴露的服務 |
| FastAPI Backend | 8000 | - (不對外) | 僅透過 Nginx 代理存取 |
| Next.js Frontend | 3000 | - (不對外) | 僅透過 Nginx 代理存取 |
| PostgreSQL | 5432 | - (不對外) | 僅 Docker 內部網路可存取 |
| Redis | 6379 | - (不對外) | 僅 Docker 內部網路可存取 |

**重要原則：** 生產環境中，僅 Nginx 的 80/443 端口對外暴露。資料庫與快取服務嚴禁對外暴露端口。

---

## 第 2 部分：CI/CD 流水線

### 2.1 流水線概覽

CI/CD 使用 GitHub Actions 實現，分為兩條流水線：

```mermaid
graph LR
    subgraph "Developer"
        DEV["git push<br/>to feature branch"]
    end

    subgraph "GitHub Actions Pipeline"
        subgraph "PR Pipeline (ci.yml)"
            LINT["Step 1: Lint<br/>---<br/>ruff check<br/>mypy type check"]
            TEST["Step 2: Test<br/>---<br/>pytest<br/>(unit + integration)<br/>coverage >= 70%"]
            BUILD["Step 3: Build<br/>---<br/>docker build<br/>image validation"]
        end

        subgraph "Main Pipeline (deploy.yml)"
            TAG["Step 4: Tag<br/>---<br/>Semantic Version<br/>Git Tag"]
            DEPLOY_AGENT["Step 5: Deploy Agent<br/>---<br/>scripts/deploy/agent.sh<br/>build + push + Cloud Run"]
            DEPLOY_API["Step 6: Deploy API<br/>---<br/>scripts/deploy/api.sh<br/>build + push + Cloud Run"]
            SMOKE["Step 7: Smoke Test<br/>---<br/>Health check<br/>tests/smoke/api.sh"]
        end
    end

    subgraph "Production (GCP)"
        PROD["Cloud Run<br/>(agent + api services)"]
    end

    DEV --> LINT
    LINT -->|pass| TEST
    TEST -->|pass| BUILD
    BUILD -->|merge to main| TAG
    TAG --> DEPLOY_AGENT
    TAG --> DEPLOY_API
    DEPLOY_AGENT --> SMOKE
    DEPLOY_API --> SMOKE
    SMOKE --> PROD
```

### 2.2 ci.yml - 持續整合

**觸發條件：** 每次 `push` 或 `pull_request`

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.11"
  NODE_VERSION: "20"

jobs:
  # ----- 後端 Lint（uv workspace 統一執行）-----
  lint-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - run: uv sync --frozen

      - run: uv run ruff check .

      - run: uv run ruff format --check .

      - run: uv run mypy agent api data

  # ----- 後端 Test -----
  test-backend:
    runs-on: ubuntu-latest
    needs: lint-backend
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: smart_lock_test
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - run: uv sync --frozen

      - name: Run pytest with coverage
        env:
          POSTGRES_URI: postgresql://test_user:test_password@localhost:5432/smart_lock_test
          APP_ENV: testing
        run: |
          uv run pytest tests/ -v --cov=agent --cov=api --cov=data --cov-report=xml --cov-fail-under=70

      - name: Upload coverage report
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage.xml

  # ----- 後端 Build（驗證 Docker image 可成功建置）-----
  build-backend:
    runs-on: ubuntu-latest
    needs: test-backend
    steps:
      - uses: actions/checkout@v4

      - name: Build agent Docker image
        run: docker build -f agent/Dockerfile -t smartlock-agent:ci-${{ github.sha }} .

      - name: Build api Docker image
        run: docker build -f api/Dockerfile -t smartlock-api:ci-${{ github.sha }} .

      - name: Verify agent image starts
        run: |
          docker run --rm -d --name agent-smoke -p 8080:8080 \
            -e POSTGRES_URI="postgresql://x:y@dummy:5432/dummy" \
            smartlock-agent:ci-${{ github.sha }}
          sleep 5
          docker logs agent-smoke
          docker stop agent-smoke || true

  # ----- 前端 Lint (V2.0) -----
  lint-frontend:
    runs-on: ubuntu-latest
    if: ${{ hashFiles('frontend/package.json') != '' }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: cd frontend && npm ci

      - name: Run ESLint
        run: cd frontend && npx eslint src/

      - name: Run TypeScript check
        run: cd frontend && npx tsc --noEmit

  # ----- 前端 Test (V2.0) -----
  test-frontend:
    runs-on: ubuntu-latest
    needs: lint-frontend
    if: ${{ hashFiles('frontend/package.json') != '' }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: cd frontend && npm ci

      - name: Run Jest tests
        run: cd frontend && npm test -- --coverage --watchAll=false
```

### 2.3 deploy.yml - 持續部署（Cloud Run）

**觸發條件：** merge 到 `main` 分支

部署改由 `scripts/deploy/agent.sh` 與 `scripts/deploy/api.sh` 執行（兩者各自處理 LINE Bot agent 與 FastAPI backend 兩個 Cloud Run 服務）。CI 端僅負責 checkout、認證 GCP、呼叫腳本。

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

env:
  GCP_PROJECT: ${{ secrets.GCP_PROJECT }}
  GCP_REGION: asia-east1

jobs:
  # ----- 版本標記 -----
  tag-version:
    runs-on: ubuntu-latest
    outputs:
      version: ${{ steps.version.outputs.new_tag }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Generate semantic version tag
        id: version
        uses: anothrNick/github-tag-action@1.71.0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          DEFAULT_BUMP: patch
          WITH_V: true

  # ----- 部署 LINE Bot Agent 至 Cloud Run -----
  deploy-agent:
    runs-on: ubuntu-latest
    needs: tag-version
    permissions:
      contents: read
      id-token: write    # for Workload Identity Federation
    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WIF_PROVIDER }}
          service_account: ${{ secrets.GCP_DEPLOY_SA }}

      - uses: google-github-actions/setup-gcloud@v2

      - name: Deploy agent (build + push + deploy + health check)
        run: ./scripts/deploy/agent.sh
        env:
          GIT_SHA: ${{ github.sha }}

  # ----- 部署 FastAPI Backend 至 Cloud Run -----
  deploy-api:
    runs-on: ubuntu-latest
    needs: tag-version
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WIF_PROVIDER }}
          service_account: ${{ secrets.GCP_DEPLOY_SA }}

      - uses: google-github-actions/setup-gcloud@v2

      - name: Deploy api (build + push + deploy + health check)
        run: ./scripts/deploy/api.sh
        env:
          GIT_SHA: ${{ github.sha }}

  # ----- Smoke Test -----
  smoke-test:
    runs-on: ubuntu-latest
    needs: [deploy-agent, deploy-api]
    steps:
      - uses: actions/checkout@v4

      - name: Health check (agent)
        run: |
          HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
            ${{ secrets.AGENT_CLOUD_RUN_URL }}/health)
          if [ "$HTTP_STATUS" != "200" ]; then
            echo "Agent health check failed with status $HTTP_STATUS"
            exit 1
          fi

      - name: API smoke test
        env:
          ADMIN_EMAIL: ${{ secrets.SMOKE_ADMIN_EMAIL }}
          ADMIN_PASSWORD: ${{ secrets.SMOKE_ADMIN_PASSWORD }}
          API_BASE_URL: ${{ secrets.API_CLOUD_RUN_URL }}
        run: ./tests/smoke/api.sh

      - name: Notify deployment result
        if: always()
        run: |
          if [ "${{ job.status }}" == "success" ]; then
            echo "Deployment successful - send success notification"
          else
            echo "Deployment failed - trigger rollback alert"
          fi
```

#### 2.3.1 部署腳本三大旗標（`scripts/deploy/agent.sh` / `scripts/deploy/api.sh`）

兩個腳本流程一致：pre-flight 檢查 → build amd64 image → push 至 Artifact Registry → `gcloud run deploy` → health check 重試。透過旗標可分離各階段：

| 旗標 | 用途 | 適用場景 |
| :--- | :--- | :--- |
| `--build-only` | 只 build Docker image，**不** push、**不** deploy | 本機驗證 Dockerfile 變更、CI build job |
| `--deploy-only` | 用既有 image（已在 Artifact Registry）重新 deploy，**不** rebuild | 純配置變更（環境變數、scaling、Secret 輪替）、回滾至特定 image tag |
| `--update-db-uri`（agent 專用）| 從 Secret Manager 讀取 `DB_PASSWORD`，自動 URL encode 後重建 `POSTGRES_URI` 並推回 Secret Manager；附 round-trip 驗證 | DB 密碼輪替後同步 `POSTGRES_URI`；**永遠不要手動構造 POSTGRES_URI**（容易忘記 URL encode 特殊字元） |

**範例：**

```bash
# 完整流程：build → push → deploy → health check
./scripts/deploy/agent.sh

# 只 build（CI build-stage 使用）
./scripts/deploy/agent.sh --build-only

# 用既有 image 重 deploy（如：只改了 env vars / scaling）
./scripts/deploy/agent.sh --deploy-only

# DB 密碼輪替後同步
./scripts/deploy/agent.sh --update-db-uri

# API 服務同理
./scripts/deploy/api.sh
./scripts/deploy/api.sh --build-only
./scripts/deploy/api.sh --deploy-only
```

**Image tagging 策略：** 兩腳本都以 `{git-sha}-{timestamp}` 命名 image tag，支援精確回滾（`--deploy-only` + 指定 tag）。

### 2.4 CI/CD 步驟詳細說明

| 步驟 | 觸發條件 | 工具 | 動作 | 失敗處理 |
| :--- | :--- | :--- | :--- | :--- |
| **Lint** | PR opened / push | `uv run ruff`, `uv run mypy` | 程式碼風格檢查、型別檢查（`uv sync --frozen` 確保依賴版本鎖定） | 阻擋 PR merge |
| **Test** | PR opened / push | `uv run pytest`, `pytest-cov` | 單元測試 + 整合測試，覆蓋率門檻 70% | 阻擋 PR merge |
| **Build** | PR opened / push | `docker build`（`agent/Dockerfile` + `api/Dockerfile`，皆為 multi-stage uv build） | 驗證兩個 service 的 Docker Image 可成功建置 | 阻擋 PR merge |
| **Tag** | merge to main | GitHub Actions | 自動生成語義化版本 Tag (SemVer) | 手動介入 |
| **Deploy Agent** | tag created | `scripts/deploy/agent.sh` | build amd64 image → push 至 Artifact Registry → `gcloud run deploy` → health check | 重試 3 次後標示失敗，不影響 API 部署 |
| **Deploy API** | tag created | `scripts/deploy/api.sh` | 同上，部署 FastAPI backend 至獨立 Cloud Run service | 重試 3 次後標示失敗 |
| **Smoke Test** | deploy completed | `curl /health` + `tests/smoke/api.sh` | 健康檢查端點、關鍵 API 驗證 | 觸發 Cloud Run revision 回滾（`gcloud run services update-traffic`） + 告警通知 |

**備註：** 本專案目前未啟用 Alembic — schema 演進透過 `SQL/Schema*.sql` 手動於 Cloud SQL 套用，不在 CI/CD 流水線中。日後若引入 migration 框架，會新增 `migrate` job 於 deploy 之前。

---

## 第 3 部分：部署檢查清單

### 3.1 部署前檢查

| 類別 | 檢查項目 | 負責人 |
| :--- | :--- | :--- |
| **程式碼品質** | [ ] Code Review 已完成並通過 | 開發者 |
| **程式碼品質** | [ ] 所有測試通過（單元測試、整合測試） | CI 自動化 |
| **程式碼品質** | [ ] 程式碼覆蓋率 >= 70% | CI 自動化 |
| **程式碼品質** | [ ] ruff lint + mypy type check 通過 | CI 自動化 |
| **安全性** | [ ] 無敏感資訊提交至版本控制 (`.env`, API keys) | 開發者 |
| **安全性** | [ ] Docker Image 安全掃描完成 | CI 自動化 |
| **資料庫** | [ ] Alembic migration 腳本已準備（如需要） | 開發者 |
| **資料庫** | [ ] Migration 已在 Staging 環境驗證 | 開發者 |
| **資料庫** | [ ] 生產資料庫已執行備份 | DevOps |
| **外部服務** | [ ] LINE Channel 配置正確（Webhook URL 等） | DevOps |
| **外部服務** | [ ] Google AI API Key 有效且額度充足 | DevOps |
| **文件** | [ ] 回滾計畫已文件化 | 開發者 |
| **溝通** | [ ] 已通知團隊即將部署 | 技術負責人 |

### 3.2 部署中監控

| 類別 | 檢查項目 | 負責人 |
| :--- | :--- | :--- |
| **流程** | [ ] 監控 GitHub Actions 部署進度 | DevOps |
| **健康檢查** | [ ] `/health` 端點回傳 200 | 自動化 |
| **日誌** | [ ] 檢查應用程式日誌無異常錯誤 | DevOps |
| **指標** | [ ] 監控 CPU / 記憶體使用率無異常飆升 | DevOps |
| **資料庫** | [ ] 確認資料庫連線正常 | 自動化 |
| **快取** | [ ] 確認 Redis 連線正常 | 自動化 |
| **外部服務** | [ ] LINE Webhook 可正常接收事件 | DevOps |

### 3.3 部署後驗證

| 類別 | 檢查項目 | 負責人 |
| :--- | :--- | :--- |
| **功能驗證** | [ ] Smoke Test 全部通過 | 自動化 |
| **功能驗證** | [ ] LINE Bot 可正常回覆訊息 | QA |
| **功能驗證** | [ ] Admin Panel 可正常登入與操作 | QA |
| **效能** | [ ] P95 API 延遲 < 2s（非 LLM 端點） | 監控系統 |
| **效能** | [ ] P95 LLM 延遲 < 10s | 監控系統 |
| **效能** | [ ] 錯誤率維持在正常範圍內 | 監控系統 |
| **資料** | [ ] 資料庫 migration 已成功套用 | DevOps |
| **文件** | [ ] 部署版本號已記錄 | DevOps |
| **文件** | [ ] 如有異常，已記錄並排定改善 | 技術負責人 |

---

## 第 4 部分：部署策略

### 4.0 Cloud Run 部署（V1.0 實際採用）

V1.0 生產部署透過 `scripts/deploy/agent.sh` 與 `scripts/deploy/api.sh` 完成。Cloud Run 內建 **revision-based traffic splitting**，原生支援 zero-downtime 部署與快速回滾，不需要應用層的 Blue-Green 切換腳本。

#### 4.0.1 標準部署流程（每次發版）

```bash
# === Agent 服務 ===
# 完整流程：pre-flight → amd64 build → push → deploy → health check
./scripts/deploy/agent.sh

# 只 build Docker image（不 push、不 deploy） — 適合本機 Dockerfile 變更驗證
./scripts/deploy/agent.sh --build-only

# 只 deploy（image 已存在於 Artifact Registry） — 適合純配置變更
./scripts/deploy/agent.sh --deploy-only

# DB 密碼輪替後同步：從 Secret Manager 讀 DB_PASSWORD，URL encode 後重建 POSTGRES_URI
./scripts/deploy/agent.sh --update-db-uri

# === API 服務 ===
./scripts/deploy/api.sh
./scripts/deploy/api.sh --build-only
./scripts/deploy/api.sh --deploy-only
```

#### 4.0.2 Cloud Run 原生回滾

每次 `gcloud run deploy` 都會建立新 revision；舊 revision 保留可立即切流。回滾不需要重 build 或 image pull：

```bash
# 列出近期 revisions
gcloud run revisions list --service=agent --region=asia-east1

# 一鍵回滾至前一 revision（流量 100% 導回）
gcloud run services update-traffic agent \
  --to-revisions=agent-00042-abc=100 \
  --region=asia-east1

# 漸進式：先導 10% 流量到新版測試
gcloud run services update-traffic agent \
  --to-revisions=agent-00043-def=10,agent-00042-abc=90 \
  --region=asia-east1
```

#### 4.0.3 Cloud SQL 連線

| 場景 | 連線方式 | 說明 |
| :--- | :--- | :--- |
| **生產（Cloud Run）** | Cloud SQL Unix socket | 透過 `--add-cloudsql-instances` 旗標掛載；應用以 `host=/cloudsql/PROJECT:REGION:INSTANCE` 連線。**無需開放公網 IP**。 |
| **本機開發** | `cloud-sql-proxy`（TCP localhost:5432） | 透過 `./scripts/dev/proxy-up.sh` 啟動，背景跑；以 `./scripts/dev/proxy-down.sh` 停止 |
| **CI / 自動化測試** | GitHub Actions 內的 `services: postgres:` 容器 | 純測試 DB，不連 Cloud SQL |

**切換本機 .env 目標 DB：**

```bash
./scripts/env/use-local.sh           # → .env.local（本機 Docker PostgreSQL）
./scripts/env/use-gcp.sh             # → .env.gcp（GCP Cloud SQL via cloud-sql-proxy）
./scripts/env/use-gcp.sh --fetch     # 重新從 Secret Manager 拉 .env.gcp
```

---

### 4.1 Blue-Green 部署 (生產環境，self-host 參考)

> 以下流程為早期 self-host VPS 的部署設計。**生產環境已遷至 Cloud Run，由 revision-based traffic splitting 取代**（見 §4.0.2）。本節保留作為 self-host 場景的參考。

生產環境採用 Blue-Green 部署策略，確保零停機時間與快速回滾能力。

```
                    ┌─────────────────────────────────┐
                    │          Nginx (Router)          │
                    │   upstream: blue / green toggle  │
                    └────────────┬────────────────────┘
                                 │
                    ┌────────────┴────────────────────┐
                    │                                  │
           ┌───────▼───────┐              ┌───────────▼───────┐
           │  Blue Env     │              │  Green Env        │
           │  (Current)    │              │  (New Version)    │
           │               │              │                   │
           │  api:v1.2.0   │              │  api:v1.3.0       │
           │  web:v1.2.0   │              │  web:v1.3.0       │
           └───────────────┘              └───────────────────┘
```

**Blue-Green 部署流程：**

```bash
#!/bin/bash
# scripts/deploy-blue-green.sh

set -e

DEPLOY_DIR="/opt/smartlock"
CURRENT_ENV=$(cat ${DEPLOY_DIR}/.current-env 2>/dev/null || echo "blue")

if [ "$CURRENT_ENV" = "blue" ]; then
  NEW_ENV="green"
else
  NEW_ENV="blue"
fi

echo "=== 當前環境: ${CURRENT_ENV}, 部署目標: ${NEW_ENV} ==="

# Step 1: 拉取新版映像檔
echo "--- Step 1: 拉取新版映像檔 ---"
docker compose -f docker-compose.${NEW_ENV}.yml pull

# Step 2: 啟動新環境
echo "--- Step 2: 啟動新環境 (${NEW_ENV}) ---"
docker compose -f docker-compose.${NEW_ENV}.yml up -d

# Step 3: 等待服務就緒
echo "--- Step 3: 等待服務就緒 ---"
sleep 15
for i in $(seq 1 10); do
  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:800${NEW_ENV_PORT}/health)
  if [ "$HTTP_STATUS" = "200" ]; then
    echo "新環境健康檢查通過"
    break
  fi
  echo "等待中... (${i}/10)"
  sleep 5
done

if [ "$HTTP_STATUS" != "200" ]; then
  echo "錯誤：新環境健康檢查失敗，中止部署"
  docker compose -f docker-compose.${NEW_ENV}.yml down
  exit 1
fi

# Step 4: 切換 Nginx 流量至新環境
echo "--- Step 4: 切換流量至 ${NEW_ENV} ---"
cp nginx/conf.d/upstream-${NEW_ENV}.conf nginx/conf.d/upstream-active.conf
docker compose exec nginx nginx -s reload

# Step 5: 驗證切換成功
echo "--- Step 5: 驗證切換 ---"
sleep 5
HEALTH=$(curl -s https://your-domain.com/health)
echo "Health response: ${HEALTH}"

# Step 6: 關閉舊環境
echo "--- Step 6: 關閉舊環境 (${CURRENT_ENV}) ---"
docker compose -f docker-compose.${CURRENT_ENV}.yml down

# Step 7: 記錄當前環境
echo "${NEW_ENV}" > ${DEPLOY_DIR}/.current-env
echo "=== 部署完成: ${NEW_ENV} 已上線 ==="
```

### 4.2 滾動部署 (Staging 環境，self-host 參考)

> 生產 Staging 走 Cloud Run（`agent-staging` / `api-staging` service），由 `./scripts/deploy/agent.sh` 部署到 staging 專案即可，不需要應用層 rolling 腳本。本節保留作為 self-host 參考。

Staging 環境（self-host 模式）採用簡化的滾動部署：

```bash
#!/bin/bash
# scripts/deploy-staging.sh

set -e

DEPLOY_DIR="/opt/smartlock-staging"

cd ${DEPLOY_DIR}

# 備份當前版本資訊
docker compose images > .previous-versions.txt

# 拉取最新映像檔
docker compose pull

# 滾動重啟（先啟新，後停舊）
docker compose up -d --remove-orphans

# 等待就緒並驗證
sleep 15
curl -f http://localhost/health || {
  echo "部署失敗，執行回滾"
  docker compose down
  docker compose up -d  # 使用本地快取的舊映像
  exit 1
}

echo "Staging 部署完成"
```

### 4.3 首次部署流程

> **Cloud Run 首次部署**：
> 1. 在 GCP 建立 Artifact Registry repository、Cloud SQL instance、Secret Manager secrets
> 2. 設定 GitHub Actions Workload Identity Federation（避免 long-lived service account key）
> 3. 執行 `./scripts/deploy/agent.sh` 與 `./scripts/deploy/api.sh` 各一次完整部署
> 4. 在 LINE Developers Console 設定 Webhook URL 為 agent service URL + `/webhook`
>
> 詳細 GCP 資源建立指令見 `docs/02-design/specs/`（API 規格）與專案 README。
>
> 以下流程為 self-host VPS 首次部署參考：

首次部署（self-host 模式）需要額外的初始化步驟：

```bash
#!/bin/bash
# scripts/initial-deploy.sh

set -e

DEPLOY_DIR="/opt/smartlock"

# Step 1: 建立目錄結構
mkdir -p ${DEPLOY_DIR}/{nginx/conf.d,certs,backups,uploads,logs}

# Step 2: 複製設定檔
cp docker-compose.prod.yml ${DEPLOY_DIR}/docker-compose.yml
cp .env.production ${DEPLOY_DIR}/.env
cp -r nginx/ ${DEPLOY_DIR}/nginx/

# Step 3: 設定 SSL 憑證（使用 Let's Encrypt）
certbot certonly --standalone -d your-domain.com
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ${DEPLOY_DIR}/certs/
cp /etc/letsencrypt/live/your-domain.com/privkey.pem ${DEPLOY_DIR}/certs/

# Step 4: 啟動服務
cd ${DEPLOY_DIR}
docker compose up -d

# Step 5: 等待 PostgreSQL 就緒
echo "等待 PostgreSQL 啟動..."
sleep 10
docker compose exec postgres pg_isready -U smartlock

# Step 6: 執行資料庫初始化
docker compose exec api alembic upgrade head

# Step 7: 載入初始 RAG 知識庫資料（如有需要）
docker compose exec api python -m smart_lock.scripts.seed_knowledge_base

# Step 8: 設定自動備份 CronJob
(crontab -l 2>/dev/null; echo "0 3 * * * cd ${DEPLOY_DIR} && ./scripts/backup.sh >> ${DEPLOY_DIR}/logs/backup.log 2>&1") | crontab -

# Step 9: 驗證
curl -f https://your-domain.com/health
echo "首次部署完成"
```

---

## 第 5 部分：監控與告警

### 5.1 應用程式指標

| 指標類別 | 指標名稱 | 類型 | 目標值 | 說明 |
| :--- | :--- | :--- | :--- | :--- |
| **API 效能** | `api_request_duration_seconds` | Histogram | P95 < 2s | REST API 請求延遲分佈（不含 LLM） |
| **API 效能** | `api_request_total` | Counter | - | API 請求總數（按 method, path, status） |
| **LLM 效能** | `llm_call_duration_seconds` | Histogram | P95 < 10s | LLM API 呼叫延遲 |
| **LLM 效能** | `llm_token_usage_total` | Counter | - | Token 使用量（按 model, type） |
| **LLM 成本** | `llm_cost_usd_total` | Counter | - | LLM 累計花費（USD） |
| **解決率** | `resolution_total` | Counter | - | 問題解決次數（按 level: L1/L2/L3） |
| **解決率** | `resolution_success_rate` | Gauge | L1 >= 40% | 各層解決成功率 |
| **知識庫** | `knowledge_base_entries_total` | Gauge | - | CaseEntry 和 ManualChunk 總數 |
| **LINE** | `webhook_processing_duration_seconds` | Histogram | P95 < 1s | LINE Webhook 處理時間（必須 < 1s 回傳 200） |

**指標實現：** V1.0 使用 FastAPI middleware 收集基礎 API 指標，提供 `/metrics` 端點。可選接入 Prometheus + Grafana。

**健康檢查端點：**

```json
// GET /health
{
  "status": "healthy",
  "version": "1.2.0",
  "timestamp": "2026-02-25T10:30:00Z",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "line_api": "ok",
    "google_ai_api": "ok"
  }
}
```

### 5.2 基礎設施指標

| 指標 | 監控目標 | 告警閾值 | 說明 |
| :--- | :--- | :--- | :--- |
| **CPU 使用率** | 所有容器 | > 80% 持續 5 分鐘 | Docker stats 或 cAdvisor |
| **記憶體使用率** | 所有容器 | > 85% 持續 5 分鐘 | 重點監控 FastAPI 與 PostgreSQL |
| **磁碟使用率** | Host Machine | > 85% | 含 pg_data, redis_data, backup_data |
| **網路 I/O** | Nginx | 異常流量 spike | 可能是 DDoS 攻擊徵兆 |
| **容器狀態** | 所有容器 | 非 running 狀態 | Docker Health Check |
| **PostgreSQL 連線池** | api 容器 | > 90% 使用率 | asyncpg pool size 配置 |
| **Redis 記憶體** | redis 容器 | > 80% maxmemory | 監控 session 與 cache 使用 |

**基礎設施監控腳本：**

```bash
#!/bin/bash
# scripts/monitor-infra.sh
# 由 cron 每 5 分鐘執行一次

DEPLOY_DIR="/opt/smartlock"
LOG_FILE="${DEPLOY_DIR}/logs/monitor.log"
ALERT_WEBHOOK_URL="${ALERT_WEBHOOK_URL:-}"

check_disk_usage() {
  DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
  if [ "$DISK_USAGE" -gt 85 ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ALERT: Disk usage at ${DISK_USAGE}%" >> ${LOG_FILE}
    # 觸發告警通知
  fi
}

check_container_health() {
  UNHEALTHY=$(docker ps --filter "health=unhealthy" --format "{{.Names}}" 2>/dev/null)
  if [ -n "$UNHEALTHY" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ALERT: Unhealthy containers: ${UNHEALTHY}" >> ${LOG_FILE}
    # 觸發告警通知
  fi
}

check_disk_usage
check_container_health
```

### 5.3 業務指標

| 指標 | 說明 | 監控頻率 |
| :--- | :--- | :--- |
| **活躍對話數** | `active_conversations` — 當前進行中的 LINE 對話 Session | 即時 |
| **問題解決率** | L1/L2 自動解決 vs L3 人工升級的比率 | 每日統計 |
| **知識庫命中率** | L1 向量搜尋命中率（相似度 >= 0.85 的比率） | 每日統計 |
| **LLM 月度花費** | Google AI API 累計費用 | 每日追蹤，月度匯總 |
| **Webhook 回應時間** | LINE Webhook 接收到回傳 200 的時間（必須 < 1 秒） | 即時 |
| **SOP 生成量** | SOP Generator 自動生成的草稿數量 | 每週統計 |
| **V2.0 工單量** | 工單建立/完成數量（按 status 分類） | 每日統計 |
| **V2.0 技師媒合時間** | 從工單建立到技師接單的平均時間 | 即時 |

### 5.4 告警配置

| 告警名稱 | 條件 | 嚴重度 | 通知管道 | 回應 SLA |
| :--- | :--- | :--- | :--- | :--- |
| API 高延遲 | P95 > 5s 持續 5 分鐘 | P2 - Warning | LINE 群組通知 | 30 分鐘內回應 |
| API 錯誤率飆升 | 5xx 比率 > 5% 持續 3 分鐘 | P1 - Critical | LINE 群組通知 + 電話 | 15 分鐘內回應 |
| LLM 呼叫失敗 | 連續失敗 > 3 次 | P1 - Critical | LINE 群組通知 | 15 分鐘內回應 |
| 資料庫連線耗盡 | 連線池使用率 > 90% | P2 - Warning | LINE 群組通知 | 30 分鐘內回應 |
| 磁碟使用率過高 | > 85% | P2 - Warning | LINE 群組通知 | 1 小時內回應 |
| 備份失敗 | 每日備份未在預期時間完成 | P1 - Critical | LINE 群組通知 + Email | 1 小時內回應 |
| 容器異常停止 | 任何容器非 running 狀態 | P1 - Critical | LINE 群組通知 + 電話 | 15 分鐘內回應 |
| LINE Webhook 逾時 | 處理時間 > 1s 比率超過 10% | P2 - Warning | LINE 群組通知 | 30 分鐘內回應 |
| LLM 月度費用超標 | 累計費用超過預算 80% | P3 - Info | Email | 1 個工作天內回應 |

**告警配置範例（結構化格式）：**

```yaml
# configs/alerts.yml
alerts:
  - name: HighErrorRate
    description: "API 5xx 錯誤率飆升"
    condition: "error_rate_5xx > 0.05 for 3m"
    severity: critical
    actions:
      - type: line_notify
        target: ops-group
      - type: phone_call
        target: on-call-engineer

  - name: HighAPILatency
    description: "API 回應延遲過高"
    condition: "api_request_duration_seconds_p95 > 5 for 5m"
    severity: warning
    actions:
      - type: line_notify
        target: ops-group

  - name: LLMCallFailure
    description: "LLM API 連續呼叫失敗"
    condition: "llm_consecutive_failures > 3"
    severity: critical
    actions:
      - type: line_notify
        target: ops-group

  - name: WebhookTimeout
    description: "LINE Webhook 處理超時"
    condition: "webhook_duration_seconds_p95 > 1 for 5m"
    severity: warning
    actions:
      - type: line_notify
        target: ops-group

  - name: BackupFailure
    description: "每日資料庫備份失敗"
    condition: "backup_job_status != success"
    severity: critical
    actions:
      - type: line_notify
        target: ops-group
      - type: email
        target: tech-lead@company.com
```

### 5.5 日誌管理

**日誌規範：**

| 項目 | 規範 |
| :--- | :--- |
| **格式** | JSON 結構化日誌 |
| **框架** | Python `structlog` |
| **等級** | DEBUG (dev) / INFO (staging, prod) |
| **必含欄位** | `timestamp`, `level`, `message`, `request_id`, `user_id` (if available), `module` |
| **LLM 呼叫日誌** | 記錄 prompt_tokens, completion_tokens, total_cost, latency_ms, model, resolution_level |
| **敏感資料** | 日誌中禁止記錄用戶完整訊息內容（僅記錄 message_id 與 content_type） |
| **收集方式** | V1.0: Docker logs + log rotation。V2.0: 可接入 Loki / ELK |
| **保留期限** | 30 天（INFO+）/ 7 天（DEBUG） |

**日誌範例：**

```json
{
  "timestamp": "2026-02-25T10:30:45.123+08:00",
  "level": "INFO",
  "message": "L1 resolution hit",
  "request_id": "req_abc123",
  "user_id": "U1234567890",
  "module": "three_layer_resolver",
  "conversation_id": "conv_xyz",
  "resolution_level": "L1",
  "case_entry_id": "ce_456",
  "similarity_score": 0.92,
  "latency_ms": 45
}
```

**Docker 日誌配置：**

```yaml
# docker-compose.prod.yml 中的日誌配置
services:
  api:
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"
        tag: "smartlock-api"
```

---

## 第 6 部分：回滾程序

### 6.1 自動回滾觸發條件

以下條件將在 Smoke Test 階段自動觸發回滾：

| 條件 | 檢測方式 | 回滾動作 |
| :--- | :--- | :--- |
| 健康檢查失敗 | `/health` 回傳非 200 | 自動回滾至前一版本 |
| API 端點驗證失敗 | `/api/v1/health` 回傳異常 | 自動回滾至前一版本 |
| 錯誤率飆升 | 5xx 比率 > 10%（部署後 5 分鐘內） | 自動回滾至前一版本 |
| 資料庫連線失敗 | 健康檢查中 database 狀態非 ok | 自動回滾至前一版本 |

### 6.2 手動回滾流程

```bash
#!/bin/bash
# scripts/rollback.sh
# 用法: ./scripts/rollback.sh [version]

set -e

DEPLOY_DIR="/opt/smartlock"
ROLLBACK_VERSION=${1:-""}

cd ${DEPLOY_DIR}

echo "=== 開始回滾程序 ==="

# Step 1: 確認回滾版本
if [ -z "$ROLLBACK_VERSION" ]; then
  echo "未指定版本，回滾至前一版本..."
  # 讀取前一版本紀錄
  ROLLBACK_VERSION=$(cat .previous-version 2>/dev/null)
  if [ -z "$ROLLBACK_VERSION" ]; then
    echo "錯誤：找不到前一版本紀錄，請手動指定版本號"
    echo "用法: ./scripts/rollback.sh v1.2.0"
    exit 1
  fi
fi

echo "回滾目標版本: ${ROLLBACK_VERSION}"

# Step 2: 拉取指定版本映像檔
echo "--- Step 2: 拉取版本 ${ROLLBACK_VERSION} 映像檔 ---"
export IMAGE_TAG=${ROLLBACK_VERSION}
docker compose -f docker-compose.prod.yml pull

# Step 3: 停止當前服務
echo "--- Step 3: 停止當前服務 ---"
docker compose -f docker-compose.prod.yml down

# Step 4: 啟動回滾版本
echo "--- Step 4: 啟動回滾版本 ---"
docker compose -f docker-compose.prod.yml up -d

# Step 5: 等待並驗證
echo "--- Step 5: 驗證回滾結果 ---"
sleep 15
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://your-domain.com/health)
if [ "$HTTP_STATUS" = "200" ]; then
  echo "回滾成功: 健康檢查通過"
else
  echo "嚴重錯誤: 回滾後健康檢查仍然失敗 (HTTP ${HTTP_STATUS})"
  echo "請立即手動介入排查"
  exit 1
fi

# Step 6: 記錄回滾事件
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ROLLBACK to ${ROLLBACK_VERSION}" >> ${DEPLOY_DIR}/logs/deploy.log

echo "=== 回滾完成 ==="
```

### 6.3 資料庫回滾

> **本專案目前未啟用 Alembic** — 生產 schema 變更採手動 SQL（見 §9.1.1）。資料庫回滾僅靠 Cloud SQL backup 還原（見下方）。Alembic 段落保留作日後啟用 migration 框架時的參考。

**Alembic Migration 回滾（日後啟用時參考）：**

```bash
# 回滾最近一次 migration
uv run alembic downgrade -1

# 回滾到指定版本
uv run alembic downgrade <revision_id>

# 查看 migration 歷史
uv run alembic history --verbose

# 查看當前版本
uv run alembic current
```

**從 Cloud SQL backup 還原（生產實際採用）：**

```bash
# 列出可用 backup
gcloud sql backups list --instance=smartlock-prod \
  --filter="status=SUCCESSFUL" --sort-by=~startTime --limit=10

# 還原至同一 instance（覆蓋）
gcloud sql backups restore <BACKUP_ID> \
  --restore-instance=smartlock-prod \
  --backup-instance=smartlock-prod

# 或：還原至新 instance（安全方式，可比對資料後切換 POSTGRES_URI）
gcloud sql backups restore <BACKUP_ID> \
  --restore-instance=smartlock-prod-restored \
  --backup-instance=smartlock-prod
```

**從備份還原資料庫（self-host 模式，最後手段）：**

```bash
#!/bin/bash
# scripts/restore-database.sh
# 用法: ./scripts/restore-database.sh <backup_file>

set -e

BACKUP_FILE=$1
DEPLOY_DIR="/opt/smartlock"

if [ -z "$BACKUP_FILE" ]; then
  echo "用法: ./scripts/restore-database.sh backups/smart_lock_20260225_030000.sql.gz"
  echo ""
  echo "可用備份檔案："
  ls -la ${DEPLOY_DIR}/backups/*.sql.gz | tail -10
  exit 1
fi

echo "警告：此操作將覆蓋生產資料庫！"
echo "備份檔案: ${BACKUP_FILE}"
read -p "確認繼續？(yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "操作取消"
  exit 0
fi

# Step 1: 停止應用服務（保持資料庫運行）
echo "--- 停止應用服務 ---"
cd ${DEPLOY_DIR}
docker compose stop api web

# Step 2: 還原資料庫
echo "--- 還原資料庫 ---"
gunzip -c ${BACKUP_FILE} | docker compose exec -T postgres psql -U smartlock -d smart_lock

# Step 3: 重新啟動應用服務
echo "--- 重新啟動應用服務 ---"
docker compose start api web

# Step 4: 驗證
sleep 10
curl -f https://your-domain.com/health && echo "還原成功" || echo "還原後驗證失敗"
```

**重要提醒：**
- 資料庫回滾可能導致資料丟失，務必在回滾前確認影響範圍
- 若 migration 包含不可逆操作（如 DROP COLUMN），則無法使用 `alembic downgrade`，須從備份還原
- 建議在執行 migration 前，先在 Staging 環境驗證 upgrade 與 downgrade 都能正常執行

---

## 第 7 部分：基礎設施即程式碼

> **本節範圍**：
> - **§7.1 / §7.2** Docker Compose、nginx 配置：**僅供 local dev 多服務一鍵起、或自行架設 self-hosted VPS 時參考**。生產環境走 Cloud Run，邊緣代理為 GCP Load Balancer。
> - **§7.3** Dockerfile：**生產實際使用**。`agent/Dockerfile` 與 `api/Dockerfile` 採 multi-stage uv build，被 `scripts/deploy/*.sh` 引用。
> - 部署實際指令見第 4 部分（部署策略）與 §2.3（CI/CD）。

### 7.1 Docker Compose 配置（local dev / self-host 參考）

#### 開發環境 (docker-compose.yml)

```yaml
# docker-compose.yml - Development
version: "3.8"

services:
  # ----- FastAPI 後端 -----
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: development
    ports:
      - "8000:8000"
    volumes:
      - ./backend/src:/app/src  # Hot reload
      - ./uploads:/app/uploads
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn smart_lock.main:app --host 0.0.0.0 --port 8000 --reload
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ----- Next.js 前端 (V2.0) -----
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      target: development
    ports:
      - "3000:3000"
    volumes:
      - ./frontend/src:/app/src  # Hot reload
    env_file: .env
    depends_on:
      - backend
    command: npm run dev
    profiles:
      - v2  # 使用 --profile v2 啟動

  # ----- PostgreSQL 16 + pgvector -----
  db:
    image: pgvector/pgvector:pg16
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./SQL/Schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
      # Knowledge Assets Volume (read-only)
      # - ./harness/task/knowledge/:/app/knowledge/:ro
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-smart_lock}
      POSTGRES_USER: ${POSTGRES_USER:-smartlock}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-devpassword}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-smartlock} -d ${POSTGRES_DB:-smart_lock}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ----- Redis -----
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
  redisdata:

networks:
  default:
    name: smartlock-net
```

#### 生產環境 (docker-compose.prod.yml)

```yaml
# docker-compose.prod.yml - Production
version: "3.8"

services:
  # ----- Nginx 反向代理 -----
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
      - ./frontend-static:/usr/share/nginx/html:ro
    depends_on:
      - backend
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "3"

  # ----- FastAPI 後端 -----
  backend:
    image: ${REGISTRY:-ghcr.io}/${IMAGE_PREFIX:-smartlock}/api:${IMAGE_TAG:-latest}
    expose:
      - "8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./uploads:/app/uploads
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
        reservations:
          cpus: "0.5"
          memory: 512M
    restart: always
    command: uvicorn smart_lock.main:app --host 0.0.0.0 --port 8000 --workers 2
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"
        tag: "smartlock-api"

  # ----- Next.js 前端 (V2.0) -----
  web:
    image: ${REGISTRY:-ghcr.io}/${IMAGE_PREFIX:-smartlock}/web:${IMAGE_TAG:-latest}
    expose:
      - "3000"
    env_file: .env
    depends_on:
      - backend
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "3"
    profiles:
      - v2  # V2.0 階段啟用

  # ----- PostgreSQL 16 + pgvector -----
  db:
    image: pgvector/pgvector:pg16
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./configs/postgresql.conf:/etc/postgresql/postgresql.conf:ro
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
        reservations:
          cpus: "1.0"
          memory: 1G
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"

  # ----- Redis -----
  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    restart: always
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "3"

  # ----- 資料庫備份 -----
  backup:
    image: postgres:16-alpine
    volumes:
      - ./backups:/backups
      - ./scripts/backup.sh:/scripts/backup.sh:ro
    environment:
      PGHOST: db
      PGUSER: ${POSTGRES_USER}
      PGPASSWORD: ${POSTGRES_PASSWORD}
      PGDATABASE: ${POSTGRES_DB}
    depends_on:
      db:
        condition: service_healthy
    entrypoint: /bin/sh
    command: >
      -c "
      echo '0 3 * * * /scripts/backup.sh' | crontab - &&
      crond -f -l 2
      "
    restart: always

volumes:
  pgdata:
    driver: local
  redisdata:
    driver: local

networks:
  default:
    name: smartlock-net
```

### 7.2 Nginx 反向代理配置（self-host 參考；生產走 GCP Load Balancer）

#### 主配置 (nginx/nginx.conf)

```nginx
# nginx/nginx.conf

user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    multi_accept on;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    # JSON 格式日誌
    log_format json_combined escape=json
        '{'
            '"time":"$time_iso8601",'
            '"remote_addr":"$remote_addr",'
            '"request":"$request",'
            '"status":$status,'
            '"body_bytes_sent":$body_bytes_sent,'
            '"request_time":$request_time,'
            '"upstream_response_time":"$upstream_response_time",'
            '"http_user_agent":"$http_user_agent",'
            '"http_x_forwarded_for":"$http_x_forwarded_for"'
        '}';

    access_log /var/log/nginx/access.log json_combined;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 50M;  # PDF 上傳大小限制

    # Gzip 壓縮
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    include /etc/nginx/conf.d/*.conf;
}
```

#### 站台配置 (nginx/conf.d/default.conf)

```nginx
# nginx/conf.d/default.conf

# Backend upstream (支援多 worker)
upstream backend {
    least_conn;
    server backend:8000;
    # 若使用 --scale backend=2，Docker Compose 會自動負載均衡
}

# Frontend upstream (V2.0)
upstream frontend {
    server web:3000;
}

# HTTP -> HTTPS 重導
server {
    listen 80;
    server_name your-domain.com;

    # Let's Encrypt 驗證用
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS 主站台
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL 憑證
    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    # SSL 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/s;
    limit_req_zone $binary_remote_addr zone=webhook_limit:10m rate=50r/s;

    # ----- LINE Webhook -----
    location /webhook {
        limit_req zone=webhook_limit burst=100 nodelay;

        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Webhook 必須快速回應
        proxy_read_timeout 5s;
        proxy_connect_timeout 2s;
    }

    # ----- Backend REST API -----
    location /api/ {
        limit_req zone=api_limit burst=50 nodelay;

        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # LLM 呼叫可能較慢
        proxy_read_timeout 30s;
        proxy_connect_timeout 5s;
    }

    # ----- Health Check -----
    # 細粒度健康檢查端點 (SLA 定義詳見 docs/02-design/specs/sla-availability-spec.md)
    #   /health      — 整體健康狀態
    #   /health/llm  — LLM (Gemini) API 可用性
    #   /health/db   — PostgreSQL 連線狀態
    #   /health/redis — Redis 連線狀態
    location /health {
        proxy_pass http://backend;
        proxy_set_header Host $host;

        # 不做 Rate Limiting
        access_log off;
    }

    # ----- FastAPI 文件 (僅非生產環境) -----
    location /docs {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        # 生產環境建議關閉：deny all;
    }

    location /openapi.json {
        proxy_pass http://backend;
        proxy_set_header Host $host;
    }

    # ----- Metrics 端點 -----
    location /metrics {
        proxy_pass http://backend;
        proxy_set_header Host $host;

        # 僅允許內部存取
        allow 10.0.0.0/8;
        allow 172.16.0.0/12;
        allow 192.168.0.0/16;
        deny all;
    }

    # ----- Frontend (V2.0) -----
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支援 (V2.0 即時通知)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 7.3 Dockerfile 配置（生產實際使用）

兩個後端服務各自有獨立的 Dockerfile，皆採 **multi-stage uv build**：

- `agent/Dockerfile` — LINE Bot agent 服務
- `api/Dockerfile` — FastAPI backend 服務

兩者共用 root 的 `pyproject.toml` + `uv.lock` + `.python-version`，透過 `uv sync --frozen --package <name>` 在 build stage 釘版安裝對應 workspace package 的依賴。runtime stage 只 copy `.venv`，不帶 build cache，最終 image 約 200-300MB。

#### Agent Dockerfile (`agent/Dockerfile`)

```dockerfile
# agent/Dockerfile

# ----- Stage 1: Builder -----
FROM python:3.11-slim AS builder

# 從 Astral 官方 image COPY uv binary（避開 build-essential，加快 build）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# Cache-friendly：先 copy 鎖定檔，避免改原始碼觸發重 sync
COPY pyproject.toml uv.lock .python-version ./
COPY agent/pyproject.toml agent/
COPY api/pyproject.toml api/
COPY data/pyproject.toml data/

RUN uv sync --frozen --no-dev --package agent

# ----- Stage 2: Runtime -----
FROM python:3.11-slim AS runtime

# 只 copy 已建好的 venv，不帶 build cache
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

# Copy agent 原始碼（runtime 不需要 api/data 模組）
COPY agent /app/agent

WORKDIR /app/agent
EXPOSE 8080

# Cloud Run 自動處理健康檢查（透過 startup probe），不需 HEALTHCHECK 指令
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

#### API Dockerfile (`api/Dockerfile`)

```dockerfile
# api/Dockerfile

# ----- Stage 1: Builder -----
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock .python-version ./
COPY agent/pyproject.toml agent/
COPY api/pyproject.toml api/
COPY data/pyproject.toml data/

RUN uv sync --frozen --no-dev --package api

# ----- Stage 2: Runtime -----
FROM python:3.11-slim AS runtime

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

COPY api /app/api

WORKDIR /app/api
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

#### Build / Push / Deploy 不直接使用 `docker build`

正式部署應該透過 `scripts/deploy/agent.sh` / `scripts/deploy/api.sh`，內含：
- amd64 build（避免 Apple Silicon 開發機 build 出 arm64 image）
- 自動標記 `{git-sha}-{timestamp}` tag（可回滾）
- push 至 Artifact Registry
- `gcloud run deploy --image ...` 並注入 Secret Manager 變數
- health check 重試

只有純 image 驗證（CI build job 或本機測試 Dockerfile 修改）才用 `docker build -f agent/Dockerfile .`。

#### 前端 Dockerfile (frontend/Dockerfile) — V2.0

```dockerfile
# frontend/Dockerfile

# ----- Stage 1: Dependencies -----
FROM node:20-alpine as dependencies

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --only=production

# ----- Stage 2: Development -----
FROM node:20-alpine as development

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev"]

# ----- Stage 3: Build -----
FROM node:20-alpine as builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ----- Stage 4: Production -----
FROM node:20-alpine as production

WORKDIR /app

# 建立非 root 使用者
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000 \
    HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD wget -q --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
```

---

## 第 8 部分：部署安全性

### 8.1 密鑰管理

| 密鑰 | 儲存方式 | 存取方式 | 輪替策略 |
| :--- | :--- | :--- | :--- |
| `GOOGLE_API_KEY` | `.env` 檔案（不入版本控制）/ GitHub Secrets | 環境變數 | 每季度輪替 |
| `LINE_CHANNEL_SECRET` | `.env` 檔案 / GitHub Secrets | 環境變數 | LINE 後台設定，按需輪替 |
| `LINE_CHANNEL_ACCESS_TOKEN` | `.env` 檔案 / GitHub Secrets | 環境變數 | LINE 後台設定，按需輪替 |
| `JWT_SECRET_KEY` | `.env` 檔案 / GitHub Secrets | 環境變數 | 每季度輪替 |
| `DATABASE_URL` | `.env` 檔案 / GitHub Secrets | 環境變數 | 密碼每季度輪替 |
| `REDIS_URL` | `.env` 檔案 / GitHub Secrets | 環境變數 | 按需設定 |
| `DEPLOY_SSH_KEY` | GitHub Secrets | CI/CD 部署專用 | 每半年輪替 |

**密鑰安全規範：**

- [ ] `.env` 檔案已加入 `.gitignore`，絕不提交至版本控制
- [ ] `.env.example` 提供所有環境變數的範本（值為佔位符）
- [ ] 生產環境密鑰與開發/Staging 環境嚴格隔離
- [ ] GitHub Secrets 用於 CI/CD 流水線中的密鑰注入
- [ ] 定期輪替所有密鑰（至少每季度一次）
- [ ] Google AI API 設定用量上限 (usage cap) 以防誤用或洩露

### 8.2 網路安全

**防火牆規則 (Host Machine)：**

```bash
# UFW 防火牆配置
# 僅開放必要端口
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH（建議限制來源 IP）
sudo ufw allow 80/tcp    # HTTP (Nginx)
sudo ufw allow 443/tcp   # HTTPS (Nginx)
sudo ufw enable

# 限制 SSH 登入來源（建議）
sudo ufw allow from <your-office-ip> to any port 22
sudo ufw deny 22/tcp
```

**Docker 網路隔離：**
- 所有服務在 `smartlock-net` bridge 網路中通訊
- 僅 Nginx 容器的 80/443 端口映射至 Host
- PostgreSQL 與 Redis 不對外暴露端口
- 容器間通訊使用 Docker DNS 服務名稱（如 `db:5432`）

**Rate Limiting：**
- Nginx 層：IP 級別限流（API: 30 req/s, Webhook: 50 req/s）
- 應用層：Redis 實現用戶級別限流（防止單一用戶濫用）

### 8.3 容器安全

- [ ] 使用官方或經過驗證的 Docker 映像檔（`python:3.11-slim`, `nginx:alpine`, `redis:7-alpine`）
- [ ] 生產環境容器以非 root 使用者運行（`appuser`, `nextjs`）
- [ ] 多階段建構 (Multi-stage Build) 減少最終映像檔大小與攻擊面
- [ ] 定期更新基礎映像檔以修補安全漏洞
- [ ] Volume 使用唯讀掛載 (`:ro`) 限制不必要的寫入權限
- [ ] 設定容器資源限制（CPU, Memory）防止單一容器耗盡主機資源

### 8.4 外部服務安全

| 外部服務 | 安全措施 |
| :--- | :--- |
| **LINE Messaging API** | 每次 Webhook 請求驗證 HMAC-SHA256 簽章；拒絕簽章不匹配的請求 |
| **Google Gemini 3 Pro API** | API Key 透過環境變數注入；設定每日/每月用量上限；Prompt Injection 防護（System Prompt 硬化、輸出過濾） |
| **Google Maps API (V2.0)** | API Key 限制 HTTP Referrer；設定每日呼叫上限 |
| **SSL/TLS** | 使用 Let's Encrypt 自動更新 SSL 憑證；強制 HTTPS；僅啟用 TLS 1.2+ |

---

## 第 9 部分：運維手冊 (Runbook)

### 9.1 資料庫遷移

**場景：** 部署新版本時需要更新資料庫 Schema

> **本專案目前未啟用 Alembic** — schema 演進透過 `SQL/Schema*.sql` 手動於 Cloud SQL 套用。下方流程：
> - **9.1.1**：實際採用方式（手動 SQL 套用）
> - **9.1.2**：日後若引入 Alembic 的參考模板（保留歷史內容）

#### 9.1.1 手動 SQL 套用（實際流程）

```bash
# === 生產 schema 變更標準流程 ===

# Step 1: 備份 Cloud SQL 資料庫
gcloud sql backups create --instance=smartlock-prod --description="pre-schema-change"

# Step 2: 在 Staging 先行驗證
# 透過 cloud-sql-proxy 連 Staging DB
./scripts/env/use-gcp.sh                 # 切到 .env.gcp（指向 Staging）
./scripts/dev/proxy-up.sh                # 啟動 proxy
psql "$POSTGRES_URI" -f SQL/Schema_v2_extensions.sql

# Step 3: 在 Production 執行
# 用 gcloud sql connect 或 cloud-sql-proxy + psql
gcloud sql connect smartlock-prod --user=smartlock --database=smart_lock
\i SQL/Schema_v2_extensions.sql

# Step 4: 驗證結果
\dt                                       # 列出 tables
\d+ user_facts                            # 檢查特定 table 結構

# Step 5: 如需回滾 — 只能從備份還原（手動 SQL 沒有自動 downgrade）
gcloud sql backups restore <BACKUP_ID> --restore-instance=smartlock-prod
```

**注意事項：**
- 生產執行 schema 變更前**必須**先建立 Cloud SQL backup
- 避免在高流量時段執行包含 `ALTER TABLE` 的變更
- 大型 schema 變更（如新增索引）建議使用 `CREATE INDEX CONCURRENTLY`
- pgvector HNSW 索引的建立可能耗時較長，建議安排在低流量時段
- 若 schema 變更涉及不可逆操作（如 `DROP COLUMN`），務必先確認 application code 已部署相容版本

#### 9.1.2 Alembic 模板（日後啟用 migration 框架時參考）

```bash
# 確認當前 migration 版本
uv run alembic current

# 查看 migration 歷史
uv run alembic history --verbose

# 套用所有待執行 migration
uv run alembic upgrade head

# 回滾最近一次 migration
uv run alembic downgrade -1

# 回滾到指定版本
uv run alembic downgrade <revision_id>
```

> 啟用 Alembic 後，CI/CD 流水線需新增 `migrate` job 於 `deploy-agent` / `deploy-api` 之前；migration 失敗應**中止部署**（手動介入）。

### 9.2 手動備份

**場景：** 排程外的緊急備份，或部署前的安全備份

#### 9.2.1 Cloud SQL 手動備份（生產實際採用）

```bash
# 立即觸發 on-demand backup
gcloud sql backups create \
  --instance=smartlock-prod \
  --description="manual-pre-deploy-$(date +%Y%m%d-%H%M%S)"

# 列出近期 backup
gcloud sql backups list --instance=smartlock-prod --limit=10

# Cloud SQL 自動備份策略（已啟用）：
#   - 每日凌晨 03:00 自動備份
#   - PITR（point-in-time-recovery）保留 7 天
#   - 自動備份保留 30 天
```

#### 9.2.2 Self-host pg_dump 備份（參考用）

```bash
#!/bin/bash
# scripts/backup.sh — self-host 模式
# 用法: ./scripts/backup.sh [backup_name]

set -e

DEPLOY_DIR="/opt/smartlock"
BACKUP_DIR="${DEPLOY_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME=${1:-"smart_lock_${TIMESTAMP}"}
BACKUP_FILE="${BACKUP_DIR}/${BACKUP_NAME}.sql.gz"
RETENTION_DAYS=30

# 確保備份目錄存在
mkdir -p ${BACKUP_DIR}

echo "=== 開始資料庫備份 ==="
echo "備份檔案: ${BACKUP_FILE}"

# 執行 pg_dump 並壓縮
docker compose exec -T db pg_dump \
  -U ${POSTGRES_USER:-smartlock} \
  -d ${POSTGRES_DB:-smart_lock} \
  --format=custom \
  --verbose \
  2>> ${DEPLOY_DIR}/logs/backup.log \
  | gzip > ${BACKUP_FILE}

# 驗證備份檔案
FILESIZE=$(stat -f%z "${BACKUP_FILE}" 2>/dev/null || stat -c%s "${BACKUP_FILE}" 2>/dev/null)
if [ "$FILESIZE" -lt 1024 ]; then
  echo "錯誤：備份檔案過小 (${FILESIZE} bytes)，可能備份失敗"
  exit 1
fi

echo "備份完成: ${BACKUP_FILE} (${FILESIZE} bytes)"

# 清理過期備份（保留 30 天）
echo "--- 清理 ${RETENTION_DAYS} 天前的舊備份 ---"
find ${BACKUP_DIR} -name "*.sql.gz" -mtime +${RETENTION_DAYS} -delete

# 列出現有備份
echo "--- 現有備份檔案 ---"
ls -lh ${BACKUP_DIR}/*.sql.gz 2>/dev/null | tail -10

echo "=== 備份流程結束 ==="
```

### 9.3 服務重啟

**場景：** 服務異常需要重啟

#### 9.3.1 Cloud Run（生產實際採用）

Cloud Run 沒有「重啟」的概念 — 觸發新 revision 即可，舊 revision 會被自動取代：

```bash
# === 強制建立新 revision（不變更 image，僅重起所有容器實例）===
gcloud run services update agent --region=asia-east1 --no-traffic
gcloud run services update-traffic agent --to-latest --region=asia-east1

# 或：純配置變更後 redeploy（不 rebuild）
./scripts/deploy/agent.sh --deploy-only

# === 查看服務狀態 ===
gcloud run services describe agent --region=asia-east1
gcloud run revisions list --service=agent --region=asia-east1

# === 即時 logs ===
gcloud run services logs tail agent --region=asia-east1
gcloud run services logs read agent --region=asia-east1 --limit=100
```

**Cloud SQL 重啟（僅在資料庫端有問題時）：**

```bash
gcloud sql instances restart smartlock-prod
```

> Cloud SQL 重啟期間 agent / api 連線會短暫中斷；應用層會透過 `_ensure_conn()` 自動重連（見 architecture 文件）。

#### 9.3.2 Self-host (Docker Compose) — 參考用

```bash
# === 重啟單一服務 ===
docker compose restart backend
docker compose restart nginx
docker compose restart redis    # 注意：會清除非持久化的快取資料

# === 重啟全部服務 ===
docker compose down && docker compose -f docker-compose.prod.yml up -d
docker compose restart backend nginx

# === 強制重建容器 ===
docker compose up -d --force-recreate backend

# === 查看服務狀態 ===
docker compose ps
docker compose logs --tail=50 -f backend
```

### 9.4 水平擴展

**場景：** 流量增加，需要擴展後端 Worker 數量

#### 9.4.1 Cloud Run autoscaling（生產實際採用）

Cloud Run 是 serverless，依請求量自動擴縮容（每個 instance 處理 `--concurrency` 個並發請求）：

```bash
# === 設定 autoscaling 上下限 ===
gcloud run services update agent \
  --region=asia-east1 \
  --min-instances=1 \
  --max-instances=10 \
  --concurrency=80

# === 調整 CPU / Memory ===
gcloud run services update agent \
  --region=asia-east1 \
  --cpu=1 \
  --memory=1Gi

# === Cloud SQL 連線池 ===
# 應用層（agent/api）以 autocommit AsyncConnection 連線，每個 Cloud Run instance 維護獨立連線
# 若連線數逼近 Cloud SQL 上限，調高 Cloud SQL tier 或設定 max-instances 上限
```

**Cloud Run 擴展注意事項：**
- V1.0 並發目標 >= 50 users → `min-instances=1, max-instances=5, concurrency=80` 足夠
- V2.0 並發目標 >= 100 users → 適度提高 `max-instances` 或 `concurrency`
- 每個 Cloud Run instance 會佔用 Cloud SQL 連線；instance 數 × 連線數 不可超過 Cloud SQL `max_connections`
- LangGraph checkpointer 與 facts/audit DB 共用 `POSTGRES_URI`，連線管理由 `_ensure_conn()` 自動處理（見 architecture 文件 H8 章）

#### 9.4.2 Self-host (Docker Compose) — 參考用

```bash
# === Docker Compose scale ===
docker compose -f docker-compose.prod.yml up -d --scale backend=3
docker compose ps
docker compose -f docker-compose.prod.yml up -d --scale backend=2

# === 調整 uvicorn workers（每個 container）===
# command: uvicorn agent.app:app --host 0.0.0.0 --port 8080 --workers 4
```

### 9.5 日誌查詢

**場景：** 排查問題時需要查詢日誌

#### 9.5.1 Cloud Logging（生產實際採用）

```bash
# === 即時 tail ===
gcloud run services logs tail agent --region=asia-east1
gcloud run services logs tail api --region=asia-east1

# === 查最近 N 行 ===
gcloud run services logs read agent --region=asia-east1 --limit=100

# === 進階篩選（gcloud logging）===

# 搜尋錯誤
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=agent AND severity>=ERROR' \
  --limit=50 --format=json

# 搜尋特定 request_id
gcloud logging read \
  'resource.type=cloud_run_revision AND jsonPayload.request_id="req_abc123"' \
  --limit=50

# 搜尋特定用戶
gcloud logging read \
  'resource.type=cloud_run_revision AND jsonPayload.user_id="U1234567890"' \
  --limit=50

# 搜尋 LLM 呼叫相關
gcloud logging read \
  'resource.type=cloud_run_revision AND (jsonPayload.event=~"llm_call|llm_token|resolution_level")' \
  --limit=100

# === 匯出特定時間範圍 ===
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=agent AND timestamp>="2026-02-25T00:00:00Z" AND timestamp<="2026-02-25T23:59:59Z"' \
  > /tmp/agent-logs-20260225.json
```

**Cloud SQL 慢查詢：**

```bash
# 連線到 Cloud SQL 後執行
gcloud sql connect smartlock-prod --user=smartlock --database=smart_lock
SELECT * FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 10;
```

#### 9.5.2 Self-host (Docker Compose) — 參考用

```bash
docker compose logs -f                              # 全部服務即時日誌
docker compose logs -f backend                      # 特定服務
docker compose logs --tail=100 backend              # 最近 100 行
docker compose logs backend 2>&1 | grep -i "error" # 搜尋錯誤
docker compose logs --since="2026-02-25T00:00:00" backend > /tmp/logs.txt
```

### 9.6 SSL 憑證更新

#### 9.6.1 Cloud Run 自動管理（生產）

Cloud Run service 自帶 `*.run.app` HTTPS 憑證，由 Google 自動續期，**運維端無動作**。

若使用自訂域名（如 `bot.example.com`）：

```bash
# 綁定自訂域名（一次性）
gcloud run domain-mappings create \
  --service=agent \
  --domain=bot.example.com \
  --region=asia-east1

# Cloud Run 會自動申請與續期 Google-Managed Certificate（基於 Let's Encrypt）
# 查看狀態
gcloud run domain-mappings describe \
  --domain=bot.example.com \
  --region=asia-east1
```

**運維責任**：在 Cloud DNS 加 CNAME 記錄指向 `ghs.googlehosted.com`，其餘 SSL 流程由 Google 處理。

#### 9.6.2 Self-host (Let's Encrypt + nginx) — 參考用

```bash
#!/bin/bash
# scripts/renew-ssl.sh — self-host 環境用
set -e

DEPLOY_DIR="/opt/smartlock"
DOMAIN="your-domain.com"

certbot renew --quiet
cp /etc/letsencrypt/live/${DOMAIN}/fullchain.pem ${DEPLOY_DIR}/certs/
cp /etc/letsencrypt/live/${DOMAIN}/privkey.pem ${DEPLOY_DIR}/certs/
docker compose exec nginx nginx -s reload
```

```bash
# 每月 1 日凌晨 2 點自動更新（cron）
0 2 1 * * /opt/smartlock/scripts/renew-ssl.sh >> /opt/smartlock/logs/ssl-renew.log 2>&1
```

### 9.7 密鑰輪替

**場景：** 定期輪替 API Key 與密碼

#### 9.7.1 Cloud Run + Secret Manager（生產實際採用）

所有敏感變數存於 GCP Secret Manager（`LINE_CHANNEL_SECRET` / `LINE_CHANNEL_ACCESS_TOKEN` / `DB_PASSWORD` / `POSTGRES_URI` / `OPIK_API_KEY` / `OPIK_WORKSPACE`）。Cloud Run 在 deploy 時注入。

**通用 Secret 輪替流程：**

```bash
# Step 1: 寫入新版本（不影響當前運行）
echo -n "NEW_VALUE" | gcloud secrets versions add LINE_CHANNEL_SECRET --data-file=-

# Step 2: 觸發 Cloud Run 載入新 secret 版本（建立新 revision）
./scripts/deploy/agent.sh --deploy-only

# Step 3: 確認服務健康
curl https://<agent-cloud-run-url>/health

# Step 4: 撤銷舊版本（可選，建議保留 1-2 個版本緩衝）
gcloud secrets versions disable <OLD_VERSION> --secret=LINE_CHANNEL_SECRET
```

**DB 密碼輪替（agent 專用快速通道）：**

```bash
# Step 1: 在 Cloud SQL 改密碼
gcloud sql users set-password smartlock --instance=smartlock-prod --password=NEW_PASSWORD

# Step 2: 推新密碼到 Secret Manager DB_PASSWORD
echo -n "NEW_PASSWORD" | gcloud secrets versions add DB_PASSWORD --data-file=-

# Step 3: 用 --update-db-uri 旗標自動重建 POSTGRES_URI
#   讀 DB_PASSWORD → URL encode → 組合 POSTGRES_URI → 寫回 Secret Manager → round-trip 驗證
./scripts/deploy/agent.sh --update-db-uri

# Step 4: redeploy 兩個服務套用新 POSTGRES_URI
./scripts/deploy/agent.sh --deploy-only
./scripts/deploy/api.sh --deploy-only
```

> **永遠不要手動構造 POSTGRES_URI** — 密碼若含特殊字元（`@`、`:`、`/`、`?`）必須 URL encode，手動容易出錯。`--update-db-uri` 旗標已內建 round-trip 驗證。

**Google AI / Vertex 認證輪替：**

V1.0 使用 GCP Service Account（透過 Workload Identity 自動認證），無 API Key 需要輪替。若使用 `credentials.json` 方式：

```bash
# Step 1: 在 IAM 建立新的 Service Account Key
# Step 2: 推到 Secret Manager
gcloud secrets versions add VERTEX_CREDENTIALS --data-file=new-key.json

# Step 3: redeploy
./scripts/deploy/agent.sh --deploy-only

# Step 4: 在 IAM 撤銷舊 Key
```

#### 9.7.2 Self-host — 參考用

```bash
# JWT Secret 輪替（self-host 模式）
NEW_SECRET=$(openssl rand -hex 32)
# 編輯 .env 中的 JWT_SECRET_KEY
docker compose restart backend
```

### 9.8 災難復原

**場景：** GCP 區域故障 / 整個服務需從備份重建

#### 9.8.1 Cloud Run + Cloud SQL（生產實際採用）

```bash
#!/bin/bash
# Cloud Run + Cloud SQL 災難復原
set -e

PROJECT=${GCP_PROJECT}
REGION=asia-east1
DR_REGION=asia-northeast1   # 切換用副區域

echo "=== Cloud DR 流程 ==="

# Step 1: 從 Cloud SQL backup 還原至新 instance（或副區域）
echo "--- Step 1: 還原 Cloud SQL ---"
LATEST_BACKUP=$(gcloud sql backups list --instance=smartlock-prod \
  --filter="status=SUCCESSFUL" --sort-by=~startTime --limit=1 --format="value(id)")
gcloud sql backups restore "${LATEST_BACKUP}" \
  --restore-instance=smartlock-prod-dr \
  --backup-instance=smartlock-prod

# Step 2: 確認 Secret Manager 中所有 secret 仍然有效
echo "--- Step 2: 驗證 Secrets ---"
for SECRET in LINE_CHANNEL_SECRET LINE_CHANNEL_ACCESS_TOKEN POSTGRES_URI OPIK_API_KEY; do
  gcloud secrets versions access latest --secret="${SECRET}" > /dev/null
  echo "  ✓ ${SECRET}"
done

# Step 3: 若 POSTGRES_URI 指向舊 instance，更新為 DR instance
echo "--- Step 3: 更新 POSTGRES_URI ---"
./scripts/deploy/agent.sh --update-db-uri    # 自動讀 DB_PASSWORD + 重組 POSTGRES_URI

# Step 4: 重新部署兩個 service
echo "--- Step 4: 重新部署 ---"
./scripts/deploy/agent.sh
./scripts/deploy/api.sh

# Step 5: 驗證 health
echo "--- Step 5: 驗證 ---"
AGENT_URL=$(gcloud run services describe agent --region=${REGION} --format="value(status.url)")
curl -f "${AGENT_URL}/health" && echo "agent 健康"

API_URL=$(gcloud run services describe api --region=${REGION} --format="value(status.url)")
curl -f "${API_URL}/health" && echo "api 健康"

# Step 6: 更新 LINE Developers Console 的 Webhook URL（若 Cloud Run URL 變更）
echo "若 Cloud Run service URL 變更，請至 LINE Developers Console 更新 Webhook URL"

echo "=== Cloud DR 完成 ==="
```

#### 9.8.2 Self-host 災難復原 — 參考用

```bash
#!/bin/bash
# scripts/disaster-recovery.sh — self-host 環境用
# 在新主機上執行完整恢復
set -e

curl -fsSL https://get.docker.com | sh
apt-get install -y docker-compose-plugin certbot

DEPLOY_DIR="/opt/smartlock"
mkdir -p ${DEPLOY_DIR}/{nginx/conf.d,certs,backups,uploads,logs,scripts}

# 從備份儲存取回設定檔與資料庫 dump
# (具體指令視備份儲存方式而定)

certbot certonly --standalone -d your-domain.com
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ${DEPLOY_DIR}/certs/
cp /etc/letsencrypt/live/your-domain.com/privkey.pem ${DEPLOY_DIR}/certs/

cd ${DEPLOY_DIR}
docker compose -f docker-compose.prod.yml up -d db

LATEST_BACKUP=$(ls -t ${DEPLOY_DIR}/backups/*.sql.gz | head -1)
gunzip -c ${LATEST_BACKUP} | docker compose exec -T db psql -U smartlock -d smart_lock

# 若引入 Alembic 的 self-host 設置，於此執行：uv run alembic upgrade head

docker compose -f docker-compose.prod.yml up -d

curl -f https://your-domain.com/health && echo "災難復原完成"

(crontab -l 2>/dev/null; echo "0 3 * * * cd ${DEPLOY_DIR} && ./scripts/backup.sh >> ${DEPLOY_DIR}/logs/backup.log 2>&1") | crontab -
```

**RPO / RTO 目標：**

| 指標 | 目標 | 說明 |
| :--- | :--- | :--- |
| **RPO (Recovery Point Objective)** | <= 24 小時 | 每日凌晨 3 點備份，最多丟失 24 小時資料 |
| **RTO (Recovery Time Objective)** | <= 2 小時 | 從發現問題到服務恢復的最大時間 |

---

## 第 10 部分：環境專屬配置

### 10.1 Development 環境

**用途：** 本地功能開發、單元測試、除錯

```bash
# 啟動完整開發環境（uvicorn + Docker PostgreSQL + ngrok）
./scripts/dev/dev-up.sh

# 切換 .env 目標 DB
./scripts/env/use-local.sh                 # 本機 Docker PostgreSQL
./scripts/env/use-gcp.sh                   # GCP Cloud SQL via cloud-sql-proxy
./scripts/env/use-gcp.sh --fetch           # 重新從 Secret Manager 拉 .env.gcp

# 連 GCP DB 模式時，需另外起 cloud-sql-proxy
./scripts/dev/proxy-up.sh
./scripts/dev/proxy-down.sh

# 停止開發環境（保留 PostgreSQL container 不刪）
./scripts/dev/dev-down.sh
```

**直接跑 agent / api（不透過 dev-up.sh）：**

```bash
# Agent（LINE Bot）
cd agent && uv run uvicorn app:app --reload --port 8000

# Agent CLI 連線測試
cd agent && uv run python main.py

# API backend
cd api && uv run uvicorn main:app --reload --port 8001

# 快速測試 /chat 端點
curl "http://localhost:8000/chat?q=門打不開"
```

**開發環境特性：**
- 應用透過 `uv run` 啟動，享有 hot reload
- PostgreSQL 跑在本機 Docker container，端口 `localhost:5432` 對外暴露
- 使用 `.env`（由 `use-local.sh` / `use-gcp.sh` 切換來源）
- LINE Bot 使用 ngrok 建立暫時公開 URL（`dev-up.sh` 會自動啟動 ngrok 並印出 URL）
- FastAPI 自動產生的 `/docs` 端點可存取

**ngrok 手動模式（如果不用 dev-up.sh 的整合啟動）：**

```bash
ngrok http 8000
# 取得公開 URL 後，至 LINE Developers Console 設定 Webhook URL
# https://xxxx.ngrok-free.app/webhook
```

### 10.2 Staging 環境

**用途：** 整合測試、UAT 驗收、部署前最後驗證

**部署方式：** Cloud Run 獨立 service（`agent-staging` / `api-staging`），透過 `./scripts/deploy/agent.sh`（指向 staging GCP project / region）部署。

**與 Production 的差異：**

| 項目 | Staging | Production |
| :--- | :--- | :--- |
| GCP Project | staging project | production project |
| LINE Channel | 獨立的 Staging Channel | 正式 Channel |
| Google AI | 開發帳號（低用量上限） | 正式帳號 |
| 資料 | 匿名化的生產資料副本 | 真實資料 |
| Cloud SQL 備份 | 每週備份 | 每日備份 + PITR（保留 30 天） |
| 日誌等級 | INFO | INFO |
| API 文件 | `/docs` 可存取 | `/docs` 關閉 |
| Cloud Run min-instances | 0（冷啟動可接受） | 1+（避免冷啟動）|
| Cloud Run max-instances | 3 | 10 |
| SSL | Cloud Run 自帶 `*.run.app` | 自訂域名 + Google-Managed Cert |

### 10.3 Production 環境

**用途：** 正式對外服務環境

**生產環境特別注意事項：**
- DB 連線走 Cloud SQL Unix socket（無公網 IP），由 `--add-cloudsql-instances` 旗標掛載
- FastAPI Debug 模式關閉（`APP_DEBUG=false`）
- `/docs` 與 `/openapi.json` 端點建議關閉或限制存取
- Cloud Run 設定 `min-instances=1` 避免冷啟動延遲
- Cloud Run 設定 `cpu` / `memory` 上限以控制成本
- 結構化 JSON 日誌（自動進 Cloud Logging，無需 log rotation）
- Cloud SQL 自動每日備份 + PITR，保留 30 天
- HTTPS 由 Cloud Run 強制（HTTP 自動 301）
- Rate Limiting 由 Cloud Armor / 應用層 token bucket 處理
- Health check：Cloud Run startup probe + `/health` endpoint（facts_db + audit_db）

### 10.4 環境變數完整清單

```bash
# =================================================================
# .env.example - 環境變數範本
# 複製此檔案為 .env 並填入實際值（或用 ./scripts/env/use-local.sh / use-gcp.sh 切換）
# .env / .env.local / .env.gcp 一律不得提交至版本控制
# 生產環境改由 GCP Secret Manager 注入（透過 scripts/deploy/*.sh）
# =================================================================

# === Application ===
APP_ENV=development                     # development / staging / production

# === Vertex AI / Gemini ===
VERTEX_PROJECT_ID=your-gcp-project
VERTEX_LOCATION=asia-east1

# === Database (PostgreSQL 16 + pgvector) ===
# V2.0 Schema 擴展: SQL/Schema_v2_extensions.sql (RBAC, inventory, signatures, audit)
# 標準連線（checkpointer / facts / audit），psycopg autocommit
POSTGRES_URI=postgresql://user:password@host:5432/smart_lock
# pgvector 連線（embedding queries）
PG_VECTOR_URI=postgresql://user:password@host:5432/smart_lock

# === LINE Messaging API（agent 必需，CLI / /chat 端點不需）===
LINE_CHANNEL_SECRET=your-channel-secret
LINE_CHANNEL_ACCESS_TOKEN=your-access-token

# === LLM Observability (Opik，可選) ===
OPIK_API_KEY=your-opik-api-key
OPIK_WORKSPACE=your-workspace

# === GCP Auth（本機開發用 service account JSON；Cloud Run 走 Workload Identity）===
GOOGLE_APPLICATION_CREDENTIALS=./credentials.json

# === AI Engine ===
CASE_LIBRARY_CONFIDENCE_THRESHOLD=0.85  # L1 向量搜尋相似度閾值
RAG_CONFIDENCE_THRESHOLD=0.70           # L2 RAG 信心度閾值
VECTOR_SEARCH_TOP_K=5                   # 向量搜尋回傳筆數

# === PostgreSQL (local Docker 模式) ===
# 僅當使用 ./scripts/dev/dev-up.sh 啟動本機 docker PostgreSQL 時相關
POSTGRES_DB=smart_lock
POSTGRES_USER=smartlock
POSTGRES_PASSWORD=your-db-password

# === Logging ===
LOG_LEVEL=DEBUG                         # DEBUG (dev) / INFO (staging, prod)
LOG_FORMAT=json                         # json (all environments)
```

> **生產環境注意**：以上變數在 Cloud Run 由 Secret Manager 注入，**不要**將 `.env` 上傳至 GCP。`scripts/deploy/agent.sh` 在 `gcloud run deploy` 時加上 `--update-secrets` 旗標自動掛載。

**各環境變數差異速查表：**

| 變數 | Development | Staging | Production |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | development | staging | production |
| `LOG_LEVEL` | DEBUG | INFO | INFO |
| `POSTGRES_URI` | 本機 docker DB（5432） / cloud-sql-proxy | Cloud SQL Unix socket（staging instance） | Cloud SQL Unix socket（prod instance） |
| `LINE_CHANNEL_*` | 開發 Channel | Staging Channel | 正式 Channel |
| `VERTEX_PROJECT_ID` | dev project | staging project | prod project |
| Secret 來源 | `.env` 檔案 | Secret Manager（staging） | Secret Manager（prod） |
| Cloud Run min-instances | N/A（本機） | 0 | 1+ |
| Cloud Run max-instances | N/A | 3 | 10 |

---

**重要提醒：** 所有部署程序在執行至生產環境前，務必先在 Staging 環境完成驗證。保持部署流程的自動化與可重複性，減少人為操作錯誤。定期演練災難復原流程，確保在真正需要時能夠順利執行。
