# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Smart Lock AI Support & Service Dispatch SaaS Platform — a LINE Bot-based AI customer service agent for smart lock troubleshooting, with a Next.js admin dashboard for operations monitoring. Built with a ReAct agent (LangGraph) backed by a `product_info/` mega-doc knowledge base (one self-contained mega-doc per brand+model, sourced strictly from `data/storage/bronze/`), plus a Medallion data pipeline.

On this branch (`refactor/agent-port`) the agent runtime is also equipped with an optional **Belief-Augmented ReAct (Turn Cycle)** prototype — Hypothesize → Decide → Execute → Calibrate — gated by `[turn_cycle].enabled` in `agent/config.toml` (default `false`). See [ADR-0010](docs/1-decisions/ADR-0010-belief-augmented-react.md) and the [Turn Cycle manual](agent/docs/manuals/turn_cycle_belief_augmented_react.md).

Primary language: **Chinese (Traditional)** for all user-facing text, comments, and documentation. Code identifiers and git messages may mix English and Chinese.

## 🔒 Architecture Lock — agent/ 知識庫架構（必讀）

**正典是 `product_info/` mega-doc，不是 `skills/` SKILL.md。** 詳見 [ADR-0008](docs/1-decisions/ADR-0008-product-info-architecture-canonical.md) 與 [Product Info Cutover Audit 2026-05-11](agent/docs/manuals/product_info_cutover_2026-05-11.md)。

| 項目 | ✅ 採用（正典）| ❌ 棄用（2026-05-11 A-3b 起）|
|---|---|---|
| 知識庫格式 | `agent/product_info/{Brand}/{Model}.md` mega-doc | `agent/skills/data/{Brand}/{Model}/skill-name/SKILL.md`（已全部刪除）|
| Agent tool | `load_product_info(name)` | `load_skill(skill_name)`（已退場）|
| Tool module | `agent/agent_tools/tools.py` | `agent/skills/tools.py` |
| Prompt 區塊標題 | `[可用產品資料]` | `[可用技能]` |

**對 AI 助手與新進開發者的硬性約束：**

1. **不准在 `agent/` 內 import `skills`** — `from skills import ...` / `import skills` / `from skills.tools import ...` 全部禁止。本 branch 已於 A-3a 退場 load_skill tool、A-3b 刪除 69 個 SKILL.md，code 已對齊；新增 import 會破壞此狀態。
2. **不准重建 `agent/skills/data/*/SKILL.md`** — 新產品知識一律寫成 `agent/product_info/{Brand}/{Model}.md` mega-doc。
3. **任何「想改回 skills/」的提案** → 先讀 ADR-0008，到 issue tracker 提案徵詢，不要直接 force-push。本 branch 上的 ADR-0008 曾於 2026-05-09 14:42 被 force-push 改標為「SUPERSEDED」；後續 5/11 A-1~A-3b 系列 commit 在本 branch 重新走回原始決議方向。

## 🧪 Experimental Lock — Belief-Augmented ReAct（Turn Cycle）

**本 branch 為 Turn Cycle 實驗 fork**，已於 67 共同題對打跑出 **89.6% strict / 100% pass+partial / 0 fails**（vs `refactor/agent-improvements` agent-port baseline 83.6% strict / 1 fail）。詳見 [ADR-0010](docs/1-decisions/ADR-0010-belief-augmented-react.md)。

**硬性約束：**

1. **預設關**：`[turn_cycle].enabled=false`、`fail_open=true`。production deploy 前需維持此狀態，避免 dual-dispatch 上線回退類事件重演（既往教訓見 commit log）。
2. **Hypothesize / Decide / Calibrate 三檔不准單獨拿出 import** — 必須走 `harness/turn_cycle_runner.run_belief_cycle()` 入口。
3. **policy 閾值**（`agent/policy.py` HIGH=0.55 / GAP=0.15）已由 B-fix-v2 調過，調整需附 quality_check 對打數據。詳見 [Action Policy Thresholds 手冊](agent/docs/manuals/action_policy_thresholds.md)。
4. **本 branch 是否進 production 待後續路線決議**（截至本文，roadmap 走向為 hermes-cs，agent-port 暫為 archive 候選；見 `docs/_audit/runtime-architecture-comparison-2026-05-13-0125.md`）。

