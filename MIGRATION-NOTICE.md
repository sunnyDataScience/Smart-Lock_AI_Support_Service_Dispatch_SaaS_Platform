# 📦 Documentation Migration Notice

**As of 2026-05-10, the project's documentation has been migrated to a new 6-tier structure under `docs_v2/`.**

---

## TL;DR

| Item | Old (deprecated) | New (active) |
| :-- | :-- | :-- |
| Hub | `docs/HOME.md` | [`docs_v2/README.md`](docs_v2/README.md) |
| Architecture | `docs/01-define/E3--*.md` + `docs/01-define/diagrams/*` | [`docs_v2/1-decisions/architecture-overview.md`](docs_v2/1-decisions/architecture-overview.md) |
| ADRs | `docs/01-define/adrs/adr-NNN-*.md` | [`docs_v2/1-decisions/ADR-NNNN-*.md`](docs_v2/1-decisions/) (22 ADRs) |
| API Contract | `docs/02-design/specs/openapi.yaml` | [`docs_v2/2-contracts/api/openapi.yaml`](docs_v2/2-contracts/api/openapi.yaml) |
| Module Specs | `docs/02-design/specs/*-spec.md` | [`docs_v2/2-contracts/modules/`](docs_v2/2-contracts/modules/) (26 modules) |
| Flows | `docs/_flows-bdd-test/v-model-left/E5x--workflow-*.md` | [`docs_v2/2-contracts/flows/business/`](docs_v2/2-contracts/flows/business/) (4 BF) + [`flows/sub/`](docs_v2/2-contracts/flows/sub/) (22 SF) |
| Functional Reqs | `docs/_flows-bdd-test/north-star-requirements.md` | [`docs_v2/2-contracts/functional-requirements/`](docs_v2/2-contracts/functional-requirements/) (FR-0001~0025) |
| Pages | `web_design_spec_prompt_pipeline/pages/*.md` | [`docs_v2/2-contracts/pages/`](docs_v2/2-contracts/pages/) (53 page-contracts) |
| Test Plan | `docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md` | [`docs_v2/3-process/test-plan.md`](docs_v2/3-process/test-plan.md) |
| Domain Knowledge | `docs/_domain-knowledge/locksmith-checklist/*` | Split: [`docs_v2/0-principles/glossary.md`](docs_v2/0-principles/glossary.md) + [`docs_v2/2-contracts/master-data/`](docs_v2/2-contracts/master-data/) + (data/, SQL/seed/ 待 CR-0006) |

---

## Why?

`docs/` 與 `web_design_spec_prompt_pipeline/` 共 254 檔存在 **三套並行的 taxonomy**：
1. 5D + TR-Gate (00-discover ~ 04-deliver)
2. VibeCoding 6-tier (新規範)
3. Pipeline structure (global/pages/modules/assembly)

導致 AI slop（讀錯版本、重複內容、矛盾敘述）+ 認知負擔。

CR-0001 統一到 VibeCoding 6-tier：

```
0-principles/  ← 不變定律 (mission, glossary, ID conventions)
1-decisions/   ← append-only (ADR, architecture overview, module boundary)
2-contracts/   ← 必與 code 同步 (API, modules, flows, FR, pages, master-data)
3-process/     ← 工作流程 (workflow, code-review, test-plan, runbook)
4-exploration/ ← per-task 一次性 (PRD, WBS, CR/CIA, audit, meeting)
5-views/       ← code 衍生視圖 (project-structure, deps, route-map — AUTO)
```

---

## Status

- ✅ **CR-0001 結構性遷移完成** (18 commits, 339 files in `docs_v2/`, 0 broken refs)
- ⏸ Phase 8a (CR-0007) docs/ supersede — **本 notice 即為其一部分**
- ⏸ Phase 8b (CR-0009) CI 路徑雙寫過渡 — 待 PM 拍板
- ⏸ Phase 9 (CR-0008) docs/ 刪除 + docs_v2/ → docs/ rename — 90 天觀察期後 (2026-08-10)
- ⏸ CR-0006 PII / agent skill data / data/ 搬離 docs — 待 ops 對齊

---

## For Contributors

### Reading existing docs
- Look in `docs_v2/` first
- `docs/` is **read-only legacy**; PRs to `docs/` will be rejected (except for fixing typos in superseded notices)
- Wikilinks may still point to old paths; the 90-day observation period allows external references to migrate

### Writing new docs
- Use the 6-tier structure under `docs_v2/`
- If unsure which tier, see [`docs_v2/4-exploration/audits/vibecoding-mapping-table-2026-05-10.md`](docs_v2/4-exploration/audits/vibecoding-mapping-table-2026-05-10.md)
- For changes touching contracts/flows/data/architecture, **must run `sunnydata-change-impact-analysis` skill first** (per `.claude/rules/change-governance.md`)

### AI / Claude Code behavior
- `.claude/rules/context-stability.md` defines tier loading priority
- `docs/` is treated as `status: superseded`; AI should prefer `docs_v2/`
- See [`docs_v2/3-process/migration-cutover-runbook.md`](docs_v2/3-process/migration-cutover-runbook.md) for full handover process

---

## Key Documents

- [Hub](docs_v2/README.md)
- [CR-0001 (parent migration CR)](docs_v2/4-exploration/change-requests/CR-0001-vibecoding-6tier-migration.md)
- [CR-0007 (docs/ supersede cutover)](docs_v2/4-exploration/change-requests/CR-0007-docs-supersede-cutover.md)
- [CR-0008 (docs/ → docs_v2/ rename)](docs_v2/4-exploration/change-requests/CR-0008-docs-final-rename.md)
- [CR-0009 (CI path update)](docs_v2/4-exploration/change-requests/CR-0009-ci-path-update.md)
- [Migration Cutover Runbook](docs_v2/3-process/migration-cutover-runbook.md)
- [Consistency Audit](docs_v2/4-exploration/audits/docs_v2-consistency-audit-2026-05-10.md)
- [VibeCoding Templates Source](VibeCoding_Workflow_Templates/INDEX.md)

---

## Timeline

| Date | Event |
| :-- | :-- |
| 2026-05-10 | CR-0001 完成 (18 commits) + CR-0007 partial cutover (本 notice + HOME/GATE redirect banners) |
| 2026-05-10 ~ 2026-08-10 | 90-day observation period |
| 2026-08-10 (預計) | CR-0008 final rename: `git rm docs/` + `git mv docs_v2 docs` |
| 2026-08-10 (預計) | bdd scenarios 從 `docs_v2/3-process/bdd/all-features.md` 拆 16 個 `.feature` 進 `tests/bdd/` |

---

🤖 Generated as part of CR-0001 Phase 8a partial cutover (2026-05-10).
