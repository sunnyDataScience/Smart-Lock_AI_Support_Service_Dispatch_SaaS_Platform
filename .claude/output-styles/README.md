# Output Styles

> ⚠️ **2026-08-06 註記**：`vibecoding-*` skill（14 個）已刪除，本檔引用已全數改指 `sunnydata-*`
> （刪除理由見 `rules/primitive-selection.md` §Cleanup history）。
> `.gitignore` 排除 `.claude/skills/`，其中 16 個 skill 只存在本機、不隨 repo 散佈；
> 實裝清單與版控狀態見 `skills/INDEX.md`。

> **See `.claude/rules/primitive-selection.md` for the full command vs skill vs output-style decision rule.**
>
> **As of v4 (2026-05-10):** 14 of the original 15 output-styles were converted into Skills. Only true behavioral modes remain here.

## Why the change

Output styles in Claude Code's harness **replace the system prompt** for the entire session — they're meant for switching the AI's persona/voice (e.g., "explain visually" mode, "Socratic tutor" mode), not for one-off task templates.

The original `01-prd-product-spec` through `14-ci-quality-gates` were really **task templates** that should activate when the user requests them, not stay active for the whole session. Forcing them through `output-style` meant constantly switching modes mid-conversation.

In v4 they were migrated to Skills under `.claude/skills/vibecoding-*/`. Those 14 skills were **deleted 2026-08-06** (their `VibeCoding_Workflow_Templates/` backing was removed in the 2026-07-08 cleanup, leaving empty shells). The conclusion still holds: task templates belong in skills or in direct writing, never in an output-style.

## What remains

| File | Purpose |
|---|---|
| `Vision-output.md` | Genuine output mode: forces visualization-first responses (diagrams, comparisons, tables) instead of code |
| `Apprentice-output.md` | Cognitive Apprenticeship mode: every code change includes decision chains, tradeoff reasoning, and decision previews so engineers learn alongside AI |

Activate with `/output-style Vision-output` or `/output-style Apprentice-output`.

## Migration map (old output-style → today)

The 2026-05-10 `vibecoding-*` skills are gone (2026-08-06). Current routing:

| Old `/output-style` | Today |
|---|---|
| `01-prd-product-spec` | Write directly (tier-4; see `rules/context-stability.md`) |
| `02-bdd-scenario-spec` | `sunnydata-testing` |
| `03-architecture-design-doc` | `sunnydata-architecture-review` / `architect` agent + a new ADR |
| `04-ddd-aggregate-spec` | `architect` agent; write directly |
| `05-api-contract-spec` | `sunnydata-api-design` + `api/openapi.yaml` (machine-readable SSOT) |
| `06-tdd-unit-spec` | `sunnydata-testing` |
| `07-code-review-checklist` | `sunnydata-code-review` |
| `08-security-checklist` | `sunnydata-security` |
| `09-database-schema-spec` | Write directly; CIA gate applies (`rules/change-governance.md`) |
| `10-backend-python-impl` | Write directly, following `rules/coding-style.md` |
| `11-frontend-component-bdd` | `sunnydata-testing` |
| `12-integration-contract-suite` | `sunnydata-testing` |
| `13-data-contract-evolution` | `sunnydata-api-design`; CIA gate applies |
| `14-ci-quality-gates` | `sunnydata-infrastructure` |

Lesson worth keeping: a skill whose whole value is "follow this external template" dies with the template. Skills must be self-contained.

## Adding a new output style

Only add a new file here if the user wants a **persistent voice/format change** for the whole session. If you find yourself writing one that says "produce X structured doc", it should be a Skill, not an output style.

Reference: `Vision-output.md` is the model for how an output style is shaped.
