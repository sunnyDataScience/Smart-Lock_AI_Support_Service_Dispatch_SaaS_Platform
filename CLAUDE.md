# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Smart Lock AI Support & Service Dispatch SaaS Platform — a LINE Bot-based AI customer service agent for smart lock troubleshooting, with a Next.js admin dashboard for operations monitoring. Built with a ReAct agent (LangGraph) backed by a `product_info/` mega-doc knowledge base (one self-contained mega-doc per brand+model, sourced strictly from `data/storage/bronze/`), plus a Medallion data pipeline.

Primary language: **Chinese (Traditional)** for all user-facing text, comments, and documentation. Code identifiers and git messages may mix English and Chinese.

## Common Commands

```bash
# Setup
conda create -n smart-lock python=3.11 && conda activate smart-lock
pip install -r agent/requirements.txt    # Agent dependencies
pip install -r data/requirements.txt     # Data pipeline dependencies
cd web && npm install                    # Web dashboard dependencies

# Run agent (CLI interactive mode — verifies LLM connectivity, no LINE Bot needed)
cd agent && python main.py

# Run FastAPI server (LINE webhook mode)
cd agent && uvicorn app:app --reload --port 8000

# Quick test endpoint (server must be running, bypasses debounce)
curl "http://localhost:8000/chat?q=門打不開"
curl "http://localhost:8000/chat?q=門打不開&user_id=test-user-1"  # custom thread

# Health check
curl http://localhost:8000/health

# Web admin dashboard
cd web && npm run dev                    # Dev server (http://localhost:3000)
cd web && npm run build                  # Production build
cd web && npm run lint                   # ESLint

# Quality testing (LLM-as-Judge eval pipeline)
cd agent && python -m quality.quality_check              # Full: agent + keyword + LLM judge
cd agent && python -m quality.quality_check --no-judge   # Agent answers + keyword match only
cd agent && python -m quality.quality_check --judge-only # Re-score existing quality_report.json
cd agent && python -m quality.quality_check --retry-failed # Retest non-pass cases only

# Skill approval (data pipeline → agent)
python data/pipeline/silver_to_skill/approve_drafts.py --dry-run
python data/pipeline/silver_to_skill/approve_drafts.py --confirm

# Debugging scripts (run from agent/)
cd agent && python scripts/view_context.py <user_id>   # Inspect checkpoint state
cd agent && python scripts/view_facts.py <user_id>     # Inspect user facts (brand, model, phone, address)
cd agent && python scripts/view_logs.py                 # Query audit logs
cd agent && python scripts/view_corrections.py          # View #資料修正 records (--all / --export / --clear)
cd agent && python scripts/view_llm_usage.py            # Query llm_usage_log (token / latency / Q&A)
cd agent && python scripts/clean_data.py                # DB cleanup

# API contract tooling (run from project root)
./scripts/generate-api-types.sh            # Generate TypeScript types from OpenAPI
./scripts/mock-server.sh                   # Start Prism mock server on port 4010
./scripts/check-operationid-orphans.sh     # Validate spec ↔ docs bidirectionality

# Deployment (Cloud Run)
chmod +x agent/scripts/deploy.sh
./agent/scripts/deploy.sh                # Full: pre-flight → build → push → deploy → health check
./agent/scripts/deploy.sh --build-only   # Docker image only
./agent/scripts/deploy.sh --deploy-only  # Deploy existing image
./agent/scripts/deploy.sh --update-db-uri # Rebuild POSTGRES_URI from DB_PASSWORD (auto URL encode)
```

No automated unit test suite exists. Testing is via `quality_check` (LLM-as-Judge), CLI (`python main.py`), or the `/chat` endpoint.

## Environment Configuration

- Copy `.env.example` to `.env` at project root. Required variables:
  - `VERTEX_PROJECT_ID`, `VERTEX_LOCATION` — Vertex AI / Gemini
  - `POSTGRES_URI` — PostgreSQL (checkpointer, facts, audit). Format: `postgresql://user:pass@host:port/db`
  - `LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN` — LINE Bot (not needed for CLI or `/chat`)
  - `OPIK_API_KEY`, `OPIK_WORKSPACE` — LLM observability (optional)
