---
title: Smart Lock AI SaaS — Documentation
status: active
last_updated: 2026-05-10
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
- [`4-exploration/`](./4-exploration/) — 商業 / 募資 / 簡報素材（BIZ-0001~0004）
- [`_archive/`](./_archive/) — legacy + extras（不再維護）

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
1. [`4-exploration/`](./4-exploration/) — 簡報、moat 分析

## 文件治理

- **AI 處理規則**：[`.claude/rules/context-stability.md`](../.claude/rules/context-stability.md)
- **變更必經 CR**：[`.claude/rules/change-governance.md`](../.claude/rules/change-governance.md)
- **誰寫誰改**：[VibeCoding OWNERSHIP-MATRIX](../VibeCoding_Workflow_Templates/OWNERSHIP-MATRIX.md)
- **frontmatter 規範**：[VibeCoding HOW-TO-INSTANTIATE](../VibeCoding_Workflow_Templates/HOW-TO-INSTANTIATE.md)
