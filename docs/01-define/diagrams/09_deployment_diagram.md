---
status: superseded
superseded_by: docs_v2/1-decisions/architecture-overview.md (deployment)
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# 09 — Deployment Diagram（部署架構圖）

> **為什麼重要？** 定義上線與環境配置，確保系統在不同環境中穩定運行。

## 概述

本圖展示平台從本地開發到生產環境的完整部署架構，包含容器化策略、網路拓撲與 CI/CD 流程。

---

## 生產環境部署架構

```mermaid
flowchart TB
    subgraph INTERNET["🌐 Internet"]
        USER_LINE["👤 客戶<br/>(LINE App)"]
        USER_TECH["🔧 技師<br/>(Mobile Browser)"]
        USER_ADMIN["👔 管理員<br/>(Desktop Browser)"]
    end

    subgraph CDN["CDN / DNS"]
        DNS["DNS<br/>(api.smartlock.com)"]
        SSL["SSL/TLS 1.2+<br/>(Let's Encrypt)"]
    end

    subgraph CLOUD["☁️ Cloud Infrastructure"]
        subgraph LB["Load Balancer"]
            NGINX["Nginx<br/>Reverse Proxy<br/>Rate Limiting"]
        end

        subgraph APP_CLUSTER["Application Cluster (Docker)"]
            subgraph APP1["Container: FastAPI #1"]
                UVICORN1["Uvicorn<br/>Python 3.11<br/>Port 8000"]
            end
            subgraph APP2["Container: FastAPI #2"]
                UVICORN2["Uvicorn<br/>Python 3.11<br/>Port 8000"]
            end
        end

        subgraph FRONTEND["Frontend (Docker)"]
            subgraph NEXT_TECH["Container: Technician App"]
                NEXTJS_T["Next.js 14 PWA<br/>Port 3000"]
            end
            subgraph NEXT_ADMIN["Container: Admin Panel"]
                NEXTJS_A["Next.js 14<br/>Port 3001"]
            end
        end

        subgraph DATA_TIER["Data Tier"]
            subgraph PG_CLUSTER["PostgreSQL Cluster"]
                PG_PRIMARY["PostgreSQL 16<br/>Primary<br/>+ pgvector 0.7<br/>Port 5432"]
                PG_REPLICA["PostgreSQL 16<br/>Read Replica"]
            end
            subgraph REDIS_CLUSTER["Redis"]
                REDIS_PRIMARY["Redis 7<br/>Primary<br/>Port 6379"]
            end
        end

        subgraph STORAGE["Persistent Storage"]
            VOLUME_PG["Volume: pg_data"]
            VOLUME_REDIS["Volume: redis_data"]
            VOLUME_FILES["Volume: file_storage<br/>(Profiles / Manuals)"]
        end

        subgraph MONITORING["Monitoring & Logging"]
            HEALTH["Health Check<br/>/health"]
            LOGS["Structured Logging<br/>(JSON)"]
            ALERTS["Alert Integration<br/>(LINE / Email)"]
        end
    end

    subgraph EXTERNAL_SVC["External Services"]
        LINE_API["LINE Platform"]
        GOOGLE_AI["Google Cloud<br/>(Gemini + Embedding)"]
        GOOGLE_MAPS["Google Maps"]
    end

    USER_LINE --> DNS
    USER_TECH --> DNS
    USER_ADMIN --> DNS
    DNS --> SSL
    SSL --> NGINX

    NGINX --> UVICORN1
    NGINX --> UVICORN2
    NGINX --> NEXTJS_T
    NGINX --> NEXTJS_A

    UVICORN1 --> PG_PRIMARY
    UVICORN2 --> PG_PRIMARY
    UVICORN1 --> REDIS_PRIMARY
    UVICORN2 --> REDIS_PRIMARY

    PG_PRIMARY --> PG_REPLICA
    PG_PRIMARY --> VOLUME_PG
    REDIS_PRIMARY --> VOLUME_REDIS

    UVICORN1 --> LINE_API
    UVICORN1 --> GOOGLE_AI
    UVICORN1 --> GOOGLE_MAPS

    style INTERNET fill:#e3f2fd,stroke:#1565c0
    style CLOUD fill:#f5f5f5,stroke:#616161
    style APP_CLUSTER fill:#f3e5f5,stroke:#7b1fa2
    style DATA_TIER fill:#e8f5e9,stroke:#2e7d32
    style EXTERNAL_SVC fill:#fff3e0,stroke:#e65100
    style MONITORING fill:#fce4ec,stroke:#c62828
```

