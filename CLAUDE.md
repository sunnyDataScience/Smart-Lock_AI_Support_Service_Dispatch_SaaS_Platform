# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Smart Lock AI Support & Service Dispatch SaaS Platform — a LINE Bot-based AI customer service agent for smart lock troubleshooting, with a Next.js admin dashboard for operations monitoring. Built with a skill-based ReAct agent (LangGraph) and a Medallion data pipeline that produces SKILL.md knowledge files.

Primary language: **Chinese (Traditional)** for all user-facing text, comments, and documentation. Code identifiers and git messages may mix English and Chinese.

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
          │   └─ LLM + tools: load_skill, update_user_info, transfer_to_human
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
- Uses `langgraph.prebuilt.create_react_agent` with 3 tools: `load_skill`, `update_user_info`, `transfer_to_human`
- System prompt loaded from `prompts/system.md`; skill list injected dynamically per-request (not in static prompt)
- Skills loaded once at startup from disk, filtered per-request by user's brand/model

**Registry pattern** — LLM, memory, storage, and embeddings are selected via config, not hardcoded:
- `llms/` — Unified LLM via LiteLLM; supports any provider with `"vertex_ai/gemini-2.5-pro"` style strings
- `memory/__init__.py` — Checkpointer registry (in-process / SQLite / PostgreSQL)
- `storage/__init__.py` — Audit log storage registry

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

### Skills System (`agent/skills/`)

**Two-stage loading:**
1. **Startup**: `load_skills()` scans `skills/data/` for SKILL.md files, parses frontmatter, infers brands/models from directory path
2. **Per-request**: `filter_skills(brand, model)` narrows to applicable skills → injected as `[可用技能]` prefix in user message

**Brand-based hierarchy:**

```
skills/data/
├── _common/           # brands=None (universal) — troubleshoot, dispatch-guide, store-info
├── Chatlock/
│   ├── _all-models/   # brands=["Chatlock"] — ts-*-chatlock, app-guide, system-settings
│   └── AI-99/         # brands=["Chatlock"], models=["AI-99"] — app-battery, app-camera
├── Dormakaba/_all-models/
└── ...
```

**Key concepts:**
- **Path-based metadata** (`skills/__init__.py`): `_common/` = universal; `{Brand}/_all-models/` = brand-wide; `{Brand}/{Model}/` = model-specific. Never hardcoded in frontmatter.
- **Skill filtering** (`filter_skills()`): Brand unknown → only `_common` skills returned. Brand known → `_common` + matching brand skills. Brand + model known → `_common` + brand-wide + model-specific.
- **Sub-skill routing**: Router skills (e.g., `troubleshoot`) direct the agent to load brand-specific sub-skills. Sub-skills with prefixes `ts-*`, `app-*`, `ss-*` are hidden from the top-level skill list (exceptions: `app-guide`, `ss-dormakaba`).
- **Prefix matching fallback** (`tools.py`): `load_skill("ts-door-stuck")` with no exact match → returns list of `ts-door-stuck-*` sub-skills for agent to choose from.
- **Brand gate**: `load_skill()` blocks loading brand-specific skills when user brand is unknown or mismatched.
- **SKILL.md format**: YAML frontmatter (`name`, `description`, `trigger_keywords`, `category`, `severity`) + Markdown SOP body.

### Tools (`agent/skills/tools.py`)

Three agent tools, all use `ContextVar` for per-request isolation in async:

| Tool | Purpose | Key behavior |
|------|---------|--------------|
| `load_skill` | Load SOP content | Brand gate + prefix matching fallback |
| `update_user_info` | Set brand/model | Validates against `config.toml` brands via `match_brand()`/`match_model()`, normalizes casing, writes to DB, updates ContextVar, returns refreshed skill list |
| `transfer_to_human` | Escalate to human | Auto-fills known facts (phone, address, device) into form template |

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
4. `silver_to_skill/` — Classify, draft, and approve SKILL.md files → output to `agent/skills/data/`

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
- **Cloud Run** deployment via `scripts/deploy/agent.sh` — pre-flight checks, builds amd64 image with `{git-sha}-{timestamp}` tag (supports rollback), pushes to Artifact Registry, deploys with Secret Manager + Cloud SQL Unix socket, health check with retry
- **DB URI management**: `deploy.sh --update-db-uri` reads `DB_PASSWORD` from Secret Manager, auto URL-encodes, constructs `POSTGRES_URI` with round-trip validation. Never manually construct POSTGRES_URI.
- Secrets managed via GCP Secret Manager: `LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN`, `DB_PASSWORD`, `POSTGRES_URI`, `OPIK_API_KEY`, `OPIK_WORKSPACE`
- **Health endpoint** (`/health`): checks facts_db + audit_db connectivity. Returns 200 (ok) or 503 (degraded) with `checks` detail.
- **DB resilience**: All 4 DB modules use `autocommit=True` + `_ensure_conn()` auto-reconnect. CloudSQL idle disconnections are handled transparently.