- `credentials.json` (GCP service account) in project root — needed for data pipeline and Vertex AI when not using `gcloud auth`
- Agent reads config from `agent/config.toml`; data pipeline reads from `data/config.toml`
- Config pattern: TOML files store env var **names** (e.g., `postgres_uri_env = "POSTGRES_URI"`), actual values come from `.env`

## Architecture

### Major Modules

1. **`agent/`** — Skill-based ReAct Agent (LINE Bot AI customer service)
2. **`data/`** — Medallion ETL Pipeline producing SKILL.md knowledge files
3. **`web/`** — Next.js Admin Dashboard (operations monitoring & conversation review)
4. **`docs/02-design/specs/`** — API Contract SSOT (OpenAPI + AsyncAPI + CI validation)
5. **`web_design_spec_prompt_pipeline/`** — AI-assisted web design prompt pipeline

### Request Processing Flow

The complete async flow from LINE webhook to reply:

```
LINE webhook (app.py)
  ├─ Sticker → immediate friendly reply (no agent)
  ├─ Image/Audio/Video → media_pending placeholder in buffer
  │                     → background: download + store → replace placeholder
  └─ Text → add to debounce buffer

Debounce buffer (harness/debounce.py)
  └─ buffer_wait (1.5s) timeout → process_and_reply()
      ├─ Safety gate: block dangerous keywords (H6)
      ├─ #資料修正 intercept (harness/data_correction.py)
      │   └─ Keyword match? → save context to DB → reply confirmation → skip agent
      ├─ Quick Reply intercept (line_ui_factory.py)
      │   └─ Brand unknown? → pause, ask brand via buttons → collect model → release
      ├─ Profile update background task (harness/profile_updater.py)
      └─ run_agent()
          ├─ Load user facts (brand/model) from DB
          ├─ Auto-infer brand from user input (infer_brand_from_text)
          ├─ Inject [可用技能] + [用戶資料] + [前情提要] prefixes
          ├─ Strip stale multimodal from checkpoint
          ├─ agent.ainvoke() with request_timeout (180s)
          │   └─ LLM + tools: load_product_info, update_user_info, transfer_to_human
          ├─ Output validator: check forbidden phrases (H7.5)
          ├─ Checkpoint cleanup: replace multimodal + tool_calls with text refs
          ├─ Audit log (H8, background)
          └─ Return AI response

Post-reply (background, non-blocking):
  ├─ Memory compression if >12 messages (harness/memory_manager.py)
  └─ Profile fact extraction via LLM (harness/profile_updater.py)
```

**GET /chat** bypasses LINE webhook and debounce buffer — calls `run_agent()` directly. Useful for testing but doesn't exercise Quick Reply or multimodal flows.

### Agent Module (`agent/`)

**Entry points:**
- `app.py` — FastAPI server with LINE webhook (`POST /webhook`), health check, and test endpoint
- `main.py` — CLI mode (verifies LLM connectivity only, no harness layers)

**Agent construction** (`agent.py`):
- Uses `langgraph.prebuilt.create_react_agent` with 3 tools: `load_product_info`, `update_user_info`, `transfer_to_human`
- System prompt loaded from `prompts/system.md`; product info catalog injected dynamically per-request (not in static prompt)
- Mega-docs loaded once at startup from disk, filtered per-request by user's brand/model
- LLM model string lives in `agent/config.toml` `[llm]` — quality_check and evals read this same config (parity with prod)

