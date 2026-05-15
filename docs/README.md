---
title: Smart Lock AI SaaS — Documentation
status: active
last_updated: 2026-05-15
related:
  - "../VibeCoding_Workflow_Templates/INDEX.md"
  - "../VibeCoding_Workflow_Templates/OWNERSHIP-MATRIX.md"
  - "../.claude/rules/context-stability.md"
  - "../.claude/rules/change-governance.md"
---

# Smart Lock AI SaaS — Documentation

> 採 VibeCoding **6-tier stability** 架構。tier 編號越小 = 越穩定 / 越權威 / AI 越早載入。

## 6-tier 結構

| Tier | 目錄 | 角色 | 更新頻率 |
| :--: | :-- | :-- | :-- |
| **0** | [`0-principles/`](./0-principles/) | 不變定律 — Mission, glossary, quality bars, ID 慣例 | 半年-年 |
| **1** | [`1-decisions/`](./1-decisions/) | append-only 判斷 — ADR、架構總覽、模組邊界 | 變更才寫新檔 |
| **2** | [`2-contracts/`](./2-contracts/) | 介面契約 — OpenAPI、Module、Flow、FR、State machine | **必與 code 同步** |
| **3** | [`3-process/`](./3-process/) | 工作流程 — Workflow、code review、quality gate、test plan、runbook | 半年 |
| **4** | [`4-exploration/`](./4-exploration/) | 一次性意圖 — PRD、SOW、WBS、CR | per-task |
| **5** | [`5-views/`](./5-views/) | code 衍生視圖 — project structure、deps、route map | refactor 後 AUTO |

**特例**：
- [`_archive/`](./_archive/) — legacy/ + extras/（不再維護，2026-05-15 歸檔）

## File Inventory (PREFIX-NNNN)

### Tier 0 — `0-principles/`
| File | Description |
|------|-------------|
| `GLOS-0001-glossary.md` | 術語 SSOT |
| `PRIN-0001-product-principles.md` | Mission / 非任務 / 品質基準 |
| `PRIN-0002-frontend-quality-attributes.md` | 前端效能 SLA |
| `PRIN-0003-technician-skill-taxonomy.md` | 技師技能分類 |
| `PRIN-0004-flow-id-conventions.md` | BF/UF/SF/FR/... 9-prefix ID 慣例 |

### Tier 1 — `1-decisions/`
| File | Description |
|------|-------------|
| `ADR-0001` ~ `ADR-0025` | Architecture Decision Records |
| `ARCH-0001-architecture-overview.md` | 系統 C4 架構總覽 |
| `DDD-0001-domain-model.md` | Domain model |
| `module-boundary/ARCH-0002~0005` | Module boundaries (agent, api, web, data-pipeline) |
| `releases/v*.md` | 85 release notes (v1.0.0 ~ v1.40.0) |

### Tier 2 — `2-contracts/`
| Subdirectory | Prefix | Count |
|---|---|---|
| `api/` | API-0001 (error codes) + openapi.yaml + asyncapi.yaml | 3+2 |
| `flows/` | BF-0000~0003, SF-* | (existing, untouched) |
| `functional-requirements/` | FR-0001~0025 | 25 |
| `modules/` | MC-0001~0023 | 23 |
| `pages/` | PC-A0/A1/A12/G1~G4/T0/T1/T3 | 10 |
| `frontend-design-system/` | DS-0000~0099 | 6 |
| `master-data/` | MDS-0001~0005 | 5 |
| `state-machines/` | SM-0001~0002 | 2 |
| `test-cases/` | TC-* | (existing, untouched) |

### Tier 3 — `3-process/`
| File | Description |
|------|-------------|
| `QG-0001-quality-gates.md` | Gate 0-4 + GR6/7/10 |
| `TP-0001-test-plan.md` | Test strategy |
| `PROC-0001-code-review-checklist.md` | Code review |
| `PROC-0002-ai-design-playbook.md` | AI design playbook |
| `PROC-0003-bdd-guide.md` | BDD guide |
| `PROC-0005-frontend-pre-merge-checklist.md` | Frontend pre-merge |
| `PROC-0006-photo-evidence-standards.md` | Photo evidence |
| `PROC-0007-deployment-runbook.md` | Deployment SOP |
| `PROC-0008-vendor-api-test-requirement.md` | Vendor API test |
| `PROC-0009-workflow-manual.md` | Workflow manual |
| `PROC-0010-security-readiness-checklist.md` | Security readiness |
| `bdd/PROC-0004-all-features.md` | BDD features |

