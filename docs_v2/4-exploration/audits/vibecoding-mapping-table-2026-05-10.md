---
title: 254 檔逐一對應表 — VibeCoding 6-Tier 遷移
date: 2026-05-10
phase: AUDIT (Phase 0 跟進產物)
status: DRAFT (Phase 0 — slop 標記 + tier 目標，搬遷時再加 reviewer/decision)
parent: vibecoding-migration-analysis-2026-05-10.md
---

# 254 檔逐一對應表

> 本表是 [`vibecoding-migration-analysis-2026-05-10.md`](./vibecoding-migration-analysis-2026-05-10.md) 的 follow-up。254 檔 = docs/ 166 + pipeline/ 88。
>
> **欄位說明**：
> - **Tier**：目標 VibeCoding tier（0/1/2/3/4/5/EXTRAS/REMOVE）
> - **Slop**：對應 §3 的哪個 slop 模式（如 §3.1 = Triple Taxonomy）
> - **Action**：MOVE / SPLIT / MERGE / RENAME / DELETE / EXTRACT / KEEP-AS-CACHE
> - **Phase**：Phase 2-6 的哪一階段處理（與遷移階段策略對應）
> - **Notes**：遷移時的具體指示

---

## A. docs/ root + 元文件 (5 檔)

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `docs/HOME.md` | hub | §3.1 | REWRITE | 2 | 改寫為 6-tier hub；保留舊 5D 索引指向新位置 |
| `docs/GATE-MAP.md` | 3 | §3.1, §3.4 | MERGE → `3-process/quality-gates.md` | 4 | 與 VibeCoding gate 系統 reconcile（D2 決策） |
| `docs/brand_model_list.md` | 0 / 2 | §3.7 | SPLIT → `0-principles/glossary.md` + `2-contracts/master-data/brand-model.md` | 3 | 純定義入 glossary；含 lifecycle 規則入 master-data |
| `docs/pair-log.md` | — | — | DELETE or KEEP at root | 6 | 開發日誌，非文件資產 |

## B. 00-discover/ (5 檔)

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `00-discover/_MOC.md` | — | §3.10 | DELETE（被 `0-principles/README.md` 取代） | 2 | |
| `00-discover/E1--project-brief-and-prd.md` | 4 | §3.2 | MOVE + SPLIT → `4-exploration/prd-2026-q1-v1-launch.md` + 抽 NFR 入 `0-principles/product-principles.md` | 4 | PRD 加 date-stamp |
| `00-discover/E1x--executive-architecture-overview.md` | 1 | §3.4 | MERGE → `1-decisions/architecture-overview.md §exec-view` | 3 | 與 E3 重複 |
| `00-discover/E1x--moat-mapping-matrix.md` | 4 / out | §3.8 | D3 決策：移到 `4-exploration/moat-and-pitch/` 或外部 sales repo | 4 | |
| `00-discover/E1x--moat-system-architecture.md` | 4 / out | §3.8 | 同上 | 4 | |
| `00-discover/E1x--presentation-blueprint.md` | 4 / out | §3.8 | 同上 | 4 | |