**Module map:**
- `core/` — Cross-cutting infrastructure: `config.py` (TOML loader), `line_bot.py` (LINE SDK wrapper)
- `llms/` — Unified LLM via LiteLLM; supports any provider with `"vertex_ai/gemini-..."` style strings
- `memory/` — Checkpointer registry (in-process / SQLite / PostgreSQL)
- `storage/` — Audit log storage registry
- `harness/` — Middleware layers (see table below)
- `agent_tools/` — Agent tools: `load_product_info`, `update_user_info`, `transfer_to_human` + ContextVar helpers
- `product_info/` — Brand-keyed mega-doc knowledge base (`{Brand}/{Model}.md` + `_common/*.md`)
- `profiles/` — User facts (hard + soft) extraction and storage
- `prompts/` — System prompt and templates
- `quality/` — `quality_check` LLM-as-Judge eval (HTML + JSON reports)
- `evals/` — Golden-set regression pipeline (`runner` → `judge` → `reporter`); see `agent/evals/README.md`

**Harness middleware layers** in `harness/`:

| Layer | File | When | Blocking? |
|-------|------|------|-----------|
| H2 | `multimodal.py` | On media message | Background download, sync buffer replace |
| H3 | `debounce.py` | All messages | Sync — merges rapid messages, orchestrates agent |
| H_DC | `data_correction.py` | Before agent if `#資料修正` | Sync — saves conversation context to DB, skips agent |
| H_QR | `line_ui_factory.py` | Before agent if brand unknown | Sync — pauses for brand/model collection |
| H4 | `profile_updater.py` | After agent reply | Background — extracts facts via LLM |
| H5 | `memory_manager.py` | Before + after agent | Sync check, background compress |
| H6 | `safety_gate.py` | Before LLM call | Sync — blocks dangerous keywords |
| H7.5 | `output_validator.py` | After LLM reply | Sync — blocks internal mechanism phrases |
| H8 | Audit in `debounce.py` | After agent reply | Background — logs tool calls + escalations |

**Checkpoint cleanup** (important for debugging):
- After each `run_agent()`, ToolMessage content (full SOP text) is replaced with `[已參考技能: {name}]`
- Multimodal HumanMessage content (base64 data) is replaced with `[使用者曾傳送圖片]` references
- This prevents context bloat in long conversations. Use `scripts/view_context.py` to inspect state.

### Product Info Knowledge Base (`agent/product_info/`)

**Two-stage loading:**
1. **Startup**: `load_all_docs()` scans `product_info/` for `.md` files, parses YAML frontmatter (`brand`, `model`, `description`), builds in-memory index
2. **Per-request**: `filter_loadable(brand, model)` decides what's loadable → catalog injected as `[可用產品資料]` prefix in user message

**Directory layout (one mega-doc per brand+model, plus `_common/*`):**

```
agent/product_info/
├── _common/                # brand=_common, model=None
│   ├── troubleshoot.md     # 通用症狀分流路由
│   ├── dispatch.md         # 派工 SOP / 安裝預約 / 保固政策
│   ├── general-knowledge.md # 電子鎖通用知識（電池/Wi-Fi/門框等）
│   └── store-info.md       # 店家資訊 / 服務區域 / 服務項目
├── Chatlock/
│   ├── A90.md              # brand=Chatlock, model=A90
│   ├── AI-88.md
│   └── AI-99.md
├── Dormakaba/              # 16 mega-docs：AS701/AS850/AS901/DP850/...
└── {Philips,Kaadas,Milre,AiLock,3E}/
```

**Sourcing rule (CRITICAL — bronze-only):**
- All mega-doc content must be derived strictly from `data/storage/bronze/`（YouTube 字幕、website、video transcript）
- **PDF (GDrive) is treated as untrustworthy**：mega-doc only embeds PDF URLs in「相關手冊」section, never quotes PDF content as authoritative steps
- This is a hard rule — adding content from sources outside bronze is a regression

**Key concepts:**
- **Strict profile gating** (`product_info/__init__.py:filter_loadable`): brand+model 齊備 → 可載入 `{Brand}/{Model}` + 全部 `_common/*`；否則只能載 `_common/*`
- **Loader exposes** `all_docs()`、`filter_loadable()`、`get_doc(name)`、`has_brand(brand)`
- **Frontmatter format**: `brand`, `model` (or `_common` + null), `description` — `description` 用於 dynamic catalog 的條列說明

### Agent Tools (`agent/agent_tools/tools.py`)

