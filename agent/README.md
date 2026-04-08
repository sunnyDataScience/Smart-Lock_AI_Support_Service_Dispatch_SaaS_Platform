# Smart Lock AI Agent

智慧電子鎖 AI 客服系統，基於 LangGraph 建構多 Agent 協作引擎 + 8 層 Harness 控制框架，透過 LINE Bot (FastAPI webhook) 對外服務。

## 功能特色

- **Software 3.0 診斷引擎**：PDCA 故障推理 + FMEA 故障樹，ProblemCard 追蹤完整診斷生命週期
- **8 層 Harness 框架**：Task（診斷推理）、Context（Token 預算）、Governance（工具風控）、Feedback（品質驗證）、Safety（危險指令 / PII / 情緒）、Observability（全節點追蹤）、Entropy（新案例偵測 + SOP 自動生成）
- **多模態前處理**：圖片/音訊/影片經 Gemini Flash-Lite 轉為文字描述，佔位→替換機制防止競態
- **7 專業 Agent 平行協作**：Router 意圖分類 + Send() fan-out，支援單一訊息多意圖平行處理
- **滑動窗口對話記憶**：Agent 可見最近 20 輪對話，配合語意摘要壓縮維持長對話連貫性
- **設定驅動零硬編碼**：config.toml 15 個區塊控制全系統行為，新增 Agent / 知識庫只需改設定
- **知識回饋閉環**：Novel ProblemCard → 匯出 → 人工審核 → 合併回知識庫
- **Token 成本斷路器**：TokenTrackingLLM proxy 追蹤所有 LLM 呼叫，超額自動熔斷
- **審計日誌 6 類**：conversation、safety_gate、tool_invocation、escalation、llm_interaction、rag_citation
- **智能使用者輪廓**：自動萃取設備/地址/電話，轉接真人時自動預填表單
- **LINE 平台適配**：訊息防抖合併、Loading 動畫、Markdown 清洗、Reply → Push 降級

## 系統架構

```
LINE 訊息
  ↓
webhook → 多模態前處理（圖片/音訊/影片 → Flash-Lite）→ 訊息緩衝池（防抖 + 媒體等待）
  ↓
pre_process → manage_memory → rewrite_query
  ↓
task_decompose [L1] → context_assemble [L2] → safety_gate [L6]
  ↓                                              ↓
  ├─ 診斷收斂 → diagnostic_respond ──────────────→ merge_answers
  ├─ 正常流程 → router → 7 Agent fan-out ────────→ merge_answers
  └─ 安全攔截 ─────────────────────────────────────→ post_process
  ↓
merge_answers → verify_answer [L5] → update_profile → entropy_check [L8] → post_process → LINE 回覆
```

## 快速開始

### 1. 安裝依賴環境

```bash
pip install -r requirements.txt
```

### 2. 設定環境變數

複製 `.env.example` 並建立 `.env` 檔案：

```env
# LINE Bot 認證
LINE_CHANNEL_SECRET="your-line-channel-secret"
LINE_CHANNEL_ACCESS_TOKEN="your-line-channel-access-token"

# LLM 供應商金鑰（依 config.toml [llm] 設定）
GEMINI_API_KEY="your-gemini-api-key"
# VERTEX_PROJECT_ID="your-gcp-project-id"   # provider=vertexai
# VERTEX_LOCATION="us-central1"
# OLLAMA_BASE_URL="http://localhost:11434"   # provider=ollama

# PostgreSQL（對話記憶 + 審計日誌 + 問題卡）
POSTGRES_URI="postgresql://user:pass@host:5432/dbname"

# 外部 API（選填）
# ORDER_API_URL="https://api.example.com/v1/status"
```

### 3. 初始化向量資料庫

```bash
cd ../data && python pipeline/silver_to_gold/seed_pgvector.py --all --reset --verbose
```

### 4. 啟動服務

```bash
# LINE Bot Webhook 伺服器
uvicorn app:app --reload

# CLI 測試模式（免 LINE 串接）
python main.py

# Production
gunicorn -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000 app:app
```

## 測試

```bash
python -m pytest tests/                          # 全部測試
python -m pytest tests/unit/ -v                  # 單元測試
python -m pytest tests/e2e/test_poc_harness.py   # Harness E2E
```