## C. 01-define/ (10 檔 + 11 diagrams)

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `01-define/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `01-define/E2--statement-of-work.md` | 4 | §3.2 | MOVE → `4-exploration/sow-2026-q1.md` | 4 | SOW 屬 exploration（per-engagement scope） |
| `01-define/E2x--wbs-project-schedule.md` | 4 | — | RENAME → `4-exploration/wbs-2026-q1.md` | 4 | |
| `01-define/E3--architecture-and-design.md` | 1 | §3.4 | MOVE + MERGE with E1x exec view → `1-decisions/architecture-overview.md` | 3 | 此為 architecture SSOT |
| `01-define/E3x--module-breakdown.md` | 1 | — | SPLIT → `1-decisions/module-boundary/{agent,api,data,web}.md` | 3 | 1 → N |
| `01-define/adrs/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `01-define/adrs/adr-001-backend-framework.md` | 1 | — | RENAME → `1-decisions/ADR-0001-backend-framework.md` | 2 | 4-digit ID |
| `01-define/adrs/adr-002-database-selection.md` | 1 | — | RENAME → `1-decisions/ADR-0002-database-selection.md` | 2 | |
| `01-define/adrs/adr-003-llm-integration-framework.md` | 1 | — | RENAME → `1-decisions/ADR-0003-llm-integration-framework.md` | 2 | |
| `01-define/adrs/adr-004-line-bot-architecture.md` | 1 | — | RENAME → `1-decisions/ADR-0004-line-bot-architecture.md` | 2 | |
| `01-define/adrs/adr-005-frontend-framework-v2.md` | 1 | — | RENAME → `1-decisions/ADR-0005-frontend-framework.md` | 2 | 移除 -v2 後綴（version in body）|
| `01-define/adrs/adr-006-llm-model-selection.md` | 1 | — | RENAME → `1-decisions/ADR-0006-llm-model-selection.md` | 2 | |
| `01-define/adrs/adr-007-llm-registry-pattern.md` | 1 | — | RENAME → `1-decisions/ADR-0007-llm-registry-pattern.md` | 2 | |
| `01-define/adrs/adr-008-product-info-architecture-canonical.md` | 1 | — | RENAME → `1-decisions/ADR-0008-product-info-architecture.md` | 2 | |
| `01-define/adrs/adr-009-agent-admin-bridge-pattern.md` | 1 | — | RENAME → `1-decisions/ADR-0009-agent-admin-bridge-pattern.md` | 2 | |
| `01-define/diagrams/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `01-define/diagrams/01_business_process_diagram.md` | 2 | §3.4 | MOVE → `2-contracts/flows/business/`（每 BF 一份；目前是綜合圖） | 3 | |
| `01-define/diagrams/02_use_case_diagram.md` | 1 | — | MERGE → `1-decisions/architecture-overview.md §use-cases` | 3 | |
| `01-define/diagrams/03_system_context_diagram.md` | 1 | — | MERGE → `1-decisions/architecture-overview.md §C4-context` | 3 | |
| `01-define/diagrams/04_high_level_architecture_diagram.md` | 1 | — | MERGE → `1-decisions/architecture-overview.md §C4-container` | 3 | |
| `01-define/diagrams/05_layered_component_diagram.md` | 1 | — | MERGE → `1-decisions/architecture-overview.md §C4-component` | 3 | |
| `01-define/diagrams/07_sequence_diagram.md` | 5 | §3.5 | MOVE → `5-views/sequence-diagrams.md` (AUTO from code traces) | 4 | |
| `01-define/diagrams/08_api_interface_diagram.md` | 5 | §3.5 | MOVE → `5-views/api-interface-map.md` (AUTO from openapi.yaml) | 4 | |
| `01-define/diagrams/09_deployment_diagram.md` | 1 | — | MERGE → `1-decisions/architecture-overview.md §deployment` | 3 | |
| `01-define/diagrams/10_security_permission_diagram.md` | 1 | — | MERGE → `1-decisions/architecture-overview.md §security` + ADR-NNN-RBAC | 3 | |
| `01-define/diagrams/E4--06_erd.md` | 1 | — | MOVE → `1-decisions/domain-model.md` | 3 | DDD aggregates 化 |
| `01-define/diagrams/index.html` | — | §3.7 | DELETE（不該在 docs/） | 2 | |
| `01-define/diagrams/image/04_high_level_architecture_diagram/architecture_evolution_technical_analysis.md` | 4 | — | MOVE → `4-exploration/audits/architecture-evolution-2026-04.md` | 4 | |

## D. 02-design/ root + harness + multi-tenant (24 檔)

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `02-design/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `02-design/E5--api-design-specification.md` | 2 | §3.4 | MERGE → prelude of `2-contracts/api/openapi.yaml` 的 README | 3 | narrative 收 README，contract 收 yaml |
| `02-design/E5x--frontend-architecture.md` | 0,1,2,3 | §3.4 | **SPLIT 4 way** per VibeCoding ADR-0001：`0-principles/frontend-quality-attributes.md` + `1-decisions/frontend-tech-stack.md` + `2-contracts/frontend-design-system.md` + `3-process/frontend-pre-merge-checklist.md` | 3 | |
| `02-design/E5x--frontend-information-arch.md` | 2,5 | §3.4 | **SPLIT**：`2-contracts/pages/*` (52 頁) + `5-views/frontend-route-map.md` (AUTO) + `4-exploration/prd §6 IA principles` | 3 | |
| `02-design/E6--development-workflow-cookbook.md` | 3 | — | MOVE → `3-process/workflow-manual.md` | 4 | |
| `02-design/E6x--project-structure-guide.md` | 5 | §3.5 | MOVE + AUTO → `5-views/project-structure.md`，跑 sunnydata-auto-regen | 4 | |
| `02-design/E6x--code-review-and-refactoring.md` | 3 | — | MOVE → `3-process/code-review-checklist.md` | 4 | |
| `02-design/E6x--file-dependencies.md` | 5 | §3.5 | MOVE + AUTO → `5-views/file-dependencies.md` | 4 | |
| `02-design/E6x--class-relationships.md` | 5 | §3.5 | MOVE + AUTO → `5-views/class-relationships.md` | 4 | |
| `02-design/error-codes.md` | 2 | §3.4 | MERGE → `2-contracts/api/openapi.yaml#components/responses` + 留 `error-codes.md` index | 3 | |
| `02-design/agent-harness/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `02-design/agent-harness/harness-architecture.md` | 1,4 | §3.2 | **SPLIT**：V1.0 部分→`1-decisions/module-boundary/agent-harness.md`；V2.0 8-layer 藍圖→`4-exploration/agent-harness-v2/architecture.md` | 3 | 文件自我宣告兩類 |
| `02-design/agent-harness/agent-layering-rules.md` | 1 | — | MERGE → `1-decisions/module-boundary/agent-harness.md §layering-rules` | 3 | |
| `02-design/agent-harness/config-evolution.md` | 4 | §3.2 | MOVE → `4-exploration/agent-harness-v2/config-evolution.md` | 4 | V2.0 |
| `02-design/agent-harness/diagnostic-intelligence-architecture.md` | 4 | §3.2 | MOVE → `4-exploration/agent-harness-v2/diagnostic.md` | 4 | V2.0 |
| `02-design/agent-harness/diagnostic-state-machine-spec.md` | 4 | §3.2 | MOVE → `4-exploration/agent-harness-v2/diagnostic-state-machine.md` | 4 | V2.0 |
| `02-design/agent-harness/gap-analysis.md` | 4 | — | MOVE → `4-exploration/audits/agent-harness-gap-2026-04.md` | 4 | |
| `02-design/agent-harness/graph-flow-redesign.md` | 4 | §3.2 | MOVE → `4-exploration/agent-harness-v2/graph-flow.md` | 4 | V2.0 |
| `02-design/agent-harness/knowledge-asset-review-checklist.md` | 3 | — | MOVE → `3-process/knowledge-asset-review-checklist.md` | 4 | |
| `02-design/agent-harness/migration-roadmap.md` | 4 | — | MOVE → `4-exploration/CR-0010-agent-harness-v2-migration.md` | 4 | |
| `02-design/agent-harness/optimization-strategy.md` | 4 | — | MOVE → `4-exploration/agent-harness-v2/optimization.md` | 4 | |
| `02-design/agent-harness/poc-spec.md` | 4 | — | MOVE → `4-exploration/agent-harness-v2/poc.md` | 4 | |
| `02-design/agent-harness/problem-card-spec.md` | 2 | — | MOVE → `2-contracts/modules/problem-card-engine.md` | 3 | 已實作的 contract |
| `02-design/agent-harness/wbs-harness-development.md` | 4 | — | MOVE → `4-exploration/agent-harness-v2/wbs.md` | 4 | |
| `02-design/platform-multi-tenant/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `02-design/platform-multi-tenant/business-model-strategy.md` | 4 | §3.2 | MOVE → `4-exploration/multi-tenant-platform/business-model.md` | 4 | 未啟動 |
| `02-design/platform-multi-tenant/dispatch-integration-spec.md` | 4 | §3.2 | MOVE → `4-exploration/multi-tenant-platform/dispatch-integration.md` | 4 | |
| `02-design/platform-multi-tenant/E5x--flows-multi-tenant.md` | 4 | §3.2 | MOVE → `4-exploration/multi-tenant-platform/flows.md` | 4 | |
| `02-design/platform-multi-tenant/external-factors-checklist.md` | 4 | §3.2 | MOVE → `4-exploration/multi-tenant-platform/external-factors.md` | 4 | |
| `02-design/platform-multi-tenant/multi-tenant-architecture.md` | 4 | §3.2 | MOVE → `4-exploration/multi-tenant-platform/architecture.md`（拍板後升 1-decisions/ADR-0010） | 4 | |