Three agent tools, all use `ContextVar` for per-request isolation in async:

| Tool | Purpose | Key behavior |
|------|---------|--------------|
| `load_product_info` | Load mega-doc | Strict profile gate — rejects loads outside `{brand}/{model} + _common/*` |
| `update_user_info` | Set brand/model | Validates via `match_brand()`/`match_model()`, normalizes casing, writes to DB (SCD Type 2), updates ContextVar, returns refreshed product info catalog |
| `transfer_to_human` | Escalate to human | Auto-fills known facts (phone, address, device) into form template; gated by `_doc_loaded_this_run` to prevent premature escalation |

### Profile & Facts System (`agent/profiles/`)

- **Hard facts** (DB, SCD Type 2): `device_brand`, `device_model`, `phone`, `address` — stored in `user_facts` table with versioning
- **Soft facts** (brand-specific, configurable per brand in `config.toml`): `door_type`, `install_date`, `unlock_methods`, etc.
- Facts collected via: Quick Reply buttons (brand/model), `update_user_info` tool (brand/model), LLM extraction post-reply (phone/address)
- Brand/model facts drive skill filtering — missing brand = limited skill access

### Data Pipeline (`data/pipeline/`)

4-layer Medallion architecture:
1. `source_to_raw/` — Download content (YouTube via yt-dlp, websites via Playwright, Google Drive)
2. `raw_to_bronze/` — Extract and convert (Whisper ASR, Vision LLM for images)
3. `bronze_to_silver/` — Semantic chunking via LLM
4. `silver_to_skill/` — Classify and draft skill candidates (legacy artifact; agent runtime no longer reads `agent/skills/data/`, use `agent/product_info/` directly per the bronze-only rule)

**Skill approval** (`approve_drafts.py`): New skills placed by brand suffix detection (e.g., name ending in `-dormakaba` → `Dormakaba/_all-models/`; no brand suffix → `_common/`). Pipeline config: `data/config.toml`.

### Database

PostgreSQL 16 with pgvector extension. Schemas in `SQL/`:
- `Schema.sql` — Core tables: users, conversations, messages, problem_cards, manual_chunks, case_entries
- `Schema_harness_migration.sql` — user_facts (SCD Type 2), audit_logs, data_corrections
- `Schema_v2_extensions.sql` — Additional extensions

Two connection string patterns: `POSTGRES_URI` (standard psycopg) for checkpointer/facts/audit, `PG_VECTOR_URI` (psycopg + pgvector) for embeddings.

All DB modules share the same `POSTGRES_URI` but maintain independent `AsyncConnection` instances with `autocommit=True`. Each module has `_ensure_conn()` for automatic reconnection on CloudSQL idle disconnections.

### Configuration Flow

All config centralized in `agent/config.toml`. Key sections: `[system]` (domain, timeout), `[llm]` (model string), `[line_bot]`, `[memory]` (compression settings + Flash model for summaries), `[skills]`, `[prompts]`, `[safety]`, `[output_validator]`, `[debounce]`, `[multimodal]`, `[user_profile]` (facts_enabled), `[quick_reply]` (brand/model lists — single source of truth for validation), `[data_correction]` (keyword intercept + DB logging), `[opik]`.

### Deployment

- **Dockerfile** at `agent/Dockerfile` — Python 3.11-slim, uvicorn on port 8080
- **Cloud Run** deployment via `agent/scripts/deploy.sh` — pre-flight checks, builds amd64 image with `{git-sha}-{timestamp}` tag (supports rollback), pushes to Artifact Registry, deploys with Secret Manager + Cloud SQL Unix socket, health check with retry
- **DB URI management**: `deploy.sh --update-db-uri` reads `DB_PASSWORD` from Secret Manager, auto URL-encodes, constructs `POSTGRES_URI` with round-trip validation. Never manually construct POSTGRES_URI.
- Secrets managed via GCP Secret Manager: `LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN`, `DB_PASSWORD`, `POSTGRES_URI`, `OPIK_API_KEY`, `OPIK_WORKSPACE`
- **Health endpoint** (`/health`): checks facts_db + audit_db connectivity. Returns 200 (ok) or 503 (degraded) with `checks` detail.
- **DB resilience**: All 4 DB modules use `autocommit=True` + `_ensure_conn()` auto-reconnect. CloudSQL idle disconnections are handled transparently.

