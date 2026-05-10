---
title: ID Mapping Legacy — 舊 ID → VibeCoding 9-prefix 對照
tier: 0
status: active
last_updated: 2026-05-10
maintainer: AI auto-update on each new BF/UF/SF/FR
related:
  - "flow-id-conventions.md"
  - "../4-exploration/change-requests/CR-0001-vibecoding-6tier-migration.md (D6)"
---

# ID Mapping Legacy

> **D6 妥協方案**：保留現有 F-XXX / REQ-NNN ID 不重編號（破壞性過高），新流程一律用 VibeCoding 9-prefix（BF/UF/SF/FR/NFR/API/TC/ADR/CR）。本檔維護新舊對照。
>
> **Phase 3 起每新增一條 BF/UF/SF/FR/CR**，AI 自動 append 一行（如有對應 legacy ID）。

---

## A. 已建立映射

### A.1 5D Essential / Extension → VibeCoding tier

| Legacy ID | Legacy 路徑 | VibeCoding 對應 | tier |
| :-- | :-- | :-- | :-- |
| E1 | `docs/00-discover/E1--project-brief-and-prd.md` | `4-exploration/prd-2026-q1-v1-launch.md` | 4 |
| E1x (moat) | `docs/00-discover/E1x--moat-*.md` | `business/moat-*.md` | business |
| E1x (exec arch) | `docs/00-discover/E1x--executive-architecture-overview.md` | `1-decisions/architecture-overview.md §exec-view` 或 `business/` | 1 / business |
| E2 | `docs/01-define/E2--statement-of-work.md` | `4-exploration/sow-2026-q1.md` | 4 |
| E2x (wbs) | `docs/01-define/E2x--wbs-project-schedule.md` | `4-exploration/wbs-2026-q1.md` | 4 |
| E2x (wbs pre-dev) | `docs/_domain-knowledge/E2x--wbs-pre-development.md` | `4-exploration/wbs-pre-development.md` | 4 |
| E3 | `docs/01-define/E3--architecture-and-design.md` | `1-decisions/architecture-overview.md` | 1 |
| E3x | `docs/01-define/E3x--module-breakdown.md` | `1-decisions/module-boundary/{agent,api,data-pipeline,web}.md` | 1 |
| E4 | `docs/01-define/diagrams/E4--06_erd.md` | `1-decisions/domain-model.md` | 1 |
| E5 | `docs/02-design/E5--api-design-specification.md` | `2-contracts/api/README.md` | 2 |
| E5x (frontend-arch) | `docs/02-design/E5x--frontend-architecture.md` | SPLIT 4-way: `0-principles/frontend-quality-attributes.md` + `1-decisions/frontend-tech-stack.md` + `2-contracts/frontend-design-system.md` + `3-process/frontend-pre-merge-checklist.md` | 0,1,2,3 |
| E5x (frontend-IA) | `docs/02-design/E5x--frontend-information-arch.md` | SPLIT: `2-contracts/pages/*` (52 頁) + `5-views/frontend-route-map.md` + PRD §6 | 2,5,4 |
| E5x (workflow-*) | `docs/_flows-bdd-test/v-model-left/E5x--workflow-{work-order,dispatch,admin-governance}.md` | `2-contracts/flows/business/BF-*.md` + `2-contracts/flows/sub/SF-*.md` + `2-contracts/state-machines/work-order.md` | 2 |
| E5x (multi-tenant flows) | `docs/02-design/platform-multi-tenant/E5x--flows-multi-tenant.md` | `4-exploration/multi-tenant-platform/flows.md` | 4 |
| E6 | `docs/02-design/E6--development-workflow-cookbook.md` | `3-process/workflow-manual.md` | 3 |
| E6x (code-review) | `docs/02-design/E6x--code-review-and-refactoring.md` | `3-process/code-review-checklist.md` | 3 |
| E6x (project-structure) | `docs/02-design/E6x--project-structure-guide.md` | `5-views/project-structure.md` | 5 |
| E6x (file-deps) | `docs/02-design/E6x--file-dependencies.md` | `5-views/file-dependencies.md` | 5 |
| E6x (class-rel) | `docs/02-design/E6x--class-relationships.md` | `5-views/class-relationships.md` | 5 |
| E7 | `docs/_flows-bdd-test/v-model-right/E7--bdd-scenarios.md` | `2-contracts/functional-requirements/FR-*.md` AC sections + `tests/bdd/*.feature` | 2 + tests |
| E7x (test-plan) | `docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md` | `3-process/test-plan.md` | 3 |
| E7x (pm-alignment) | `docs/_flows-bdd-test/decision-log/E7x--pm-alignment-Q1-Q10.md` | `1-decisions/ADR-0013~0022-pm-alignment-q*.md` | 1 |
| E7x (module-spec) | `docs/_flows-bdd-test/v-model-left/E7x--module-spec-v1-core.md` | `2-contracts/modules/{conversation-manager, problem-card-engine, three-layer-resolver, pricing-engine, sop-generator}.md` | 2 |
| E8 | `docs/04-deliver/E8--security-and-readiness-checklists.md` | `3-process/security-readiness-checklist.md` | 3 |
| E9 | `docs/04-deliver/E9--deployment-and-operations-guide.md` | `3-process/deployment-runbook.md` | 3 |
| E9x | `docs/04-deliver/E9x--documentation-and-maintenance.md` | `3-process/docs-maintenance-guide.md` | 3 |
| GR6 | `docs/03-develop/GR6--code-complete.md` | `3-process/quality-gates.md §GR6-code-complete` | 3 |
| GR7 | `docs/03-develop/GR7--integration.md` | `3-process/quality-gates.md §GR7-integration` | 3 |
| GR10 | `docs/04-deliver/GR10--ga-readiness.md` | `3-process/quality-gates.md §GR10-ga-readiness` | 3 |