## Common Commands

```bash
# Setup — uv workspace (Python 3.11)
# uv 安裝（任一方式）：
#   pip install --user uv
#   pipx install uv
# 一行裝齊三個 module 的所有 deps + dev tools：
uv sync
# 後續任何時候只要 pyproject.toml 改了就重跑 uv sync

# Web dashboard (Node 環境，與 uv 無關)
cd web && npm install

# Run agent (CLI interactive mode — verifies LLM connectivity, no LINE Bot needed)
cd agent && uv run python main.py

# Run FastAPI agent server (LINE webhook mode)
cd agent && uv run uvicorn app:app --reload --port 8000

# 或一鍵起本地開發環境（DB + ngrok + uvicorn，內部會用 uv run）
./scripts/dev/dev-up.sh

# Run REST API backend
cd api && uv run uvicorn main:app --reload --port 8001

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
cd agent && uv run python -m quality.quality_check              # Full: agent + keyword + LLM judge
cd agent && uv run python -m quality.quality_check --no-judge   # Agent answers + keyword match only
cd agent && uv run python -m quality.quality_check --judge-only # Re-score existing quality_report.json
cd agent && uv run python -m quality.quality_check --retry-failed # Retest non-pass cases only

# Skill approval (data pipeline → agent)
uv run python data/pipeline/silver_to_skill/approve_drafts.py --dry-run
uv run python data/pipeline/silver_to_skill/approve_drafts.py --confirm

# Debugging scripts (run from project root — tools auto-add agent/ to sys.path)
# 推薦用 `uv run` 確保 venv 解析正確（不需手動 source .venv/bin/activate）
uv run tests/tools/view_context.py <user_id>   # Inspect checkpoint state
uv run tests/tools/view_facts.py <user_id>     # Inspect user facts
uv run tests/tools/view_logs.py                # Query audit logs
uv run tests/tools/view_corrections.py         # View #資料修正 records
uv run tests/tools/clean_data.py               # DB cleanup
uv run tests/tools/simulate_e2e.py             # E2E simulation

# 若已 activate venv（source .venv/bin/activate）也可直接執行：
# Linux/macOS: ./tests/tools/view_facts.py        (透過 shebang)
# Windows    : python tests\tools\view_facts.py

# Local dev environment (Docker DB + ngrok + uvicorn)
./scripts/dev/dev-up.sh                  # Start everything
./scripts/dev/dev-down.sh                # Tear down (DB container preserved)

# Switch DB target (.env management)
./scripts/env/use-local.sh               # → .env.local (本機 docker)
./scripts/env/use-gcp.sh                 # → .env.gcp (GCP Cloud SQL via proxy)
./scripts/env/use-gcp.sh --fetch         # Refresh .env.gcp from Secret Manager
./scripts/dev/proxy-up.sh                # Start cloud-sql-proxy (for GCP mode)
./scripts/dev/proxy-down.sh              # Stop cloud-sql-proxy

# API smoke test (after uvicorn is up)
ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=changeme123 ./tests/smoke/api.sh

# API contract tooling (run from project root)
./scripts/ci/generate-api-types.sh            # Generate TypeScript types from OpenAPI
./scripts/ci/mock-server.sh                   # Start Prism mock server on port 4010
./scripts/ci/check-operationid-orphans.sh     # Validate spec ↔ docs bidirectionality

# Deployment (Cloud Run)
# Deploy LINE Bot agent
./scripts/deploy/agent.sh                # Full: pre-flight → build → push → deploy → health check
./scripts/deploy/agent.sh --build-only   # Docker image only
./scripts/deploy/agent.sh --deploy-only  # Deploy existing image
./scripts/deploy/agent.sh --update-db-uri # Rebuild POSTGRES_URI from DB_PASSWORD (auto URL encode)

# Deploy FastAPI backend
./scripts/deploy/api.sh                  # Full deploy
./scripts/deploy/api.sh --build-only
./scripts/deploy/api.sh --deploy-only
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

1. **`agent/`** — ReAct Agent backed by `product_info/` mega-doc knowledge base (LINE Bot AI customer service); optional Belief-Augmented ReAct (Turn Cycle) gated by config
2. **`data/`** — Medallion ETL Pipeline (Bronze → Silver SOP drafts; final mega-doc 由業主審稿後手動更新 `agent/product_info/`)
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
          ├─ Inject [可用產品資料] + [用戶資料] + [前情提要] prefixes
          │  └─ (optional, gated by [turn_cycle].enabled)
          │     Belief-Augmented prefix → Hypothesize + Decide → [Belief Hint]
          ├─ Strip stale multimodal from checkpoint
          ├─ agent.ainvoke() with request_timeout (180s)
          │   └─ LLM + tools: load_product_info, update_user_info, transfer_to_human
          ├─ Output validator: check forbidden phrases (H7.5)
          ├─ Calibrate (optional, post-reply) → CalibrationSignal persisted to BeliefState
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
- Mega-docs loaded once at startup from disk (`product_info/`), filtered per-request by user's brand/model
- LLM model string lives in `agent/config.toml` `[llm]` — quality_check and evals read this same config (parity with prod)
- Optional Belief-Augmented pre-pass: when `[turn_cycle].enabled=true`，先跑 Hypothesize + Decide 產 `[Belief Hint]`，附加到 system prompt 前綴。Calibrate 在 reply 後跑，把信號寫回 BeliefState 供下輪 Hypothesize 修正 belief。詳見 [Turn Cycle manual](agent/docs/manuals/turn_cycle_belief_augmented_react.md)。

**Module map:**
- `core/` — Cross-cutting infrastructure: `config.py` (TOML loader), `line_bot.py` (LINE SDK wrapper), `brand_match.py`, `tracing.py`
- `llms/` — Unified LLM via LiteLLM; supports any provider with `"vertex_ai/gemini-..."` style strings
- `memory/` — Checkpointer registry (in-process / SQLite / PostgreSQL)
- `storage/` — Audit log storage registry
- `harness/` — Middleware layers (see table below)
- `agent_tools/` — Agent tools: `load_product_info`, `update_user_info`, `transfer_to_human` + ContextVar helpers
- `product_info/` — Brand-keyed mega-doc knowledge base (`{Brand}/{Model}.md` + `_common/*.md`)
- `belief.py` / `belief_store.py` / `hypothesize.py` / `policy.py` / `calibrate.py` — Belief-Augmented ReAct primitives (BeliefState v2 schema, hypothesizer LLM module, action decision policy, calibration signal classifier)
- `profiles/` — User facts (hard + soft) extraction and storage
- `prompts/` — System prompt and templates
- `quality/` — `quality_check` LLM-as-Judge eval (HTML + JSON reports); supports `--turn-cycle` flag for A/B
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
| H_TC | `turn_cycle.py` + `turn_cycle_runner.py` | Pre-agent (when enabled) | Sync — Hypothesize + Decide → `[Belief Hint]` prefix |

**Checkpoint cleanup** (important for debugging):
- After each `run_agent()`, ToolMessage content (full mega-doc text) is replaced with `[已參考產品資料: {name}]`
- Multimodal HumanMessage content (base64 data) is replaced with `[使用者曾傳送圖片]` references
- This prevents context bloat in long conversations. Use `tests/tools/view_context.py` to inspect state.

### Product Info Knowledge Base (`agent/product_info/`)

**Two-stage loading:**
1. **Startup**: `load_all_docs()` scans `product_info/` for `.md` files, parses YAML frontmatter (`brand`, `model`, `description`), builds in-memory index
2. **Per-request**: `filter_loadable(brand, model)` decides what's loadable → catalog injected as `[可用產品資料]` prefix in user message

**Directory layout (one mega-doc per brand+model, plus `_common/*`):**

```
agent/product_info/
├── _common/                # brand=_common, model=None
│   ├── troubleshoot.md
│   ├── dispatch.md
│   ├── general-knowledge.md
│   └── store-info.md
├── Chatlock/{A90,AI-88,AI-99}.md
├── Dormakaba/                # 16 mega-docs：AS701/AS850/AS901/DP850/...
└── {Philips,Kaadas,Milre,AiLock,3E}/
```

**Sourcing rule (CRITICAL — bronze-only):** all mega-doc content must be derived strictly from `data/storage/bronze/`（YouTube 字幕、website、video transcript）。PDF (GDrive) 不可信，mega-doc 只引 URL 不抄內容。

**Strict profile gating** (`product_info/__init__.py:filter_loadable`): brand+model 齊備 → 可載入 `{Brand}/{Model}` + 全部 `_common/*`；否則只能載 `_common/*`。

詳見 [Product Info Cutover Audit 2026-05-11](agent/docs/manuals/product_info_cutover_2026-05-11.md) — A-1～A-3b 階段切換的完整紀錄。

### Tools (`agent/agent_tools/tools.py`)

Three agent tools, all use `ContextVar` for per-request isolation in async:

| Tool | Purpose | Key behavior |
|------|---------|--------------|
| `load_product_info` | Load mega-doc | Strict profile gate — rejects loads outside `{brand}/{model} + _common/*` |
| `update_user_info` | Set brand/model | Validates via `match_brand()`/`match_model()`, normalizes casing, writes to DB (SCD Type 2), updates ContextVar, returns refreshed product info catalog |
| `transfer_to_human` | Escalate to human | Auto-fills known facts (phone, address, device) into form template; gated by `_doc_loaded_this_run` to prevent premature escalation |

### Belief-Augmented ReAct (Turn Cycle, optional)

新增於本 branch 的實驗模組。**預設關閉** (`[turn_cycle].enabled=false`)。

- `agent/belief.py` — `BeliefState` v2 schema：`primary_intent` / `hypotheses[]`（含 `likely_misframe`）/ `confidence` / `ownership_status` / `next_action` 等
- `agent/belief_store.py` — PostgreSQL 持久化（`belief_states` 表，每 session 一筆，按 turn append）
- `agent/hypothesize.py` — Hypothesize meta-skill：渲染對話歷史 + facts → 呼 LLM → JSON parse → 回 `Hypothesis[]`
- `agent/policy.py` — Action Decision Policy (`decide()`)：拿 BeliefState + threshold（HIGH=0.55 / GAP=0.15）決定 COMMIT / PROBE / EXPLORE / ESCALATE
- `agent/calibrate.py` — Calibrate signal classifier：看客戶下一輪回應分類為 DENY / CONFIRM / ADD / SHIFT / IMPATIENT / NEUTRAL，回灌 Hypothesize 用
- `agent/harness/turn_cycle.py` / `turn_cycle_runner.py` — orchestrator + LLM caller wrapper
- `agent/harness/belief_hint.py` — render `(BeliefState, ActionDecision)` 為 `[Belief Hint]` 字串注入 prompt prefix

詳細手冊：[Turn Cycle / Belief-Augmented ReAct manual](agent/docs/manuals/turn_cycle_belief_augmented_react.md)。設計決議：[ADR-0010](docs/1-decisions/ADR-0010-belief-augmented-react.md)。閾值調整理由：[Action Policy Thresholds](agent/docs/manuals/action_policy_thresholds.md)。

### Profile & Facts System (`agent/profiles/`)

- **Hard facts** (DB, SCD Type 2): `device_brand`, `device_model`, `phone`, `address` — stored in `user_facts` table with versioning
- **Soft facts** (brand-specific, configurable per brand in `config.toml`): `door_type`, `install_date`, `unlock_methods`, etc.
- Facts collected via: Quick Reply buttons (brand/model), `update_user_info` tool (brand/model), LLM extraction post-reply (phone/address)
- Brand/model facts drive product info filtering — missing brand = only `_common/*` mega-docs accessible

### Data Pipeline (`data/pipeline/`)

4-layer Medallion architecture:
1. `source_to_raw/` — Download content (YouTube via yt-dlp, websites via Playwright, Google Drive)
2. `raw_to_bronze/` — Extract and convert (Whisper ASR, Vision LLM for images)
3. `bronze_to_silver/` — Semantic chunking via LLM
4. `silver_to_skill/` — Classify and draft skill candidates (legacy artifact; agent runtime no longer reads `agent/skills/data/`, use `agent/product_info/` directly per the bronze-only rule)

`silver_to_skill/` 仍可跑當輔助線索，但其產物在 A-3b 後不再進 runtime；新產品知識由業主直接審稿/編輯 `agent/product_info/{Brand}/{Model}.md`。

### Database

PostgreSQL 16 with pgvector extension. Schemas in `SQL/`:
- `Schema.sql` — Core tables: users, conversations, messages, problem_cards, manual_chunks, case_entries
- `Schema_harness_migration.sql` — user_facts (SCD Type 2), audit_logs, data_corrections
- `Schema_v2_extensions.sql` — Additional extensions

Two connection string patterns: `POSTGRES_URI` (standard psycopg) for checkpointer/facts/audit, `PG_VECTOR_URI` (psycopg + pgvector) for embeddings.

All DB modules share the same `POSTGRES_URI` but maintain independent `AsyncConnection` instances with `autocommit=True`. Each module has `_ensure_conn()` for automatic reconnection on CloudSQL idle disconnections.

### Configuration Flow

All config centralized in `agent/config.toml`. Key sections: `[system]` (domain, timeout), `[llm]` (model string), `[line_bot]`, `[memory]` (compression settings + Flash model for summaries), `[product_info]`, `[prompts]`, `[safety]`, `[output_validator]`, `[debounce]`, `[multimodal]`, `[user_profile]` (facts_enabled), `[quick_reply]` (brand/model lists — single source of truth for validation), `[data_correction]` (keyword intercept + DB logging), `[opik]`, `[turn_cycle]` (Belief-Augmented ReAct: `enabled`, `fail_open`).

### Deployment

- **Dockerfile** at `agent/Dockerfile` — Python 3.11-slim, uvicorn on port 8080
- **Cloud Run** deployment via `scripts/deploy/agent.sh` — pre-flight checks, builds amd64 image with `{git-sha}-{timestamp}` tag (supports rollback), pushes to Artifact Registry, deploys with Secret Manager + Cloud SQL Unix socket, health check with retry
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

**API integration status:** Active migration from mock data to live API. Many admin/knowledge-base/accounting pages now call generated typed clients (see commits `feat(web): /xxx 串接 ...`). Pages still on mock data are flagged in their components. Treat the OpenAPI spec at `docs/2-contracts/api/openapi.yaml` as source of truth — regenerate types via `./scripts/ci/generate-api-types.sh` after any spec change.

**Component organization:** `src/components/{domain}/` — `layout/`, `dashboard/`, `conversations/`, `problem-cards/`, `work-orders/`, `technicians/`, `accounting/`, `knowledge-base/`, `dispatch-queue/`, `admin/`, `ui/`. Generated API types live in `web/types/api.generated.ts` (resolved via tsconfig `@/types/*` alias) and are imported by domain hooks/clients.

**Sidebar navigation:** Nested nav with `NavItem[]` supporting `children?: NavChild[]`. Active parent auto-expands children.

**Design tokens:** CSS custom properties in `globals.css` — primary `#2563EB`, accent `#F59E0B`. Fonts: Inter + Noto Sans TC. Dark sidebar (`#1E293B`) + light content (`#F8FAFC`).

### API Contract System (`docs/2-contracts/api/`)

Machine-readable API contracts as single source of truth for frontend development:

- `openapi.yaml` — REST API 3.1 specification
- `asyncapi.yaml` — WebSocket/SSE/Webhook/Domain Events spec
- `generated/api.generated.ts` — Auto-generated TypeScript types

```bash
# Lint specs
npx @stoplight/spectral-cli lint docs/02-design/specs/openapi.yaml

# Generate TypeScript types
./scripts/ci/generate-api-types.sh

# Start mock server (Prism on port 4010)
./scripts/ci/mock-server.sh

# Validate operationId bidirectionality (specs ↔ docs)
./scripts/ci/check-operationid-orphans.sh
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
