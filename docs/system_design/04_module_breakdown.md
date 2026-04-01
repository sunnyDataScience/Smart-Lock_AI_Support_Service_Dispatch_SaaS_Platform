# 電子鎖智能客服與派工平台 — 模組分解與依賴關係

> **版本:** v1.0 | **日期:** 2026-03-31
> **關聯文件:** `02_project_brief_and_prd.md`, `05_architecture_and_design_document.md`, `executive_architecture_overview.md`, `WBS_電子鎖智能平台.md`

---

## 目錄

- [1. 系統架構總覽](#1-系統架構總覽)
- [2. 模組依賴關係](#2-模組依賴關係)
- [3. V1.0 模組詳細規格](#3-v10-模組詳細規格)
- [4. V2.0 模組詳細規格](#4-v20-模組詳細規格)
- [5. 跨模組共用服務](#5-跨模組共用服務)
- [6. 跨模組資料流](#6-跨模組資料流)
- [7. MVP 範圍與 12 週計畫](#7-mvp-範圍與-12-週計畫)

---

## 1. 系統架構總覽

### 1.1 三端架構圖

```mermaid
graph TB
    subgraph "使用者端"
        C["Consumer<br/>LINE Bot"]
        T["Technician<br/>Web App (PWA)"]
        A["Admin<br/>Panel"]
    end

    subgraph "API 閘道層"
        GW["FastAPI Backend<br/>Uvicorn + Pydantic v2<br/>JWT + RBAC"]
    end

    subgraph "AI 服務層"
        LLM["LLM Gateway<br/>LangChain 0.3 LCEL"]
        GEMINI["Google Gemini 3 Pro"]
        EMB["Embedding Service<br/>text-embedding-004 (768d)"]
    end

    subgraph "業務引擎層"
        CS["customer_service<br/>對話 + 問題卡 + 解決引擎"]
        KB["knowledge_base<br/>案例庫 + 手冊 + SOP"]
        DSP_BIZ["dispatch (V2.0)<br/>派工 + 報價"]
        ACC_BIZ["accounting (V2.0)<br/>帳務 + 結算"]
    end

    subgraph "資料層"
        PG["PostgreSQL 16<br/>+ pgvector 0.7"]
        REDIS["Redis 7<br/>Session Cache"]
    end

    subgraph "外部服務"
        LINE_API["LINE Messaging API"]
        MAPS["Google Maps API"]
    end

    C --> LINE_API
    LINE_API --> GW
    T --> GW
    A --> GW

    GW --> LLM
    GW --> CS
    GW --> KB
    GW --> DSP_BIZ
    GW --> ACC_BIZ

    LLM --> GEMINI
    LLM --> EMB

    CS --> PG
    CS --> REDIS
    KB --> PG
    DSP_BIZ --> PG
    ACC_BIZ --> PG

    DSP_BIZ --> MAPS

    classDef user fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    classDef api fill:#FFF3E0,stroke:#E65100,stroke-width:2px
    classDef ai fill:#EDE7F6,stroke:#4527A0,stroke-width:2px
    classDef biz fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    classDef data fill:#F3E5F5,stroke:#6A1B9A,stroke-width:2px
    classDef ext fill:#ECEFF1,stroke:#37474F,stroke-width:2px

    class C,T,A user
    class GW api
    class LLM,GEMINI,EMB ai
    class CS,KB,DSP_BIZ,ACC_BIZ biz
    class PG,REDIS data
    class LINE_API,MAPS ext
```

### 1.2 技術堆疊摘要

| 層級 | 技術選型 |
|:-----|:---------|
| 使用者介面 | LINE Messaging API (Consumer) / Next.js 14 + React 19 + shadcn/ui + Tailwind (Admin & Technician) |
| API 閘道 | FastAPI + Uvicorn / Pydantic v2 / OpenAPI / JWT + RBAC |
| AI 服務 | LangChain 0.3 LCEL / Google Gemini 3 Pro / text-embedding-004 / LangSmith |
| 資料存取 | SQLAlchemy 2.0 Async / asyncpg / Alembic Migration / aioredis |
| 基礎設施 | PostgreSQL 16 + pgvector 0.7 / Redis 7 / Docker Compose / TLS 1.2+ / AES-256 |

---

## 2. 模組依賴關係

### 2.1 分階段依賴圖

```mermaid
graph TB
    subgraph "Phase 0-1: MVP 基礎 (W1-W7)"
        M1["M1: LINE Bot 接入"]
        M2["M2: 對話管理"]
        M3["M3: ProblemCard 引擎"]
        M4["M4: 三層解決引擎"]
        M5["M5: 知識庫管理"]

        M1 --> M2
        M2 --> M3
        M3 --> M4
        M4 --> M5
    end

    subgraph "Phase 2-4: V1.0 完整 (W8-W17)"
        M6["M6: Admin Panel V1.0"]
        M7["M7: SOP 自動生成"]
        M8["M8: LLM Gateway"]

        M6 --> M5
        M6 --> M2
        M7 --> M4
        M7 --> M5
        M8 --> M3
        M8 --> M4
    end

    subgraph "Phase 5-8: V2.0 派工帳務 (W18-W31)"
        M9["M9: 派工引擎"]
        M10["M10: 報價引擎"]
        M11["M11: 帳務模組"]
        M12["M12: 技師 Web App"]
        M13["M13: Admin Panel V2.0"]

        M4 -.->|L3 升級| M9
        M9 --> M10
        M9 --> M11
        M12 --> M9
        M13 --> M9
        M13 --> M11
    end

    classDef v1 fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    classDef v1full fill:#BBDEFB,stroke:#1565C0,stroke-width:2px
    classDef v2 fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px

    class M1,M2,M3,M4,M5 v1
    class M6,M7,M8 v1full
    class M9,M10,M11,M12,M13 v2
```

### 2.2 依賴矩陣

| 模組 | 依賴 | 被依賴 |
|:-----|:-----|:-------|
| M1: LINE Bot 接入 | LINE Messaging API | M2 對話管理 |
| M2: 對話管理 | M1, Redis | M3, M6 |
| M3: ProblemCard 引擎 | M2, LLM Gateway | M4, M9 |
| M4: 三層解決引擎 | M3, M5, LLM Gateway | M7, M9 |
| M5: 知識庫管理 | PostgreSQL + pgvector | M4, M6, M7 |
| M6: Admin Panel V1.0 | M2, M5 | -- |
| M9: 派工引擎 | M3 (ProblemCard), Google Maps | M10, M11, M12, M13 |
| M10: 報價引擎 | M9 | M11 |
| M11: 帳務模組 | M9, M10 | M12, M13 |
| M12: 技師 Web App | M9 | -- |
| M13: Admin Panel V2.0 | M6, M9, M11 | -- |

---

## 3. V1.0 模組詳細規格

### 3.1 M1: LINE Bot 接入模組

**職責：** 接收 LINE Webhook 事件、驗證簽章、路由事件至對應處理器、發送回覆訊息。

| 項目 | 內容 |
|:-----|:-----|
| **核心服務** | `WebhookHandler`, `MessageRouter`, `FlexMessageBuilder`, `RichMenuManager` |
| **AI 整合** | 無直接 AI 整合（純通訊層） |
| **關鍵技術** | FastAPI, line-bot-sdk-python 3, HMAC-SHA256 簽章驗證 |

**資料庫表：**

| 表名 | 關鍵欄位 | 說明 |
|:-----|:---------|:-----|
| `line_users` | `id`, `line_user_id`, `display_name`, `status_message`, `created_at` | LINE 用戶基本資料 |
| `webhook_events` | `id`, `event_type`, `line_user_id`, `payload`, `processed_at`, `created_at` | Webhook 事件日誌 |

---

### 3.2 M2: 對話管理模組

**職責：** 管理對話狀態機（Idle → Collecting → Resolving → Resolved）、Session 生命週期、多輪上下文維護。

| 項目 | 內容 |
|:-----|:-----|
| **核心服務** | `ConversationService`, `SessionManager`, `StateTransitionEngine`, `ContextTracker` |
| **AI 整合** | 對話上下文傳遞給 LLM Gateway 用於意圖識別 |
| **關鍵技術** | Redis（Session 暫存, TTL 30min）, 狀態機模式 |

**資料庫表：**

| 表名 | 關鍵欄位 | 說明 |
|:-----|:---------|:-----|
| `conversations` | `id`, `line_user_id`, `status` (idle/collecting/resolving/resolved), `started_at`, `resolved_at`, `resolution_path` (L1/L2/L3), `message_count` | 對話主表 |
| `messages` | `id`, `conversation_id`, `role` (user/assistant/system), `content`, `media_urls`, `created_at` | 對話訊息記錄 |

**Redis 結構：**

| Key Pattern | Value | TTL |
|:------------|:------|:----|
| `session:{line_user_id}` | JSON（對話狀態、已蒐集欄位、上下文摘要） | 30 min |

---

### 3.3 M3: ProblemCard 引擎

**職責：** 從自然語言對話中擷取結構化欄位，AI 輔助推斷缺失欄位，驗證完整性，生成 Flex Message 供消費者確認。

| 項目 | 內容 |
|:-----|:-----|
| **核心服務** | `ProblemCardService`, `FieldExtractor`, `CompletenessChecker`, `FlexCardRenderer` |
| **AI 整合** | Gemini 3 Pro — NLU 欄位擷取、缺失欄位推斷、意圖分類（維修/購買/諮詢/派工） |
| **關鍵技術** | LangChain LCEL, Pydantic Schema 約束輸出 |

**資料庫表：**

| 表名 | 關鍵欄位 | 說明 |
|:-----|:---------|:-----|
| `problem_cards` | `id`, `conversation_id`, `line_user_id`, `category`, `urgency`, `completeness_score`, `sentiment_label`, `status` (draft/confirmed/resolved), `domain_attributes` (JSONB), `created_at` | 問題診斷卡（領域無關核心 + JSONB 領域欄位） |

> **ProblemCard 領域無關設計**: 核心表欄位僅保留跨領域通用屬性（id, status, completeness_score, sentiment_label 等）。電子鎖特有欄位（brand, model, symptom, door_type, network_type, location, media_urls）遷入 `domain_attributes` JSONB，支援多垂直領域擴展而不需 Schema 變更。

**AI Prompt 範本：**
- 意圖識別 Prompt：分類用戶訊息為 `repair` / `purchase` / `inquiry` / `dispatch` / `other`
- 欄位擷取 Prompt：從對話上下文中提取 brand, model, symptom, location 等結構化欄位
- 追問生成 Prompt：根據缺失欄位生成自然的追問句

---

### 3.4 M4: 三層解決引擎

**職責：** 基於已確認的 ProblemCard，依序執行三層解決策略：L1 案例庫向量搜尋 → L2 RAG 手冊推理 → L3 人工轉接/建工單。

| 項目 | 內容 |
|:-----|:-----|
| **核心服務** | `ResolutionService`, `L1CaseSearcher`, `L2RAGPipeline`, `L3HumanHandoff`, `FeedbackCollector` |
| **AI 整合** | **L1:** pgvector 語意搜尋（text-embedding-004, 相似度 >= 0.85）。**L2:** RAG Pipeline — 手冊 chunks 檢索 + Gemini 整合生成（標註來源頁碼）。 |
| **關鍵技術** | pgvector HNSW 索引, LangChain LCEL Pipeline, Token 成本追蹤 |

**資料庫表：**

| 表名 | 關鍵欄位 | 說明 |
|:-----|:---------|:-----|
| `resolution_attempts` | `id`, `problem_card_id`, `layer` (L1/L2/L3), `result`, `confidence_score`, `source_ids[]`, `feedback` (helpful/not_helpful), `created_at` | 解決嘗試記錄 |

**解決流程：**

```mermaid
graph TD
    PC[ProblemCard Confirmed] --> L1{L1: 案例庫搜尋<br/>相似度 >= 0.85?}
    L1 -->|命中 Top-3| R1[回覆步驟化方案<br/>附「有幫助/沒幫助」]
    L1 -->|未命中| L2{L2: RAG Pipeline<br/>手冊 chunks 檢索}
    R1 --> FB1{消費者回饋}
    FB1 -->|有幫助| DONE[案件結案<br/>觸發 SOP 生成]
    FB1 -->|沒幫助| L2
    L2 -->|生成回覆| R2[回覆 AI 推理方案<br/>標註來源頁碼]
    L2 -->|無相關 chunks| L3[L3: 人工轉接<br/>或建立派工單]
    R2 --> FB2{消費者回饋}
    FB2 -->|有幫助| DONE
    FB2 -->|沒幫助| L3

    style DONE fill:#22c55e,color:#fff
    style L3 fill:#ef4444,color:#fff
```

---

### 3.5 M5: 知識庫管理模組

**職責：** 案例庫 CRUD、PDF 手冊上傳/切分/Embedding、向量搜尋、SOP 自動生成/審核/發布、增量更新。

| 項目 | 內容 |
|:-----|:-----|
| **核心服務** | `KnowledgeBaseService`, `PDFParsingPipeline`, `EmbeddingBatchProcessor`, `SOPGeneratorService`, `SOPReviewWorkflow` |
| **AI 整合** | **Embedding:** text-embedding-004（768 維）批量向量化。**SOP 生成:** Gemini 從成功對話中分析並草擬 SOP（問題描述、適用條件、解決步驟、注意事項）。 |
| **關鍵技術** | PyMuPDF（PDF 解析）, pgvector HNSW 索引, 事件驅動（成功解決 → 觸發 SOP 生成） |

**資料庫表：**

| 表名 | 關鍵欄位 | 說明 |
|:-----|:---------|:-----|
| `case_entries` | `id`, `title`, `brand`, `model`, `symptom`, `solution_steps`, `embedding` (vector 768d), `source` (manual/auto_sop/import), `status` (active/archived), `hit_count`, `created_at` | 案例庫條目 |
| `manual_chunks` | `id`, `manual_id`, `chunk_index`, `content`, `embedding` (vector 768d), `page_number`, `created_at` | 手冊分段 |
| `manuals` | `id`, `brand`, `model`, `file_name`, `file_path`, `total_chunks`, `processing_status` (uploading/chunking/embedding/ready), `created_at` | 產品手冊 |
| `sop_drafts` | `id`, `conversation_id`, `problem_card_id`, `title`, `problem_description`, `applicable_conditions`, `solution_steps`, `precautions`, `status` (draft/approved/rejected/published), `reviewer_id`, `family_reviewer_id`, `created_at` | SOP 草稿 |

---

### 3.6 M-Harness: Agent Harness 框架 (harness/)

**職責：** LangGraph multi-agent 架構的 8 層運行時框架，為所有 AI agent 節點提供統一的任務分解、上下文組裝、治理閘門、安全邊界與可觀測性基礎設施。

| 項目 | 內容 |
|:-----|:-----|
| **核心服務** | `TaskDecomposer` (L1), `ContextAssembler` (L2), `GovernanceGate` (L3), `FeedbackLoop` (L4), `SafetyBoundary` (L5), `ObservabilityTap` (L6), `HumanEscalation` (L7), `EntropyTracker` (L8) |
| **AI 整合** | 包裹所有 LangGraph agent 節點，GraphState 注入 5 個 harness 欄位（harness_trace_id, governance_result, safety_flags, feedback_signals, entropy_score） |
| **關鍵技術** | LangGraph StateGraph, config.toml `[harness]` 區段集中配置, Phase 0 骨架全部 disabled |

**8 層架構摘要：**

| 層級 | 名稱 | 職責 | 護城河對應 |
|:-----|:-----|:-----|:-----------|
| L1 | Task Decomposition | 將使用者意圖拆解為可執行子任務 | Moat A + F |
| L2 | Context Assembly | 組裝 ProblemCard + 知識庫 + 對話歷史上下文 | Moat A + F |
| L3 | Governance Gate | 治理閘門：Token 預算、品質門檻、合規檢查 | -- |
| L4 | Feedback Loop | 收集使用者回饋 + 自動品質評估 | Moat F |
| L5 | Safety Boundary | Prompt Injection 攔截、PII 過濾、Output Guardrail | Moat F |
| L6 | Observability Tap | 結構化日誌、LangSmith 追蹤、成本歸因 | Moat J |
| L7 | Human Escalation | 人工介入判斷與升級路由 | -- |
| L8 | Entropy Tracker | 對話混亂度偵測、模型信心衰減追蹤 | Moat A + F |

---

### 3.7 M-Data: 資料管線模組 (data/)

**職責：** ETL 管線實作 Medallion Architecture，將原始數據（Bronze）清洗為結構化數據（Silver）再聚合為分析就緒數據（Gold）。

| 項目 | 內容 |
|:-----|:-----|
| **核心服務** | `BronzeIngestor`, `SilverTransformer`, `GoldAggregator`, `DataQualityChecker` |
| **AI 整合** | Silver 層觸發 Embedding 批量計算；Gold 層產出訓練語料供 Moat A 語言模型回訓 |
| **關鍵技術** | PostgreSQL JSONB, 事件驅動 ETL, 資料品質閘門 |

---

### 3.8 M-Frontend: 前端應用模組 (frontend/)

**職責：** V1.0 Admin Panel 前端應用，採用 Next.js 14 統一前端技術棧（取代原 Jinja2/HTMX 方案），V2.0 技師 Web App 共用同一代碼庫。

| 項目 | 內容 |
|:-----|:-----|
| **核心服務** | Next.js 14 App Router, React Server Components, shadcn/ui 元件庫 |
| **AI 整合** | 無直接 AI 整合（呈現層），透過 FastAPI REST API 消費後端服務 |
| **關鍵技術** | Next.js 14, TypeScript 5+, shadcn/ui + Tailwind CSS, PWA (V2.0 技師端) |

---

### 3.9 M6: Admin Panel V1.0

**職責：** 提供知識庫管理 UI、對話紀錄查詢、SOP 審核佇列、營運儀表板、系統設定。

| 項目 | 內容 |
|:-----|:-----|
| **核心服務** | `DashboardService`, `ConversationViewService`, `KnowledgeBaseAdminService`, `SOPReviewUIService` |
| **AI 整合** | 無直接 AI 整合（呈現層） |
| **關鍵技術** | V1.0: FastAPI + Jinja2/HTMX（快速開發）；V2.0 升級: Next.js 14 + shadcn/ui |

**頁面清單：**

| 頁面 | 路由 | 主要功能 |
|:-----|:-----|:---------|
| 營運儀表板 | `/dashboard` | 今日對話數、自助解決率、問題分布、品牌排行 |
| 對話列表 | `/conversations` | 按日期/狀態/消費者篩選，標示解決途徑 |
| 對話詳情 | `/conversations/[id]` | 完整對話記錄、ProblemCard、解決路徑 |
| 問題卡列表 | `/problem-cards` | 按狀態/品牌/日期篩選 |
| 案例庫 | `/knowledge-base/cases` | 案例 CRUD、CSV 匯入 |
| 手冊管理 | `/knowledge-base/manuals` | PDF 上傳、處理進度、品牌分類 |
| SOP 審核佇列 | `/knowledge-base/sop-drafts` | 待審核 SOP 列表 |
| SOP 審核面板 | `/knowledge-base/sop-drafts/[id]` | 審核/核准/退回/刪除 |
| 系統設定 | `/settings` | 帳號管理、系統配置 |

---

## 4. V2.0 模組詳細規格

### 4.1 M9: 派工引擎

**職責：** 技師自動匹配（技能 x 地區 x 評分 x 可用時段）、工單生命週期管理（Created → Assigned → InProgress → Completed）、推播通知。

| 項目 | 內容 |
|:-----|:-----|
| **核心服務** | `DispatchService`, `TechnicianMatcher`, `WorkOrderLifecycleManager`, `NotificationDispatcher` |
| **AI 整合** | 無直接 AI 整合（規則引擎匹配） |
| **關鍵技術** | 匹配演算法（加權評分：距離 40% + 技能匹配 30% + 歷史評分 20% + 負載均衡 10%）, WebSocket (即時更新), Google Maps Distance API |

**資料庫表：**

| 表名 | 關鍵欄位 | 說明 |
|:-----|:---------|:-----|
| `work_orders` | `id`, `problem_card_id`, `technician_id`, `status` (created/assigned/in_progress/completed/cancelled), `address`, `latitude`, `longitude`, `estimated_price`, `final_price`, `eta`, `started_at`, `completed_at`, `created_at` | 派工工單 |
| `technicians` | `id`, `user_id`, `name`, `phone`, `skills[]` (品牌認證), `service_regions[]`, `availability_status` (available/busy/offline), `rating`, `total_completed`, `created_at` | 技師資料 |
| `technician_skills` | `id`, `technician_id`, `brand`, `lock_type`, `certification_date`, `expiry_date` | 技師技能認證 |
| `dispatch_logs` | `id`, `work_order_id`, `matched_technicians[]`, `accepted_by`, `dispatch_type` (auto/manual), `created_at` | 派工匹配記錄 |

**工單生命週期：**

```mermaid
stateDiagram-v2
    [*] --> Created: L3 轉派工 / 手動建立
    Created --> Assigned: 技師接單
    Assigned --> InProgress: 技師到場開始維修
    InProgress --> Completed: 提交完工報告
    Assigned --> Cancelled: 技師取消 (30min 內)
    Created --> Cancelled: 管理員取消
    Completed --> [*]
    Cancelled --> Created: 重新派工
```

---

### 4.2 M10: 報價引擎

**職責：** 維護品牌 x 鎖型 x 工項的標準報價矩陣，計算加價項目（夜間/假日/遠程/高樓），自動生成報價單。

| 項目 | 內容 |
|:-----|:-----|
| **核心服務** | `PricingService`, `PriceMatrixManager`, `SurchargeCalculator`, `QuotationGenerator` |
| **AI 整合** | 無直接 AI 整合（規則引擎） |
| **關鍵技術** | 規則引擎模式、多條件疊加計算 |

**資料庫表：**

| 表名 | 關鍵欄位 | 說明 |
|:-----|:---------|:-----|
| `price_rules` | `id`, `brand`, `lock_type`, `work_item`, `base_labor`, `base_material`, `total`, `effective_from`, `effective_to`, `version` | 標準報價矩陣 |
| `surcharge_rules` | `id`, `name`, `trigger_condition` (night/holiday/distance/high_floor), `surcharge_type` (fixed/percentage), `surcharge_value`, `priority`, `is_active`, `created_at` | 加價規則 |
| `quotations` | `id`, `work_order_id`, `base_price`, `surcharges[]`, `total_price`, `status` (draft/confirmed/final), `created_at` | 報價單 |

**預設加價規則：**

| 規則名稱 | 觸發條件 | 加價方式 |
|:---------|:---------|:---------|
| 夜間加價 | 22:00-06:00 | +30% |
| 假日加價 | 國定假日/週日 | +50% |
| 遠程加價 | 距離 > 30km | +$500 固定 |
| 高樓加價 | 樓層 > 5F（無電梯） | +$200/層 |

---

### 4.3 M11: 帳務模組

**職責：** 技師墊付款追蹤、月度結算報表、對帳單、記帳憑證（借方/貸方科目）產出。

| 項目 | 內容 |
|:-----|:-----|
| **核心服務** | `AccountingService`, `AdvanceTracker`, `MonthlySettlementGenerator`, `VoucherGenerator`, `ReconciliationService` |
| **AI 整合** | 無直接 AI 整合 |
| **關鍵技術** | PostgreSQL 交易（ACID）、PDF 報表生成、CSV/Excel 匯出 |

**資料庫表：**

| 表名 | 關鍵欄位 | 說明 |
|:-----|:---------|:-----|
| `transactions` | `id`, `work_order_id`, `technician_id`, `type` (payment/advance/settlement/refund), `amount`, `description`, `status` (pending/approved/rejected/settled), `created_at` | 帳務交易記錄 |
| `advance_claims` | `id`, `work_order_id`, `technician_id`, `amount`, `receipt_photo_url`, `status` (submitted/approved/rejected), `reviewed_by`, `reviewed_at` | 墊付款申請 |
| `monthly_settlements` | `id`, `technician_id`, `month`, `total_cases`, `total_labor`, `total_advances`, `deductions`, `net_amount`, `status` (draft/approved/paid), `approved_by`, `created_at` | 月度結算 |
| `accounting_vouchers` | `id`, `settlement_id`, `voucher_number`, `debit_account`, `credit_account`, `amount`, `description`, `created_at` | 記帳憑證 |

---

### 4.4 M12: 技師 Web App

**職責：** 提供案件池瀏覽、一鍵接單、完工報告提交、個人帳務中心。Mobile-First PWA 設計。

| 項目 | 內容 |
|:-----|:-----|
| **核心服務** | `CasePoolService`, `OrderAcceptanceService`, `CompletionReportService`, `TechnicianAccountService` |
| **AI 整合** | 無直接 AI 整合（呈現層） |
| **關鍵技術** | Next.js 14 + PWA, Responsive Design (Mobile-First), Web Push API |

**頁面清單：**

| 頁面 | 路由 | 主要功能 |
|:-----|:-----|:---------|
| 技師登入 | `/tech-login` | 身分驗證 |
| 案件池 | `/pool` | 可接案件瀏覽、排序（距離/報酬/緊急度） |
| 我的工單 | `/my-orders` | 已接案件管理 |
| 工單詳情/完工回報 | `/my-orders/[id]` | 查看詳情、提交完工報告（照片+材料+工時） |
| 帳戶中心 | `/account` | 收入統計、墊付款狀態、歷史工單 |

---

### 4.5 M13: Admin Panel V2.0

**職責：** 在 V1.0 基礎上擴展：營運儀表板（派工指標）、派工監控、技師管理、帳務審核、客訴處理。

| 項目 | 內容 |
|:-----|:-----|
| **核心服務** | `OperationsDashboardService`, `DispatchMonitorService`, `TechnicianManagementService`, `AccountingAdminService`, `ComplaintManagementService` |
| **AI 整合** | 無直接 AI 整合（呈現層） |
| **關鍵技術** | Next.js 14 + shadcn/ui + Tailwind, Google Maps 視覺化 |

**新增頁面：**

| 頁面 | 路由 | 主要功能 |
|:-----|:-----|:---------|
| 工單列表 | `/work-orders` | 全生命週期追蹤、狀態篩選、逾時告警 |
| 工單詳情 | `/work-orders/[id]` | Timeline、手動指派、狀態變更 |
| 技師管理 | `/technicians` | 技師 CRUD、技能認證、服務區域 |
| 技師詳情 | `/technicians/[id]` | 績效統計、技能到期提醒 |
| 帳務管理 | `/accounting` | 月結報表、墊付款審核、憑證匯出 |

---

## 5. 跨模組共用服務

| 服務 | 職責 | 使用模組 |
|:-----|:-----|:---------|
| **UserManagement** | LINE 用戶綁定、技師/管理員帳號、JWT 認證、RBAC 權限 (admin / technician / user) | 全模組 |
| **LLMGateway** | 統一 LLM 呼叫入口、Prompt 模板管理、Token 追蹤、Retry/Fallback、LangSmith 追蹤 | M3, M4, M5 (SOP) |
| **EmbeddingService** | text-embedding-004 批量向量化、向量正規化 | M4 (搜尋), M5 (索引) |
| **NotificationService** | LINE Push Message、Web Push (技師端)、系統內通知 | M1, M9, M12 |
| **ObservabilityStack** | 結構化日誌 (JSON + trace_id)、LangSmith LLM 追蹤、Health Check API | 全模組 |

---

## 6. 跨模組資料流

### 6.1 完整資料流圖：從報修到結算

```mermaid
graph TD
    subgraph "消費者端"
        U["Consumer 發送 LINE 訊息"]
    end

    subgraph "M1: LINE Bot 接入"
        WH["Webhook Handler<br/>接收事件 + 驗證簽章"]
    end

    subgraph "M2: 對話管理"
        CM["ConversationService<br/>狀態機: Idle → Collecting"]
    end

    subgraph "M3: ProblemCard 引擎"
        PC["ProblemCardService<br/>NLU 擷取 + AI 推斷"]
        FLEX["FlexCardRenderer<br/>Flex Message 確認"]
    end

    subgraph "M4: 三層解決引擎"
        L1["L1: pgvector 語意搜尋<br/>案例庫 (>= 0.85)"]
        L2["L2: RAG Pipeline<br/>手冊 + Gemini 推理"]
        L3["L3: 人工轉接 / 建工單"]
    end

    subgraph "M5: 知識庫"
        KB["案例庫 + 手冊 chunks<br/>向量索引"]
        SOP["SOP 自動生成<br/>→ 審核 → 發布"]
    end

    subgraph "M9: 派工引擎 (V2.0)"
        DSP["DispatchService<br/>技師匹配 + 工單管理"]
    end

    subgraph "M10: 報價引擎 (V2.0)"
        PRC["PricingService<br/>報價矩陣 + 加價計算"]
    end

    subgraph "M11: 帳務模組 (V2.0)"
        ACC["AccountingService<br/>墊付追蹤 + 月結"]
    end

    U --> WH
    WH --> CM
    CM --> PC
    PC --> FLEX
    FLEX -->|消費者確認| L1
    L1 -->|命中| U
    L1 -->|未命中| L2
    L2 -->|生成回覆| U
    L2 -->|無結果| L3
    L1 -.->|成功案例| SOP
    L2 -.->|成功案例| SOP
    SOP -.->|審核發布| KB
    L1 --> KB
    L2 --> KB
    L3 --> DSP
    DSP --> PRC
    DSP -->|完工| ACC

    classDef v1 fill:#E3F2FD,stroke:#1565C0
    classDef v2 fill:#E8F5E9,stroke:#2E7D32
    class WH,CM,PC,FLEX,L1,L2,L3,KB,SOP v1
    class DSP,PRC,ACC v2
```

---

## 7. MVP 範圍與 12 週計畫

### 7.1 MVP 定義（Phase 0-2, W1-W12）

MVP 聚焦於「AI 智能客服 + 知識庫管理」的閉環，不含派工與帳務。

| 週次 | 里程碑 | 交付模組 | 關鍵產出 |
|:-----|:-------|:---------|:---------|
| W1-W2 | Phase 0: 架構設計 | -- | SRS, DB Schema, API Spec, ProblemCard Schema |
| W3-W4 | LINE Bot 基礎 | M1: LINE Bot 接入, M2: 對話管理 | Bot 可對話、多輪 Session、圖片接收 |
| W4-W5 | 問題卡引擎 | M3: ProblemCard 引擎 | NLU 擷取、Flex Message 確認、意圖分類 |
| W5-W7 | 三層解決引擎 | M4: 三層解決引擎 | L1 向量搜尋、L2 RAG Pipeline、L3 人工轉接 |
| W7 | Admin 基礎 | M6: Admin Panel V1.0 (基礎) | 登入、ProblemCard 列表、對話記錄 |
| W8-W9 | 知識庫大規模匯入 | M5: 知識庫管理 | 全品牌手冊向量化、歷史案例匯入 |
| W9-W10 | Prompt 工程優化 | M4 調校 | 準確率 >= 80%（50 題測試） |
| W10-W11 | 自進化知識庫 | M5: SOP 自動生成 | SOP 自動生成 → 審核 → 一鍵發布 |
| W11-W12 | Admin 完整版 | M6: Admin Panel V1.0 (完整) | 儀表板、知識庫管理、SOP 審核 |

### 7.2 V2.0 延伸（Phase 5-8, W18-W31）

| 週次 | 里程碑 | 交付模組 |
|:-----|:-------|:---------|
| W18-W19 | V2.0 需求與設計 | -- |
| W20-W22 | 技師工作台 | M12: 技師 Web App |
| W22-W24 | 派工 + 報價 | M9: 派工引擎, M10: 報價引擎 |
| W25-W27 | 帳務系統 | M11: 帳務模組 |
| W27-W28 | Admin V2.0 | M13: Admin Panel V2.0 |
| W28-W31 | 整合測試 + UAT + 上線 | 全模組 |

---

> **文件結尾**
> 本文件定義了電子鎖智能客服與派工平台的模組分解、依賴關係、資料庫設計與開發計畫，作為系統開發的架構參考。
