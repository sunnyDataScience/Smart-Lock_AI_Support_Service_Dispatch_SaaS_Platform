# Architecture（細節）

> 主檔 `CLAUDE.md` 只放架構不變量與硬約束。這份是「需要時才展開」的結構導覽。
> 注意：模組職責、目錄結構大多能直接 `ls` / 讀 code 確認 —— 以 code 為準，本檔僅作地圖。

## Major Modules

1. **`agent/`** — ReAct Agent，靠 `product_info/` mega-doc 知識庫（LINE Bot AI 客服）；optional Belief-Augmented ReAct（Turn Cycle），config 控
2. **`data/`** — Medallion ETL Pipeline（Bronze → Silver SOP drafts；最終 mega-doc 由業主審稿後手動更新 `agent/product_info/`）
3. **`web/`** — Next.js Admin Dashboard（營運監控、對話審閱）
4. **`docs/architecture/api/`** — API Contract SSOT（OpenAPI 3.1 + CI validation）
5. **`web_design_spec_prompt_pipeline/`** — AI 輔助網頁設計 prompt pipeline

## Request Processing Flow

LINE webhook 到回覆的完整 async 流程：

```
LINE webhook (app.py)
  ├─ Sticker → 立即友善回覆（不走 agent）
  ├─ Image/Audio/Video → buffer 放 media_pending placeholder
  │                     → background: download + store → 取代 placeholder
  └─ Text → 加入 debounce buffer

Debounce buffer (harness/debounce.py)
  └─ buffer_wait (1.5s) timeout → process_and_reply()
      ├─ Safety gate：擋危險關鍵字 (H6)
      ├─ #資料修正 intercept (harness/data_correction.py)
      │   └─ 關鍵字命中？→ 存對話 context 進 DB → 回確認 → 跳過 agent
      ├─ Quick Reply intercept (line_ui_factory.py)
      │   └─ 品牌未知？→ 暫停，用按鈕問品牌 → 收集型號 → 放行
      ├─ Profile update background task (harness/profile_updater.py)
      └─ run_agent()
          ├─ 從 DB 載 user facts（brand/model）
          ├─ 從用戶輸入自動推品牌 (infer_brand_from_text)
          ├─ 注入 [可用產品資料] + [用戶資料] + [前情提要] 前綴
          │  └─ (optional, gated by [turn_cycle].enabled)
          │     Belief-Augmented prefix → Hypothesize + Decide → [Belief Hint]
          ├─ 從 checkpoint 剝除過時 multimodal
          ├─ agent.ainvoke()（request_timeout 180s）
          │   └─ LLM + tools：load_product_info, update_user_info, transfer_to_human
          ├─ Output validator：檢查 forbidden phrases (H7.5)
          ├─ Calibrate (optional, post-reply) → CalibrationSignal 寫回 BeliefState
          ├─ Checkpoint cleanup：multimodal + tool_calls 換成文字參照
          ├─ Audit log (H8, background)
          └─ 回傳 AI response

Post-reply (background, 非阻塞)：
  ├─ Memory compression（>12 messages，harness/memory_manager.py）
  └─ Profile fact extraction via LLM (harness/profile_updater.py)
```

`GET /chat` 繞過 LINE webhook + debounce，直呼 `run_agent()` —— 測試用，不會經 Quick Reply / multimodal。

## Agent Module (`agent/`)

**Entry points：**
- `app.py` — FastAPI server，LINE webhook（`POST /webhook`）、health check、測試端點
- `main.py` — CLI 模式（僅驗證 LLM 連線，無 harness 層）

**Agent 構造（`agent.py`）：**
- `langgraph.prebuilt.create_react_agent` + 3 tools：`load_product_info`, `update_user_info`, `transfer_to_human`
- System prompt 來自 `prompts/system.md`；product info catalog 每請求動態注入（不在靜態 prompt）
- Mega-docs 啟動時從 `product_info/` 一次載入，每請求按 brand/model 過濾
- LLM model string 在 `agent/config.toml` `[llm]` — quality_check 與 evals 讀同一份（與 prod parity）
- Optional Belief-Augmented pre-pass：`[turn_cycle].enabled=true` 時先跑 Hypothesize + Decide 產 `[Belief Hint]` 附到 system prompt 前綴；Calibrate 在 reply 後跑回寫 BeliefState

**Module map：**
- `core/` — 橫切基建：`config.py`（TOML loader）、`line_bot.py`（LINE SDK wrapper）、`brand_match.py`、`tracing.py`
- `llms/` — 統一 LLM via LiteLLM；支援 `"vertex_ai/gemini-..."` 風格 provider string
- `memory/` — Checkpointer registry（in-process / SQLite / PostgreSQL）
- `storage/` — Audit log storage registry
- `harness/` — Middleware 層（見下表）
- `agent_tools/` — Agent tools + ContextVar helpers
- `product_info/` — 品牌鍵 mega-doc 知識庫（`{Brand}/{Model}.md` + `_common/*.md`）
- `belief.py` / `belief_store.py` / `hypothesize.py` / `policy.py` / `calibrate.py` — Belief-Augmented ReAct primitives
- `profiles/` — User facts（hard + soft）萃取與儲存
- `prompts/` — System prompt 與模板
- `quality/` — `quality_check` LLM-as-Judge eval（HTML + JSON 報告）；`--turn-cycle` 旗標做 A/B
- `evals/` — Golden-set regression pipeline（`runner` → `judge` → `reporter`）；見 `agent/evals/README.md`