---

## Docker Compose 配置（開發環境）

```mermaid
flowchart LR
    subgraph DOCKER["Docker Compose (Local Dev)"]
        subgraph NET["Network: smartlock-net"]
            APP["fastapi-app<br/>:8000"]
            PG["postgres<br/>:5432"]
            REDIS["redis<br/>:6379"]
        end

        APP -->|POSTGRES_URI| PG
        APP -->|REDIS_URL| REDIS
    end

    ENV[".env<br/>(API Keys)"] -.->|mount| APP
    VOL_PG["./data/pgdata"] -.->|volume| PG
    VOL_REDIS["./data/redisdata"] -.->|volume| REDIS
```

---

## CI/CD Pipeline

```mermaid
flowchart LR
    subgraph DEV["Development"]
        CODE["Developer Push<br/>to GitHub"]
    end

    subgraph CI["CI (GitHub Actions)"]
        LINT["Lint<br/>(flake8 / black)"]
        TEST["Test<br/>(pytest + pytest-asyncio)"]
        BUILD["Build<br/>Docker Image"]
        SCAN["Security Scan<br/>(dependency check)"]
    end

    subgraph CD["CD (GitHub Actions)"]
        PUSH_IMG["Push Image<br/>to Registry"]
        DEPLOY_STG["Deploy to<br/>Staging"]
        SMOKE["Smoke Test"]
        DEPLOY_PROD["Deploy to<br/>Production"]
    end

    CODE --> LINT --> TEST --> BUILD --> SCAN
    SCAN --> PUSH_IMG --> DEPLOY_STG --> SMOKE --> DEPLOY_PROD

    style DEV fill:#e3f2fd
    style CI fill:#f3e5f5
    style CD fill:#e8f5e9
```

---

## 環境配置對照

| 配置項 | 開發環境 | Staging | 生產環境 |
|:-------|:---------|:--------|:---------|
| **部署方式** | docker-compose | docker-compose | Docker + Load Balancer |
| **FastAPI 實例** | 1 | 1 | 2+ (auto-scale) |
| **PostgreSQL** | 本地容器 | 雲端單節點 | 雲端託管 + Read Replica |
| **Redis** | 本地容器 | 雲端單節點 | 雲端託管 |
| **SSL** | 自簽憑證 | Let's Encrypt | Let's Encrypt / CloudFlare |
| **備份** | 無 | 每日 | 每日自動 + 30 天保留 |
| **監控** | Debug Log | 基本健康檢查 | 結構化日誌 + 警報 |
| **域名** | localhost:8000 | staging.smartlock.com | api.smartlock.com |

---

## 容器規格

| 容器 | Base Image | 資源限制 | 端口 | 依賴 |
|:-----|:-----------|:---------|:-----|:-----|
| fastapi-app | python:3.11-slim | 2 CPU / 4GB RAM | 8000 | postgres, redis |
| postgres | postgres:16-alpine | 2 CPU / 4GB RAM | 5432 | - |
| redis | redis:7-alpine | 1 CPU / 1GB RAM | 6379 | - |
| technician-app | node:20-alpine | 1 CPU / 2GB RAM | 3000 | fastapi-app |
| admin-panel | node:20-alpine | 1 CPU / 2GB RAM | 3001 | fastapi-app |

---

## 備份與災難復原

| 項目 | 策略 | 頻率 | 保留期 |
|:-----|:-----|:-----|:-------|
| PostgreSQL 資料 | pg_dump + 增量 WAL | 每日 + 即時 WAL | 30 天 |
| Redis 快取 | RDB Snapshot | 每小時 | 7 天 |
| 使用者 Profile | 檔案同步至 Object Storage | 每日 | 30 天 |
| Docker Image | Registry 版本保留 | 每次部署 | 最近 10 版 |
| 災難復原 RTO | | | < 4 小時 |
| 災難復原 RPO | | | < 1 小時 |