### Tier 4 — `4-exploration/`
| File | Description |
|------|-------------|
| `PRD-0001-2026-q1-v1-launch.md` | V1 PRD |
| `SOW-0001-2026-q1.md` | Q1 SOW |
| `WBS-0001-2026-q1.md` | Q1 WBS |
| `WBS-0002-2026-q2-tactical-refactor.md` | Q2 tactical refactor |
| `WBS-0003-phase-3.3-backlog-2026-q2.md` | Phase 3.3 backlog |
| `WBS-0004-phase-5-flow-index-backlog-2026-q2.md` | Phase 5 flow index |
| `BIZ-0001-executive-architecture-overview.md` | Executive architecture |
| `BIZ-0002-moat-system-architecture.md` | Moat system architecture |
| `BIZ-0003-moat-mapping-matrix.md` | Moat mapping matrix |
| `BIZ-0004-presentation-blueprint.md` | Presentation blueprint |

### Tier 5 — `5-views/`
| File | Description |
|------|-------------|
| `VIEW-0001-class-relationships.md` | Class relationships |
| `VIEW-0002-file-dependencies.md` | File dependencies |
| `VIEW-0003-frontend-route-map.md` | Frontend route map |
| `VIEW-0004-project-structure.md` | Project structure |
| `VIEW-0005-traceability-matrix.md` | Traceability matrix |

## Reading Paths

### Path A — 新人 / 新對話
1. [`0-principles/PRIN-0001-product-principles.md`](./0-principles/PRIN-0001-product-principles.md) — Mission / 非任務 / 品質基準
2. [`0-principles/GLOS-0001-glossary.md`](./0-principles/GLOS-0001-glossary.md) — 術語 SSOT
3. [`1-decisions/ARCH-0001-architecture-overview.md`](./1-decisions/ARCH-0001-architecture-overview.md) — 系統 C4
4. [`3-process/PROC-0009-workflow-manual.md`](./3-process/PROC-0009-workflow-manual.md) — 怎麼做事

### Path B — 改 API / 改 Flow
1. [`.claude/rules/change-governance.md`](../.claude/rules/change-governance.md) — 是否要 CR
2. [`2-contracts/api/openapi.yaml`](./2-contracts/api/openapi.yaml) — REST 契約
3. [`2-contracts/api/asyncapi.yaml`](./2-contracts/api/asyncapi.yaml) — Async 契約
4. [`2-contracts/flows/`](./2-contracts/flows/) — BF / SF
5. [`2-contracts/modules/`](./2-contracts/modules/) — 模組 contract

### Path C — 規劃功能
1. [`4-exploration/PRD-0001-2026-q1-v1-launch.md`](./4-exploration/PRD-0001-2026-q1-v1-launch.md) — V1 PRD
2. 起新 PRD：`vibecoding-write-prd` skill → `4-exploration/prd-YYYY-QN-*.md`
3. 起新 CR：`sunnydata-change-impact-analysis` skill

### Path D — Operate / Deploy
1. [`3-process/PROC-0007-deployment-runbook.md`](./3-process/PROC-0007-deployment-runbook.md) — 部署 SOP
2. [`3-process/PROC-0010-security-readiness-checklist.md`](./3-process/PROC-0010-security-readiness-checklist.md) — 上線前
3. [`3-process/QG-0001-quality-gates.md`](./3-process/QG-0001-quality-gates.md) — Gate 0-4 + GR6/7/10

### Path E — 投資人 / Stakeholder
1. [`4-exploration/BIZ-*`](./4-exploration/) — 簡報、moat 分析（BIZ-0001~0004）

## 文件治理

- **AI 處理規則**：[`.claude/rules/context-stability.md`](../.claude/rules/context-stability.md)
- **變更必經 CR**：[`.claude/rules/change-governance.md`](../.claude/rules/change-governance.md)
- **誰寫誰改**：[VibeCoding OWNERSHIP-MATRIX](../VibeCoding_Workflow_Templates/OWNERSHIP-MATRIX.md)
- **frontmatter 規範**：[VibeCoding HOW-TO-INSTANTIATE](../VibeCoding_Workflow_Templates/HOW-TO-INSTANTIATE.md)