### A.2 TR-Gate → quality-gates instance（D2 拍板配套）

| TR Gate | 投資人視角名稱 | quality-gates 對應 | 工程角色 |
| :-- | :-- | :-- | :-- |
| TR0 | Idea Gate | `quality-gates.md §pre-discovery` | 問題驗證 |
| TR1 | Concept Gate | `quality-gates.md §gate-0-discovery` | PRD draft |
| TR2 | Scope Gate | `quality-gates.md §gate-1-define` | SOW + ADR |
| TR3 | Architecture Gate | `quality-gates.md §gate-1-define` | E3 + ERD |
| TR4 | Spec Complete Gate | `quality-gates.md §gate-2-design` | API + Module contracts |
| TR5 | Build Ready Gate | `quality-gates.md §gate-2-design` | Dev workflow + AC |
| TR6 | Code Complete Gate | `quality-gates.md §gate-3-develop / GR6` | 模組單測 |
| TR7 | Integration Gate | `quality-gates.md §gate-3-develop / GR7` | 整合測試 |
| TR8 | Validation Gate | `quality-gates.md §gate-4-deliver` | UAT + 安全 |
| TR9 | Launch Ready Gate | `quality-gates.md §gate-4-deliver` | 部署 + SLA |
| TR10 | GA Gate | `quality-gates.md §gate-5-operate / GR10` | GA 監控 |

### A.3 north-star-requirements REQ-NNN → FR-NNNN（Phase 3 起逐筆建立）