**Harness middleware 層（`harness/`）：**

| Layer | File | When | Blocking? |
|-------|------|------|-----------|
| H2 | `multimodal.py` | 收到 media | Background download，sync buffer replace |
| H3 | `debounce.py` | 所有訊息 | Sync — 合併快速訊息、orchestrate agent |
| H_DC | `data_correction.py` | agent 前若 `#資料修正` | Sync — 存對話 context 進 DB、跳過 agent |
| H_QR | `line_ui_factory.py` | agent 前若品牌未知 | Sync — 暫停收集 brand/model |
| H4 | `profile_updater.py` | agent 回覆後 | Background — LLM 萃取 facts |
| H5 | `memory_manager.py` | agent 前 + 後 | Sync check，background compress |
| H6 | `safety_gate.py` | LLM 呼叫前 | Sync — 擋危險關鍵字 |
| H7.5 | `output_validator.py` | LLM 回覆後 | Sync — 擋內部機制字眼 |
| H8 | Audit in `debounce.py` | agent 回覆後 | Background — 記 tool calls + escalations |
| H_TC | `turn_cycle.py` + `turn_cycle_runner.py` | Pre-agent（啟用時）| Sync — Hypothesize + Decide → `[Belief Hint]` 前綴 |

**Checkpoint cleanup（除錯重點）：**
- 每次 `run_agent()` 後，ToolMessage content（完整 mega-doc 文字）換成 `[已參考產品資料: {name}]`
- Multimodal HumanMessage content（base64）換成 `[使用者曾傳送圖片]` 參照
- 避免長對話 context 膨脹。用 `tests/tools/view_context.py` 檢視 state。

## Profile & Facts System (`agent/profiles/`)

- **Hard facts**（DB, SCD Type 2）：`device_brand`, `device_model`, `phone`, `address` — 存 `user_facts` 表，帶版本
- **Soft facts**（品牌特定，`config.toml` 每品牌可設）：`door_type`, `install_date`, `unlock_methods` 等
- 收集途徑：Quick Reply 按鈕（brand/model）、`update_user_info` tool（brand/model）、回覆後 LLM 萃取（phone/address）
- Brand/model facts 驅動 product info 過濾 —— 缺 brand = 只能存取 `_common/*`

## Data Pipeline (`data/pipeline/`)

4 層 Medallion：
1. `source_to_raw/` — 下載（YouTube via yt-dlp、website via Playwright、Google Drive）
2. `raw_to_bronze/` — 萃取轉換（Whisper ASR、Vision LLM for images）
3. `bronze_to_silver/` — LLM 語意切塊
4. `silver_to_skill/` — 分類、草擬 skill candidate（**legacy**；runtime 不再讀 `agent/skills/data/`，依 bronze-only 規則直用 `agent/product_info/`）

`silver_to_skill/` 仍可跑當輔助線索，但產物在 A-3b 後不進 runtime；新知識由業主直接審稿/編輯 `agent/product_info/{Brand}/{Model}.md`。

## Database

PostgreSQL 16 + pgvector。Schema 在 `SQL/`：
- `Schema.sql` — 核心表：users, conversations, messages, problem_cards, manual_chunks, case_entries
- `Schema_harness_migration.sql` — user_facts（SCD Type 2）, audit_logs, data_corrections
- `Schema_v2_extensions.sql` — 額外延伸

兩種連線字串：`POSTGRES_URI`（標準 psycopg，checkpointer/facts/audit）、`PG_VECTOR_URI`（psycopg + pgvector，embeddings）。
所有 DB module 共用 `POSTGRES_URI` 但各自獨立 `AsyncConnection`（`autocommit=True`），各有 `_ensure_conn()` 處理 CloudSQL idle 斷線重連。

## Configuration Flow

全部集中在 `agent/config.toml`。主要區段：`[system]`（domain, timeout）、`[llm]`（model string）、`[line_bot]`、`[memory]`（壓縮設定 + Flash model）、`[product_info]`、`[prompts]`、`[safety]`、`[output_validator]`、`[debounce]`、`[multimodal]`、`[user_profile]`（facts_enabled）、`[quick_reply]`（brand/model 清單 —— 驗證的單一真實來源）、`[data_correction]`、`[opik]`、`[turn_cycle]`（`enabled`, `fail_open`）。

## Deployment

