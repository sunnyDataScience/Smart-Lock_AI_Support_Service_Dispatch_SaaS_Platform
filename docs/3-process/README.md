---
title: 3-process — 工作流程與品質閘
tier: 3
status: active
last_updated: 2026-05-10
---

# Tier 3 — Process (How We Work)

> 變更頻率：**半年**。
> 寫入：HUMAN-ONLY（流程 = 治理選擇）。

## 包含

| 檔案 | 角色 | 來源 |
| :-- | :-- | :-- |
| `workflow-manual.md` | 全流程：full vs MVP mode | `docs/02-design/E6--development-workflow-cookbook.md` |
| `bdd-guide.md` | BDD 方法論 | copy from VibeCoding template |
| `code-review-checklist.md` | 程式碼審查標準 | `docs/02-design/E6x--code-review-and-refactoring.md` |
| `security-readiness-checklist.md` | 上線前安全檢查 | `docs/04-deliver/E8--security-and-readiness-checklists.md` + `_flows-bdd-test/v-model-right/security-checklist.md` |
| `deployment-runbook.md` | 部署 SOP（Cloud Run、Secret Manager、DB migration）| `docs/04-deliver/E9--deployment-and-operations-guide.md` |
| `docs-maintenance-guide.md` | 文件治理 | `docs/04-deliver/E9x--documentation-and-maintenance.md` + 6-tier 規則 |
| `quality-gates.md` | TR0-TR10 / GR6/7/10 / Gate 0-4 階段門檻 | `docs/GATE-MAP.md` + `03-develop/GR6-7` + `04-deliver/GR10` 整合（CR-0001 D2）|
| `test-plan.md` | 測試金字塔 / coverage / integration / performance | `docs/_flows-bdd-test/v-model-right/{E7x,integration-test-matrix,performance-baseline}.md` |
| `vendor-api-test-requirement.md` | 每 vendor 測試前置 | copy from VibeCoding template |
| `frontend-pre-merge-checklist.md` | 前端 PR 前自我檢查 | `web_design_spec_prompt_pipeline/guides/quality_checklist.md` + `references/prereq_document_checklist.md` |
| `ai-design-playbook.md` | Pencil + Figma MCP + Claude Code 工業化設計 SOP | `web_design_spec_prompt_pipeline/design-system-specs/AI_DESIGN_INDUSTRIAL_PLAYBOOK.md` |
| `knowledge-asset-review-checklist.md` | SKILL.md 審核 | `docs/02-design/agent-harness/knowledge-asset-review-checklist.md` |
| `photo-evidence-standards.md` | 完工照片拍攝規範 | `docs/_domain-knowledge/locksmith-checklist/16_完工照片拍攝規範.md` |

## 規則

- 流程文件 = SOP；改 SOP 要 review，不可 AI 自改
- TR-gate（投資人視角）↔ quality-gate（工程視角）映射在 `quality-gates.md §TR-mapping`
- `quality-gates.md` 是 CR-0001 D2 的落地點：保留 TR 文化但工程統一 quality-gate