## E. 02-design/specs/ (26 檔)

> 規則：`*-spec.md` → `2-contracts/modules/*.md`（一份對應一個模組契約）；`openapi.yaml` / `asyncapi.yaml` → `2-contracts/api/`。

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `02-design/specs/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `02-design/specs/README.md` | 2 | — | MERGE → `2-contracts/api/README.md` | 3 | |
| `02-design/specs/openapi.yaml` | 2 | — | MOVE → `2-contracts/api/openapi.yaml` | 3 | **核心契約** |
| `02-design/specs/asyncapi.yaml` | 2 | — | MOVE → `2-contracts/api/asyncapi.yaml` | 3 | |
| `02-design/specs/audit-log-spec.md` | 2 | — | MOVE → `2-contracts/modules/audit-logger.md` | 3 | |
| `02-design/specs/b2b-api-spec.md` | 4 | §3.2 | MOVE → `4-exploration/multi-tenant-platform/b2b-api.md`（未啟動 OEM）| 4 | |
| `02-design/specs/brand-data-api-spec.md` | 4 | §3.2 | MOVE → `4-exploration/multi-tenant-platform/brand-data-api.md` | 4 | |
| `02-design/specs/consumer-tracking-entry.md` | 2 | — | MOVE → `2-contracts/modules/consumer-tracking.md` | 3 | |
| `02-design/specs/data-export-spec.md` | 2 | — | MOVE → `2-contracts/modules/data-export.md` | 3 | |
| `02-design/specs/dispatch-weights.md` | 2 | — | MOVE → `2-contracts/modules/dispatch-engine.md §weights` | 3 | |
| `02-design/specs/e-signature-spec.md` | 2 | — | MOVE → `2-contracts/modules/e-signature.md` | 3 | |
| `02-design/specs/i18n-strategy.md` | 1 | — | MOVE → `1-decisions/ADR-0011-i18n-strategy.md`（draft → accepted）| 3 | |
| `02-design/specs/inter-agent-messaging-spec.md` | 2 | — | MOVE → `2-contracts/modules/inter-agent-messaging.md` | 3 | |
| `02-design/specs/inventory-management-spec.md` | 2 | — | MOVE → `2-contracts/modules/inventory.md` | 3 | |
| `02-design/specs/notification-channel-strategy.md` | 1,2 | — | SPLIT：策略 → `1-decisions/ADR-0012-notification-channels.md`；契約 → `2-contracts/modules/notification.md` | 3 | |
| `02-design/specs/rbac-dynamic-spec.md` | 2 | — | MOVE → `2-contracts/modules/rbac.md` | 3 | |
| `02-design/specs/realtime-messaging-spec.md` | 2 | — | MOVE → `2-contracts/modules/realtime-messaging.md` | 3 | |
| `02-design/specs/refund-approval-spec.md` | 2 | — | MOVE → `2-contracts/modules/refund-service.md` | 3 | |
| `02-design/specs/role-matrix-v1.md` | 2 | §3.4 | MERGE → `2-contracts/modules/rbac.md §role-matrix` | 3 | |
| `02-design/specs/sla-availability-spec.md` | 0,2 | — | SPLIT：targets → `0-principles/frontend-quality-attributes.md §SLA`；運作 → `2-contracts/modules/sla-monitor.md` | 3 | |
| `02-design/specs/sla-policy.md` | 0 | — | MERGE → `0-principles/product-principles.md §SLA-policy` | 3 | |
| `02-design/specs/vision-processing-spec.md` | 2 | — | MOVE → `2-contracts/modules/vision-processing.md` | 3 | |
| `02-design/specs/warranty-dispute-spec.md` | 2 | — | MOVE → `2-contracts/modules/warranty-claim.md` | 3 | |
| `02-design/specs/webhook-spec.md` | 2 | — | MERGE → `2-contracts/api/asyncapi.yaml §webhooks` | 3 | |
| `02-design/specs/workday-sla-policy.md` | 0 | — | MERGE → `0-principles/product-principles.md §workday-policy` | 3 | |
| `02-design/specs/work-order-state-machine-extensions.md` | 2 | — | MERGE → `2-contracts/state-machines/work-order.md §extensions` | 3 | |

## F. 03-develop/ + 03-plan/ + 04-deliver/ (8 檔)

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `03-develop/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `03-develop/GR6--code-complete.md` | 3 | — | MERGE → `3-process/quality-gates.md §GR6` | 4 | |
| `03-develop/GR7--integration.md` | 3 | — | MERGE → `3-process/quality-gates.md §GR7` | 4 | |
| `03-plan/serverless-architecture-plan.md` | 4 | — | MOVE → `4-exploration/CR-0011-serverless-architecture.md` | 4 | |
| `04-deliver/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `04-deliver/E8--security-and-readiness-checklists.md` | 3 | — | MOVE → `3-process/security-readiness-checklist.md` | 4 | |
| `04-deliver/E9--deployment-and-operations-guide.md` | 3 | — | MOVE → `3-process/deployment-runbook.md` | 4 | |
| `04-deliver/E9x--documentation-and-maintenance.md` | 3 | — | MOVE → `3-process/docs-maintenance-guide.md` | 4 | |
| `04-deliver/GR10--ga-readiness.md` | 3 | — | MERGE → `3-process/quality-gates.md §GR10` | 4 | |

## G. _audit/ (7 檔，含本檔)

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `_audit/code-architecture-review-2026-05-06-1521.md` | 4 | §3.6 | MOVE → `4-exploration/audits/code-architecture-2026-05-06.md` | 4 | |
| `_audit/consistency-matrix-2026-05-06-1521.md` | 4 | §3.6 | MOVE → `4-exploration/audits/consistency-matrix-2026-05-06.md` | 4 | |
| `_audit/F-flow-disconnect-scan.md` | 4 | §3.6 | MOVE → `4-exploration/audits/flow-disconnect-2026-05.md` | 4 | |
| `_audit/refactor-plan-phase1-2-2026-05-06.md` | 4 | §3.6 | MOVE → `4-exploration/CR-0002-refactor-phase1-2.md` | 4 | |
| `_audit/refactor-plan-tier1-2026-05-06.md` | 4 | §3.6 | MOVE → `4-exploration/CR-0003-refactor-tier1-multi-tenant.md` | 4 | |
| `_audit/wbs-refactor-phase1-2-2026-05-06.md` | 4 | §3.6 | MOVE → `4-exploration/CR-0002-wbs.md` | 4 | |
| `_audit/wbs-refactor-tier1-2026-05-06.md` | 4 | §3.6 | MOVE → `4-exploration/CR-0003-wbs.md` | 4 | |
| `_audit/vibecoding-migration-analysis-2026-05-10.md` (本檔) | 4 | — | MOVE → `4-exploration/audits/vibecoding-migration-2026-05-10.md` | 6 | shipped 後歸檔 |
| `_audit/vibecoding-mapping-table-2026-05-10.md` (本檔) | 4 | — | MOVE → `4-exploration/audits/vibecoding-mapping-2026-05-10.md` | 6 | 同上 |

## H. _domain-knowledge/ (33 檔)

> 規則：定義入 0-principles/glossary；結構化資料搬出 docs/ 到 `data/`；師傅名冊絕對不該在 docs/。

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `_domain-knowledge/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `_domain-knowledge/E2x--wbs-pre-development.md` | 4 | — | MOVE → `4-exploration/wbs-pre-development.md` | 4 | |
| `_domain-knowledge/locksmith-checklist/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `_domain-knowledge/locksmith-checklist/README.md` | 0 | §3.7 | MOVE → `0-principles/glossary.md §domain-knowledge-overview` | 3 | |
| `_domain-knowledge/locksmith-checklist/01_各品牌電子鎖維修手冊/INDEX.md` | data | §3.7 | MOVE → `data/manuals/INDEX.md` | 5 | 不是 docs |
| `_domain-knowledge/locksmith-checklist/02_品牌與型號完整清單.md` | 2 | §3.7 | MOVE → `2-contracts/master-data/brand-model.md` | 3 | structured master data |
| `_domain-knowledge/locksmith-checklist/03_故障碼_蜂鳴聲_燈號對照表.md` | 2 / data | §3.7 | SPLIT：定義入 `2-contracts/master-data/fault-codes.md`；對照表 YAML 入 `data/fault-codes.yaml` | 3 | |
| `_domain-knowledge/locksmith-checklist/04_歷史客服對話紀錄/INDEX.md` | data | §3.7 | MOVE → `data/conversations/INDEX.md`（如尚未存在）| 5 | training data |
| `_domain-knowledge/locksmith-checklist/05_常見問題集（FAQ）.md` | data / agent-skill | §3.7 | MOVE → `agent/skills/data/_common/faq.md` | 5 | agent skill source |
| `_domain-knowledge/locksmith-checklist/06_客戶常用口語對照表.md` | 0 | §3.7 | MERGE → `0-principles/glossary.md §customer-vocabulary` | 3 | |
| `_domain-knowledge/locksmith-checklist/07_故障分類體系.md` | 0,2 | §3.7 | SPLIT：分類定義入 `0-principles/glossary.md`；taxonomy 入 `2-contracts/master-data/fault-taxonomy.md` | 3 | |
| `_domain-knowledge/locksmith-checklist/08_負面情緒關鍵詞清單.md` | data / agent-skill | §3.7 | MOVE → `agent/skills/data/_common/sentiment-keywords.md` | 5 | |
| `_domain-knowledge/locksmith-checklist/09_「電話可解決」vs「需派工」分類.md` | 2 | §3.7 | MOVE → `2-contracts/modules/dispatch-engine.md §triage-rules` | 3 | |
| `_domain-knowledge/locksmith-checklist/10_SOP審核流程定義.md` | 2 | §3.7 | MOVE → `2-contracts/flows/sub/SF-sop-review.md` | 3 | |
| `_domain-knowledge/locksmith-checklist/13_合作師傅名冊.md` | data / DB | §3.7 | **REMOVE from docs**, → DB seed `SQL/seed/technicians.sql` 或 ops/ | 5 | **PII 不該在 docs** |
| `_domain-knowledge/locksmith-checklist/14_派工業務規則.md` | 2 | §3.7 | MOVE → `2-contracts/modules/dispatch-engine.md §business-rules` | 3 | |
| `_domain-knowledge/locksmith-checklist/15_師傅分級標準.md` | 0 | §3.7 | MERGE → `0-principles/glossary.md §technician-tiers` | 3 | |
| `_domain-knowledge/locksmith-checklist/16_完工照片拍攝規範.md` | 3 | §3.7 | MOVE → `3-process/photo-evidence-standards.md` | 4 | |
| `_domain-knowledge/locksmith-checklist/17_帳務流程與結算報表範本.md` | 2 | §3.7 | MOVE → `2-contracts/flows/business/BF-monthly-settlement.md` | 3 | |
| `_domain-knowledge/locksmith-checklist/18_爭議處理案例.md` | 4 | §3.7 | MOVE → `4-exploration/dispute-case-library.md` | 4 | |
| `_domain-knowledge/locksmith-checklist/19_各工種常用物料清單.md` | 2 | §3.7 | MOVE → `2-contracts/master-data/materials-catalog.md` | 3 | |
| `_domain-knowledge/requirements/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `_domain-knowledge/requirements/README.md` | 4 | — | MOVE → `4-exploration/data-collection/README.md` | 4 | |
| `_domain-knowledge/requirements/01~09 子目錄 README.md` (9 份) | 4 | — | MOVE → `4-exploration/data-collection/0X_*.md` | 4 | |
| `_domain-knowledge/requirements/需求資料齊全度報告.md` | 4 | — | MOVE → `4-exploration/audits/data-completeness-2026.md` | 4 | |