- **Dockerfile** 在 `agent/Dockerfile` — Python 3.11-slim，uvicorn port 8080
- **Cloud Run** via `scripts/deploy/agent.sh` — pre-flight、build amd64 image（`{git-sha}-{timestamp}` tag，支援 rollback）、push Artifact Registry、deploy 帶 Secret Manager + Cloud SQL Unix socket、health check 重試
- **DB URI 管理**：`deploy.sh --update-db-uri` 從 Secret Manager 讀 `DB_PASSWORD`、自動 URL-encode、構建 `POSTGRES_URI` 並 round-trip 驗證。**永不手動構建 POSTGRES_URI。**
- Secrets via GCP Secret Manager：`LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN`, `DB_PASSWORD`, `POSTGRES_URI`, `OPIK_API_KEY`, `OPIK_WORKSPACE`
- **Health endpoint**（`/health`）：檢查 facts_db + audit_db；回 200 (ok) / 503 (degraded) 帶 `checks` 細節
- **DB resilience**：4 個 DB module 都用 `autocommit=True` + `_ensure_conn()` 自動重連，CloudSQL idle 斷線透明處理

## Web Admin Dashboard (`web/`)

Next.js 15（App Router）+ React 19 + TypeScript。Tailwind CSS 4、Recharts、Lucide。Path alias `@/*` → `./src/*`。無 UI 元件庫 —— 全 Tailwind 自刻。

**Page groups（41 個 page.tsx，含 root redirect）：**

| Group | Routes |
|-------|--------|
| Root / Auth | `/`（→ `/dashboard`）, `/login`, `/dashboard`, `/settings` |
| Conversations | `/conversations`, `/conversations/[id]` |
| Problem Cards | `/problem-cards`, `/problem-cards/[id]` |
| Work Orders | `/work-orders`, `/work-orders/[id]`, `/work-orders/kanban`, `/work-orders/map` |
| Technicians | `/technicians`, `/technicians/[id]` |
| Accounting | `/accounting`, `/accounting/invoices`, `/accounting/vouchers`, `/accounting/revenue` |
| Knowledge Base | `/knowledge-base`, `/knowledge-base/cases`(+ `/new`, `/[id]`, `/[id]/edit`), `/knowledge-base/manuals`, `/knowledge-base/sop-drafts`(+ `/[id]`), `/knowledge-base/family-reviews` |
| Admin — Operations | `/admin/dispatch-queue`, `/admin/refunds`, `/admin/warranty-claims`, `/admin/disputes`, `/admin/inventory`, `/admin/sentiment-alerts`, `/admin/customers` |
| Admin — Reports | `/admin/reports/kpi`, `/admin/reports/revenue`, `/admin/reports/technician-ranking` |
| Admin — System | `/admin/audit-events`, `/admin/roles`, `/admin/api-status`, `/admin/knowledge-base/sop-performance` |

- **API integration**：mock → live API 遷移中。多數 admin/knowledge-base/accounting 頁已呼叫生成的 typed client。OpenAPI spec（`docs/architecture/api/openapi.yaml`）為真實來源 —— 改 spec 後跑 `./scripts/ci/generate-api-types.sh` 重生型別。
- **Component**：`src/components/{domain}/`。生成型別在 `web/types/api.generated.ts`（tsconfig `@/types/*` alias）。
- **Sidebar**：巢狀 `NavItem[]` 支援 `children?: NavChild[]`，active parent 自動展開。
- **Design tokens**：`globals.css` CSS 變數 — primary `#2563EB`、accent `#F59E0B`。字體 Inter + Noto Sans TC。深色 sidebar `#1E293B` + 淺色內容 `#F8FAFC`。

## API Contract System (`docs/architecture/api/`)

- `openapi.yaml` — REST API 3.1 spec
- `web/types/api.generated.ts` — 自動生成 TypeScript 型別

> **`dev_new_arch` (f00ac91) 退場**：AsyncAPI spec（`asyncapi.yaml`）、operationId 雙向檢查、TC-NNNN test-case registry 在 docs 重構中移除；相關 CI（`orphan-check.yml`, `test-case-coverage.yml`, `asyncapi-validate.mjs`）一併移除。

CI workflows（`.github/workflows/`）：`spec-lint.yml`, `api-types-sync.yml`, `mock-smoke.yml` —— 都 gate on OpenAPI spec 變更。

## Web Design Spec Pipeline (`web_design_spec_prompt_pipeline/`)

AI 輔助網頁開發 prompt pipeline —— 把需求轉成結構化、AI 可執行的 prompt：
- `guides/` — 實作策略與 QA checklist
- `global/` — Design tokens 與品牌系統模板
- `pages/` — 23 個頁面 spec，附 `MAPPING.md` 交叉索引
- `modules/` — 8 種可複用 UI 模組
- `assembly/` — Pipeline orchestrator
- `design-system-specs/` — 工業設計系統（foundations, components, patterns）含 Penpot assets

## Documentation

`docs/` 用 5D 框架（DISCOVER → DEFINE → DESIGN → DEVELOP → DELIVER）+ TR gate（TR0–TR10）。關鍵檔：
- `docs/05_architecture_and_design_document.md` — 系統架構
- `docs/01_development_workflow_cookbook.md` — 開發流程
- `docs/HOME.md` — 文件中樞
