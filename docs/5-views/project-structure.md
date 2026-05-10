---
title: Project Structure (AI-AUTO)
tier: 5
status: active
last_regenerated: 2026-05-10
generator: manual (sunnydata-auto-regen TBD); from `find` over agent/, api/, data/, web/, SQL/
DO_NOT_EDIT: |
  Tier 5 = AI-AUTO 視圖。手動編輯會在下次 regen 被覆寫。
  如果輸出不對 → 修 generator，不要改本檔。
related:
  - "../1-decisions/module-boundary/{agent,api,data-pipeline,web}.md"
---

# Project Structure

> Auto-derived from filesystem tree. Last regenerated: 2026-05-10.

## Top-level

```
.
├── agent/              # LINE Bot AI agent (Python/FastAPI)
├── api/                # REST/WebSocket backend (Python/FastAPI)
├── data/               # Medallion ETL pipeline + storage
├── web/                # Next.js 15 + React 19 admin/tech frontend
├── SQL/                # DB schema + seeds + migrations
├── scripts/            # CI / dev / deploy / env management
├── tests/              # smoke + tools + bdd (Phase 9 將收 tests/bdd/)
├── docs/               # Documentation (legacy 5D — Phase 8 後 superseded)
├── docs/            # Documentation (NEW VibeCoding 6-tier)
├── web_design_spec_prompt_pipeline/  # Pipeline 工具 (legacy — pipelined 已遷 docs/)
├── VibeCoding_Workflow_Templates/    # 模板 source-of-truth
├── .claude/            # Claude Code agents/skills/rules/hooks
├── .github/workflows/  # CI workflows
└── 配置文件 (CLAUDE.md, README.md, pyproject.toml, ...)
```

## agent/ — LINE Bot AI Agent

```
agent/
├── app.py              # FastAPI webhook entry
├── agent.py            # ReAct agent with 3 tools (load_skill / update_user_info / transfer_to_human)
├── main.py             # CLI mode
├── config.toml         # 全部 runtime config
├── core/               # Cross-cutting infra (config loader, line_bot wrapper)
├── llms/               # LiteLLM unified interface
├── memory/             # Checkpointer registry (in-process / SQLite / PostgreSQL)
├── storage/            # Audit log storage registry
├── harness/            # Middleware H1-H12 (debounce, multimodal, safety_gate, output_validator, ...)
├── skills/             # Skill loader + 3 tools
│   └── data/           # SKILL.md tree by brand/model
│       ├── _common/    # Universal skills
│       ├── Chatlock/{_all-models, AI-99/, ...}
│       ├── Dormakaba/_all-models/
│       └── ... (Milre, Philips, Kaadas, AiLock, 3E, Waferlock)
├── profiles/           # User facts (hard SCD2 + soft per-brand)
├── prompts/            # System prompt + templates
├── notifications/      # Channel adapters (LINE / FCM / Email / SMS)
├── integrations/       # External system clients (admin_api)
├── embeddings/         # Embedding service wrappers
├── quality/            # quality_check (LLM-as-Judge eval)
└── evals/              # Golden-set regression pipeline (runner → judge → reporter)
```

## api/ — REST Backend

```
api/
├── main.py             # FastAPI app entry
├── core/               # auth, db, config, exceptions
├── middleware/         # JWT, RBAC, tenant context
├── models/             # Pydantic + SQLAlchemy models
├── routers/            # API endpoint definitions (per resource)
├── services/           # Business logic
├── realtime/           # WebSocket / SSE handlers
├── agent/integrations/ # Agent ↔ API bridge
├── data/               # In-process media storage
└── tests/              # pytest tests
```

## data/ — Medallion Pipeline

```
data/
├── config.toml
├── pipeline/
│   ├── source_to_raw/      # Download (yt-dlp / Playwright / Google Drive)
│   ├── raw_to_bronze/      # Whisper ASR / Vision LLM / PDF parse
│   ├── bronze_to_silver/   # LLM semantic chunking
│   └── silver_to_skill/    # Classify + draft + approve → SKILL.md
└── storage/
    ├── raw/{youtube, video, website, line_chat, gdrive}/
    ├── bronze/{...}/
    └── silver/{...}/
```

## web/ — Next.js Frontend

```
web/
├── src/app/            # Next.js App Router (52 page.tsx files)
│   ├── dashboard, conversations, problem-cards, work-orders, technicians, accounting, settings
│   ├── knowledge-base/{cases, manuals, sop-drafts, family-reviews}
│   ├── admin/{refunds, roles, inventory, audit-events, warranty-claims, disputes,
│   │         customers/{[id]}, dispatch-queue, dispatch-manual,
│   │         reports/{kpi, revenue, technician-ranking},
│   │         knowledge-base/sop-performance, sentiment-alerts, schedule-requests, api-status}
│   ├── pool, my-orders/{[id]/{delay,door-check,material-request,reschedule,scope-change,signature}}
│   ├── account/{schedule}
│   ├── login, tech-login
│   ├── scope-change/[token]/, track/[token]/
│   ├── notifications, work-orders/{[id], kanban, map}
│   └── page.tsx (root)
├── src/components/     # 依 domain 組織（layout, dashboard, conversations, ...）
├── src/lib/            # API client, utils
├── types/api.generated.ts  # 自動生成 (從 openapi.yaml)
└── public/
```

## 統計

- Python file count: 200
- TypeScript file count: 161
- Web routes (page.tsx): 61
- SKILL.md files: 67
- Test files: 25

## 變更紀錄

| 日期 | 變更 |
| :--- | :--- |
| 2026-05-10 | 初版 — Phase 7 完成後手動 regen |
