# 04 — High-Level Architecture Diagram（高層架構圖）

> **為什麼重要？** 給全體團隊共識的大藍圖，所有人對系統全貌有一致理解。

## 概述

本圖以 C4 Model Level 2 的方式，展示平台內部的主要容器（Container）及其互動方式，涵蓋前端介面、後端服務、資料儲存與外部整合。

---

## 高層架構圖

```mermaid
flowchart TB
    subgraph CLIENTS["客戶端介面"]
        LINE["📱 LINE Official Account<br/>(Rich Menu + Flex Message)"]
        TECH_APP["📱 技師 Web App<br/>(Next.js 14 / PWA)"]
        ADMIN["💻 Admin Panel<br/>(Next.js 14 / shadcn/ui)"]
    end

    subgraph GATEWAY["API Gateway Layer"]
        FASTAPI["⚡ FastAPI Application<br/>(Python 3.11+ / Uvicorn)"]
        WEBHOOK["/webhook<br/>LINE Webhook Handler"]
        REST_API["/api/v1/*<br/>REST API Endpoints"]
    end

    subgraph AI_ENGINE["AI Engine Layer"]
        LANGGRAPH["🧠 LangGraph State Machine<br/>(工作流編排)"]

        subgraph HARNESS["Agent Harness Framework"]
            L1["L1 Task Decompose<br/>(ProblemCard)"]
            L2["L2 Context Assemble<br/>(Freshness + Budget)"]
            L6["L6 Safety Gate<br/>(Dangerous Instruction Check)"]
            L5["L5 Verify Answer<br/>(Quality Eval + Retry)"]
            L8["L8 Entropy Check<br/>(Novel Detection + SOP)"]
        end

        subgraph AGENTS["Multi-Agent System"]
            HW["Hardware<br/>Technician"]
            SALES["Sales<br/>Representative"]
            STORE["Store<br/>Assistant"]
            APP["App<br/>Specialist"]
            MANUAL["Manual<br/>Librarian"]
            WEB["Web<br/>Researcher"]
            RECEP["Receptionist"]
        end

        ROUTER["🔀 Intent Router<br/>(LLM-based + Guardrail)"]
        MERGER["🔗 Answer Merger<br/>(Multi-agent Fusion)"]
    end

    subgraph LLM_LAYER["LLM & Embedding Layer"]
        GEMINI["🌟 Google Gemini<br/>(gemini-2.5-flash)"]
        EMBED["📐 text-embedding-004<br/>(768 dim)"]
    end

    subgraph DATA_LAYER["Data & Storage Layer"]
        PG["🐘 PostgreSQL 16<br/>(+ pgvector HNSW)"]
        REDIS["⚡ Redis 7<br/>(Session Cache)"]

        subgraph VECTOR_COLLECTIONS["向量知識庫"]
            KB_VIDEO["kb_video"]
            KB_LINE["kb_line_chat"]
            KB_WEB["kb_website"]
            KB_YT["kb_youtube"]
            KB_MANUAL["kb_gdrive"]
        end
    end

    subgraph EXTERNAL["External Services"]
        LINE_API["LINE Messaging API"]
        DUCK["DuckDuckGo Search"]
        ORDER["訂單查詢 API"]
        MAPS["Google Maps API"]
    end

    LINE -->|Webhook| WEBHOOK
    TECH_APP -->|REST| REST_API
    ADMIN -->|REST| REST_API

    WEBHOOK --> FASTAPI
    REST_API --> FASTAPI
    FASTAPI --> LANGGRAPH

    LANGGRAPH --> L1
    L1 --> L2
    L2 --> L6
    L6 --> ROUTER
    ROUTER --> AGENTS
    AGENTS --> MERGER
    MERGER --> L5
    L5 -->|retry| L2
    L5 -->|pass| L8
    L8 --> LANGGRAPH

    AGENTS -->|推論| GEMINI
    AGENTS -->|向量化| EMBED
    AGENTS -->|向量搜尋| PG
    LANGGRAPH -->|Session| REDIS
    LANGGRAPH -->|Checkpoint| PG

    FASTAPI -->|Reply/Push| LINE_API
    WEB -->|搜尋| DUCK
    AGENTS -->|訂單查詢| ORDER
    AGENTS -->|距離計算| MAPS

    style CLIENTS fill:#e3f2fd,stroke:#1565c0
    style GATEWAY fill:#f5f5f5,stroke:#616161
    style AI_ENGINE fill:#f3e5f5,stroke:#7b1fa2
    style HARNESS fill:#ede7f6,stroke:#4527a0
    style LLM_LAYER fill:#fff3e0,stroke:#e65100
    style DATA_LAYER fill:#e8f5e9,stroke:#2e7d32
    style EXTERNAL fill:#fce4ec,stroke:#c62828
```

---

## 技術棧總覽

| 層級 | 技術選型 | 說明 |
|:-----|:---------|:-----|
| **前端** | Next.js 14 + Tailwind CSS + shadcn/ui | 技師 PWA + Admin Panel |
| **API 層** | FastAPI + Uvicorn | 非同步 REST API + Webhook |
| **AI 編排** | LangGraph + LangChain 0.3 (LCEL) | 多 Agent 工作流狀態機 |
| **LLM** | Google Gemini 2.5 Flash | 意圖路由、對話生成、資訊擷取 |
| **Embedding** | Google text-embedding-004 | 768 維文字向量化 |
| **主資料庫** | PostgreSQL 16 + pgvector 0.7 | 關聯式資料 + HNSW 向量索引 |
| **快取** | Redis 7 | Session 快取、Debounce Buffer |
| **ORM** | SQLAlchemy 2.0 (async) | 非同步資料庫操作 |
| **容器化** | Docker + docker-compose | 本地開發 + 生產部署 |
| **CI/CD** | GitHub Actions | 自動測試 + 部署 |

---

## 架構設計原則

| 原則 | 實踐 |
|:-----|:-----|
| **Modular Monolith** | V1.0 單體架構，模組邊界清晰，V2.0 可拆分微服務 |
| **Event-Driven** | LangGraph 狀態驅動 + Debounce 訊息緩衝 |
| **ReAct Pattern** | Agent 推論 → 工具呼叫 → 觀察結果 → 再推論 |
| **Fan-out / Fan-in** | 多 Agent 平行分派 → 合併回答 |
| **SCD Type 2** | 使用者事實歷史版本追蹤 |
| **Medallion Architecture** | 資料處理：Raw → Bronze → Silver → Gold |
