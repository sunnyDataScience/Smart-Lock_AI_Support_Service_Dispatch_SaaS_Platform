# 專案結構指南 - 電子鎖智能客服與派工平台

**文件版本:** v3.0
**最後更新:** 2026-04-04
**主要作者:** 技術負責人
**狀態:** 活躍 (Active)

---

## 目錄

- [1. 指南目的](#1-指南目的)
- [2. 核心設計原則](#2-核心設計原則)
- [3. 頂層目錄結構](#3-頂層目錄結構)
- [4. Agent 目錄詳解 (agent/)](#4-agent-目錄詳解-agent)
  - [4.1 graph/ -- LangGraph Workflow Engine](#41-graph----langgraph-workflow-engine)
  - [4.2 agents/ -- Multi-Agent System](#42-agents----multi-agent-system)
  - [4.3 harness/ -- 8-Layer Agent Governance Framework](#43-harness----8-layer-agent-governance-framework)
  - [4.4 tools/ -- Retriever & Action Tools](#44-tools----retriever--action-tools)
  - [4.5 core/ -- System Foundations](#45-core----system-foundations)
  - [4.6 llms/ + embeddings/ -- AI Providers](#46-llms--embeddings----ai-providers)
  - [4.7 memory/ + profiles/ + storage/ -- Persistence](#47-memory--profiles--storage----persistence)
  - [4.8 data/ -- ETL Knowledge Base Pipeline](#48-data----etl-knowledge-base-pipeline)
  - [4.9 services/ -- V2.0 Business Logic Services](#49-services----v20-business-logic-services)
  - [4.10 scripts/ -- Admin CLI Utilities](#410-scripts----admin-cli-utilities)
- [5. 前端目錄詳解 (frontend/) - V2.0](#5-前端目錄詳解-frontend---v20)
- [6. Docker 與部署結構](#6-docker-與部署結構)
  - [6.1 docker-compose.yml 服務定義](#61-docker-composeyml-服務定義)
  - [6.2 .github/workflows/](#62-githubworkflows)
- [7. 設定檔與知識資產](#7-設定檔與知識資產)
- [8. 檔案命名約定](#8-檔案命名約定)
- [9. 演進原則](#9-演進原則)

---

## 1. 指南目的

本指南為「電子鎖智能客服與派工 SaaS 平台」提供標準化、可擴展且易於理解的目錄與檔案結構規範。具體目標：

- **新人快速上手：** 任何新加入的開發者閱讀本文件後，應能在 30 分鐘內定位任何模組的程式碼位置。
- **一致性保障：** 團隊成員在新增功能或模組時，遵循統一的組織方式，避免結構混亂。
- **關注點分離：** 透過 LangGraph 節點 + 模組化子目錄，確保 graph 流程、agent 邏輯、工具實作、持久化各自獨立。
- **版本演進可控：** V1.0（LangGraph Multi-Agent LINE Bot）與 V2.0（16 個業務服務模組 + 前端管理台）的目錄結構能平滑過渡，無需大幅重構。

---

## 2. 核心設計原則

### 2.1 按領域/功能組織 (Organize by Domain/Feature)

相關的業務功能（對話管理、問題卡、知識庫、派工等）應集中在同一目錄下，而非按技術類型（controllers、models、services）分散。這確保修改某個業務功能時，變更範圍侷限在單一目錄內。

```
# 正確 - 按領域組織
agent/services/dispatch/engine.py
agent/services/dispatch/models.py
agent/services/pricing/engine.py

# 錯誤 - 按類型組織
models/dispatch.py
models/pricing.py
controllers/dispatch.py
controllers/pricing.py
```

### 2.2 Clean Architecture 分層

每個業務領域橫跨三層，依賴方向由外向內：

```
Infrastructure (外層) --> Application (中層) --> Domain (內層)
```

- **Domain Layer：** 純業務邏輯，零外部依賴。包含 entities、value objects、domain events。
- **Application Layer：** 編排業務流程。包含 use cases、DTOs、validators。依賴 Domain Layer。
- **Infrastructure Layer：** 與外部世界交互。包含 web routers、repositories、external API clients。依賴 Application Layer。

### 2.3 設定外部化 (Configuration Externalization)

所有環境相關設定（資料庫連線、API Key、LINE Channel Secret 等）透過環境變數或 `config.toml` 載入，絕不寫死在程式碼中。

### 2.4 根目錄簡潔 (Clean Root Directory)

專案根目錄只放專案級別的設定檔（`README.md`、`.gitignore`、`docker-compose.yml` 等），核心原始碼位於 `agent/`（後端）和 `frontend/`（前端）子目錄中。

### 2.5 可預測性 (Predictability)

看到功能名稱就能推斷出檔案位置。例如：知道有個「問題卡」功能，就能預測以下路徑存在：

- `agent/harness/task/problem_card.py` -- ProblemCard dataclass
- `agent/harness/task/decomposer.py` -- task_decompose() 節點
- `agent/harness/task/prompts/decompose_task.md` -- LLM prompt
- `agent/config.toml [harness.task]` -- 設定開關

---

## 3. 頂層目錄結構

```plaintext
Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/
├── agent/                    # AI Agent Application Core
│   ├── agents/prompts/       # 14 agent prompt templates
│   ├── core/                 # System foundations (config, constants, debounce, line_bot)
│   ├── embeddings/           # Embedding providers (ollama, vertexai)
│   ├── graph/                # LangGraph state machine (state, builder, nodes)
│   ├── harness/              # 8-Layer Agent Governance Framework
│   │   ├── context/          # L2: Context Assembly + Token Budget
│   │   ├── entropy/          # L8: SOP Generation + Anomaly Detection
│   │   ├── feedback/         # L5: Response Verification
│   │   ├── governance/       # L3: Tool Registry + Risk Levels
│   │   ├── observability/    # L7: Tracing + Metrics
│   │   ├── safety/           # L6: Safety Gate (PII, dangerous keywords, sentiment)
│   │   └── task/             # L1: Task Decomposition + Diagnostic Intelligence
│   │       ├── knowledge/    # Knowledge assets (SOPs, fault_trees, failure_modes, OCAP)
│   │       ├── prompts/      # Diagnostic reasoning prompts
│   │       └── taxonomy/     # Classification taxonomies
│   ├── llms/                 # LLM providers (ollama, gemini, vertexai)
│   ├── memory/               # Chat history persistence (postgres, sqlite)
│   ├── profiles/             # User profile management
│   ├── scripts/              # Admin tools (seed_db, debug, view_logs)
│   ├── services/             # V2.0 Business Logic Services (16 modules)
│   │   ├── audit/            # Structured audit logging (7 event types)
│   │   ├── auth/             # Dynamic RBAC (7 roles)
│   │   ├── brand/            # Brand OEM data upload API
│   │   ├── complaint/        # CRM complaint lifecycle
│   │   ├── completion/       # Completion evidence chain
│   │   ├── consent/          # Appearance change + e-signature
│   │   ├── dispatch/         # Technician matching algorithm
│   │   ├── dispute/          # Dispute evidence package
│   │   ├── export/           # Data export (CSV/JSON/PDF)
│   │   ├── finance/          # Refund approval + dual-sign
│   │   ├── inventory/        # Material/stock management
│   │   ├── messaging/        # Inter-agent protocol + realtime chat
│   │   ├── pricing/          # Quote engine + modifiers
│   │   ├── technician/       # Multi-dimensional rating
│   │   ├── warranty/         # Warranty claims + disputes
│   │   └── work_order/       # Exception handling (5 flows)
│   ├── storage/              # Audit log storage (postgres, sqlite)
│   ├── tests/                # Unit/integration/E2E tests
│   ├── tools/                # RAG tools + transfer_human + handoff/handback
│   ├── app.py                # LINE Bot webhook entry
│   ├── config.toml           # Master configuration (14 sections)
│   └── main.py               # CLI test mode
│
├── data/                     # Data Pipeline & Storage
│   ├── pipeline/             # ETL stages (raw -> bronze -> silver -> gold)
│   │   ├── source_to_raw/    #   Raw data collection
│   │   ├── raw_to_bronze/    #   Text extraction (YouTube, LINE, Website, GDrive)
│   │   ├── bronze_to_silver/ #   LLM content enrichment
│   │   └── silver_to_gold/   #   Vectorization -> pgvector write
│   ├── storage/              # Data lake (raw/bronze/silver layers, ~228 JSON files)
│   ├── database/             # pgvector startup config
│   ├── embeddings/           # Embedding providers (ETL)
│   ├── llms/                 # LLM providers (ETL)
│   ├── config.toml           # ETL pipeline config
│   └── requirements.txt      # Data pipeline dependencies
│
├── docs/                     # Project Documentation
│   ├── adrs/                 # 6 Architecture Decision Records
│   ├── agent-harness-refactor/ # Diagnostic intelligence + optimization strategy
│   ├── Locksmith_Preparation_Checklist/ # 20 domain expertise documents
│   ├── project-docs/         # Core project documents (this directory)
│   ├── system_design/        # System design artifacts
│   │   ├── diagrams/         # 10 Mermaid architecture diagrams
│   │   ├── gap/              # GAP analysis reports
│   │   ├── requirements/     # 10 requirement categories
│   │   └── specs/            # 14 V2.0 design specifications
│   └── VibeCoding_Workflow_Templates/ # Development methodology templates
│
├── SQL/                      # Database Schema
│   ├── Schema.sql            # PostgreSQL 16 + pgvector (V1.0 + V2.0 base)
│   └── Schema_v2_extensions.sql # V2.0 extensions (RBAC, inventory, signatures, audit)
│
├── frontend/                 # V2.0 Next.js 14 Admin Panel + Tech App
│
├── .claude/                  # Claude Code config
├── .env                      # Environment variables (not version-controlled)
├── .gitignore                # Git ignore rules
└── README.md                 # Project introduction & quickstart
```

---

## 4. Agent 目錄詳解 (agent/)

V1.0 核心系統採用 LangGraph Multi-Agent 架構。所有 AI 業務邏輯集中於 `agent/` 目錄，以 graph 節點為骨架、agent 子圖為肌肉、tools 為觸手。V2.0 新增 `services/` 目錄承載 16 個業務服務模組。

### 4.1 graph/ -- LangGraph Workflow Engine

Graph 層定義整個對話流程的拓撲結構：節點（node）負責處理邏輯，邊（edge）負責條件路由。

```plaintext
agent/graph/
├── state.py                            # GraphState TypedDict (14 fields)
├── builder.py                          # StateGraph assembly, node wiring, edge routing
└── nodes.py                            # 7 workflow nodes
```

**`state.py` -- GraphState TypedDict（14 欄位）**

| 類別 | 欄位 | Reducer | 說明 |
|------|------|---------|------|
| Core | `messages` | `add_messages` | Agent 對話歷史 |
| Core | `question` | `_keep_last` | 原始使用者輸入 |
| Core | `user_profile` | `_keep_last` | 使用者輪廓 Markdown |
| Core | `answer` | `_keep_last` | 最終回覆文字 |
| Core | `history` | `operator.add` | 路徑追蹤（除錯用） |
| Core | `summary` | `_keep_last` | 對話摘要（記憶管理） |
| Core | `next_agents` | `_keep_last` | 多 agent 派發清單 |
| Core | `ui_hints` | `_add_or_reset` | UI metadata（平行分支合併） |
| Core | `response_ui` | `_keep_last` | 最終 LINE Message 物件 |
| Harness | `task` | `_merge_dict` | L1: goal, subtasks, problem_card_id |
| Harness | `context_meta` | `_merge_dict` | L2: freshness_scores, budget_used |
| Harness | `feedback` | `_merge_dict` | L5: verification_status, quality_scores |
| Harness | `safety` | `_merge_dict` | L6: permission_level, flagged_risks |
| Harness | `entropy` | `_merge_dict` | L8: novel_resolution, sop_candidates |

**`builder.py` -- StateGraph 組裝**

- `build_graph()`: 建立 `StateGraph(GraphState)`，串接所有節點與條件邊
- `route_by_intent()`: 根據 `next_agents` 使用 `Send()` 實現 fan-out 平行派發
- Harness 節點以條件邊插入，`is_layer_enabled()` 為 False 時自動跳過

**`nodes.py` -- 7 個工作流節點**

| 節點 | 說明 |
|------|------|
| `pre_process` | 載入 user_profile、將 question 轉為 HumanMessage |
| `manage_memory` | 訊息超過閾值（50 則）時觸發語意摘要壓縮 |
| `router` | LLM 意圖分類，輸出 next_agents 清單 |
| `merge_answers` | Fan-in 合併多 agent 回覆，處理 ui_hints |
| `update_profile` | SCD Type 2 使用者輪廓更新（hard_facts + soft_profile） |
| `post_process` | Markdown 清理 + LINE Flex Message 建構 |
| `rewrite_query` | 查詢改寫（目前 disabled） |

**Graph 流程概覽：**

```
START -> pre_process -> manage_memory -> [harness nodes] -> router
  -> route_by_intent (fan-out) -> [7 agent subgraphs] -> merge_answers
  -> [verify_answer] -> update_profile -> [entropy_check] -> post_process -> END
```

`[方括號]` 節點為 Harness 層，依 `config.toml` 開關決定啟用或 pass-through。

---

### 4.2 agents/ -- Multi-Agent System

每個 Agent 是獨立的 LangGraph 子圖，擁有專屬 system prompt 與工具集。

```plaintext
agent/agents/
├── __init__.py                         # build_agent_executor(), build_all_agents(), load_prompt_template()
└── prompts/                            # 14 個 .md prompt 模板
    ├── router.md                       #   意圖分類 prompt
    ├── summarize_messages.md           #   語意摘要壓縮 prompt
    ├── merge_answers.md                #   多 agent 合併 prompt
    ├── update_profile.md               #   使用者輪廓更新 prompt
    ├── transfer_human_form.md          #   轉接真人表單 prompt
    ├── rewrite_query.md                #   查詢改寫 prompt (disabled)
    ├── hardware_technician.md          #   硬體維修技師
    ├── sales_representative.md         #   報價與客服專員
    ├── store_assistant.md              #   門市與規格助理
    ├── app_specialist.md               #   APP 設定專家
    ├── manual_librarian.md             #   說明書管理員
    ├── web_researcher.md               #   網路搜尋助手
    ├── receptionist.md                 #   前台接待專員
    └── order_clerk.md                  #   訂單查詢專員 (未啟用)
```

**Agent 子圖模式：** `START -> agent_llm -> [has tool_calls?] -> tools -> agent_llm -> ... -> END`

每個 agent 的 `agent_llm` 節點綁定 system prompt + 可用工具，`ToolNode` 自動處理工具呼叫迴圈。

**7 個啟用中的 Agent：**

| Agent | Label | Tools | 知識庫 |
|-------|-------|-------|--------|
| `hardware_technician` | 硬體維修技師 | db_video, transfer_to_human | 核心技術與維修知識 |
| `sales_representative` | 報價與客服專員 | db_line_chat, transfer_to_human | 客服實務與報價 |
| `store_assistant` | 門市與規格助理 | db_website, transfer_to_human | 營業資訊與產品規格 |
| `app_specialist` | APP 設定專家 | db_youtube, transfer_to_human | APP 操作教學影片 |
| `manual_librarian` | 說明書管理員 | db_manuals, transfer_to_human | PDF 說明書下載 |
| `web_researcher` | 網路搜尋助手 | db_web_search, transfer_to_human | DuckDuckGo 即時搜尋 |
| `receptionist` | 前台接待專員 | transfer_to_human | 無知識庫（一般對話） |

---

### 4.3 harness/ -- 8-Layer Agent Governance Framework

Harness 是 Agent 系統的運行時治理基礎設施。8 層架構中，各層的 V1.0 啟用狀態與成本特性如下：

```plaintext
agent/harness/
├── __init__.py                         # is_harness_enabled(), is_layer_enabled()
│
├── task/                               # L1: Task Decomposition + Diagnostic Intelligence
│   ├── __init__.py
│   ├── decomposer.py                  #   task_decompose() — Software 3.0 diagnostic reasoning
│   ├── problem_card.py                #   ProblemCard dataclass + CRUD
│   ├── knowledge_loader.py            #   Knowledge asset loader (SOPs, fault trees, OCAP)
│   ├── prompts/                       #   Diagnostic reasoning prompt templates
│   │   ├── decompose_task.md          #     Task decomposition prompt
│   │   └── diagnostic_reasoning.md    #     Diagnostic reasoning chain prompt
│   ├── taxonomy/                      #   Classification taxonomies
│   │   ├── components.toml            #     Hardware component taxonomy
│   │   └── symptoms.toml              #     Symptom classification taxonomy
│   └── knowledge/                     #   Structured knowledge assets
│       ├── README.md                  #     Knowledge asset documentation
│       ├── sop/                       #     Standard Operating Procedures
│       │   ├── SOP-CS-001.json        #       Customer service SOP
│       │   ├── SOP-DISPATCH-001.json  #       Dispatch SOP
│       │   ├── SOP-EMERGENCY-001.json #       Emergency SOP
│       │   └── SOP-HW-001.json       #       Hardware troubleshooting SOP
│       ├── fault_trees/               #     Fault tree decision models
│       │   ├── FT-HW-001.json        #       Fault tree: hardware category 1
│       │   ├── FT-HW-002.json        #       Fault tree: hardware category 2
│       │   ├── FT-HW-003.json        #       Fault tree: hardware category 3
│       │   ├── FT-HW-004.json        #       Fault tree: hardware category 4
│       │   └── FT-HW-005.json        #       Fault tree: hardware category 5
│       ├── failure_modes/             #     Failure mode registry
│       │   └── failure_mode_registry.json #   Structured failure mode definitions
│       ├── failures/                  #     Failure taxonomy
│       │   └── failure_taxonomy.json  #       Hierarchical failure classification
│       └── ocap_rules.json           #     OCAP (Occurrence, Cause, Action, Prevention) rules
│
├── context/                            # L2: Context Assembly + Token Budget
│   ├── assembler.py                   #   context_assemble() — context selection
│   ├── budget.py                      #   Token budget calculation
│   └── freshness.py                   #   Source freshness scoring
│
├── governance/                         # L3: Tool Governance
│   ├── registry.py                    #   ToolRegistry (risk levels)
│   └── validator.py                   #   Parameter schema validation
│
├── feedback/                           # L5: Feedback & Verification
│   └── verifier.py                    #   verify_answer() — quality assessment + retry
│
├── safety/                             # L6: Safety & Control
│   └── gate.py                        #   safety_gate() — PII detection, dangerous keywords, sentiment
│
├── observability/                      # L7: Observability
│   ├── tracer.py                      #   @traced decorator
│   └── metrics.py                     #   SessionMetrics + execution report
│
└── entropy/                            # L8: Entropy Management
    ├── checker.py                     #   entropy_check() — novel case detection
    └── sop_generator.py               #   Auto-generate SOP from novel cases
```

> **注意：** L4 (State & Memory) 由既有 `memory/` + `profiles/` 模組承擔，未在 harness 目錄中重複。
> 完整設計規格請參閱 `docs/agent-harness-refactor/`。

**V1.0 各層啟用狀態：**

| Layer | 名稱 | V1.0 狀態 | 成本特性 | 說明 |
|-------|------|-----------|---------|------|
| L1 | Task Decompose | ON | LLM call | Software 3.0 diagnostic reasoning，結合知識資產進行故障推理 |
| L2 | Context Assembly | OFF (V1.2) | LLM call | 需要 data proof 驗證 context 精選的效益後才啟用 |
| L3 | Governance | ON | lightweight, no LLM | 純 registry 查詢 + schema 驗證，零 LLM 成本 |
| L4 | State & Memory | ON | core | memory/ + profiles/ 承擔，系統核心功能 |
| L5 | Feedback/Verify | OFF (V1.2) | LLM call | 回答驗證會增加 latency，需評估成本效益後啟用 |
| L6 | Safety Gate | ON | regex-based, zero cost | 純正則比對 PII、危險關鍵字、情緒偵測，零延遲 |
| L7 | Observability | ON | decorator, zero latency | `@traced` decorator 注入，不影響 request path |
| L8 | Entropy | ON | async, off request path | 非同步執行，新案例偵測與 SOP 產生不阻塞主流程 |

**啟用判斷規則：** `config.toml [harness]` master switch + 各層獨立 `enabled` flag。`builder.py` 中 `is_layer_enabled()` 為 False 時，該層節點自動 pass-through。

---

### 4.4 tools/ -- Retriever & Action Tools

```plaintext
agent/tools/
├── __init__.py                         # build_tools(), UI_TYPE_MAP
├── base.py                             # Tool base abstraction
├── base_retriever.py                   # RAG retriever shared logic
├── pgvector_store.py                   # pgvector RAG tools (5 knowledge bases)
├── api_store.py                        # REST API query tool
├── web_search.py                       # DuckDuckGo web search
├── chroma_store.py                     # ChromaDB tool (backup)
├── transfer_human.py                   # Transfer to human agent + handoff/handback context
└── line_ui_factory.py                  # LINE Flex Message builder
```

**5 個 pgvector 知識庫：**

| Collection | 內容 | UI 類型 |
|------------|------|---------|
| `kb_video` | 技術維修影片逐字稿 | 文字 |
| `kb_line_chat` | LINE 客服對話紀錄 | 文字 |
| `kb_website` | 官網頁面內容 | 文字 |
| `kb_youtube` | YouTube APP 教學影片 | VIDEO_CARD |
| `kb_gdrive` | PDF 說明書 | DOWNLOAD_CARD |

`line_ui_factory.py` 根據 `ui_hints` 中的 `ui_type` 自動建構 LINE Flex Message（影片卡片、下載卡片等）。

**Handoff/Handback 機制 (GAP #5)：** `transfer_human.py` 實現 AI-to-Human handoff 與 Human-to-AI handback 的上下文傳遞，確保轉接時問題卡、對話摘要、已嘗試方案等資訊完整移交。

---

### 4.5 core/ -- System Foundations

```plaintext
agent/core/
├── config.py                           # TOML config loader (14 exported constants)
├── constants.py                        # Global constant definitions
├── line_bot.py                         # LINE Messaging API integration
├── debounce.py                         # Message buffering (2s wait, 300s TTL)
└── debug_log.py                        # Audit log recording
```

- **`config.py`**：讀取 `config.toml`，匯出 `SYSTEM_CONFIG`、`LLM_CONFIG`、`AGENTS_CONFIG`、`INTENTS_CONFIG`、`MEMORY_CONFIG`、`USER_PROFILE_CONFIG`、`TEMPLATES_CONFIG`、`PROMPTS_CONFIG`、`HARNESS_CONFIG`、`REQUIRED_SLOTS` 等 14 個模組級常數。
- **`line_bot.py`**：封裝 LINE Bot SDK，處理 webhook 簽章驗證、reply/push message、loading animation。
- **`debounce.py`**：使用者連續傳送多則訊息時，等待 2 秒（P0 優化後從 5s 降至 2s）無新訊息後才合併處理，避免重複觸發 graph。

---

### 4.6 llms/ + embeddings/ -- AI Providers

```plaintext
agent/llms/
├── __init__.py                         # get_llm(config) factory
├── vertexai_model.py                   # Google Vertex AI (production)
├── gemini_model.py                     # Google Gemini API (development)
└── ollama_model.py                     # Ollama local inference (offline dev)

agent/embeddings/
├── __init__.py                         # get_embeddings(config) factory
├── vertexai_embed.py                   # Vertex AI text-embedding-004
└── ollama_embed.py                     # Ollama local embedding
```

透過 `config.toml [llm].provider` 切換 LLM 供應商（`"vertexai"` / `"gemini"` / `"ollama"`），程式碼零修改。Embedding 供應商由各 `[[databases]]` 條目的 `embedding_provider` 欄位獨立指定。

---

### 4.7 memory/ + profiles/ + storage/ -- Persistence

```plaintext
agent/memory/
├── __init__.py                         # get_checkpointer() factory
├── postgres_saver.py                   # PostgreSQL checkpointer (LangGraph native)
└── sqlite_saver.py                     # SQLite checkpointer (local dev)

agent/profiles/
├── __init__.py                         # ProfileManager
└── manager.py                          # SCD Type 2: hard_facts (PostgreSQL) + soft_profile (.md)

agent/storage/
├── __init__.py                         # get_storage() factory
├── postgres_impl.py                    # PostgreSQL audit log
└── sqlite_impl.py                      # SQLite audit log (fallback)
```

- **memory/**：LangGraph 原生 checkpointer，負責對話 thread 的 state 持久化。超過 `max_messages_threshold`（50 則）時由 `manage_memory` 節點觸發語意摘要壓縮。
- **profiles/**：使用者輪廓採 SCD Type 2 模式——`hard_facts`（電話、地址、設備型號）存 PostgreSQL JSONB，`soft_profile`（行為偏好）存 Markdown 檔案。
- **storage/**：原始對話紀錄（user + AI）的審計日誌持久化。

---

### 4.8 data/ -- ETL Knowledge Base Pipeline

```plaintext
data/
├── pipeline/
│   ├── source_to_raw/                  # Raw data collection scripts
│   ├── raw_to_bronze/                  # Text extraction (YouTube, LINE, Website, GDrive)
│   ├── bronze_to_silver/               # LLM content enrichment & structuring
│   └── silver_to_gold/                 # Vector embedding -> pgvector write
├── storage/                            # Data lake (~228 JSON files across layers)
│   ├── raw/                            #   Raw layer files
│   ├── bronze/                         #   Bronze layer extracted text
│   └── silver/                         #   Silver layer structured JSON
│       ├── video/                      #     Video transcripts (LLM enriched)
│       ├── website/                    #     Website page content
│       └── youtube/                    #     YouTube tutorial videos
├── database/                           # pgvector startup config
├── embeddings/                         # Embedding providers (ETL)
├── llms/                               # LLM providers (ETL)
├── config.toml                         # ETL pipeline config
└── requirements.txt                    # Data pipeline dependencies
```

採用 **Medallion Architecture**（Raw -> Bronze -> Silver -> Gold）：

| 層級 | 處理內容 | 輸出 |
|------|---------|------|
| **Raw** | 原始檔案收集（PDF、影片 URL、網頁 URL） | 原始檔案 |
| **Bronze** | 文字擷取（YouTube 字幕、LINE 對話匯出、網頁爬蟲、GDrive PDF） | 純文字 |
| **Silver** | LLM 內容增強（摘要、分類、結構化 JSON） | 結構化 JSON |
| **Gold** | 向量嵌入（text-embedding-004）-> pgvector 寫入 | pgvector collections |

---

### 4.9 services/ -- V2.0 Business Logic Services

V2.0 新增 16 個業務服務模組，集中在 `agent/services/` 目錄下。每個模組對應一個或多個 GAP Analysis 識別的功能缺口，在同一 FastAPI 進程內以 bounded context 模式運作，**不拆微服務**。

```plaintext
agent/services/
├── __init__.py
├── audit/                              # Structured audit logging (7 event types)
├── auth/                               # Dynamic RBAC (7 roles)
├── brand/                              # Brand OEM data upload API
├── complaint/                          # CRM complaint lifecycle
├── completion/                         # Completion evidence chain
├── consent/                            # Appearance change + e-signature
├── dispatch/                           # Technician matching algorithm
├── dispute/                            # Dispute evidence package
├── export/                             # Data export (CSV/JSON/PDF)
├── finance/                            # Refund approval + dual-sign
├── inventory/                          # Material/stock management
├── messaging/                          # Inter-agent protocol + realtime chat
├── pricing/                            # Quote engine + modifiers
├── technician/                         # Multi-dimensional rating
├── warranty/                           # Warranty claims + disputes
└── work_order/                         # Exception handling (5 flows)
```

**16 個模組與 GAP 對應關係：**

| 模組 | GAP # | 核心功能 |
|------|-------|---------|
| `complaint/` | GAP #1 | CRM 客訴生命週期管理（建立、追蹤、結案） |
| `work_order/` | GAP #2 | 工單異常處理（5 種流程：取消、改派、延期、追加、爭議） |
| `messaging/` | GAP #3, #7 | Inter-agent 通訊協定 + 即時聊天（WebSocket） |
| `auth/` | GAP #6, #16 | 動態 RBAC（7 角色：admin、dispatcher、technician、customer、brand_manager、finance、auditor） |
| `pricing/` | GAP #9, #23 | 報價引擎（品牌 x 鎖型 x 難度 + 夜間/假日/偏遠加成） |
| `technician/` | GAP #10 | 技師多維度評分（技能、速度、客評、完工率） |
| `finance/` | GAP #11 | 退款審核 + 雙簽制（dispatcher + finance 雙重確認） |
| `warranty/` | GAP #12 | 保固理賠 + 爭議處理流程 |
| `audit/` | GAP #13 | 結構化審計日誌（7 種事件類型：login、action、data_change、approval、export、error、security） |
| `export/` | GAP #14 | 資料匯出（CSV/JSON/PDF 格式，含浮水印與權限控管） |
| `inventory/` | GAP #17 | 材料/庫存管理（技師隨車庫存 + 倉庫庫存） |
| `consent/` | GAP #18, #19 | 外觀變更同意書 + 電子簽名（e-signature） |
| `dispute/` | GAP #20 | 爭議證據包（照片、影片、對話紀錄打包） |
| `brand/` | GAP #21 | 品牌 OEM 資料上傳 API（產品規格、韌體、安裝手冊） |
| `dispatch/` | GAP #24 | 技師匹配演算法（skill x region x rating x availability） |
| `completion/` | GAP #25 | 完工證據鏈（before/after 照片 + 客戶簽收 + GPS） |

**V1 與 V2 整合點**：
- `tools/transfer_human.py` 觸發 L3 escalation -> `services/dispatch/` 建立 WorkOrder（FK -> ProblemCard）
- `harness/task/problem_card.py` 的 ProblemCard 是 `services/work_order/` 和 `services/dispatch/` 的上游資料來源

**模組邊界規則**：
- 各模組**不互相 import**，透過 DB 和 event 解耦
- 所有模組共用 `SQL/Schema_v2_extensions.sql` 定義的資料表
- 模組間通訊走 DB event 或 `services/messaging/` 提供的 inter-agent protocol

---

### 4.10 scripts/ -- Admin CLI Utilities

```plaintext
agent/scripts/
├── test_build.py                       # Verify graph build integrity
├── seed_db.py                          # Initialize / rebuild knowledge base
├── view_logs.py                        # View audit logs
├── view_context.py                     # View conversation context
├── view_facts.py                       # View user hard_facts
├── debug_db.py                         # Database debugging tool
├── clean_data.py                       # Clean temp data
└── mock_api.py                         # Mock API server (testing)
```

---

## 5. 前端目錄詳解 (frontend/)

> **注意**：前端目錄為 V2.0 規劃，使用 Next.js 14+ App Router 架構。

使用 Next.js 14+ App Router 架構，為管理後台與技師工作台提供 Web UI。

主要路由群組：

| 路由群組 | 用途 | 佈局 |
|----------|------|------|
| `(auth)/` | 登入、忘記密碼 | 置中卡片，無側邊欄 |
| `(dashboard)/` | 所有後台管理頁面 | 側邊欄 + 頂部導航 |

頁面與 API 端點的對應關係：

| 前端頁面 | 後端 API |
|----------|----------|
| `/dashboard` | `GET /api/v1/dashboard/stats` |
| `/conversations` | `GET /api/v1/conversations` |
| `/problem-cards` | `GET /api/v1/problem-cards` |
| `/knowledge-base/cases` | `GET /api/v1/knowledge-base/cases` |
| `/knowledge-base/sop-drafts` | `GET /api/v1/sop-drafts` |
| `/work-orders` | `GET /api/v2/work-orders` |
| `/technicians` | `GET /api/v2/technicians` |
| `/accounting/reconciliations` | `GET /api/v2/accounting/reconciliations` |

---

## 6. Docker 與部署結構

> **注意**：Docker 與 CI/CD 設定尚未建立，以下為目標部署架構規劃。

### 6.1 docker-compose.yml 服務定義

```plaintext
docker-compose.yml
│
├── agent                               # FastAPI backend (LangGraph + V2.0 services)
│   ├── build: ./agent
│   ├── ports: 8000:8000
│   ├── depends_on: db, redis
│   ├── env_file: .env
│   └── volumes: ./agent:/app (dev hot reload)
│
├── frontend                            # Next.js frontend
│   ├── build: ./frontend
│   ├── ports: 3000:3000
│   ├── depends_on: agent
│   └── env_file: .env
│
├── db                                  # PostgreSQL 16 + pgvector
│   ├── image: pgvector/pgvector:pg16
│   ├── ports: 5432:5432
│   ├── volumes: pgdata:/var/lib/postgresql/data
│   └── environment:
│       ├── POSTGRES_DB: smart_lock
│       ├── POSTGRES_USER: (from .env)
│       └── POSTGRES_PASSWORD: (from .env)
│
├── redis                               # Redis cache
│   ├── image: redis:7-alpine
│   ├── ports: 6379:6379
│   └── volumes: redisdata:/data
│
└── nginx                               # Nginx reverse proxy
    ├── image: nginx:alpine
    ├── ports: 80:80, 443:443
    ├── depends_on: agent, frontend
    └── volumes: ./nginx/conf.d:/etc/nginx/conf.d
```

**Nginx 路由規則：**

| 路徑 | 上游服務 | 說明 |
|------|---------|------|
| `/api/v1/*` | `agent:8000` | V1.0 REST API |
| `/api/v2/*` | `agent:8000` | V2.0 REST API |
| `/webhook/*` | `agent:8000` | LINE Webhook |
| `/docs`, `/openapi.json` | `agent:8000` | FastAPI auto-generated API docs |
| `/*` | `frontend:3000` | Next.js frontend |

### 6.2 .github/workflows/

```plaintext
.github/workflows/
│
├── ci.yml                              # CI (triggered on push / PR)
│   ├── jobs:
│   │   ├── lint-backend:               #   ruff check + mypy
│   │   ├── test-backend:               #   pytest (with PostgreSQL service container)
│   │   ├── lint-frontend:              #   eslint + tsc --noEmit (V2.0)
│   │   └── test-frontend:              #   jest (V2.0)
│   └── triggers: push, pull_request
│
└── deploy.yml                          # CD (triggered on merge to main)
    ├── jobs:
    │   ├── build-images:               #   docker build + push to registry
    │   ├── run-migrations:             #   alembic upgrade head
    │   └── deploy:                     #   docker-compose up -d (or K8s apply)
    └── triggers: push to main
```

---

## 7. 設定檔與知識資產

### 7.1 config.toml -- 14 區塊系統設定

`agent/config.toml` 是系統唯一的非機密設定檔，納入版本控制。所有可配置行為集中於此。

| # | Section | 關鍵設定 |
|---|---------|---------|
| 1 | `[system]` | `domain`（業務領域描述）、`thread_prefix`、`request_timeout=120`、`sensitive_keywords`（報價/金流觸發詞） |
| 2 | `[debounce]` | `buffer_wait=2s`、`buffer_ttl=300s`、`cleanup_interval=60s` |
| 3 | `[line_bot]` | `loading_animation_time=60`（秒，5 的倍數） |
| 4 | `[templates]` | 系統錯誤訊息、Push fallback 前綴、逾時回覆文字 |
| 5 | `[llm]` | `provider`（vertexai/gemini/ollama）、`model_name`、`temperature`、各供應商連線參數 |
| 6 | `[[databases]]` | 7 個 retriever 定義（`name`、`type`、`collection_name`、`top_k`、`embedding_*`） |
| 7 | `[[agents]]` | 7 個 agent 定義（`name`、`label`、`tools`、`prompt_file`） |
| 8 | `[[intents]]` | 9 個意圖路由規則（`name`、`target`、`description`、`require_slots`） |
| 9 | `[memory]` | `type=postgres`、`max_messages_threshold=50`、`context_retention_pair=20`、`router_context_pairs=3` |
| 10 | `[required_slots]` | `device_model`、`device_brand`（故障排除前必填） |
| 11 | `[user_profile]` | `enabled`、`profile_dir`、`facts_enabled`、`fact_attributes`、`extraction` regex |
| 12 | `[storage]` | `type=postgres`、`postgres_uri_env`（審計日誌後端） |
| 13 | `[prompts]` | 所有 prompt 模板的路徑註冊表（router、summarizer、merger、profile_updater 等） |
| 14 | `[harness]` | Master switch + 7 個 layer 子區塊（task、context、governance、feedback、safety、observability、entropy） |

### 7.2 SQL Schema

| 檔案 | 說明 | 版本控制 |
|------|------|---------|
| `SQL/Schema.sql` | PostgreSQL 16 + pgvector 主 schema（V1.0 核心表 + V2.0 基礎表） | Yes |
| `SQL/Schema_v2_extensions.sql` | V2.0 擴展 DDL（RBAC、inventory、e-signature、audit log 等） | Yes |

### 7.3 Knowledge Assets

`agent/harness/task/knowledge/` 目錄下儲存結構化知識資產，供 L1 Diagnostic Intelligence 使用：

| 路徑 | 內容 | 檔案數 |
|------|------|--------|
| `knowledge/sop/` | 標準作業程序（客服、派工、緊急、硬體） | 4 個 JSON |
| `knowledge/fault_trees/` | 故障樹決策模型（硬體分類） | 5 個 JSON |
| `knowledge/failure_modes/` | 故障模式登記表（failure_mode_registry.json） | 1 個 JSON |
| `knowledge/failures/` | 故障分類法（failure_taxonomy.json） | 1 個 JSON |
| `knowledge/ocap_rules.json` | OCAP 規則（Occurrence, Cause, Action, Prevention） | 1 個 JSON |

這些知識資產由 `knowledge_loader.py` 載入，在 `decomposer.py` 的 diagnostic reasoning 流程中被引用，實現 Software 3.0 的知識驅動故障推理。

### 7.4 V2.0 Design Specifications

`docs/02-design/specs/` 目錄下包含 14 份 V2.0 設計規格文件：

| 規格文件 | 說明 |
|----------|------|
| `audit-log-spec.md` | 審計日誌規格 |
| `b2b-api-spec.md` | B2B API 規格 |
| `brand-data-api-spec.md` | 品牌資料 API 規格 |
| `data-export-spec.md` | 資料匯出規格 |
| `e-signature-spec.md` | 電子簽名規格 |
| `inter-agent-messaging-spec.md` | Inter-agent 通訊規格 |
| `inventory-management-spec.md` | 庫存管理規格 |
| `moat-mapping-matrix.md` | 技術護城河對應矩陣 |
| `rbac-dynamic-spec.md` | 動態 RBAC 規格 |
| `realtime-messaging-spec.md` | 即時通訊規格 |
| `refund-approval-spec.md` | 退款審核規格 |
| `sla-availability-spec.md` | SLA 可用性規格 |
| `vision-processing-spec.md` | 影像處理規格 |
| `warranty-dispute-spec.md` | 保固爭議規格 |

### 7.5 環境變數 (.env)

機密資訊一律透過 `.env` 注入，不納入版本控制。`config.toml` 中以 `*_env` 後綴欄位指定對應的環境變數名稱。

```plaintext
# === LINE Messaging API ===
LINE_CHANNEL_SECRET=your-channel-secret
LINE_CHANNEL_ACCESS_TOKEN=your-access-token

# === Database ===
POSTGRES_URI=postgresql+asyncpg://user:password@db:5432/smart_lock
PG_VECTOR_URI=postgresql+asyncpg://user:password@db:5432/smart_lock

# === Google Vertex AI ===
VERTEX_PROJECT_ID=your-gcp-project-id
VERTEX_LOCATION=us-central1

# === Google Gemini (dev alternative) ===
GEMINI_API_KEY=your-api-key

# === Ollama (local dev) ===
OLLAMA_BASE_URL=http://localhost:11434

# === API Tools ===
ORDER_API_URL=https://api.example.com/v1/status
ORDER_API_TOKEN=your-bearer-token
```

### 7.6 設定分工原則

| 類別 | 存放位置 | 版本控制 |
|------|---------|---------|
| 系統行為 | `agent/config.toml` | Yes |
| 機密金鑰 | `.env` | No |
| Prompt 模板 | `agent/agents/prompts/*.md` | Yes |
| Diagnostic Prompts | `agent/harness/task/prompts/*.md` | Yes |
| Knowledge Assets | `agent/harness/task/knowledge/**/*.json` | Yes |
| Taxonomy | `agent/harness/task/taxonomy/*.toml` | Yes |
| ETL 設定 | `data/config.toml` | Yes |
| DB Schema (V1) | `SQL/Schema.sql` | Yes |
| DB Schema (V2) | `SQL/Schema_v2_extensions.sql` | Yes |
| V2.0 Design Specs | `docs/02-design/specs/*.md` | Yes |

---

## 8. 檔案命名約定

### 8.1 Python（後端）

| 類別 | 約定 | 範例 |
|------|------|------|
| 模組/檔案 | `snake_case.py` | `problem_card.py` |
| 目錄 | `snake_case` | `fault_trees/` |
| 類別 | `PascalCase` | `ProblemCard`, `ToolRegistry` |
| 函式/方法 | `snake_case` | `create_problem_card()` |
| 常數 | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| 測試檔案 | `test_*.py` | `test_decomposer.py` |
| Pydantic DTO | `PascalCase` + 後綴 `DTO` | `ProblemCardCreateDTO` |
| Protocol | `PascalCase` + 後綴 `Repository`/`Service` | `CaseRepository`, `LLMService` |

### 8.2 TypeScript / React（前端）

| 類別 | 約定 | 範例 |
|------|------|------|
| React 元件 | `PascalCase.tsx` | `ProblemCardViewer.tsx` |
| 工具函式/Hook | `camelCase.ts` | `useDebounce.ts`, `format.ts` |
| 目錄 | `kebab-case` | `knowledge-base/`, `work-orders/` |
| API 模組 | `kebab-case.ts` | `problem-cards.ts` |
| 型別定義 | `camelCase.ts` | `entities.ts` |
| 測試檔案 | `*.test.ts` / `*.test.tsx` | `button.test.tsx` |
| CSS 模組 | `camelCase.module.css` | `sidebar.module.css` |
| Next.js 頁面 | `page.tsx`（固定） | `app/dashboard/page.tsx` |

### 8.3 其他檔案

| 類別 | 約定 | 範例 |
|------|------|------|
| Markdown 文件 | `snake_case.md` 或編號前綴 | `08_project_structure_guide.md` |
| Knowledge JSON | `UPPER-KEBAB-NNN.json` | `SOP-HW-001.json`, `FT-HW-003.json` |
| Taxonomy | `snake_case.toml` | `components.toml`, `symptoms.toml` |
| Shell 腳本 | `snake_case.sh` | `setup_dev.sh` |
| Docker 設定 | 官方慣例 | `Dockerfile`, `docker-compose.yml` |
| 環境變數 | `UPPER_SNAKE_CASE` | `DATABASE_URL` |

---

## 9. 模組擴展原則

### 9.1 新增 Service 模組的標準流程

當需要新增一個業務服務模組時：

1. **建立模組目錄**：`agent/services/{module_name}/`
   - `__init__.py`
   - `engine.py` -- 核心業務邏輯
   - `models.py` -- Pydantic/dataclass 資料模型
   - `routes.py` -- FastAPI router（掛載到 `app.py`）

2. **新增設定 section**：`config.toml [{module_name}]`
   - 所有行為參數外部化
   - `enabled = false` 預設，開關可控

3. **建立資料庫 migration**：`SQL/Schema_v2_extensions.sql` 新增 DDL
   - FK 連結到既有實體（如 `work_orders.problem_card_id -> problem_cards.card_id`）

4. **掛載 Router**：`app.py` 新增 `app.include_router(module_router, prefix="/api/v2")`

5. **建立測試**：`agent/tests/` 中新增對應測試

6. **更新文件**：對應 GAP Analysis 項目標記為已實作

### 9.2 新增 Harness Layer 的流程

1. 在 `agent/harness/{layer_name}/` 建立模組
2. `config.toml [harness.{layer_name}]` 新增設定區塊（`enabled = false` 預設）
3. `graph/builder.py` 中以條件邊插入節點
4. `graph/state.py` 中新增對應 state field（如需要）

### 9.3 結構變更原則

- 任何**頂層目錄結構**的變更，必須透過 ADR（Architecture Decision Record）記錄至 `docs/01-define/adrs/`。
- 新增 service 模組遵循上述標準流程，無需 ADR。
- `core/` 中新增共用模組需經過 code review 確認其確實為跨領域共用。
- 保持**可預測性**比追求「完美結構」更重要 -- 一致性是第一優先。

---

## 附錄 A：快速定位指南

| 我想要... | 去哪裡 |
|----------|--------|
| 新增一個 Agent | `config.toml [[agents]]` 新增條目 + `agents/prompts/new_agent.md` 建立 prompt |
| 新增一個意圖 | `config.toml [[intents]]` 新增條目，`target` 指向對應 agent |
| 新增知識庫 | `config.toml [[databases]]` 新增條目 + `data/pipeline/` 建立 ETL 流程 |
| 切換 LLM 供應商 | `config.toml [llm].provider`（vertexai / gemini / ollama） |
| 修改 Graph 流程 | `graph/builder.py`（新增節點 or 修改邊路由） |
| 新增 Harness 層 | `harness/{layer_name}/` 建立模組 + `config.toml [harness.xxx]` 設定 |
| 新增 V2.0 業務模組 | `services/{module_name}/` 建立模組 + `config.toml` + `SQL/Schema_v2_extensions.sql` |
| 新增/修改知識資產 | `harness/task/knowledge/` 下對應子目錄（sop/, fault_trees/, etc.） |
| 查看 GAP 分析 | `docs/_gap-analysis/gap-analysis-report-cn.md` |
| 查看 V2.0 設計規格 | `docs/02-design/specs/` |
| 除錯對話內容 | `scripts/view_logs.py`、`scripts/view_context.py` |
| 修改 LINE 訊息樣式 | `tools/line_ui_factory.py` |
| 更新使用者輪廓邏輯 | `profiles/manager.py` + `agents/prompts/update_profile.md` |
| 新增敏感詞 | `config.toml [system].sensitive_keywords` |
| 查看資料庫 Schema | `SQL/Schema.sql`（V1）、`SQL/Schema_v2_extensions.sql`（V2） |
| 查看使用者 hard_facts | `scripts/view_facts.py` |
| 環境變數說明 | `.env`（機密）、`config.toml`（非機密） |
| 架構決策記錄 | `docs/01-define/adrs/` |

## 附錄 B：依賴方向圖

```plaintext
                    ┌─────────────────────┐
                    │   app.py (入口)      │
                    └──────────┬──────────┘
                               │ 組裝所有元件
                               ▼
┌──────────────────────────────────────────────────────┐
│                 Infrastructure Layer                  │
│                                                      │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌───────┐ │
│  │ Routers │  │ Repos    │  │External │  │ Cache │ │
│  │(FastAPI)│  │(SQLAlchm)│  │(LINE,   │  │(Redis)│ │
│  │         │  │          │  │ Google, │  │       │ │
│  │         │  │          │  │ LangChn)│  │       │ │
│  └────┬────┘  └────┬─────┘  └────┬────┘  └───┬───┘ │
│       │            │             │            │      │
└───────┼────────────┼─────────────┼────────────┼──────┘
        │            │             │            │
        ▼            ▼             ▼            ▼
┌──────────────────────────────────────────────────────┐
│                  Application Layer                    │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │  Use Cases   │  │    DTOs      │  │ Interfaces│  │
│  │  (orchestrate│  │ (data xfer   │  │ (Protocol │  │
│  │   flows)     │  │  objects)    │  │  defs)    │  │
│  └──────┬───────┘  └──────────────┘  └───────────┘  │
│         │                                            │
└─────────┼────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────┐
│                    Domain Layer                       │
│                                                      │
│  ┌──────────┐  ┌───────────────┐  ┌──────────────┐  │
│  │ Entities │  │ Value Objects │  │Domain Events │  │
│  │ (business│  │ (immutable    │  │ (domain      │  │
│  │  models) │  │  values)      │  │  events)     │  │
│  └──────────┘  └───────────────┘  └──────────────┘  │
│                                                      │
│               零外部依賴，純業務邏輯                   │
└──────────────────────────────────────────────────────┘
```

**依賴規則：** 箭頭方向代表依賴方向。外層可以依賴內層，內層絕不依賴外層。Infrastructure 透過 Application 層定義的 Protocol (interfaces) 實作依賴反轉。