| Legacy REQ | 新 FR | 對應 BF/UF | 預定路徑 |
| :-- | :-- | :-- | :-- |
| REQ-001 LINE 客服報修受理 | FR-0001 | BF-0001 LINE 報修 → ProblemCard | `2-contracts/functional-requirements/FR-0001-line-intake.md` |
| REQ-002 ProblemCard 智能分診 | FR-0002 | BF-0001 | `2-contracts/functional-requirements/FR-0002-problem-card-triage.md` |
| REQ-003 自動派工演算法 | FR-0003 | BF-0002 派工到完工 | `FR-0003-auto-dispatch.md` |
| REQ-004 手動派工 + audit | FR-0004 | BF-0002 | `FR-0004-manual-dispatch.md` |
| REQ-005 技師接單回報 | FR-0005 | UF-0002 | `FR-0005-tech-accept.md` |
| REQ-006 到場拍照 | FR-0006 | UF-0002 | `FR-0006-onsite-photo.md` |
| REQ-007 材料申請 | FR-0007 | UF-0003 材料申請 | `FR-0007-material-request.md` |
| REQ-008 Scope Change | FR-0008 | UF-0004 範圍變更 | `FR-0008-scope-change.md` |
| REQ-009 完工簽名 | FR-0009 | UF-0002 | `FR-0009-completion-sign.md` |
| REQ-010 改約 / 延遲 | FR-0010 | UF-0005 | `FR-0010-reschedule-delay.md` |
| REQ-011 消費者付款 | FR-0011 | UF-0006 付款 | `FR-0011-consumer-payment.md` |
| REQ-012 技師月結撥款 | FR-0012 | BF-monthly-settlement | `FR-0012-monthly-settlement.md` |
| REQ-013 對帳爭議雙簽 | FR-0013 | UF-0007 | `FR-0013-dual-sign-dispute.md` |
| REQ-014 退款流程 | FR-0014 | UF-0008 退款 | `FR-0014-refund.md` |
| REQ-015 保固申訴 | FR-0015 | UF-0009 保固 | `FR-0015-warranty-claim.md` |
| REQ-016 SLA 2hr 到場 | FR-0016 (NFR) | BF-0002 + state-machine | `FR-0016-sla-2hr.md` |
| REQ-017 SOP 草稿審核 | FR-0017 | UF-0010 SOP review | `FR-0017-sop-draft-review.md` |
| REQ-018 客服接管對話 | FR-0018 | UF-0011 | `FR-0018-cs-takeover.md` |
| REQ-019 動態 RBAC | FR-0019 | UF-0012 RBAC 管理 | `FR-0019-rbac-dynamic.md` |
| REQ-020 稽核日誌 | FR-0020 (NFR) | (cross-cutting) | `FR-0020-audit-log.md` |
| REQ-021 Dashboard / 報表 | FR-0021 | UF-0013 | `FR-0021-dashboard-reports.md` |
| REQ-022 消費者工單追蹤 | FR-0022 | UF-0014 | `FR-0022-consumer-tracking.md` |
| REQ-023 錯誤頁 / 離線 | FR-0023 (NFR) | (cross-cutting) | `FR-0023-error-offline.md` |

### A.4 _flows-bdd-test F-XXX → BF/UF（保留 F-XXX 別名）

> 過渡期 F-XXX 與 BF/UF 雙重命名；新文件 frontmatter 必加 `legacy_id: F-XXX`。

