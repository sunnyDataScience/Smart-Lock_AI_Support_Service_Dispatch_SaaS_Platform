# 專案結構指南 - 電子鎖智能客服與派工平台

**文件版本:** v2.0
**最後更新:** 2026-04-01
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
  - [4.3 harness/ -- 8-Layer Harness Framework](#43-harness----8-layer-harness-framework)
  - [4.4 tools/ -- Retriever & Action Tools](#44-tools----retriever--action-tools)
  - [4.5 core/ -- System Foundations](#45-core----system-foundations)
  - [4.6 llms/ + embeddings/ -- AI Providers](#46-llms--embeddings----ai-providers)
  - [4.7 memory/ + profiles/ + storage/ -- Persistence](#47-memory--profiles--storage----persistence)
  - [4.8 data/ -- ETL Knowledge Base Pipeline](#48-data----etl-knowledge-base-pipeline)
- [5. 前端目錄詳解 (frontend/) - V2.0](#5-前端目錄詳解-frontend---v20)
  - [5.1 src/app/ - Next.js App Router](#51-srcapp---nextjs-app-router)
  - [5.2 src/components/ - 共用元件](#52-srccomponents---共用元件)
  - [5.3 src/lib/ - 工具函式與 API 客戶端](#53-srclib---工具函式與-api-客戶端)
- [6. Docker 與部署結構](#6-docker-與部署結構)
  - [6.1 docker-compose.yml 服務定義](#61-docker-composeyml-服務定義)
  - [6.2 .github/workflows/](#62-githubworkflows)
- [7. 設定檔結構](#7-設定檔結構)
- [8. 檔案命名約定](#8-檔案命名約定)
- [9. 演進原則](#9-演進原則)

---

## 1. 指南目的

本指南為「電子鎖智能客服與派工 SaaS 平台」提供標準化、可擴展且易於理解的目錄與檔案結構規範。具體目標：

- **新人快速上手：** 任何新加入的開發者閱讀本文件後，應能在 30 分鐘內定位任何模組的程式碼位置。
- **一致性保障：** 團隊成員在新增功能或模組時，遵循統一的組織方式，避免結構混亂。
- **關注點分離：** 透過 LangGraph 節點 + 模組化子目錄，確保 graph 流程、agent 邏輯、工具實作、持久化各自獨立。
- **版本演進可控：** V1.0（LangGraph Multi-Agent LINE Bot）與 V2.0（技師工作台 + 派工/報價/對帳）的目錄結構能平滑過渡，無需大幅重構。

---

## 2. 核心設計原則

### 2.1 按領域/功能組織 (Organize by Domain/Feature)

相關的業務功能（對話管理、問題卡、知識庫、派工等）應集中在同一目錄下，而非按技術類型（controllers、models、services）分散。這確保修改某個業務功能時，變更範圍侷限在單一目錄內。

```
# 正確 - 按領域組織
domains/conversation/entities.py
domains/conversation/events.py
domains/problem_card/entities.py

# 錯誤 - 按類型組織
models/conversation.py
models/problem_card.py
controllers/conversation.py
controllers/problem_card.py
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

所有環境相關設定（資料庫連線、API Key、LINE Channel Secret 等）透過環境變數或 `configs/` 目錄下的設定檔載入，絕不寫死在程式碼中。

### 2.4 根目錄簡潔 (Clean Root Directory)

專案根目錄只放專案級別的設定檔（`README.md`、`.gitignore`、`docker-compose.yml` 等），核心原始碼位於 `agent/`（後端）和 `frontend/`（前端）子目錄中。

### 2.5 可預測性 (Predictability)

看到功能名稱就能推斷出檔案位置。例如：知道有個「問題卡」功能，就能預測以下路徑存在：

- `agent/harness/task/problem_card.py` — ProblemCard dataclass
- `agent/harness/task/decomposer.py` — task_decompose() 節點
- `agent/harness/task/prompts/decompose_task.md` — LLM prompt
- `agent/config.toml [harness.task]` — 設定開關

---

## 3. 頂層目錄結構

```plaintext
Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/
│
├── agent/                              # LangGraph Multi-Agent System (AI 客服核心)
│   ├── app.py                          #   FastAPI entry (LINE webhook + V2 routers)
│   ├── main.py                         #   CLI testing harness
│   ├── config.toml                     #   系統設定檔
│   ├── requirements.txt                #   Python dependencies
│   ├── graph/                          #   LangGraph workflow 定義
│   ├── agents/                         #   7 Agent 子圖 + 14 prompt templates
│   ├── harness/                        #   8-Layer Harness Framework
│   ├── tools/                          #   7 retriever tools
│   ├── llms/                           #   LLM providers
│   ├── embeddings/                     #   Embedding providers
│   ├── memory/                         #   Checkpointer (PostgreSQL / SQLite)
│   ├── profiles/                       #   User profile (SCD Type 2)
│   ├── core/                           #   Config, LINE Bot, Debounce, Debug Log
│   ├── storage/                        #   Audit log backends
│   ├── dispatch/                       #   智慧派工引擎 (技師匹配 / 工單生命週期) [尚未建立 — Phase 6 建立]
│   ├── pricing/                        #   報價引擎 (品牌 × 鎖型 × 難度) [尚未建立 — Phase 6 建立]
│   ├── accounting/                     #   帳務模組 (對帳 / 結算 / 憑證) [尚未建立 — Phase 7 建立]
│   ├── docs/                           #   Agent 相關文件 (手冊、進度報告)
│   └── scripts/                        #   Admin CLI utilities
│
├── frontend/                           # Next.js 14+ 前端 (Admin Panel + 技師工作台) [尚未建立 — Phase 5 建立]
│   ├── src/
│   │   ├── app/                        #   Next.js App Router (頁面路由)
│   │   │   ├── (auth)/                 #     登入 / 忘記密碼
│   │   │   └── (dashboard)/            #     後台管理 (儀表板 / 對話 / 知識庫 / 派工 / 帳務)
│   │   ├── components/                 #   共用元件 (ui / layout / features / providers)
│   │   ├── lib/                        #   API 客戶端 / Hooks / Utils / Types
│   │   └── __tests__/                  #   前端測試 (Jest + RTL)
│   ├── package.json
│   ├── tailwind.config.ts
│   └── tsconfig.json
│
├── data/                               # ETL Pipeline (知識庫資料處理)
│   ├── pipeline/                       #   Medallion Architecture 分層處理
│   │   ├── source_to_raw/              #     原始資料收集
│   │   ├── raw_to_bronze/              #     文字擷取 (YouTube, LINE, Website, GDrive)
│   │   ├── bronze_to_silver/           #     LLM 內容增強
│   │   └── silver_to_gold/             #     向量化 → pgvector 寫入
│   ├── storage/                        #   Silver/Gold 層資料檔案
│   ├── database/                       #   pgvector 啟動設定
│   ├── embeddings/                     #   Embedding providers
│   ├── llms/                           #   LLM providers (ETL 用)
│   ├── docs/                           #   ETL Pipeline 文件與報告
│   ├── config.toml                     #   ETL pipeline 設定
│   └── requirements.txt                #   Data pipeline dependencies
│
├── SQL/                                # Database DDL
│   └── Schema.sql                      #   PostgreSQL schema
│
├── nginx/                              # Nginx 反向代理設定 [尚未建立 — Phase 4 建立]
│   └── conf.d/                         #   路由規則 (/api→agent, /webhook→agent, /*→frontend)
│
├── docs/                               # 專案文件
│   ├── project-docs/                   #   核心專案文件 (本目錄)
│   ├── system_design/                  #   系統設計 (PRD, SOW, diagrams)
│   ├── agent-harness-refactor/         #   Agent Harness 重構規格
│   └── adrs/                           #   Architecture Decision Records
│
├── .github/workflows/                  # CI/CD Pipeline [尚未建立 — Phase 1 建立]
│   ├── ci.yml                          #   lint + test (backend & frontend)
│   └── deploy.yml                      #   build → push → migrate → deploy
│
├── docker-compose.yml                  # 容器編排 (agent + frontend + db + redis + nginx) [尚未建立 — Phase 1 建立]
├── .claude/                            #   Claude Code 設定
├── .env                                #   環境變數 (不納入版本控制)
├── .gitignore                          #   Git 忽略規則
└── README.md                           #   專案介紹與快速入門
```

---

## 4. Agent 目錄詳解 (agent/)

V1.0 核心系統採用 LangGraph Multi-Agent 架構。所有業務邏輯集中於 `agent/` 目錄，以 graph 節點為骨架、agent 子圖為肌肉、tools 為觸手。

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
START → pre_process → manage_memory → [harness nodes] → router
  → route_by_intent (fan-out) → [7 agent subgraphs] → merge_answers
  → [verify_answer] → update_profile → [entropy_check] → post_process → END
```

`[方括號]` 節點為 Harness 層，Phase 0 為 pass-through skeleton。

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

**Agent 子圖模式：** `START → agent_llm → [has tool_calls?] → tools → agent_llm → ... → END`

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

### 4.3 harness/ -- 8-Layer Harness Framework

Harness 是 Agent 系統的運行時基礎設施層。所有模組預設 disabled（`config.toml [harness] enabled = false`），Phase 0 為 skeleton pass-through。

```plaintext
agent/harness/
├── __init__.py                         # is_harness_enabled(), is_layer_enabled()
├── task/                               # L1: Task Representation
│   ├── decomposer.py                  #   task_decompose() - 問題分解
│   └── problem_card.py                #   ProblemCard dataclass + CRUD
├── context/                            # L2: Context Assembly
│   ├── assembler.py                   #   context_assemble() - 上下文精選
│   ├── budget.py                      #   Token budget 計算
│   └── freshness.py                   #   來源新鮮度評分
├── governance/                         # L3: Tool Governance
│   ├── registry.py                    #   ToolRegistry (risk levels)
│   └── validator.py                   #   參數 schema 驗證
├── feedback/                           # L5: Feedback & Verification
│   └── verifier.py                    #   verify_answer() - 品質評估 + retry
├── safety/                             # L6: Safety & Control
│   └── gate.py                        #   safety_gate() - 危險指令攔截
├── observability/                      # L7: Observability
│   ├── tracer.py                      #   @traced decorator
│   └── metrics.py                     #   SessionMetrics + 執行報告
└── entropy/                            # L8: Entropy Management
    ├── checker.py                     #   entropy_check() - 新案例偵測
    └── sop_generator.py               #   從新案例自動產生 SOP
```

> **注意：** L4 (State & Memory) 由既有 `memory/` + `profiles/` 模組承擔，未在 harness 目錄中重複。
> 完整設計規格請參閱 `docs/agent-harness-refactor/`。

---

### 4.4 tools/ -- Retriever & Action Tools

```plaintext
agent/tools/
├── __init__.py                         # build_tools(), UI_TYPE_MAP
├── base.py                             # 工具基礎抽象
├── base_retriever.py                   # RAG retriever 共用邏輯
├── pgvector_store.py                   # pgvector RAG 工具 (5 個知識庫)
├── api_store.py                        # REST API 查詢工具
├── web_search.py                       # DuckDuckGo 網路搜尋
├── chroma_store.py                     # ChromaDB 工具 (備用)
├── transfer_human.py                   # 轉接真人客服
└── line_ui_factory.py                  # LINE Flex Message 建構器
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

---

### 4.5 core/ -- System Foundations

```plaintext
agent/core/
├── config.py                           # TOML 設定載入器 (14 個匯出常數)
├── constants.py                        # 全域常數定義
├── line_bot.py                         # LINE Messaging API 整合
├── debounce.py                         # 訊息緩衝 (5s wait, 300s TTL)
└── debug_log.py                        # 審計日誌記錄
```

- **`config.py`**：讀取 `config.toml`，匯出 `SYSTEM_CONFIG`、`LLM_CONFIG`、`AGENTS_CONFIG`、`INTENTS_CONFIG`、`MEMORY_CONFIG`、`USER_PROFILE_CONFIG`、`TEMPLATES_CONFIG`、`PROMPTS_CONFIG`、`HARNESS_CONFIG`、`REQUIRED_SLOTS` 等 14 個模組級常數。
- **`line_bot.py`**：封裝 LINE Bot SDK，處理 webhook 簽章驗證、reply/push message、loading animation。
- **`debounce.py`**：使用者連續傳送多則訊息時，等待 5 秒無新訊息後才合併處理，避免重複觸發 graph。

---

### 4.6 llms/ + embeddings/ -- AI Providers

```plaintext
agent/llms/
├── __init__.py                         # get_llm(config) 工廠函式
├── vertexai_model.py                   # Google Vertex AI (生產環境)
├── gemini_model.py                     # Google Gemini API (開發環境)
└── ollama_model.py                     # Ollama 本地推理 (離線開發)

agent/embeddings/
├── __init__.py                         # get_embeddings(config) 工廠函式
├── vertexai_embed.py                   # Vertex AI text-embedding-004
└── ollama_embed.py                     # Ollama 本地嵌入
```

透過 `config.toml [llm].provider` 切換 LLM 供應商（`"vertexai"` / `"gemini"` / `"ollama"`），程式碼零修改。Embedding 供應商由各 `[[databases]]` 條目的 `embedding_provider` 欄位獨立指定。

---

### 4.7 memory/ + profiles/ + storage/ -- Persistence

```plaintext
agent/memory/
├── __init__.py                         # get_checkpointer() 工廠函式
├── postgres_saver.py                   # PostgreSQL checkpointer (LangGraph 原生)
└── sqlite_saver.py                     # SQLite checkpointer (本地開發)

agent/profiles/
├── __init__.py                         # ProfileManager
└── manager.py                          # SCD Type 2: hard_facts (PostgreSQL) + soft_profile (.md)

agent/storage/
├── __init__.py                         # get_storage() 工廠函式
├── postgres_impl.py                    # PostgreSQL 審計日誌
└── sqlite_impl.py                      # SQLite 審計日誌 (回退)
```

- **memory/**：LangGraph 原生 checkpointer，負責對話 thread 的 state 持久化。超過 `max_messages_threshold`（50 則）時由 `manage_memory` 節點觸發語意摘要壓縮。
- **profiles/**：使用者輪廓採 SCD Type 2 模式——`hard_facts`（電話、地址、設備型號）存 PostgreSQL JSONB，`soft_profile`（行為偏好）存 Markdown 檔案。
- **storage/**：原始對話紀錄（user + AI）的審計日誌持久化。

---

### 4.8 data/ -- ETL Knowledge Base Pipeline

```plaintext
data/
├── pipeline/
│   ├── source_to_raw/                  # Raw 資料收集腳本
│   ├── raw_to_bronze/                  # 文字擷取 (YouTube, LINE, Website, GDrive)
│   ├── bronze_to_silver/               # LLM 內容增強與結構化
│   └── silver_to_gold/                 # 向量嵌入 → pgvector 寫入
├── storage/
│   ├── silver/                         # Silver 層 JSON 檔案
│   │   ├── video/                      #   影片逐字稿 (LLM enriched)
│   │   ├── website/                    #   官網頁面內容
│   │   └── youtube/                    #   YouTube 教學影片
│   └── gold/                           #   Gold 層向量化資料
├── config.toml                         # ETL pipeline 設定
└── requirements.txt                    # Data pipeline dependencies
```

採用 **Medallion Architecture**（Raw → Bronze → Silver → Gold）：

| 層級 | 處理內容 | 輸出 |
|------|---------|------|
| **Raw** | 原始檔案收集（PDF、影片 URL、網頁 URL） | 原始檔案 |
| **Bronze** | 文字擷取（YouTube 字幕、LINE 對話匯出、網頁爬蟲、GDrive PDF） | 純文字 |
| **Silver** | LLM 內容增強（摘要、分類、結構化 JSON） | 結構化 JSON |
| **Gold** | 向量嵌入（text-embedding-004）→ pgvector 寫入 | pgvector collections |

---

### 4.9 scripts/ -- Admin CLI Utilities

```plaintext
agent/scripts/
├── test_build.py                       # 驗證 graph 建構完整性
├── seed_db.py                          # 初始化 / 重建知識庫
├── view_logs.py                        # 查看審計日誌
├── view_context.py                     # 查看對話上下文
├── view_facts.py                       # 查看使用者 hard_facts
├── debug_db.py                         # 資料庫除錯工具
├── clean_data.py                       # 清理暫存資料
└── mock_api.py                         # Mock API server (測試用)
```

### 4.10 V2.0 模組規劃 (dispatch/ pricing/ accounting/)

V2.0 在 `agent/` 同一 FastAPI 進程內新增 3 個 bounded context，**不拆微服務**。

```plaintext
agent/
├── graph/                       # V1.0 (不動)
├── agents/                      # V1.0 (不動)
├── harness/                     # V1.0 (不動)
│
├── dispatch/                    # V2.0 NEW ── 派工引擎
│   ├── __init__.py
│   ├── engine.py                #   TechnicianMatcher: skill × region × rating 匹配
│   ├── models.py                #   WorkOrder, Assignment, TechnicianProfile dataclass
│   ├── notifications.py         #   LINE Push + WebSocket 通知
│   └── routes.py                #   FastAPI router: /api/v2/work-orders/*
│
├── pricing/                     # V2.0 NEW ── 計價引擎
│   ├── __init__.py
│   ├── engine.py                #   PriceRule 查詢 + 加成計算 (night/holiday/remote)
│   ├── models.py                #   PriceRule, Quotation dataclass
│   └── routes.py                #   FastAPI router: /api/v2/pricing/*
│
├── accounting/                  # V2.0 NEW ── 帳務模組
│   ├── __init__.py
│   ├── invoicing.py             #   Invoice CRUD
│   ├── settlement.py            #   月結對帳 + Reconciliation 批次
│   ├── models.py                #   Invoice, Reconciliation, Settlement dataclass
│   └── routes.py                #   FastAPI router: /api/v2/accounting/*
│
├── app.py                       # FastAPI: V1 webhook + V2 routers mount
└── config.toml                  # 新增 [dispatch] [pricing] [accounting] sections
```

**V1↔V2 整合點**：`tools/transfer_human.py` 觸發 L3 escalation → `dispatch/engine.py` 建立 WorkOrder（FK → ProblemCard）。

**模組邊界規則**：
- dispatch/ 可讀取 `harness/task/problem_card.py` 的 ProblemCard
- pricing/ 只讀取 `config.toml` 的 PriceRule 設定
- accounting/ 只讀取 WorkOrder + Invoice，不碰 LangGraph state
- 三個模組**不互相 import**，透過 DB 和 event 解耦

---

## 5. 前端目錄詳解 (frontend/)

> **注意**：前端目錄尚未建立，以下為 Phase 5 的目標結構規劃。

使用 Next.js 14+ App Router 架構，為管理後台與技師工作台提供 Web UI。

```plaintext
frontend/src/
│
├── app/                                # ── Next.js App Router ──
│   ├── layout.tsx                      # 根佈局（全域 providers, 字型, metadata）
│   ├── page.tsx                        # 首頁（重導向至 /dashboard）
│   ├── globals.css                     # 全域樣式（Tailwind base）
│   │
│   ├── (auth)/                         # 認證相關頁面（不含側邊欄佈局）
│   │   ├── layout.tsx                  #   認證頁面專用佈局（置中卡片）
│   │   ├── login/
│   │   │   └── page.tsx                #   登入頁
│   │   └── forgot-password/
│   │       └── page.tsx                #   忘記密碼頁
│   │
│   ├── (dashboard)/                    # 後台主區域（含側邊欄佈局）
│   │   ├── layout.tsx                  #   後台佈局（側邊欄 + 頂部導航 + 主內容區）
│   │   │
│   │   ├── dashboard/
│   │   │   └── page.tsx                #   儀表板首頁
│   │   │                               #     - 今日對話統計
│   │   │                               #     - AI 解析成功率趨勢
│   │   │                               #     - 待處理工單數
│   │   │                               #     - 待審核 SOP 提醒
│   │   │
│   │   ├── conversations/
│   │   │   ├── page.tsx                #   對話列表頁（搜尋、篩選、分頁）
│   │   │   └── [id]/
│   │   │       └── page.tsx            #   對話詳情頁（訊息時間軸、問題卡關聯）
│   │   │
│   │   ├── problem-cards/
│   │   │   ├── page.tsx                #   問題卡列表頁
│   │   │   └── [id]/
│   │   │       └── page.tsx            #   問題卡詳情/編輯頁
│   │   │
│   │   ├── knowledge-base/
│   │   │   ├── page.tsx                #   知識庫總覽
│   │   │   ├── cases/
│   │   │   │   ├── page.tsx            #   案例庫列表
│   │   │   │   ├── new/
│   │   │   │   │   └── page.tsx        #   新增案例
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx        #   案例詳情/編輯
│   │   │   ├── manuals/
│   │   │   │   ├── page.tsx            #   手冊管理（上傳 PDF、查看分片）
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx        #   手冊分片檢視
│   │   │   ├── faq/
│   │   │   │   └── page.tsx            #   FAQ 管理
│   │   │   └── sop-drafts/
│   │   │       ├── page.tsx            #   SOP 草稿待審列表
│   │   │       └── [id]/
│   │   │           └── page.tsx        #   SOP 草稿審核頁（核准/駁回/採納）
│   │   │
│   │   ├── work-orders/                # V2.0 - 派工管理
│   │   │   ├── page.tsx                #   工單列表（看板/列表雙視圖）
│   │   │   ├── new/
│   │   │   │   └── page.tsx            #   建立工單
│   │   │   └── [id]/
│   │   │       └── page.tsx            #   工單詳情（狀態追蹤、技師指派）
│   │   │
│   │   ├── technicians/                # V2.0 - 技師管理
│   │   │   ├── page.tsx                #   技師列表（含地圖檢視）
│   │   │   ├── new/
│   │   │   │   └── page.tsx            #   新增技師
│   │   │   └── [id]/
│   │   │       └── page.tsx            #   技師詳情（技能、排程、評分）
│   │   │
│   │   ├── accounting/                 # V2.0 - 對帳管理
│   │   │   ├── page.tsx                #   對帳總覽
│   │   │   ├── reconciliations/
│   │   │   │   ├── page.tsx            #   對帳單列表
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx        #   對帳單詳情（明細、確認）
│   │   │   ├── settlements/
│   │   │   │   └── page.tsx            #   結算記錄
│   │   │   └── vouchers/
│   │   │       └── page.tsx            #   憑證查詢
│   │   │
│   │   └── settings/                   # 系統設定
│   │       ├── page.tsx                #   設定總覽
│   │       ├── general/
│   │       │   └── page.tsx            #   一般設定（平台名稱、LINE Channel 等）
│   │       ├── ai-config/
│   │       │   └── page.tsx            #   AI 參數設定（信心閾值、模型選擇）
│   │       ├── lock-models/
│   │       │   └── page.tsx            #   電子鎖型號管理
│   │       └── users/
│   │           └── page.tsx            #   管理員帳號管理
│   │
│   └── api/                            # Next.js API Routes (BFF, 若需要)
│       └── auth/
│           └── [...nextauth]/
│               └── route.ts            #   NextAuth.js 認證端點
│
├── components/                         # ── 共用元件 ──
│   ├── ui/                             # 基礎 UI 元件（Button, Input, Modal, Table 等）
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── select.tsx
│   │   ├── modal.tsx
│   │   ├── data-table.tsx              #   通用資料表格（排序、篩選、分頁）
│   │   ├── badge.tsx
│   │   ├── card.tsx
│   │   ├── toast.tsx
│   │   └── loading-spinner.tsx
│   ├── layout/                         # 佈局元件
│   │   ├── sidebar.tsx                 #   側邊欄導航
│   │   ├── top-nav.tsx                 #   頂部導航列
│   │   ├── breadcrumb.tsx              #   麵包屑導航
│   │   └── page-header.tsx             #   頁面標題區塊
│   ├── features/                       # 業務功能元件
│   │   ├── conversation-timeline.tsx   #   對話訊息時間軸
│   │   ├── problem-card-viewer.tsx     #   問題卡結構化檢視
│   │   ├── knowledge-search.tsx        #   知識庫搜尋元件
│   │   ├── sop-review-panel.tsx        #   SOP 審核面板
│   │   ├── work-order-kanban.tsx       #   V2.0 - 工單看板
│   │   ├── technician-map.tsx          #   V2.0 - 技師地圖標記
│   │   ├── quotation-builder.tsx       #   V2.0 - 報價單建構器
│   │   └── reconciliation-table.tsx    #   V2.0 - 對帳明細表
│   └── providers/                      # Context Providers
│       ├── auth-provider.tsx           #   認證狀態管理
│       ├── theme-provider.tsx          #   主題（淺色/深色）
│       └── toast-provider.tsx          #   全域通知
│
├── lib/                                # ── 工具函式與 API 客戶端 ──
│   ├── api/                            # 後端 API 客戶端
│   │   ├── client.ts                   #   Axios/Fetch 封裝（攔截器、token 注入、錯誤處理）
│   │   ├── conversations.ts            #   對話相關 API
│   │   ├── problem-cards.ts            #   問題卡相關 API
│   │   ├── knowledge-base.ts           #   知識庫相關 API
│   │   ├── work-orders.ts              #   V2.0 - 派工相關 API
│   │   ├── technicians.ts              #   V2.0 - 技師相關 API
│   │   ├── pricing.ts                  #   V2.0 - 報價相關 API
│   │   ├── accounting.ts               #   V2.0 - 對帳相關 API
│   │   └── auth.ts                     #   認證相關 API
│   ├── hooks/                          # 自訂 React Hooks
│   │   ├── useAuth.ts                  #   認證狀態 hook
│   │   ├── usePagination.ts            #   分頁 hook
│   │   ├── useDebounce.ts              #   防抖 hook
│   │   └── useWebSocket.ts             #   V2.0 - WebSocket 即時通知
│   ├── utils/                          # 通用工具函式
│   │   ├── format.ts                   #   日期、金額格式化
│   │   ├── validation.ts               #   前端驗證規則
│   │   └── constants.ts                #   前端常數（狀態標籤、顏色對應等）
│   └── types/                          # TypeScript 型別定義
│       ├── api.ts                      #   API 請求/回應型別
│       ├── entities.ts                 #   業務實體型別
│       └── common.ts                   #   通用型別（Pagination, SortOrder 等）
│
└── __tests__/                          # 前端測試（Jest + React Testing Library）
    ├── components/
    │   ├── ui/
    │   │   └── button.test.tsx
    │   └── features/
    │       ├── problem-card-viewer.test.tsx
    │       └── work-order-kanban.test.tsx
    ├── lib/
    │   └── api/
    │       └── client.test.ts
    └── app/
        └── dashboard/
            └── page.test.tsx
```

### 5.1 src/app/ - Next.js App Router

採用 Next.js App Router 的檔案系統路由。關鍵路由群組：

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
| `/work-orders` | `GET /api/v1/work-orders` (V2.0) |
| `/technicians` | `GET /api/v1/technicians` (V2.0) |
| `/accounting/reconciliations` | `GET /api/v1/accounting/reconciliations` (V2.0) |

### 5.2 src/components/ - 共用元件

元件分為三個層次：

- **`ui/`**：純 UI 元件，無業務邏輯。可跨專案複用。基於 shadcn/ui 或類似元件庫客製化。
- **`layout/`**：佈局結構元件，定義頁面骨架。
- **`features/`**：業務功能元件，包含特定業務邏輯，與後端 API 型別緊密耦合。

### 5.3 src/lib/ - 工具函式與 API 客戶端

- **`api/`**：每個後端領域對應一個 API 模組，封裝所有 HTTP 請求。`client.ts` 統一處理 token 注入、錯誤攔截、回應格式化。
- **`hooks/`**：封裝常用的狀態邏輯，保持元件簡潔。
- **`types/`**：TypeScript 型別定義，確保前後端型別一致。可由 `scripts/generate_api_client.sh` 從 OpenAPI spec 自動生成。

---

## 6. Docker 與部署結構

> **注意**：Docker 與 CI/CD 設定尚未建立，以下為目標部署架構規劃。

### 6.1 docker-compose.yml 服務定義

```plaintext
docker-compose.yml
│
├── agent                               # FastAPI 後端服務 (LangGraph + 派工 + 帳務)
│   ├── build: ./agent
│   ├── ports: 8000:8000
│   ├── depends_on: db, redis
│   ├── env_file: .env
│   └── volumes: ./agent:/app (開發環境 hot reload)
│
├── frontend                            # Next.js 前端服務
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
├── redis                               # Redis 快取
│   ├── image: redis:7-alpine
│   ├── ports: 6379:6379
│   └── volumes: redisdata:/data
│
└── nginx                               # Nginx 反向代理
    ├── image: nginx:alpine
    ├── ports: 80:80, 443:443
    ├── depends_on: agent, frontend
    └── volumes: ./nginx/conf.d:/etc/nginx/conf.d
```

**Nginx 路由規則：**

| 路徑 | 上游服務 | 說明 |
|------|---------|------|
| `/api/v1/*` | `agent:8000` | 後端 REST API |
| `/webhook/*` | `agent:8000` | LINE Webhook |
| `/docs`, `/openapi.json` | `agent:8000` | FastAPI 自動生成的 API 文件 |
| `/*` | `frontend:3000` | Next.js 前端 |

### 6.2 .github/workflows/

```plaintext
.github/workflows/
│
├── ci.yml                              # 持續整合（每次 push / PR 觸發）
│   ├── jobs:
│   │   ├── lint-backend:               #   ruff check + mypy
│   │   ├── test-backend:               #   pytest（含 PostgreSQL service container）
│   │   ├── lint-frontend:              #   eslint + tsc --noEmit (V2.0)
│   │   └── test-frontend:              #   jest (V2.0)
│   └── triggers: push, pull_request
│
└── deploy.yml                          # 持續部署（merge 到 main 時觸發）
    ├── jobs:
    │   ├── build-images:               #   docker build + push to registry
    │   ├── run-migrations:             #   alembic upgrade head
    │   └── deploy:                     #   docker-compose up -d (或 K8s apply)
    └── triggers: push to main
```

---

## 7. 設定檔結構

### 7.1 config.toml -- 14 區塊系統設定

`agent/config.toml` 是系統唯一的非機密設定檔，納入版本控制。所有可配置行為集中於此。

| # | Section | 關鍵設定 |
|---|---------|---------|
| 1 | `[system]` | `domain`（業務領域描述）、`thread_prefix`、`request_timeout=120`、`sensitive_keywords`（報價/金流觸發詞） |
| 2 | `[debounce]` | `buffer_wait=5s`、`buffer_ttl=300s`、`cleanup_interval=60s` |
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
| 14 | `[harness]` | Master switch + 7 個 layer 子區塊（task、context、governance、feedback、safety、observability、entropy），全部預設 disabled |

### 7.2 環境變數 (.env)

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

# === Google Gemini (開發替代) ===
GEMINI_API_KEY=your-api-key

# === Ollama (本地開發) ===
OLLAMA_BASE_URL=http://localhost:11434

# === API Tools ===
ORDER_API_URL=https://api.example.com/v1/status
ORDER_API_TOKEN=your-bearer-token
```

### 7.3 設定分工原則

| 類別 | 存放位置 | 版本控制 |
|------|---------|---------|
| 系統行為 | `agent/config.toml` | Yes |
| 機密金鑰 | `.env` | No |
| Prompt 模板 | `agent/agents/prompts/*.md` | Yes |
| ETL 設定 | `data/config.toml` | Yes |
| DB Schema | `SQL/Schema.sql` | Yes |

---

## 8. 檔案命名約定

### 8.1 Python（後端）

| 類別 | 約定 | 範例 |
|------|------|------|
| 模組/檔案 | `snake_case.py` | `problem_card_repo.py` |
| 目錄 | `snake_case` | `knowledge_base/` |
| 類別 | `PascalCase` | `ProblemCard`, `ResolveQueryUseCase` |
| 函式/方法 | `snake_case` | `create_problem_card()` |
| 常數 | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| 測試檔案 | `test_*.py` | `test_resolve_query.py` |
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
| Shell 腳本 | `snake_case.sh` | `setup_dev.sh` |
| Docker 設定 | 官方慣例 | `Dockerfile`, `docker-compose.yml` |
| 環境變數 | `UPPER_SNAKE_CASE` | `DATABASE_URL` |
| Alembic 遷移 | 編號前綴 + 描述 | `004_add_pgvector_extension.py` |

---

## 9. 模組擴展原則

### 9.1 新增模組的標準流程

當需要新增一個業務模組（例如 V2.0 的 `dispatch/`）時：

1. **建立模組目錄**：`agent/dispatch/`
   - `__init__.py`
   - `engine.py` — 核心業務邏輯
   - `models.py` — Pydantic/dataclass 資料模型
   - `routes.py` — FastAPI router（掛載到 `app.py`）

2. **新增設定 section**：`config.toml [dispatch]`
   - 所有行為參數外部化
   - `enabled = false` 預設，開關可控

3. **建立資料庫 migration**：`SQL/` 新增 DDL
   - FK 連結到既有實體（如 `work_orders.problem_card_id → problem_cards.card_id`）

4. **掛載 Router**：`app.py` 新增 `app.include_router(dispatch_router, prefix="/api/v2")`
   - `infrastructure/persistence/repositories/notification_repo.py` - Repository 實作

4. **建立測試：**
   - `tests/unit/domains/test_notification_entities.py`
   - `tests/unit/application/test_notification_use_cases.py`
   - `tests/features/test_notification_api.py`

5. **建立遷移：** `alembic/versions/xxx_create_notifications.py`

6. **註冊路由：** 在 `main.py` 中 `include_router()`

### 9.3 結構變更原則

- 任何**頂層目錄結構**的變更，必須透過 ADR（Architecture Decision Record）記錄。
- 新增領域模組遵循上述標準流程，無需 ADR。
- `core/` 中新增共用模組需經過 code review 確認其確實為跨領域共用。
- 保持**可預測性**比追求「完美結構」更重要 --- 一致性是第一優先。

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
| 除錯對話內容 | `scripts/view_logs.py`、`scripts/view_context.py` |
| 修改 LINE 訊息樣式 | `tools/line_ui_factory.py` |
| 更新使用者輪廓邏輯 | `profiles/manager.py` + `agents/prompts/update_profile.md` |
| 新增敏感詞 | `config.toml [system].sensitive_keywords` |
| 查看資料庫 Schema | `SQL/Schema.sql` |
| 查看使用者 hard_facts | `scripts/view_facts.py` |
| 環境變數說明 | `.env`（機密）、`config.toml`（非機密） |
| 架構決策記錄 | `docs/adrs/` |

## 附錄 B：依賴方向圖

```plaintext
                    ┌─────────────────────┐
                    │   main.py (入口)     │
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
│  │  (編排業務   │  │ (資料傳輸    │  │ (Protocol │  │
│  │   流程)      │  │  物件)       │  │  定義)    │  │
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
│  │ (業務    │  │ (值物件)      │  │ (領域事件)   │  │
│  │  實體)   │  │               │  │              │  │
│  └──────────┘  └───────────────┘  └──────────────┘  │
│                                                      │
│               零外部依賴，純業務邏輯                   │
└──────────────────────────────────────────────────────┘
```

**依賴規則：** 箭頭方向代表依賴方向。外層可以依賴內層，內層絕不依賴外層。Infrastructure 透過 Application 層定義的 Protocol (interfaces.py) 實作依賴反轉。