## 專案結構

```
agent/
├── app.py                      # FastAPI webhook 入口：LINE 訊息四向路由（文字/貼圖/多模態/其他）
├── main.py                     # CLI 測試腳本 + Harness 驗證 demo
├── config.toml                 # 全系統核心設定檔（15 區塊，零硬編碼）
├── requirements.txt
│
├── domain/                     # 業務領域模型（與 harness 框架分離）
│   ├── problem_card.py         #   ProblemCard 資料結構 + PostgreSQL CRUD
│   └── diagnostic_state_machine.py  #   PDCA 診斷狀態機（10 狀態 + 轉移規則）
│
├── graph/                      # LangGraph 狀態機
│   ├── state.py                #   GraphState TypedDict（含 Harness 層欄位）
│   ├── builder.py              #   圖組裝：12 節點 + 條件邊 + fan-out + checkpointer
│   └── nodes.py                #   所有節點實作（pre_process ~ post_process）
│
├── agents/                     # 多 Agent 子圖建構器
│   ├── __init__.py             #   build_agent_executor()：LLM ↔ ToolNode 迴圈
│   └── prompts/                #   各 Agent 的 System Prompt（.md 模板）
│       ├── hardware_technician.md
│       ├── sales_representative.md
│       ├── store_assistant.md
│       ├── app_specialist.md
│       ├── manual_librarian.md
│       ├── web_researcher.md
│       ├── receptionist.md
│       ├── rewrite_query.md
│       ├── merge_answers.md
│       ├── update_profile.md
│       ├── summarize_messages.md
│       └── transfer_human_form.md
│
├── harness/                    # 8 層 Harness 控制框架
│   ├── __init__.py             #   is_harness_enabled() / is_layer_enabled()
│   ├── task/                   #   L1: 診斷推理引擎
│   │   ├── decomposer.py      #     Software 3.0 LLM 推理編排
│   │   ├── knowledge_loader.py #     症狀/故障/故障樹知識載入
│   │   ├── prompts/            #     diagnostic_reasoning.md（PDCA prompt）
│   │   ├── taxonomy/           #     symptoms.toml, components.toml
│   │   └── knowledge/          #     fault_trees/*.json, failure_taxonomy.json
│   ├── context/                #   L2: 上下文管理
│   │   ├── assembler.py        #     來源評分 + Token 預算（V1.0 pass-through）
│   │   ├── freshness.py        #     Config 驅動新鮮度衰減
│   │   ├── budget.py           #     Token 成本估算 + 定價表
│   │   └── token_tracker.py    #     TokenTrackingLLM proxy + SessionBudget
│   ├── governance/             #   L3: 工具治理
│   │   ├── registry.py         #     ToolRegistry（風險等級分類）
│   │   └── validator.py        #     語意參數驗證（空查詢/標點/超長）
│   ├── feedback/               #   L5: 回覆品質驗證（V1.0 pass-through）
│   │   └── verifier.py
│   ├── safety/                 #   L6: 安全閘
│   │   └── gate.py             #     危險指令 + PII + 情緒/Red_Code 偵測
│   ├── observability/          #   L7: 可觀測性
│   │   ├── tracer.py           #     @traced 裝飾器 + PostgreSQL 寫入
│   │   └── metrics.py          #     SessionMetrics 聚合
│   └── entropy/                #   L8: 熵管理
│       ├── checker.py          #     新案例偵測（novelty heuristic）
│       ├── sop_generator.py    #     LLM 生成 SOP 候選
│       └── prompts/            #     generate_sop.md
│
├── core/                       # 核心基礎設施
│   ├── config.py               #   config.toml 載入 + 15 組設定解構
│   ├── debounce.py             #   訊息防抖 + 媒體佔位等待 + LangGraph 呼叫
│   ├── multimodal.py           #   Gemini Flash-Lite 媒體前處理 pipeline
│   ├── media_storage/          #   媒體存儲抽象層（local / GCS / S3）
│   ├── line_bot.py             #   LINE Messaging API 封裝（Reply → Push 降級）
│   ├── debug_display.py        #   終端 debug 顯示（路徑樹 / ProblemCard / Harness）
│   ├── debug_log.py            #   LLM messages 詳細日誌
│   └── constants.py            #   共用常數
│
├── tools/                      # 工具箱
│   ├── base.py                 #   BaseTool 抽象類別 + LangChain 轉換
│   ├── base_retriever.py       #   檢索類工具通用介面
│   ├── pgvector_store.py       #   pgvector RAG 檢索（5 知識庫）
│   ├── api_store.py            #   訂單 API 查詢
│   ├── web_search.py           #   DuckDuckGo 網頁搜尋
│   ├── transfer_human.py       #   轉接真人（表單生成 + 通知）
│   └── line_ui_factory.py      #   FlexMessage UI 工廠（VIDEO_CARD / DOWNLOAD_CARD）
│
├── services/                   # V2.0 業務服務模組（派工/定價/保固/爭議...）
│   ├── dispatch/               #   智慧派工引擎
│   ├── pricing/                #   報價引擎
│   ├── warranty/               #   保固判定
│   ├── work_order/             #   工單管理
│   ├── technician/             #   技師管理
│   └── ...                     #   audit, auth, brand, complaint, consent, ...
│
├── storage/                    # 審計日誌持久化（PostgreSQL / SQLite 雙軌）
│   ├── __init__.py             #   Registry 模式工廠
│   ├── postgres_impl.py        #   6 類事件結構化寫入
│   └── sqlite_impl.py          #   SQLite 本地開發 fallback
│
├── memory/                     # 對話記憶 Checkpointer
│   ├── __init__.py             #   Registry 模式工廠
│   ├── postgres_saver.py       #   AsyncPostgresSaver（生產環境）
│   └── sqlite_saver.py         #   SqliteSaver（本地開發）
│
├── messaging/                  # Agent 間通訊
│   ├── __init__.py             #   AgentMessage 資料結構 + 工廠函式
│   └── bus.py                  #   MessageBus 中央匯流排
│
├── profiles/                   # 使用者輪廓管理
│   └── ...                     #   LLM 萃取 + Markdown 持久化 + SCD Type 2 Facts
│
├── llms/                       # LLM 引擎工廠（Gemini / Vertex AI / Ollama）
├── embeddings/                 # Embedding 引擎工廠（Per-DB 獨立配置）
│
├── tests/                      # 測試
│   ├── unit/                   #   59 項單元測試（狀態機 / 知識載入 / 安全 / 治理）
│   ├── e2e/                    #   Harness 端到端測試
│   └── integration/            #   整合測試
│
├── scripts/                    # 輔助腳本
└── docs/                       # 技術文件
    ├── assets/                 #   architecture.mmd（Mermaid 架構圖）
    ├── manuals/                #   系統擴充指南、設定檔說明、待修清單
    └── reports/                #   開發進度報告
```

