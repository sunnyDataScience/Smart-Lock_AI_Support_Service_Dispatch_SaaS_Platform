---
status: superseded
superseded_by: docs_v2/5-views/project-structure.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# 專案結構指南 - 電子鎖智能客服與派工平台

**文件版本:** v3.1
**最後更新:** 2026-05-06
**主要作者:** 技術負責人
**狀態:** 活躍 (Active)

> **v3.1 變更摘要：** 同步 uv workspace 結構（`pyproject.toml` 取代 `requirements.txt`）、補 `scripts/{dev,env,ci,deploy}` 子目錄分類、`scripts/view_*.py` → `tests/tools/`、`silver_to_gold/` → `silver_to_skill/`、harness/ 從 8 層子目錄改寫為 8 個扁平 middleware 檔案、registry pattern 三種變體精確化（LiteLLM 字串路由 vs dict registry vs 直接 export）。

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
  - [4.10 tests/tools/ + scripts/ -- 跨平台工具與部署腳本](#410-teststools--scripts----跨平台工具與部署腳本)
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

看到功能名稱就能推斷出檔案位置。例如：知道有個「技能」功能，就能預測以下路徑存在：

- `agent/skills/data/{Brand}/{Model}/SKILL.md` -- 技能知識文件（YAML frontmatter + Markdown SOP）
- `agent/skills/__init__.py` -- `load_skills()` / `filter_skills()` 進入點
- `agent/skills/tools.py` -- `load_skill` / `update_user_info` / `transfer_to_human` 三個 agent tool
- `agent/config.toml [skills]` -- 設定開關

> **歷史備註：** 早期 V1 設計中以「ProblemCard + harness/task/」承擔故障推理，現已被 SKILL-based ReAct agent 取代。本文件中仍出現的 `harness/task/` 路徑屬歷史脈絡描述，不再對應現存程式碼。

---

## 3. 頂層目錄結構

```plaintext
Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/
├── agent/                    # AI Agent Application Core
│   ├── agents/prompts/       # 14 agent prompt templates
│   ├── core/                 # System foundations (config, constants, debounce, line_bot)
│   ├── embeddings/           # Embedding providers (ollama, vertexai)
│   ├── graph/                # LangGraph state machine (state, builder, nodes)
│   ├── harness/              # 8 個扁平 middleware 檔案（H2/H3/H_DC/H_QR/H4/H5/H6/H7.5）
│   │   ├── debounce.py       # H3: 訊息去抖 + 編排核心（含 H8 audit log 旁路）
│   │   ├── multimodal.py     # H2: 多模態下載 + buffer 替換
│   │   ├── data_correction.py # H_DC: #資料修正 攔截
│   │   ├── line_ui_factory.py # H_QR: Quick Reply 品牌詢問
│   │   ├── profile_updater.py # H4: LLM 提取使用者資料
│   │   ├── memory_manager.py # H5: 對話記憶壓縮
│   │   ├── safety_gate.py    # H6: 危險關鍵字攔截
│   │   ├── output_validator.py # H7.5: 輸出驗證（禁止洩漏內部機制）
│   │   └── media_storage/    # 多模態存儲後端 registry
│   ├── llms/                 # LLM providers (ollama, gemini, vertexai)
│   ├── memory/               # Chat history persistence (postgres, sqlite)
│   ├── profiles/             # User profile management
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
│   ├── pipeline/             # ETL stages (raw -> bronze -> silver -> skill)
│   │   ├── source_to_raw/    #   Raw data collection
│   │   ├── raw_to_bronze/    #   Text extraction (YouTube, LINE, Website, GDrive)
│   │   ├── bronze_to_silver/ #   LLM 語意切塊
│   │   └── silver_to_skill/  #   Classify -> SKILL.md draft -> approve_drafts.py
│   ├── storage/              # Data lake (raw/bronze/silver layers, ~228 JSON files)
│   ├── database/             # pgvector startup config
│   ├── embeddings/           # Embedding providers (ETL)
│   ├── llms/                 # LLM providers (ETL)
│   ├── config.toml           # ETL pipeline config
│   └── pyproject.toml        # uv workspace member（依賴從這裡讀，鎖在根 uv.lock）
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
├── scripts/                  # Cross-cutting shell scripts (dev / env / ci / deploy)
├── tests/                    # 整合測試與除錯工具（debug tools）
│   ├── tools/                #   除錯與資料檢視工具（view_*.py / clean_data.py / simulate_e2e.py）
│   └── smoke/                #   煙測腳本（api.sh）
│
├── pyproject.toml            # uv workspace root（members: agent, api, data）
├── uv.lock                   # 統一鎖檔，由 `uv sync` 生成與更新
├── .python-version           # 釘 Python 3.11（pyenv 兼容）
├── .claude/                  # Claude Code config
├── .env                      # Environment variables (not version-controlled)
├── .gitignore                # Git ignore rules
└── README.md                 # Project introduction & quickstart
```

### 3.1 uv Workspace 結構

專案採用 [uv workspace](https://docs.astral.sh/uv/concepts/workspaces/) 進行多模組依賴管理，從根目錄統一執行 `uv sync` 即可同步所有子模組依賴。

```plaintext
pyproject.toml          # workspace root（members: agent, api, data）
agent/pyproject.toml    # agent 子模組依賴（LangGraph + LINE Bot + LiteLLM）
api/pyproject.toml      # api 子模組依賴（FastAPI 管理後台 API）
data/pyproject.toml     # data pipeline 依賴（yt-dlp / Playwright / Whisper）
.python-version         # 釘 Python 3.11（pyenv 兼容）
uv.lock                 # 統一 lock，由 `uv sync` 生成與更新
```

**為什麼選 uv workspace 而非各模組獨立 venv：**

- **單一 lock**：跨模組依賴衝突在 `uv sync` 時即時發現，避免「在 agent 跑得起來、在 api 跑不起來」的版本漂移。
- **快速切換**：`uv run -p agent python main.py` 即可指定執行 context，不需 `cd agent && source .venv/bin/activate`。
- **CI 一致性**：CI 與本機共用同一份 `uv.lock`，杜絕「在 CI 才出錯」的依賴重現問題。

> 舊有 `requirements.txt` 已淘汰。歷史 commit 中可見的 `pip install -r agent/requirements.txt` 指令請改為 `uv sync`（從專案根目錄執行）。

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

### 4.3 harness/ -- Middleware 治理層（8 個扁平檔案）

> **與 V1.0 設計文件的差異：** 早期設計提案（`docs/agent-harness-refactor/`）規劃 8 層子目錄（task/、context/、governance/...），實際落地時為**降低耦合與啟動延遲**，所有 harness middleware 改為**扁平單檔模組**，由 `harness/debounce.py` 作為編排核心同步觸發。沒有 sub-package、沒有跨層共享 state，每個檔案就是一個 middleware。

**實際結構（截至 v3.1）：**

```plaintext
agent/harness/
├── debounce.py          # H3: 訊息去抖 + 編排核心（buffer_wait=1.5s）
├── multimodal.py        # H2: 多模態下載 + buffer placeholder 替換
├── data_correction.py   # H_DC: #資料修正 攔截，存 conversation context 到 DB
├── line_ui_factory.py   # H_QR: Quick Reply 品牌/型號詢問
├── profile_updater.py   # H4: 背景任務，LLM 提取使用者資料（電話、地址）
├── memory_manager.py    # H5: 對話記憶壓縮（>12 則自動摘要）
├── safety_gate.py       # H6: 危險關鍵字攔截
├── output_validator.py  # H7.5: 輸出驗證（禁止洩漏內部機制詞彙）
└── media_storage/       # 多模態檔案儲存後端（dict registry：local / gcs）
```

> **H8 audit log** 目前漂在 `debounce.py` 內部 background task，未獨立成檔。若未來規模擴大可抽出為 `harness/audit.py`。
> **L4 State & Memory** 由 `memory/` + `profiles/` 模組承擔（不在 harness/）。

**Middleware 觸發順序與成本：**

| 編號 | 檔案 | 觸發時機 | 阻塞 | 成本特性 |
|------|------|---------|------|---------|
| H2 | `multimodal.py` | 收到 image/audio/video | 背景下載 + 同步 buffer 替換 | 受網路 IO 影響 |
| H3 | `debounce.py` | 所有訊息 | 同步（buffer_wait=1.5s） | 純 asyncio.sleep |
| H_DC | `data_correction.py` | `#資料修正` 關鍵字 | 同步 — 存 DB 後跳過 agent | DB 寫入 |
| H_QR | `line_ui_factory.py` | 品牌未知 | 同步 — 暫停問品牌 | 零 LLM |
| H4 | `profile_updater.py` | agent 回覆後 | 背景 — LLM 抽取 | LLM call |
| H5 | `memory_manager.py` | agent 前後 | 同步檢查 + 背景壓縮 | LLM call（壓縮時） |
| H6 | `safety_gate.py` | LLM call 前 | 同步 | regex，零延遲 |
| H7.5 | `output_validator.py` | LLM 回覆後 | 同步 | regex，零延遲 |
| H8 | `debounce.py` 內部 | agent 回覆後 | 背景 | DB 寫入 |

**設計原則：**

- **編排集中於 `debounce.py`**：其他 middleware 都是「被 debounce.py 呼叫的純函式或 task」，沒有迴圈依賴。
- **背景任務不阻塞回覆**：H4、H5（壓縮階段）、H8 都是 `asyncio.create_task` fire-and-forget，使用者體感延遲 = LLM 回覆延遲，不疊加。
- **每個 middleware 自己管 ContextVar**：避免在 async 環境下用全域變數造成 request 串味。

> **歷史脈絡：** 早期設計中的 L1 Task Decomposition + 知識資產（SOP/fault_trees/OCAP rules）方案已被 **SKILL-based ReAct agent** 取代。`agent/skills/data/` 取代了 `harness/task/knowledge/`，`agent/agent.py` 的 `create_react_agent` 取代了 `task_decompose()`。詳見 [4.8 data/](#48-data----etl-knowledge-base-pipeline) 與 `agent/skills/`。

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
├── __init__.py                         # build_llm() — LiteLLM 字串前綴路由
└── litellm_model.py                    # LiteLLM 統一封裝（vertex_ai / openai / anthropic / ollama）

agent/embeddings/
├── __init__.py                         # build 函式直接 export（無 registry）
├── vertexai_embed.py                   # Vertex AI text-embedding-004
└── ollama_embed.py                     # Ollama local embedding
```

**Registry pattern 在 agent/ 內的三種變體：**

| 模組 | 切換機制 | 實作風格 | 為何如此選擇 |
|------|---------|---------|-------------|
| `agent/llms/` | **LiteLLM 字串前綴路由**（如 `"vertex_ai/gemini-2.5-pro"`、`"openai/gpt-4o"`） | 不是 dict registry，但同樣 config-driven — 字串解析交給 LiteLLM 完成 | 供應商爆炸時不想為每家寫 wrapper；LiteLLM 已涵蓋 100+ 模型 |
| `agent/memory/__init__.py` | dict registry（key: `in-process` / `sqlite` / `postgres`） | 顯式 dict 對應到 LangGraph 原生 checkpointer | 只有 3 個後端，dict 比 entry-point 更直接 |
| `agent/storage/__init__.py` | dict registry（key 同上） | 顯式 dict 對應到審計日誌實作 | 同上 |
| `agent/embeddings/` | build 函式直接 export，無 registry | `build_vertexai_embeddings()` / `build_ollama_embeddings()` 個別 import | 規模小（2 家），加 registry 反而增加間接層 |

切換時改 `config.toml`：`[llm] model_name = "vertex_ai/gemini-2.5-pro"` / `[memory] type = "postgres"` / `[storage] type = "sqlite"`，程式碼零修改。Embedding 供應商由各 `[[databases]]` 條目的 `embedding_provider` 欄位獨立指定。

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
│   ├── bronze_to_silver/               # LLM 語意切塊 + 結構化
│   └── silver_to_skill/                # Classify -> SKILL.md draft -> approve_drafts.py
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
└── pyproject.toml                      # uv workspace member
```

採用 **Medallion Architecture**（Raw -> Bronze -> Silver -> Skill/Gold）：

| 層級 | 處理內容 | 輸出 |
|------|---------|------|
| **Raw** | 原始檔案收集（PDF、影片 URL、網頁 URL） | 原始檔案 |
| **Bronze** | 文字擷取（YouTube 字幕、LINE 對話匯出、網頁爬蟲、GDrive PDF） | 純文字 |
| **Silver** | LLM 語意切塊與分類（chunking + categorization） | 結構化 JSON |
| **Skill (Gold)** | 分類 → 起草 → 人審 → SKILL.md（YAML frontmatter + Markdown SOP） | `agent/skills/data/{Brand}/{Model}/SKILL.md` |

> **命名說明**：通用 Medallion 文獻多以「Gold」稱呼最終層，本專案最終產物是給 ReAct agent 使用的知識文件 `SKILL.md`，故目錄命名為 `silver_to_skill/` 而非 `silver_to_gold/`。意義上等價，命名上更貼近實際產物。`approve_drafts.py` 是 Gold 層的人工審核閘門。

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

### 4.10 tests/tools/ + scripts/ -- 跨平台工具與部署腳本

#### 4.10.1 tests/tools/ -- 除錯與資料檢視工具

> 已從 `agent/scripts/` 移至專案根目錄 `tests/tools/`，從**專案根目錄**執行
> 即可（不需 `cd agent`）。Python 腳本內已自行把 `agent/` 加入 `sys.path`。

```plaintext
tests/tools/
├── view_logs.py                        # 審計日誌查詢
├── view_context.py                     # checkpointer 對話狀態檢視
├── view_facts.py                       # user_facts 表（SCD Type 2，brand/model/phone/address）
├── view_corrections.py                 # #資料修正 紀錄（--all / --export / --clear）
├── clean_data.py                       # DB 清理（測試重置）
└── simulate_e2e.py                     # E2E 模擬（debounce / Quick Reply / 多模態）
```

**跨平台執行方式：**

| 平台 | 推薦指令 | 備註 |
|------|---------|------|
| Linux / macOS | `./tests/tools/view_facts.py <user_id>` | 透過 shebang `#!/usr/bin/env python3` 直接執行 |
| pyenv 使用者 | `python3 tests/tools/view_facts.py <user_id>` | 避開 `python` shim 找不到 3.11 的問題 |
| 統一 uv 環境 | `uv run tests/tools/view_facts.py <user_id>` | 使用 workspace 的 `uv.lock` 解析依賴 |
| Windows | `python tests\tools\view_facts.py <user_id>` 或 `py tests\tools\view_facts.py <user_id>` | 反斜線分隔；`py` 是 Windows Python launcher |

#### 4.10.2 scripts/ -- 跨切面 shell 腳本

```plaintext
scripts/
├── dev/      # 本機開發環境（dev-up.sh / dev-down.sh / proxy-up.sh / proxy-down.sh）
├── env/      # 環境切換（use-local.sh / use-gcp.sh，切換 .env 指向）
├── ci/       # API 契約 CI（generate-api-types.sh / mock-server.sh /
│             #   check-operationid-orphans.sh / generate-mapping-api-index.sh）
└── deploy/   # Cloud Run 部署（agent.sh / api.sh）
```

**遷移備註：** 早期 `scripts/dev-up.sh`、`scripts/use-local.sh`、`scripts/deploy.sh` 等扁平佈局已淘汰，請以 [`scripts/README.md`](../../scripts/README.md) 為入口取得最新指令對照表與跨平台說明（Linux / macOS / Windows）。

**煙測腳本** 不在 `scripts/` 而在 `tests/smoke/`：
- `tests/smoke/api.sh` — 需先設定 `ADMIN_EMAIL` 與 `ADMIN_PASSWORD` 環境變數，例：
  ```bash
  ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=changeme123 ./tests/smoke/api.sh
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
| 新增/修改知識資產 | `agent/skills/data/{Brand}/{Model}/SKILL.md`（透過 data pipeline `silver_to_skill/approve_drafts.py` 審核入庫） |
| 查看 GAP 分析 | `docs/_gap-analysis/gap-analysis-report-cn.md` |
| 查看 V2.0 設計規格 | `docs/02-design/specs/` |
| 除錯對話內容 | `tests/tools/view_logs.py`、`tests/tools/view_context.py`（從專案根執行；`uv run` 或 shebang 皆可） |
| 修改 LINE 訊息樣式 | `tools/line_ui_factory.py` |
| 更新使用者輪廓邏輯 | `profiles/manager.py` + `agents/prompts/update_profile.md` |
| 新增敏感詞 | `config.toml [system].sensitive_keywords` |
| 查看資料庫 Schema | `SQL/Schema.sql`（V1）、`SQL/Schema_v2_extensions.sql`（V2） |
| 查看使用者 hard_facts | `tests/tools/view_facts.py <user_id>`（從專案根執行） |
| 模擬 E2E 對話流程 | `tests/tools/simulate_e2e.py`（debounce / Quick Reply / 多模態） |
| 清理測試資料庫 | `tests/tools/clean_data.py` |
| 切換 DB 目標 | `./scripts/env/use-local.sh` 或 `./scripts/env/use-gcp.sh`（詳見 `scripts/README.md`） |
| 啟動本機開發環境 | `./scripts/dev/dev-up.sh`（Docker DB + ngrok + uvicorn） |
| 部署到 Cloud Run | `./scripts/deploy/agent.sh` 或 `./scripts/deploy/api.sh` |
| API 煙測 | `ADMIN_EMAIL=... ADMIN_PASSWORD=... ./tests/smoke/api.sh` |
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