### Web Admin Dashboard (`web/`)

Next.js 15 + React 19 + TypeScript admin dashboard for operations teams.

**Tech stack:** Next.js 15 (App Router), React 19, Tailwind CSS 4, Recharts (charts), Lucide (icons). Path alias `@/*` → `./src/*`. No UI component library — all custom components with Tailwind CSS.

**Page groups** (41 page.tsx files, including root redirect):

| Group | Routes |
|-------|--------|
| Root / Auth | `/` (→ `/dashboard`), `/login`, `/dashboard`, `/settings` |
| Conversations | `/conversations`, `/conversations/[id]` |
| Problem Cards | `/problem-cards`, `/problem-cards/[id]` |
| Work Orders | `/work-orders`, `/work-orders/[id]`, `/work-orders/kanban`, `/work-orders/map` |
| Technicians | `/technicians`, `/technicians/[id]` |
| Accounting | `/accounting`, `/accounting/invoices`, `/accounting/vouchers`, `/accounting/revenue` |
| Knowledge Base | `/knowledge-base`, `/knowledge-base/cases` (+ `/new`, `/[id]`, `/[id]/edit`), `/knowledge-base/manuals`, `/knowledge-base/sop-drafts` (+ `/[id]`), `/knowledge-base/family-reviews` |
| Admin — Operations | `/admin/dispatch-queue`, `/admin/refunds`, `/admin/warranty-claims`, `/admin/disputes`, `/admin/inventory`, `/admin/sentiment-alerts`, `/admin/customers` |
| Admin — Reports | `/admin/reports/kpi`, `/admin/reports/revenue`, `/admin/reports/technician-ranking` |
| Admin — System | `/admin/audit-events`, `/admin/roles`, `/admin/api-status`, `/admin/knowledge-base/sop-performance` |

**API integration status:** Active migration from mock data to live API. Many admin/knowledge-base/accounting pages now call generated typed clients (see commits `feat(web): /xxx 串接 ...`). Pages still on mock data are flagged in their components. Treat the OpenAPI spec at `docs/02-design/specs/openapi.yaml` as source of truth — regenerate types via `./scripts/generate-api-types.sh` after any spec change.

**Component organization:** `src/components/{domain}/` — `layout/`, `dashboard/`, `conversations/`, `problem-cards/`, `work-orders/`, `technicians/`, `accounting/`, `knowledge-base/`, `dispatch-queue/`, `admin/`, `ui/`. Generated API types live in `docs/02-design/specs/generated/api.generated.ts` and are imported by domain hooks/clients.

**Sidebar navigation:** Nested nav with `NavItem[]` supporting `children?: NavChild[]`. Active parent auto-expands children.

**Design tokens:** CSS custom properties in `globals.css` — primary `#2563EB`, accent `#F59E0B`. Fonts: Inter + Noto Sans TC. Dark sidebar (`#1E293B`) + light content (`#F8FAFC`).

### API Contract System (`docs/02-design/specs/`)

Machine-readable API contracts as single source of truth for frontend development:

- `openapi.yaml` — REST API 3.1 specification
- `asyncapi.yaml` — WebSocket/SSE/Webhook/Domain Events spec
- `generated/api.generated.ts` — Auto-generated TypeScript types

```bash
# Lint specs
npx @stoplight/spectral-cli lint docs/02-design/specs/openapi.yaml

# Generate TypeScript types
./scripts/generate-api-types.sh

# Start mock server (Prism on port 4010)
./scripts/mock-server.sh

# Validate operationId bidirectionality (specs ↔ docs)
./scripts/check-operationid-orphans.sh
```

CI workflows (`.github/workflows/`): `spec-lint.yml`, `api-types-sync.yml`, `orphan-check.yml`, `mock-smoke.yml` — all gate on spec file changes.