## 設定檔概覽

`config.toml` 15 個區塊：

| # | 區塊 | 用途 |
|---|------|------|
| 1 | `[system]` | 全域參數（domain、thread_prefix、timeout） |
| 2 | `[llm]` | LLM 供應商 + 模型設定 |
| 3 | `[debounce]` | 防抖計時器 + 清理間隔 |
| 4 | `[[databases]]` | pgvector 知識庫定義（5 個 collection） |
| 5 | `[tools]` | 工具啟停開關 |
| 6 | `[[intents]]` | 意圖定義 + Agent 對應 |
| 7 | `[[agents]]` | Agent 名稱 + Prompt + 工具 + Fallback |
| 8 | `[templates]` | 錯誤/超時回覆模板 |
| 9 | `[memory]` | Checkpointer 後端 + 壓縮閾值 + 滑動窗口 |
| 10 | `[required_slots]` | Slot Filling 必填欄位 |
| 11 | `[user_profile]` | 輪廓萃取開關 + Facts DB |
| 12 | `[prompts]` | Prompt 檔案路徑對照表 |
| 13 | `[harness]` | Harness 8 層啟停 + 參數（task/context/governance/safety/feedback/observability/entropy/budget） |
| 14 | `[line]` | LINE 平台設定（loading animation） |
| 15 | `[multimodal]` | 多模態處理（Flash-Lite 模型 + 媒體存儲） |