| Legacy F-XXX | 名稱 | 新主 ID | 別名 frontmatter |
| :-- | :-- | :-- | :-- |
| F-001 | LINE 報修 → ProblemCard | UF-0001 | `legacy_id: F-001` |
| F-002 | 客服審 PC → 開 WO | UF-0015 | `legacy_id: F-002` |
| F-003 | 自動派工規則引擎 | SF-0003 | `legacy_id: F-003` |
| F-004 | 手動派工 | UF-0016 | `legacy_id: F-004` |
| F-005 | 技師接單 → 出發 | UF-0002 | `legacy_id: F-005` |
| F-006 | 到場拍照 | UF-0017 | `legacy_id: F-006` |
| F-007 | 材料申請 | UF-0003 | `legacy_id: F-007` |
| F-008 | Scope Change | UF-0004 | `legacy_id: F-008` |
| F-009 | 完工簽名 | UF-0018 | `legacy_id: F-009` |
| F-010 | 改約 / 延遲 | UF-0005 | `legacy_id: F-010` |
| F-011 | 消費者付款 | UF-0006 | `legacy_id: F-011` |
| F-012 | 技師月結撥款 | BF-0003 | `legacy_id: F-012` |
| F-013 | 對帳爭議雙簽 | UF-0007 | `legacy_id: F-013` |
| F-014 | 退款流程 | UF-0008 | `legacy_id: F-014` |
| F-015 | 保固申訴 | UF-0009 | `legacy_id: F-015` |
| F-016 | SLA 紅色警報 | SF-0016 | `legacy_id: F-016` |
| F-017 | SOP 草稿審核 | UF-0010 | `legacy_id: F-017` |
| F-018 | 客服接管對話 | UF-0011 | `legacy_id: F-018` |
| F-019 | RBAC 動態調整 | UF-0012 | `legacy_id: F-019` |
| F-020 | 稽核日誌 | (cross-cutting NFR/FR-0020) | `legacy_id: F-020` |
| F-021 | Dashboard / 報表 | UF-0013 | `legacy_id: F-021` |
| F-022 | 消費者端工單追蹤 | UF-0014 | `legacy_id: F-022` |
| F-023 | 錯誤頁 / 離線 | (cross-cutting FR-0023) | `legacy_id: F-023` |

### A.5 BDD F-XXX (different namespace) → TC-NNNN

> 注意：BDD 文件中的 F-101/F-102 等是 BDD Feature ID，與 user flow F-001~F-023 是不同 namespace。

| BDD Feature | 對應 user flow | 新 TC ID |
| :-- | :-- | :-- |
| F-101~F-110 | F-001 LINE 報修 等 | TC-0101~0110 |
| F-201~F-211 | F-005 技師接單 等 V2.0 | TC-0201~0211 |
| F-105 admin V1.0 | F-002 / F-021 | TC-0105 |
| F-205 admin V2.0 | F-019 / F-020 | TC-0205 |

### A.6 PM Q1-Q10 拍板 → ADR

| Legacy Q | 拍板 | 新 ADR |
| :-- | :-- | :-- |
| Q1 (RBAC 階層) | A | ADR-0013 |
| Q2 (雙簽 escalation) | A | ADR-0014 |
| Q3 (消費者 token 設計) | C | ADR-0015 |
| Q4 (爭議 SLA / 工作日 calendar) | C | ADR-0016 |
| Q5 (SLA Soft 警報語意) | B | ADR-0017 |
| Q6 (派工繞過權限) | A | ADR-0018 |
| Q7 (金流 provider) | B (待 follow-up) | ADR-0023（Q7-followup）|
| Q8 (改約通知) | A | ADR-0019 |
| Q9 (Scope Change 雙確認) | B | ADR-0020 |
| Q10 (其他) | — | ADR-0021 |

---

## B. 命名規範（從本 commit 起新流程必遵）

```
BF-NNNN   Business Flow（業務能力，E2E）
UF-NNNN   User Flow（per-actor）
SF-NNNN   Sub-Flow（共享步驟）
FR-NNNN   Functional Requirement（業務規則）
NFR-NNNN  Non-Functional Requirement（性能 / 安全 / 可用性）
API-NNNN  API endpoint（單一 endpoint contract）
TC-NNNN   Test Case（含 BDD Feature / scenario）
ADR-NNNN  Architecture Decision Record
CR-NNNN   Change Request（CIA）
```

NNNN = 4-digit 從 0001 起遞增不重用。

新增 ID 時：
1. 取下一個未用編號
2. 寫對應 markdown 檔（用 VibeCoding template）
3. **append 一行到本檔**（如有對應 legacy ID）
4. frontmatter 加 `id` + `legacy_id`（如有）

---

## C. 變更紀錄

| 日期 | 內容 |
| :--- | :--- |
| 2026-05-10 | 初版 — A.1~A.6 完整對照建立 |