## I. _flows-bdd-test/ (17 檔)

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `_flows-bdd-test/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `_flows-bdd-test/_review-notes.md` | 4 | §3.6 | MOVE → `4-exploration/audits/flows-review-notes.md` | 4 | |
| `_flows-bdd-test/_SSOT-alignment-matrix.md` | 5 | §3.5 | **AUTO** → `5-views/traceability-matrix.md` （sunnydata-auto-regen 產出；D7 決策）| 4 | 23 流程 × 8 維禁手寫 |
| `_flows-bdd-test/north-star-requirements.md` | 0,2 | §3.4 | SPLIT：principles 入 `0-principles/product-principles.md §requirements`；REQ-NNN 個別入 `2-contracts/functional-requirements/FR-XXXX.md` | 3 | |
| `_flows-bdd-test/_archive/E7x--module-roadmap-v2-draft.md` | 4 | — | MOVE → `4-exploration/archive/module-roadmap-v2-draft.md` | 4 | |
| `_flows-bdd-test/decision-log/E7x--pm-alignment-Q1-Q10.md` | 1 | — | SPLIT：每 Q 一個 ADR → `1-decisions/ADR-0013~0022-pm-alignment-q*.md` | 3 | |
| `_flows-bdd-test/decision-log/Q7-followup--payment-provider-decision.md` | 1,4 | — | MOVE → `1-decisions/ADR-0023-payment-provider.md`（拍板後）+ `4-exploration/CR-payment-provider.md`（決策過程）| 4 | |
| `_flows-bdd-test/v-model-left/E1x--user-journey-map.md` | 4 | — | MOVE → `4-exploration/prd-2026-q1-v1-launch.md §user-journeys` | 4 | |
| `_flows-bdd-test/v-model-left/E5x--workflow-admin-governance.md` | 2 | — | SPLIT BF/SF → `2-contracts/flows/business/BF-admin-governance.md` + `2-contracts/flows/sub/SF-{rbac,audit,inventory,dispute}.md` | 3 | |
| `_flows-bdd-test/v-model-left/E5x--workflow-dispatch.md` | 2 | — | SPLIT → `2-contracts/flows/business/BF-dispatch.md` + state-machine | 3 | |
| `_flows-bdd-test/v-model-left/E5x--workflow-work-order.md` | 2 | — | SPLIT → `2-contracts/flows/business/BF-work-order.md` + `2-contracts/state-machines/work-order.md` (16 states) | 3 | |
| `_flows-bdd-test/v-model-left/E7x--module-spec-v1-core.md` | 2 | — | SPLIT → `2-contracts/modules/{conversation-manager,problem-card-engine,three-layer-resolver,pricing-engine,sop-generator}.md`（5 模組）| 3 | |
| `_flows-bdd-test/v-model-right/E7--bdd-scenarios.md` | 2 | — | SPLIT：AC 入 `2-contracts/functional-requirements/FR-*.md`；scenarios 抽到 `tests/bdd/*.feature` | 3 | |
| `_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md` | 3 | — | MOVE → `3-process/test-plan.md` | 4 | |
| `_flows-bdd-test/v-model-right/integration-test-matrix.md` | 3 | — | MERGE → `3-process/test-plan.md §integration-matrix` | 4 | |
| `_flows-bdd-test/v-model-right/performance-baseline.md` | 0,3 | — | SPLIT：targets → `0-principles/frontend-quality-attributes.md §performance`；runbook → `3-process/test-plan.md §performance` | 4 | |
| `_flows-bdd-test/v-model-right/security-checklist.md` | 3 | — | MERGE → `3-process/security-readiness-checklist.md §extension` | 4 | |

## J. _gap-analysis/ + _meeting-minutes/ + _superseded/ (6 檔)

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `_gap-analysis/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `_gap-analysis/gap-analysis-report.md` | 4 | — | MOVE → `4-exploration/audits/gap-analysis-2026.md` | 4 | |
| `_gap-analysis/gap-analysis-report-cn.md` | 4 | §3.4 | MERGE → 上一份的中英並列或刪 cn 版 | 4 | |
| `_meeting-minutes/_MOC.md` | — | §3.10 | DELETE | 2 | |
| `_meeting-minutes/20260404_架構討論_meeting_minutes.md` | 4 | — | MOVE → `4-exploration/meetings/20260404-architecture.md` | 4 | |
| `_superseded/01_smart_lock_prd.md` | 4 | — | MOVE → `4-exploration/archive/01_smart_lock_prd.md`（status: superseded）| 4 | |

---

## K. web_design_spec_prompt_pipeline/ (88 檔)

### K.1 root + global (5 檔)

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `pipeline/README.md` | — | §3.1 | MERGE → `extras/web-frontend/pipeline/README.md` | 5 | |
| `pipeline/lovable_組裝.md` | extras | — | MOVE → `extras/web-frontend/pipeline/tools/lovable.md` | 5 | |
| `pipeline/global/BASE_DESIGN_SYSTEM.md` | extras | §3.1 | DELETE（與 VibeCoding `2-contracts/frontend-design-system.template.md` 重複）| 5 | |
| `pipeline/global/SYSTEM_DOCUMENT_SPEC.md` | extras | §3.1 | DELETE（4-tier vs VibeCoding 6-tier 衝突）| 5 | |
| `pipeline/global/01_sunny_brand_system.md` | — | §3.8 | DELETE（不是 Smart Lock 專案）| 5 | |
| `pipeline/global/02_smartlock_dispatch_brand_system.md` | 2 | — | MERGE → `2-contracts/frontend-design-system.md §brand-system` | 5 | |

### K.2 guides + references + modules (7 檔)

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `pipeline/guides/implementation_guide.md` | extras | — | MOVE → `extras/web-frontend/pipeline/implementation.md` | 5 | |
| `pipeline/guides/quality_checklist.md` | 3 | — | MERGE → `3-process/frontend-pre-merge-checklist.md` | 5 | |
| `pipeline/guides/vibe_coding_build_strategy.md` | 3 | — | MERGE → `3-process/workflow-manual.md §frontend-variant` | 5 | |
| `pipeline/references/website_recipes.md` | extras / external | — | MOVE → `extras/` 或刪（與 Smart Lock 無關通用框架）| 5 | D5 決策 |
| `pipeline/references/prereq_document_checklist.md` | 3 | — | MERGE → `3-process/frontend-pre-merge-checklist.md §prereq` | 5 | |
| `pipeline/references/ui_style_benchmark_report.md` | 4 | — | MOVE → `4-exploration/audits/ui-style-benchmark.md` | 5 | |
| `pipeline/modules/MODULE_REGISTRY.md` | extras / external | §3.8 | MOVE → 外部 repo（與 Smart Lock 無關通用模組登記表）| 5 | D5 決策 |
| `pipeline/modules/WEBSITE_MODULE_MATRIX.md` | extras / external | §3.8 | 同上 | 5 | |

### K.3 pages (24 檔)

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `pipeline/pages/page_template.md` | — | §3.1 | DELETE（用 VibeCoding `2-contracts/page-contract.template.md`）| 5 | |
| `pipeline/pages/MAPPING.md` | 5 | §3.5 | AUTO → `5-views/frontend-route-map.md` 一部分（D7 決策）| 5 | |
| `pipeline/pages/02_admin_dashboard.md` | 2 | — | SPLIT → `2-contracts/pages/A1-dashboard.md` | 5 | 含 1 頁 |
| `pipeline/pages/03_admin_conversations.md` | 2 | — | SPLIT → `2-contracts/pages/A2-conversations-list.md` + `A3-conversation-detail.md` | 5 | 含 2 頁 |
| `pipeline/pages/04_admin_problem_cards.md` | 2 | — | SPLIT → 2 頁 | 5 | |
| `pipeline/pages/05_admin_knowledge_base.md` | 2 | — | SPLIT → 5 頁（A6~A10）| 5 | |
| `pipeline/pages/06_admin_work_orders.md` | 2 | — | MOVE → `2-contracts/pages/A11-work-orders.md` | 5 | |
| `pipeline/pages/07_admin_work_order_detail.md` | 2 | — | MOVE → `2-contracts/pages/A12-work-order-detail.md` | 5 | |
| `pipeline/pages/08_admin_technicians.md` | 2 | — | SPLIT → 2 頁（A13/A14）| 5 | |
| `pipeline/pages/09_admin_accounting.md` | 2 | — | MOVE → `2-contracts/pages/A15-accounting.md` | 5 | |
| `pipeline/pages/10_admin_advanced.md` | 2 | — | SPLIT → 6 頁（A17-A22）| 5 | |
| `pipeline/pages/11_tech_pool.md` | 2 | — | MOVE → `2-contracts/pages/T1-pool.md` | 5 | |
| `pipeline/pages/12_tech_my_orders.md` | 2 | — | SPLIT → 2 頁（T2/T3）| 5 | |
| `pipeline/pages/13_tech_account.md` | 2 | — | MOVE → `2-contracts/pages/T6-account.md` | 5 | |
| `pipeline/pages/14_auth_and_settings.md` | 2 | — | SPLIT → `A0-login.md` + `A16-settings.md` + `T0-tech-login.md` | 5 | |
| `pipeline/pages/15_admin_customers_and_diagnostics.md` | 2 | — | SPLIT → 4 頁（A23/A24/A32/A33）| 5 | |
| `pipeline/pages/16_admin_technician_detail.md` | 2 | — | SPLIT → 3 頁（A25/A26/A27）| 5 | |
| `pipeline/pages/17_admin_dispatch_queue_and_reports.md` | 2 | — | SPLIT → 4 頁（A28/A29/A30/A31）| 5 | |
| `pipeline/pages/18_admin_multi_tenant.md` | 4 | §3.2 | MOVE → `4-exploration/multi-tenant-platform/pages.md`（V3.0 未實作）| 5 | |
| `pipeline/pages/19_tech_workorder_subflows.md` | 2 | — | MOVE → `2-contracts/pages/T-subflows.md` | 5 | |
| `pipeline/pages/20_admin_dispatch_manual.md` | 2 | — | MOVE → `2-contracts/pages/A37-dispatch-manual.md` | 5 | |
| `pipeline/pages/21_global_notifications.md` | 2 | — | MOVE → `2-contracts/pages/G1-notifications.md` | 5 | |
| `pipeline/pages/22_reschedule_calendar.md` | 2 | — | MOVE → `2-contracts/pages/G3-reschedule-calendar.md` | 5 | |
| `pipeline/pages/23_global_offline.md` | 2 | — | MOVE → `2-contracts/pages/G2-offline.md` | 5 | |
| `pipeline/pages/23a_global_error_boundaries.md` | 2 | — | MOVE → `2-contracts/pages/G4-error-boundaries.md` | 5 | |

### K.4 assembly (14 檔)

> **整批屬中間產物，不該進 git。Phase 5 移除並改 CI 產出。**

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `pipeline/assembly/PIPELINE_ORCHESTRATOR.md` | extras | — | MOVE → `extras/web-frontend/pipeline/orchestrator.md` | 5 | |
| `pipeline/assembly/01~13_*_integrated.md` (13 份) | — | §3.9 | DELETE（Phase 5 改 CI 產出 .gitignore）| 5 | 中間產物 |

### K.5 design-system-specs (40 檔)

| 現位置 | Tier | Slop | Action | Phase | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `design-system-specs/AI_DESIGN_INDUSTRIAL_PLAYBOOK.md` | 3 | — | MOVE → `3-process/ai-design-playbook.md` | 5 | |
| `design-system-specs/00_foundations_spec.md` | 2 | §3.4 | MERGE → `2-contracts/frontend-design-system.md §foundations` | 5 | |
| `design-system-specs/01_components_spec.md` | 2 | §3.4 | MERGE → `2-contracts/frontend-design-system.md §components` | 5 | |
| `design-system-specs/02_patterns_spec.md` | 2 | §3.4 | MERGE → `2-contracts/frontend-design-system.md §patterns` | 5 | |
| `design-system-specs/03_templates_spec.md` | 2 | §3.4 | MERGE → `2-contracts/frontend-design-system.md §templates` | 5 | |
| `design-system-specs/99_documentation_spec.md` | 3 | — | MERGE → `3-process/frontend-pre-merge-checklist.md §documentation` | 5 | |
| `design-system-specs/grok/00_~99_*.md` (5 份) | — | §3.4 | DELETE（Grok 變體與 smartlock 重複）| 5 | |
| `design-system-specs/smartlock/00_~99_*.md` (5 份) | 2 | §3.4 | MERGE → `2-contracts/frontend-design-system.md §smartlock-instance`（與 base 合併）| 5 | |
| `design-system-specs/cloning/CLONE_WORKFLOW_PLAYBOOK.md` | extras | — | MOVE → `extras/web-frontend/design-cloning/playbook.md` | 5 | |
| `design-system-specs/cloning/checklists/*.md` (2 份) | extras | — | MOVE → `extras/web-frontend/design-cloning/checklists/` | 5 | |
| `design-system-specs/cloning/clones/_example_stripe/README.md` | extras | — | MOVE → `extras/web-frontend/design-cloning/clones/example-stripe.md` | 5 | |
| `design-system-specs/cloning/prompts/*.md` (8 份) | extras | — | MOVE → `extras/web-frontend/design-cloning/prompts/` | 5 | |
| `design-system-specs/cloning/templates/*.md` (6 份) | extras | — | MOVE → `extras/web-frontend/design-cloning/templates/` | 5 | |
| `design-system-specs/design_all.pen` (binary) | extras | — | MOVE → `extras/web-frontend/design.pen` | 5 | binary，加 .gitattributes |
| `design-system-specs/images/*.png` (6 張) | extras | — | MOVE → `extras/web-frontend/images/` | 5 | |

---

## L. 統計

| 分類 | 檔案數 | 占比 | 主要動作 |
| :-- | --: | --: | :-- |
| MOVE 至 0/1/2/3-tier | ~95 | 37% | 直接搬檔 + frontmatter 補齊 |
| SPLIT（一檔拆多檔） | ~22 | 9% | 較高風險，需逐檔審查 |
| MERGE（多檔合一）| ~30 | 12% | 內容比對 + 解 conflict |
| AUTO（5-views）| ~6 | 2% | sunnydata-auto-regen 接管 |
| MOVE 至 4-exploration | ~50 | 20% | 含 audit / CR / archive |
| MOVE 至 extras / external | ~30 | 12% | pipeline 通用框架 + cloning |
| DELETE（_MOC / 中間產物 / 重複）| ~21 | 8% | 9 份 _MOC + 13 份 _integrated + 重複 |
| **總計** | **254** | 100% | |

---

## M. Phase 排程預估

| Phase | 內容 | 行數估計 | 工作日估 |
| :-- | :-- | --: | --: |
| Phase 2 骨架 | 建 6 個 tier 目錄 + 0-principles 全填 + ADR rename + 9 份 _MOC 刪 | ~150 commits | 3-5 天 |
| Phase 3 Contract | 02-design/specs/ + flows + frontend-arch SPLIT + master-data | ~80 PR | 2-3 週 |
| Phase 4 Process / Exploration / Views | 04-deliver + GATE + _audit + _gap + _meeting + 5-views AUTO | ~40 PR | 1-2 週 |
| Phase 5 Pipeline | smartlock design system + 22 page specs + extras | ~30 PR | 1 週 |
| Phase 6 收尾 | 舊路徑 superseded + wikilink rewrite + 觀察 | — | 3 天 + 1 個月觀察 |
| **合計** | | | **5-8 週** |

---

## N. 變更紀錄

| 日期 | 內容 |
| :--- | :--- |
| 2026-05-10 18:35 | 初版 — 254 檔逐一對應 + slop 標記 + Phase 排程；待人類拍板 §6 八決策再升 CR |