### Web Design Spec Pipeline (`web_design_spec_prompt_pipeline/`)

AI-assisted web development prompt pipeline — converts requirements into structured AI-executable prompts:

- `guides/` — Implementation strategies and QA checklists
- `global/` — Design tokens and brand system templates
- `pages/` — 23 page specs with `MAPPING.md` cross-reference index
- `modules/` — 8 reusable UI module types
- `assembly/` — Pipeline orchestrator for prompt composition
- `design-system-specs/` — Industrial design system (foundations, components, patterns) with Penpot assets

## Documentation

Docs in `docs/` using a 5D framework (DISCOVER → DEFINE → DESIGN → DEVELOP → DELIVER) and TR gate system (TR0–TR10). Key files:
- `docs/05_architecture_and_design_document.md` — System architecture
- `docs/01_development_workflow_cookbook.md` — Dev workflow
- `docs/HOME.md` — Documentation hub

## Post-Commit Progress Report (MANDATORY)

每次 `git commit` 完成後，**必須**立即撰寫一份進度報告，集中**平放**於專案根目錄的 `report/` 資料夾，使用**全專案統一遞增的版本號**命名。

### 規則

1. **觸發時機**：每完成一次 `git commit` 後立即寫入（不可跳過、不可合併到下次 commit 才補）。
2. **存放位置**：所有報告**全部直接放在專案根目錄 `report/` 底下**，**禁止**建立任何子資料夾、**禁止**在檔名加上模組前綴。
   - 影響哪個模組（`agent/quality/`、`agent/agent_tools/`、`agent/product_info/`、`web/...`、`data/...` 等）僅在報告內文 `**影響模組**` 欄位註明
   - 跨模組變更 → 在內文列出全部受影響模組
3. **版本號規則 (Semantic Versioning)**：**全專案共用一條版本序號**，每次新增報告 +1，格式 `vMAJOR.MINOR.PATCH`：
   - **MAJOR**：破壞性變更（API 變動、移除功能、格式不相容）
   - **MINOR**：新增功能、不破壞相容性的擴充
   - **PATCH**：bug 修復、文件/註解調整、refactor、perf 優化
   - 寫入前先 `ls report/v*.md` 取**整個 `report/` 資料夾**最新版號 +1 對應段
   - 同一 commit 只壓一個版本號
4. **檔名格式**：`v{MAJOR.MINOR.PATCH}.md`
   - 首份報告：`v1.0.0.md`
   - 不加模組名、日期、commit SHA、主題；這些一律寫在報告內文
5. **內容範本**：

   ```markdown
   # 進度報告 v{MAJOR.MINOR.PATCH}：{一句話標題}

   - **版本**: v{MAJOR.MINOR.PATCH}（前版：v{previous} → 本版升級類型：MAJOR/MINOR/PATCH）
   - **Commit**: `{sha7}` ({YYYY-MM-DD HH:mm})
   - **分支**: {branch-name}
   - **作者**: {git user.name}
   - **影響模組**: {主要模組}（+ 其他受影響模組，若有）

   ## 變更摘要 (WHAT)
   {1–3 條條列：這次 commit 改了什麼}

   ## 背景與動機 (WHY)
   {為什麼做這個變更，解決什麼問題}

   ## 影響評估 (IMPACT)
   - 破壞性變更：{有/無，若有具體說明}
   - 後續動作：{需要 migration、重跑測試、更新文檔等}

   ## 驗證方式
   {如何確認這次變更正確：跑了什麼測試、人工驗證步驟}

   ## 下一步 (NEXT)
   {接下來要做什麼，或本次未完成項目}
   ```

6. **語言**：使用繁體中文撰寫。
7. **長度**：精簡為主，建議 30–80 行；單純 typo/格式修正可縮至 10 行內。
8. **不寫入的例外**：純機械變更（如 `.gitignore`、lock file 自動更新、commit 訊息修正）可跳過，**不消耗版本號**，但需在下一次正式 commit 的報告內以一行附註說明。