### Web Admin Dashboard (`web/`)

Next.js 15 + React 19 + TypeScript admin dashboard for operations teams.

**Tech stack:** Next.js 15 (App Router), React 19, Tailwind CSS 4, Recharts (charts), Lucide (icons). Path alias `@/*` → `./src/*`. No UI component library — all custom components with Tailwind CSS.

**Implemented pages:**

| Route | Purpose |
|-------|---------|
| `/` | Redirects to `/dashboard` |
| `/dashboard` | KPI cards, work order trend chart, technician status pie chart |
| `/conversations` | Customer conversation list with search/filter |
| `/conversations/[id]` | Chat timeline (AI/customer bubbles), customer info sidebar |
| `/problem-cards` | Problem card list with status/resolution level |
| `/problem-cards/[id]` | FMEA diagnosis chain, L1/L2/L3 resolution timeline, linked conversation |
| `/work-orders` | Work order list with filters |
| `/work-orders/[id]` | Work order detail with sidebar |
| `/work-orders/kanban` | Kanban board view |
| `/work-orders/map` | Map view with work order panel |
| `/technicians` | Technician list with table |
| `/technicians/[id]` | Technician detail with sidebar |
| `/accounting` | Settlement dashboard with tables |
| `/accounting/invoices` | Invoice management table |
| `/accounting/revenue` | Revenue charts (brand breakdown, service type) |
| `/knowledge-base` | Redirects to `/knowledge-base/cases` |
| `/knowledge-base/cases` | Case library with card grid |
| `/knowledge-base/manuals` | Manuals table |
| `/knowledge-base/sop-drafts` | SOP draft list |
| `/knowledge-base/sop-drafts/[id]` | SOP draft review detail |
| `/admin/dispatch-queue` | Dispatch queue monitoring (stuck/retry/timeout stats) |
| `/admin/refunds` | Refund review queue with SLA countdown |
| `/admin/warranty-claims` | Warranty claims with status/remaining days |
| `/admin/disputes` | Dispute resolution with dual evidence panel |
| `/admin/inventory` | Inventory management with stock alerts |
| `/admin/reports/kpi` | KPI dashboard (funnel, SLA rings, NPS, scatter plot) |
| `/admin/reports/revenue` | Revenue report with trend chart and pivot table |
| `/admin/reports/technician-ranking` | Technician leaderboard with podium |
| `/admin/knowledge-base/sop-performance` | SOP performance (placeholder) |
| `/admin/audit-events` | Audit log with expandable JSON detail |
| `/admin/roles` | RBAC role cards + permission matrix |
| `/admin/customers` | Customer master file with risk and warranty indicators |
| `/settings` | System settings with 4-tab layout |

All 33 pages implemented. Frontend-only with mock data — no API integration with agent backend yet.

**Component organization:** `src/components/{domain}/` — `layout/` (Sidebar, Header), `dashboard/` (KpiCard, charts), `conversations/` (ChatTimeline, ConversationsTable), `problem-cards/` (FmeaDiagnosisCard, ResolutionTimeline), `work-orders/` (KanbanBoard, MapView, WorkOrdersTable), `technicians/` (TechniciansTable, TechnicianDetailSidebar), `accounting/` (SettlementTable, InvoicesTable, revenue charts), `knowledge-base/` (CaseCardGrid, ManualsTable, SopDraftsList), `dispatch-queue/` (DispatchQueueTable), `admin/` (RefundReviewTable, WarrantyClaimsTable, InventoryTable), `ui/` (StatusBadge, SolidBadge).

**Sidebar navigation:** Nested nav with `NavItem[]` supporting `children?: NavChild[]`. Groups: 派工管理 (2), 帳務與結算 (4), 知識庫 (3), 報表中心 (4), 稽核與權限 (2). Active parent auto-expands children.

**Design tokens:** CSS custom properties in `globals.css` — primary `#2563EB`, accent `#F59E0B`. Fonts: Inter + Noto Sans TC. Dark sidebar (`#1E293B`) + light content (`#F8FAFC`).

**Current state:** Frontend-only with mock data. No API integration with agent backend yet. API contracts defined in `docs/02-design/specs/` will drive future integration.

### API Contract System (`docs/02-design/specs/`)

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
