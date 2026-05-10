---
title: VibeCoding 6-Tier 遷移分析（docs/ + web_design_spec_prompt_pipeline/）
date: 2026-05-10
phase: AUDIT (CR-pre-draft)
status: DRAFT (Phase 0 — 完整盤點 + slop 模式辨識 + 高層對應)
owners: [架構審查 / Doc Steward]
related:
  - "[VibeCoding INDEX](../../VibeCoding_Workflow_Templates/INDEX.md)"
  - "[VibeCoding OWNERSHIP-MATRIX](../../VibeCoding_Workflow_Templates/OWNERSHIP-MATRIX.md)"
  - "[.claude/rules/context-stability.md](../../.claude/rules/context-stability.md)"
  - "[.claude/rules/change-governance.md](../../.claude/rules/change-governance.md)"
  - "[code-architecture-review-2026-05-06-1521](./code-architecture-review-2026-05-06-1521.md)"
  - "[refactor-plan-tier1-2026-05-06](./refactor-plan-tier1-2026-05-06.md)"
followup_files:
  - "vibecoding-mapping-table-2026-05-10.md  (per-file mapping, 254 rows — 待產出)"
  - "vibecoding-migration-CR-2026-05-10.md   (CIA/CR 文件 — 待產出，先 stop at §8)"
---

# VibeCoding 6-Tier 遷移分析

> **本檔目的**：把現有 `docs/` (166 檔) 與 `web_design_spec_prompt_pipeline/` (88 檔) 共 254 個文件，盤點現有結構問題（AI slop 模式）、產出對應到 VibeCoding 6-tier 架構的高層 mapping、定義遷移階段。
>
> **本檔不做**：實際移檔；本檔是 Phase 0 「畫地圖」，不是 Phase 1 「遷移」。Phase 1 必須先有 CIA + 人類拍板 §8 才能動。
>
> **下一步**：依 §8 的開放決策表，請 PM/Tech Lead 拍板，再產 CR-NNNN CIA 與 mapping table。

---

## §1 Executive Summary

### 1.1 問題

專案目前有 **三套競爭的 taxonomy** 同時存在：

| Taxonomy | 位置 | 核心結構 | 數量 | 狀態 |
| :-- | :-- | :-- | :-- | :-- |
| **5D + TR-Gate**（舊） | `docs/00-discover` ~ `docs/04-deliver` + `docs/_*` 八個 underscore zones | DISCOVER → DEFINE → DESIGN → DEVELOP → DELIVER；TR0-TR10；E1-E9 + GR6/7/10 | 166 檔 | Active（HOME.md / GATE-MAP.md 仍指這套）|
| **VibeCoding 6-Tier**（新） | `VibeCoding_Workflow_Templates/0-principles ... 5-views` | 0-principles / 1-decisions / 2-contracts / 3-process / 4-exploration / 5-views | 模板層，無實例 | **Active（已被 .claude/rules 採納為主規範）** |
| **Web Design Pipeline**（獨立） | `web_design_spec_prompt_pipeline/{global, pages, modules, assembly, design-system-specs, guides, references}` | Global → Pages → Modules → Assembly → Generate | 88 檔 | Active 但與 docs/ 雙向未整合 |

三套並存，**符合 v3-style「按 phase 分」、v4-style「按 stability 分」、與 ad-hoc「按 generation pipeline 分」三種完全不同的編排哲學**。AI 與新人讀文件時無法判斷 source of truth，落入經典「文件矛盾→AI 腦補」的 slop loop。

### 1.2 核心判斷（Linus 五層思考摘要）

- 🟢 **資料結構分析**：254 個文件本質上只有 ≈ 30 個獨立的 source-of-truth 概念（PRD、ADRs、API 契約、Flow、State machines、Test plan、Domain glossary、Design tokens、Page contracts...）。**目前一個概念被 2-4 個檔案分述**（典型 slop）。
- 🟡 **特殊情況**：5D 框架的 `00-/01-/02-/03-/04-` 加上 `_audit/_domain-knowledge/_flows-bdd-test/_gap-analysis/_meeting-minutes/_superseded` 共 11 個頂層分類，違反 Linus 「good taste = 消除分類爆炸」。**VibeCoding 只有 6 個 tier**，每個 tier 有清楚的 update cadence。
- 🔴 **複雜度**：HOME.md 的「Reading Path A-E」5 條讀法 × _MOC.md 9 份索引 × ext-E1/ext-E5/ext-E6 自創 prefix —— 複雜度遠超必要。
- ⚠️ **破壞性風險**：直接搬檔會破壞所有 `[[wikilink]]`、cross-ref、外部 PR/Issue 連結；必須漸進式。
- ✅ **實用主義**：問題真實存在（`.claude/rules/change-governance.md` 已強制要求 contract 變更走 CIA，但 contract 散在 `02-design/specs/` + `02-design/agent-harness/` + `02-design/platform-multi-tenant/` + `_flows-bdd-test/v-model-left/`，CIA 找不到單一目標）。

### 1.3 最重要的 3 個 slop 模式（細節見 §3）

1. **Tier mismatch in single file**：同一檔混合 V1.0 現況 + V2.0/V3.0 設計藍圖（typical: `agent-harness/_MOC.md` 自我宣告「分兩類」、`platform-multi-tenant/multi-tenant-architecture.md` 100% 是 1-decisions / ADR 內容卻擺在 02-design）。
2. **三套並存的 ID 系統**：`E1/E1x/E5x` (5D-essentials) + `F-001~F-023 / REQ-NNN` (north-star) + VibeCoding 規範的 `BF/UF/SF/FR/ADR/CR/TC` 9-prefix —— 三套都被使用，互相不映射。
3. **Audit 報告自身就是 slop**：`docs/_audit/` 7 份檔案是 2026-05-06 一次性審查產物，本來該是 tier-4 exploration（CR-NNNN），但被當成獨立 zone 留存（見本檔 §3.7）。

---

## §2 三套 Taxonomy 的精確映射（高層）

下表把現有結構對應到 VibeCoding 的 6 個 tier。**這只是「應該屬於」的標記，不是「立即移動」**。

### 2.1 docs/ → VibeCoding tier

| 現位置 | 主要內容 | VibeCoding 目標 tier | 備註 |
| :-- | :-- | :-- | :-- |
| `docs/HOME.md` | 文件導覽 | （元文件，留在 docs/ root） | 改寫為 6-tier hub |
| `docs/GATE-MAP.md` | TR0-TR10 框架 | `3-process/quality-gates.md` | TR-gate vs VibeCoding gate 需 reconciliation（兩套 gate 系統不可並存） |
| `docs/brand_model_list.md` | 品牌型號清單 | `0-principles/glossary.template.md` 或 `2-contracts/master-data-specification.template.md` | Master data — 看是否帶 lifecycle/governance |
| `docs/pair-log.md` | 開發日誌 | （留在 docs/ 或刪除） | Ephemeral — 不屬六層任何一層 |
| `docs/00-discover/E1--project-brief-and-prd.md` | PRD | `4-exploration/prd.template.md`（date-stamp） | PRD 本質是 exploration，非 1-decisions |
| `docs/00-discover/E1x--moat-*.md` | 競爭護城河、投資簡報 | `4-exploration/`（標 status: shipped）或 **獨立 sales/ folder** | **不是工程文件**，混在 docs/ 中是 slop |
| `docs/00-discover/E1x--executive-architecture-overview.md` | 執行摘要架構 | `1-decisions/architecture-overview.template.md` 的「executive view」section | 與 E3 重複 |
| `docs/00-discover/E1x--presentation-blueprint.md` | 投資簡報結構 | （搬出 docs/ 到 sales/ 或 archive） | 同上 |
| `docs/01-define/E2--statement-of-work.md` | SOW + 範圍 | `4-exploration/prd.template.md` 或 `1-decisions/architecture-overview.template.md` | SOW = scope contract，可獨立 tier |
| `docs/01-define/E2x--wbs-project-schedule.md` | WBS | `4-exploration/wbs.template.md`（date-stamp） | |
| `docs/01-define/E3--architecture-and-design.md` | 系統架構 | `1-decisions/architecture-overview.template.md` | |
| `docs/01-define/E3x--module-breakdown.md` | 模組分解 | `1-decisions/module-boundary.template.md`（每模組一份） | 1 → N 拆分 |
| `docs/01-define/adrs/adr-001 ~ adr-009` | 9 份 ADR | `1-decisions/ADR-NNNN-xxx.md` | 直接搬，rename for 4-digit ID |
| `docs/01-define/diagrams/01_~10_*.md` | C4 / sequence / deploy diagrams | `1-decisions/architecture-overview.template.md` 的 sub-section 或 `5-views/` | C4 是 decision；deploy/sequence 偏 view |
| `docs/01-define/diagrams/E4--06_erd.md` | ERD | `1-decisions/domain-model.template.md` | DDD aggregate 視圖 |
| `docs/01-define/diagrams/index.html` | HTML 索引 | （搬出 docs/ 或刪） | 不是文件 |
| `docs/02-design/E5--api-design-specification.md` | API narrative | `2-contracts/api-spec.template.md` 的 prelude | 真正契約是 specs/openapi.yaml |
| `docs/02-design/E5x--frontend-architecture.md` | Frontend arch | **split per VibeCoding ADR-0001**：`0-principles/frontend-quality-attributes` + `1-decisions/frontend-tech-stack` + `2-contracts/frontend-design-system` + `3-process/frontend-pre-merge-checklist` |
| `docs/02-design/E5x--frontend-information-arch.md` | 48 頁 IA | **split**：`2-contracts/page-contract.template.md`（每頁一份）+ `5-views/frontend-route-map.template.md`（自動產生）+ `4-exploration/prd.template.md §6`（IA principles）|
| `docs/02-design/E6--development-workflow-cookbook.md` | Dev 工作流 | `3-process/workflow-manual.md` | |
| `docs/02-design/E6x--project-structure-guide.md` | 專案結構 | `5-views/project-structure.template.md`（**自動產生**） |
| `docs/02-design/E6x--code-review-and-refactoring.md` | Code review 標準 | `3-process/code-review-checklist.md` | |
| `docs/02-design/E6x--file-dependencies.md` | 檔案依賴 | `5-views/file-dependencies.template.md`（**自動產生**） |
| `docs/02-design/E6x--class-relationships.md` | 類別關係 | `5-views/class-relationships.template.md`（**自動產生**） |
| `docs/02-design/error-codes.md` | 錯誤碼目錄 | `2-contracts/api-spec.template.md` 的 error-codes section | 應在 OpenAPI components.responses |
| `docs/02-design/specs/openapi.yaml` | OpenAPI 3.1 | `2-contracts/api/openapi.yaml`（VibeCoding `2-contracts/` 直收 yaml） | **核心契約** |
| `docs/02-design/specs/asyncapi.yaml` | AsyncAPI 2.6 | `2-contracts/api/asyncapi.yaml` | |
| `docs/02-design/specs/*-spec.md` (24 份) | 領域技術規格 | `2-contracts/module-contract.template.md`（每 spec 一份） | 大部分 mismatch — narrative spec 應結構化 |
| `docs/02-design/agent-harness/*.md` (12 份) | Harness 框架（**V1.0 現況 + V2.0 藍圖混在一起**） | **必須拆分**：V1.0 現況→`1-decisions/architecture-overview` + `2-contracts/module-contract`；V2.0 藍圖→`4-exploration/`（標 status: draft）|
| `docs/02-design/platform-multi-tenant/*.md` (5 份) | 多租戶架構（未實作） | `4-exploration/`（標 status: draft）+ 拍板後 → `1-decisions/ADR-NNNN-multi-tenant-isolation.md` | **整個 zone 是 draft，目前掛在 02-design 是 tier mismatch** |
| `docs/03-develop/GR6/GR7/_MOC.md` | Gate review checklists | `3-process/quality-gates.md` 的 sub-checklists | TR-gate 與 VibeCoding gate reconciliation |
| `docs/03-plan/serverless-architecture-plan.md` | Serverless 計畫 | `4-exploration/`（status: draft） |
| `docs/04-deliver/E8--security-and-readiness-checklists.md` | 安全清單 | `3-process/security-readiness-checklist.md` | |
| `docs/04-deliver/E9--deployment-and-operations-guide.md` | 部署運維 | `3-process/deployment-runbook.template.md` | |
| `docs/04-deliver/E9x--documentation-and-maintenance.md` | 文件維護 | `3-process/docs-maintenance-guide.md` | |
| `docs/04-deliver/GR10--ga-readiness.md` | GA 檢查 | `3-process/quality-gates.md` 的 GA section | |
| `docs/_audit/*.md` (7 份) | 2026-05-06 一次性審查 | `4-exploration/CR-NNNN-*.md`（一份審查報告 = 一個 CR） | **即為本目錄性質：tier-4 exploration，不該是常駐 zone** |
| `docs/_domain-knowledge/locksmith-checklist/*` (19 檔) | 鎖匠領域知識 | `0-principles/glossary.template.md` 的擴充 + 部分搬到 `data/`（domain data 而非文件） | 19 → ~6 條 glossary entry + N 個 data file |
| `docs/_domain-knowledge/requirements/*` (9 子目錄) | 資料蒐集追蹤 | `4-exploration/`（標 status 與 owner） | 屬資料蒐集 WBS，非 contract |
| `docs/_domain-knowledge/E2x--wbs-pre-development.md` | 資料蒐集 WBS | `4-exploration/wbs.template.md` | |
| `docs/_flows-bdd-test/_SSOT-alignment-matrix.md` | 23 流程 × 8 維 | `2-contracts/traceability-matrix.template.md`（**自動產生** by `sunnydata-auto-regen`） | **目前手動維護 = slop；該移到 5-views 性質的自動產出** |
| `docs/_flows-bdd-test/north-star-requirements.md` | REQ-NNN catalog | `2-contracts/functional-requirement.template.md`（每 REQ 一份）+ `0-principles/product-principles.template.md`（NFR/QA 部分）|
| `docs/_flows-bdd-test/v-model-left/E1x--user-journey-map.md` | 使用者旅程 | `4-exploration/prd.template.md §3` 的 user journey section | |
| `docs/_flows-bdd-test/v-model-left/E5x--workflow-*.md` (3 份) | 工作流（work-order/dispatch/admin-governance） | `2-contracts/flow-business.template.md`（BF）+ `2-contracts/flow-sub.template.md`（SF）+ `2-contracts/state-machine.template.md` | **核心 flow contract** |
| `docs/_flows-bdd-test/v-model-left/E7x--module-spec-v1-core.md` | 模組規格 + UT 案例 | `2-contracts/module-contract.template.md`（每模組一份） | |
| `docs/_flows-bdd-test/v-model-right/E7--bdd-scenarios.md` | BDD scenarios | `2-contracts/functional-requirement.template.md` 的 AC section + `tests/bdd/*.feature` | |
| `docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md` | 測試計畫 | `3-process/test-plan.template.md` | |
| `docs/_flows-bdd-test/v-model-right/integration-test-matrix.md` | IT 矩陣 | `3-process/test-plan.template.md` 的 integration section | |
| `docs/_flows-bdd-test/v-model-right/performance-baseline.md` | 性能基準 | `0-principles/frontend-quality-attributes.template.md` + `3-process/test-plan.template.md` | |
| `docs/_flows-bdd-test/v-model-right/security-checklist.md` | 安全檢查 | `3-process/security-readiness-checklist.md` 的補充 | |
| `docs/_flows-bdd-test/decision-log/*.md` (2 份) | PM 決策紀錄 | `1-decisions/`（每個決策一份 ADR，標 supersedes/superseded_by） | |
| `docs/_flows-bdd-test/_archive/*` | 已封存 | `4-exploration/archive/` | |
| `docs/_gap-analysis/*.md` (3 份) | Gap 分析報告 | `4-exploration/CR-NNNN-gap-analysis-*.md`（date-stamp） | |
| `docs/_meeting-minutes/*.md` | 會議紀錄 | `4-exploration/meetings/`（date-stamp） | |
| `docs/_superseded/*.md` | 已替代 | `4-exploration/archive/`（標 status: superseded） | |

### 2.2 web_design_spec_prompt_pipeline/ → VibeCoding tier

| 現位置 | 主要內容 | VibeCoding 目標 tier | 備註 |
| :-- | :-- | :-- | :-- |
| `web_design_spec_prompt_pipeline/README.md` | Pipeline 入口 | （元文件，整體搬至 `extras/web-frontend/pipeline/`） | 整個 pipeline 屬於 frontend "extras" |
| `pipeline/global/BASE_DESIGN_SYSTEM.md` | Design tokens 模板 | **VibeCoding 已有** `2-contracts/frontend-design-system.template.md` | 兩個是同概念 |
| `pipeline/global/SYSTEM_DOCUMENT_SPEC.md` | 四層系統文件模板 | （刪 — 與 VibeCoding 6-tier 衝突的 4-tier 設計） | **slop：另一套 4-tier taxonomy** |
| `pipeline/global/01_sunny_brand_system.md` | 桑尼品牌實例 | （與本專案無關，搬到 archive 或刪） | 不是 Smart Lock 專案資產 |
| `pipeline/global/02_smartlock_dispatch_brand_system.md` | Smart Lock 品牌系統 | `2-contracts/frontend-design-system.template.md`（本專案實例） | **這個保留** |
| `pipeline/pages/page_template.md` | 頁面規格範本 | `2-contracts/page-contract.template.md`（VibeCoding 已有更標準版） | 替換 |
| `pipeline/pages/02_~23a_*.md` (22 份頁面 spec) | 個別頁面 spec | `2-contracts/page-contract.template.md`（每頁一份） | 22 個 page contract |
| `pipeline/pages/MAPPING.md` | IA × pipeline 對照 | `2-contracts/traceability-matrix.template.md`（**自動產生**） | 手動維護 = slop |
| `pipeline/modules/MODULE_REGISTRY.md` | 8 大模組 + L1/L2/L3 深度 | （**屬通用框架，搬出本專案到 extras 或獨立 repo**） | 不是 Smart Lock 專屬內容 |
| `pipeline/modules/WEBSITE_MODULE_MATRIX.md` | 模組 × 網站類型 | （同上） | |
| `pipeline/assembly/PIPELINE_ORCHESTRATOR.md` | 組裝指南 | `extras/web-frontend/pipeline/PIPELINE_ORCHESTRATOR.md` | Process |
| `pipeline/assembly/01_~13_*_integrated.md` (13 份) | 完整組裝 prompt | （產出物，**搬到 build artifacts，不該進 docs/**） | **這些是中間生成物，不是 source of truth** |
| `pipeline/guides/implementation_guide.md` | 實施指南 | `3-process/`（process guide） | |
| `pipeline/guides/quality_checklist.md` | 品質檢查 | `3-process/frontend-pre-merge-checklist.template.md` | 已有 VibeCoding 對應 |
| `pipeline/guides/vibe_coding_build_strategy.md` | 建置策略 | `3-process/workflow-manual.md` 的 frontend variant | |
| `pipeline/lovable_組裝.md` | Lovable 工具 SOP | （留在 extras 或 archive） | 工具特定，非 contract |
| `pipeline/references/website_recipes.md` | 10 種網站配方 | （extras 或 archive） | 通用框架資料 |
| `pipeline/references/prereq_document_checklist.md` | 前置文件檢核 | `3-process/` | |
| `pipeline/references/ui_style_benchmark_report.md` | UI 風格 benchmark | `4-exploration/`（status: shipped） | |
| `pipeline/design-system-specs/00_~99_*.md` (5 份基準 + 5 份 grok + 5 份 smartlock) | Foundations / Components / Patterns / Templates / Documentation 規格 | `2-contracts/frontend-design-system.template.md` 的 sub-sections | **15 份 → 1 份 + 4 份 sub-section** |
| `pipeline/design-system-specs/AI_DESIGN_INDUSTRIAL_PLAYBOOK.md` | Pencil + Figma MCP + Claude Code 戰法 | `3-process/`（process guide） | |
| `pipeline/design-system-specs/cloning/*` (15 檔) | Design 複製方法論 | `extras/`（外部工具方法論） | |
| `pipeline/design-system-specs/grok/*` | Grok 變體規格 | （刪或 archive — variant of smartlock） | 重複 |

---

## §3 AI Slop 模式分類

### §3.1 Triple Taxonomy Conflict（最嚴重）

**症狀**：HOME.md 推 5D + TR-gate；VibeCoding INDEX.md 推 6-tier；pipeline README.md 推 Global/Pages/Modules/Assembly。三套都 active，沒有單一 SSOT。

**證據**：
- `.claude/rules/context-stability.md` 已宣告六層為主規範
- `docs/HOME.md` 仍以 5D 為主導覽
- `web_design_spec_prompt_pipeline/README.md` 不引用任一套

**影響**：AI 讀 docs 時不知道哪份才是 source of truth，傾向腦補 reconciliation。

**修法**：選一套（VibeCoding 6-tier，因 .claude/rules 已採納）；其他二套標 deprecated/superseded。

### §3.2 V1.0 / V2.0 / V3.0 Mixed in Single File

**症狀**：同一文件混合「現況」與「未來藍圖」，違反 tier 分離原則（現況→1-decisions / 藍圖→4-exploration）。

**證據**：
- `docs/02-design/agent-harness/_MOC.md` 自我宣告「文件分兩類：V1.0 現行 vs V2.0 設計藍圖」 — 12 份 harness 文件混雜
- `docs/02-design/platform-multi-tenant/multi-tenant-architecture.md` 100% 是未啟動的多租戶設計 → 屬 4-exploration，不是 02-design
- `docs/_flows-bdd-test/v-model-left/E7x--module-spec-v1-core.md` 已 SPLIT V1.0 / V2.0（部分修正過）

**修法**：
- 現況 spec → tier 1 / 2（`status: accepted`）
- 未來藍圖 → tier 4（`status: draft` + `shipped-as: ADR-NNNN` 待填）

### §3.3 Triple ID System Coexistence

**症狀**：
- 5D 用 `E1, E1x, E5x, GR6, GR7, GR10`
- _flows-bdd-test 用 `F-001~F-023, REQ-NNN, AT-NNN, ST-NNN, IT-NNN, UT-NNN, PT-NNN, SEC-NNN, DEC-NNN, Q1-Q10`
- VibeCoding 規範 `BF/UF/SF/FR/NFR/API/TC/ADR/CR` 9-prefix（`VibeCoding_Workflow_Templates/0-principles/flow-id-conventions.md`）

三套全用，無正式 mapping table。

**修法**：採 VibeCoding 9-prefix 為主；舊 ID 保留 alias（過渡期）；產出 `0-principles/id-mapping-legacy.md` 文件記錄歷史對應。

### §3.4 Cross-Zone Scattering

**症狀**：相同概念散在 3+ 個位置。

**證據**：

| 概念 | 散在 |
| :-- | :-- |
| Architecture overview | `00-discover/E1x--executive-architecture-overview` + `01-define/E3--architecture-and-design` + `01-define/diagrams/04_high_level_architecture` + `02-design/agent-harness/harness-architecture` + `02-design/platform-multi-tenant/multi-tenant-architecture` |
| API contract | `02-design/E5--api-design-specification` (narrative) + `02-design/specs/openapi.yaml` (machine) + `02-design/specs/*-spec.md` (24 narrative specs) |
| Work order flow | `_flows-bdd-test/v-model-left/E5x--workflow-work-order` + `_flows-bdd-test/v-model-right/E7--bdd-scenarios` + `02-design/specs/work-order-state-machine-extensions` |
| RBAC | `02-design/specs/rbac-dynamic-spec` + `02-design/specs/role-matrix-v1` + `01-define/diagrams/10_security_permission_diagram` + `_flows-bdd-test/v-model-left/E5x--workflow-admin-governance` |
| Test plan | `_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness` + `_flows-bdd-test/v-model-right/integration-test-matrix` + `_flows-bdd-test/v-model-right/performance-baseline` + `_flows-bdd-test/v-model-right/security-checklist` + `03-develop/GR7--integration` |
| Frontend page contract | `02-design/E5x--frontend-information-arch` (IA 48 頁) + `web_design_spec_prompt_pipeline/pages/*` (22 spec) + `web_design_spec_prompt_pipeline/pages/MAPPING.md` |

**修法**：每個概念合併到單一 source of truth 文件；其他位置改為 reference link。

### §3.5 Manual Maintenance of Auto-Regenerable Views

**症狀**：明明可以從 code/source 自動產生的 5-views 內容卻手動維護，立刻 rot。

**證據**：
- `docs/02-design/E6x--project-structure-guide.md` — 手寫的目錄結構，與 `tree src/` 不一定一致
- `docs/02-design/E6x--file-dependencies.md` — 手寫的依賴圖
- `docs/02-design/E6x--class-relationships.md` — 手寫的類別關係
- `docs/_flows-bdd-test/_SSOT-alignment-matrix.md` — 23 流程 × 8 維手動矩陣
- `web_design_spec_prompt_pipeline/pages/MAPPING.md` — IA × spec 手動對照

**修法**：搬到 `5-views/` + 標 `auto-regenerated by sunnydata-auto-regen`；手動維護的鎖死。

### §3.6 Audit / Refactor Plans as Permanent Zones

**症狀**：`docs/_audit/` 7 份檔案是 2026-05-06 一次性審查產物，但被當成常駐 zone（沒有 status frontmatter、沒有 archive 機制）。

**證據**：本檔本身就是其中之一 — 寫完不歸檔等於下次審查時又會產生新的 `_audit/` 內容堆疊。

**修法**：
- 一次性審查 = `4-exploration/CR-NNNN-*.md`（Change Request 編號）
- 設定 `4-exploration/` 的 `archive/` 子目錄；`status: shipped` 後自動歸檔
- `_audit/` 整個 zone 廢棄

### §3.7 Domain Knowledge as Documentation

**症狀**：`docs/_domain-knowledge/locksmith-checklist/` 19 份檔案是「鎖匠維修知識」，本質是 **AI agent 的 skill 來源資料**，但被當成 docs 維護。

**證據**：
- `02_品牌與型號完整清單.md` → 應為 `0-principles/glossary` 或結構化 master data
- `03_故障碼_蜂鳴聲_燈號對照表.md` → 應為 structured data file（CSV/YAML），不是 markdown
- `13_合作師傅名冊.md` → DB content，絕對不該在 docs/

**修法**：
- 純定義（術語）→ `0-principles/glossary.template.md`
- 結構化資料（型號表、故障碼表）→ `data/` 下 YAML/CSV 並由 pipeline 餵入 `agent/skills/`
- DB content（師傅名冊）→ DB seed scripts，從 docs/ 移除

### §3.8 Marketing/Sales Material in Engineering Docs

**症狀**：`docs/00-discover/E1x--moat-mapping-matrix.md`、`E1x--executive-architecture-overview.md`、`E1x--moat-system-architecture.md`、`E1x--presentation-blueprint.md` 是給投資人/銷售的素材，不是工程文件。

**修法**：搬到專案外部的 `sales/` 或 `pitch/` repo，從 docs/ 移除。docs/ 只放工程相關資產。

### §3.9 Pipeline 中間產物進 source tree

**症狀**：`web_design_spec_prompt_pipeline/assembly/01_~13_*_integrated.md` 13 份「完整組裝 prompt」是把 global + pages + modules 拼接的中間產物，每次重新組裝就要重寫，存進 git 等於同步 cache。

**修法**：assembly/*_integrated.md 改為 build script 產出（CI artifact），不進 git。

### §3.10 Two MOC Conventions Coexist

**症狀**：docs/ 內有兩種索引慣例 —— `_MOC.md`（Map of Content，Obsidian/Foam 風格）與 `README.md`（VibeCoding/GitHub 風格），而且兩種都用。

**證據**：
- 9 份 `_MOC.md`：`00-discover/_MOC.md`, `01-define/_MOC.md`, `02-design/_MOC.md` ...
- 4 份 `README.md`：`02-design/specs/README.md`, `_domain-knowledge/requirements/README.md` ...

**修法**：VibeCoding 全用 `README.md`（GitHub 慣例）；統一全改為 `README.md`，`_MOC.md` 廢棄。

---

## §4 對應到 VibeCoding 的目標結構（草案）

```
docs/
├── README.md                                  ← 6-tier hub（取代 HOME.md）
│
├── 0-principles/
│   ├── product-principles.md                 ← from E1 PRD §0/§1 + north-star NFR/QA
│   ├── glossary.md                           ← from _domain-knowledge 部分 + brand_model_list
│   ├── flow-id-conventions.md                ← copy from VibeCoding template + 加 5D/F-XXX legacy alias
│   ├── frontend-quality-attributes.md        ← from E5x--frontend-architecture §QA + performance-baseline
│   └── id-mapping-legacy.md                  ← E1/E1x/F-XXX/REQ-NNN → BF/UF/SF/FR/ADR 對照
│
├── 1-decisions/
│   ├── ADR-0001-backend-framework.md         ← rename from adr-001
│   ├── ADR-0002-database-selection.md
│   ├── ... ADR-0009 (existing 9)
│   ├── ADR-0010-multi-tenant-isolation.md   ← when phase A 啟動
│   ├── architecture-overview.md             ← E3 + E1x exec view 合併
│   ├── domain-model.md                      ← E4 ERD + DDD aggregates
│   ├── module-boundary/
│   │   ├── agent.md                         ← from E3x + agent-harness V1.0 sections
│   │   ├── api.md
│   │   ├── data-pipeline.md
│   │   └── web.md
│   └── frontend-tech-stack.md               ← from E5x--frontend-architecture §Stack
│
├── 2-contracts/
│   ├── api/
│   │   ├── openapi.yaml                     ← move from 02-design/specs/
│   │   └── asyncapi.yaml
│   ├── modules/                              ← 一個 module 一份 contract
│   │   ├── agent-harness.md
│   │   ├── conversation-manager.md
│   │   ├── problem-card-engine.md
│   │   ├── work-order-service.md
│   │   ├── dispatch-engine.md
│   │   ├── sop-generator.md
│   │   ├── refund-service.md
│   │   ├── pricing-engine.md
│   │   ├── warranty-claim.md
│   │   ├── audit-logger.md
│   │   ├── rbac-service.md
│   │   └── ... (其餘 specs/*.md → 此處)
│   ├── flows/
│   │   ├── business/                         ← BF (E2E business capabilities)
│   │   │   ├── BF-0001-line-report-to-resolution.md
│   │   │   ├── BF-0002-dispatch-to-completion.md
│   │   │   └── ...
│   │   ├── user/                             ← UF (per-actor)
│   │   │   ├── UF-0001-consumer-line-report.md
│   │   │   ├── UF-0002-technician-accept-job.md
│   │   │   └── ...
│   │   └── sub/                              ← SF (shared steps)
│   │       ├── SF-0001-payment-collection.md
│   │       └── ...
│   ├── functional-requirements/              ← FR-NNNN，from north-star REQ-NNN
│   │   ├── FR-0001-line-intake.md
│   │   └── ...
│   ├── state-machines/
│   │   ├── work-order.md                     ← from E5x--workflow-work-order §state machine
│   │   └── refund.md
│   ├── master-data/
│   │   ├── brand-model.md                    ← from brand_model_list.md
│   │   └── fault-codes.md                    ← from _domain-knowledge/03_*
│   ├── frontend-design-system.md             ← from pipeline/design-system-specs/smartlock + global/02_smartlock_*
│   ├── pages/                                 ← from pipeline/pages/*
│   │   ├── A1-dashboard.md
│   │   ├── A2-conversations.md
│   │   └── ... (52 pages)
│   ├── flow-index.md                         ← AUTO from frontmatter scan
│   └── traceability-matrix.md                ← AUTO from cross-ref scan
│
├── 3-process/
│   ├── workflow-manual.md                    ← E6
│   ├── bdd-guide.md                          ← copy VibeCoding template
│   ├── code-review-checklist.md              ← E6x--code-review-and-refactoring
│   ├── security-readiness-checklist.md       ← E8 + v-model-right/security-checklist
│   ├── deployment-runbook.md                 ← E9
│   ├── docs-maintenance-guide.md             ← E9x
│   ├── quality-gates.md                      ← GATE-MAP + 5D TR0-TR10 reconcile
│   ├── test-plan.md                          ← v-model-right/E7x + integration-test-matrix
│   ├── frontend-pre-merge-checklist.md       ← pipeline/guides/quality_checklist
│   └── vendor-api-test-requirement.md        ← copy VibeCoding template
│
├── 4-exploration/
│   ├── prd-2026-q1-v1-launch.md              ← rename E1 with date
│   ├── wbs-2026-q1-v1.md                     ← rename E2x with date
│   ├── wbs-pre-development.md                ← _domain-knowledge/E2x
│   ├── moat-and-pitch/                       ← consider moving out of docs/ entirely
│   │   ├── moat-system-architecture.md
│   │   └── presentation-blueprint.md
│   ├── multi-tenant-platform/                ← all 02-design/platform-multi-tenant/* (status: draft)
│   ├── agent-harness-v2/                     ← V2.0 藍圖部分（拆出後）
│   ├── change-requests/
│   │   ├── CR-0001-vibecoding-migration-2026-05-10.md  ← 本檔的後續 CIA
│   │   ├── CR-0002-debounce-refactor.md      ← from refactor-plan-phase1-2
│   │   └── CR-0003-multi-tenant-tier1.md     ← from refactor-plan-tier1
│   ├── audits/                               ← from _audit/ + _gap-analysis/
│   │   ├── code-architecture-review-2026-05-06.md
│   │   ├── consistency-matrix-2026-05-06.md
│   │   └── gap-analysis-2026-04.md
│   ├── meetings/                             ← from _meeting-minutes/
│   │   └── 20260404-architecture-discussion.md
│   └── archive/                              ← shipped/superseded 自動歸這
│       └── (from _superseded/, _flows-bdd-test/_archive/)
│
└── 5-views/                                   ← 全部 AUTO，禁手寫
    ├── project-structure.md
    ├── file-dependencies.md
    ├── class-relationships.md
    └── frontend-route-map.md
```

`web_design_spec_prompt_pipeline/` 整個目錄的命運：

- 工具方法論（PIPELINE_ORCHESTRATOR / lovable_組裝 / cloning/ / AI_DESIGN_INDUSTRIAL_PLAYBOOK） → `extras/web-frontend/pipeline/`
- 通用框架資料（MODULE_REGISTRY / WEBSITE_MODULE_MATRIX / website_recipes） → 搬出本專案到獨立 repo（與 Smart Lock 業務無關）
- 本專案實例（smartlock/ design-system + 22 page specs + 02_smartlock_dispatch_brand_system） → `docs/2-contracts/frontend-design-system.md` + `docs/2-contracts/pages/`
- 中間產物（assembly/*_integrated.md） → 不進 git，CI 產出

---

## §5 遷移階段策略

```
Phase 0  Plan 期（本檔）                     ← 完成
   └─ 完整盤點 + slop 模式辨識 + 高層 mapping + 目標結構草案

Phase 1  CIA 與決策                          ← 待 PM/TL 拍板
   ├─ 產 CR-0001 CIA 文件
   ├─ §8 列出 8 條 Human Decisions Required（見本檔 §6）
   └─ 等決策完成才進 Phase 2

Phase 2  骨架建置（不破壞舊 docs）            ← 約 3-5 天
   ├─ 在 docs/ 並列建立 0-principles ~ 5-views 6 個目錄
   ├─ 寫 docs/README.md（取代 HOME.md 成為新 hub）
   ├─ 0-principles/ 全部填滿（5 份）
   ├─ 1-decisions/ ADR-0001~9 直接 rename + 4-digit
   └─ 全程 dry-run，舊路徑不刪

Phase 3  Contract 遷移（最危險）              ← 約 2-3 週
   ├─ 02-design/specs/openapi.yaml → 2-contracts/api/
   ├─ 24 份 narrative spec → 24 份 module-contract
   ├─ flow 文件結構化為 BF/UF/SF
   ├─ traceability-matrix 改為 AUTO
   ├─ 每搬一份立刻補 frontmatter（last-synced-with / source-paths）
   └─ 持續跑 sunnydata-doc-freshness 檢查 drift

Phase 4  Process / Exploration / Views       ← 約 1-2 週
   ├─ 3-process/ 從 04-deliver + GATE-MAP + pipeline/guides 整合
   ├─ 4-exploration/ 把 _audit + _gap-analysis + _meeting-minutes + _superseded 全收
   └─ 5-views/ 跑 sunnydata-auto-regen 全自動產出

Phase 5  Pipeline 整併                       ← 約 1 週
   ├─ smartlock design system → 2-contracts/frontend-design-system.md
   ├─ 22 page specs → 2-contracts/pages/
   ├─ 通用框架類搬出本 repo
   └─ assembly/_integrated.md 改 CI 產出

Phase 6  舊路徑收尾                          ← 約 3 天
   ├─ 舊 docs/00-04 + _* zone 全標 status: superseded + 指向新位置
   ├─ wikilinks 批次改寫
   ├─ HOME.md / GATE-MAP.md 加 redirect note
   └─ 觀察 1 個月後實際刪除舊檔
```

---

## §6 ⚠️ Human Decisions Required（CIA §8 預列）

此處先預列待人類拍板的 8 條決策。**Phase 1 CIA 文件正式產出後，會把這些放入 §8，AI 不可在這些未拍板前動手**。

| # | 決策 | 選項 | 影響 |
| :-- | :-- | :-- | :-- |
| D1 | 是否採用 VibeCoding 6-tier 為唯一 docs taxonomy？ | (a) 全採用 (b) 並存（保留 5D 為 legacy view）(c) 不採用 | (a) 大遷移、徹底解決 slop；(b) slop 短期殘留；(c) 違反 .claude/rules |
| D2 | TR0-TR10 gate 與 VibeCoding `3-process/quality-gates.md` 如何 reconcile？ | (a) TR-gate 廢棄全用 quality-gates (b) TR-gate 改為 quality-gates 的 instance (c) 兩套並存 | (a) 較簡 (b) 保留 TR 文化 |
| D3 | `00-discover/E1x--moat-*` 與 `presentation-blueprint` 是否該留在 docs/？ | (a) 搬出到 sales/ repo (b) 留在 4-exploration/ (c) 刪除 | docs/ 只放工程文件 vs 包山包海 |
| D4 | `_domain-knowledge/locksmith-checklist/` 19 份去哪？ | (a) 拆 glossary + data/ (b) 整體搬到 data/domain-knowledge/ (c) 留 docs 但加 frontmatter | (a) 最乾淨；(c) 漸進 |
| D5 | `web_design_spec_prompt_pipeline/` 整個目錄處置？ | (a) 拆 docs/2-contracts + extras + 外部 repo (b) 整體搬到 docs/extras/web-pipeline/ (c) 維持原狀並加 frontmatter | 需要 PM 與前端確認 pipeline 是否仍 active |
| D6 | F-001~F-023 / REQ-NNN 是否要重新編號為 BF/UF/SF/FR？ | (a) 重編號 + 留 alias (b) 不動，加 mapping legacy 文件 (c) VibeCoding 適應現有編號 | 影響 PR/Issue 的 grep |
| D7 | `_flows-bdd-test/_SSOT-alignment-matrix` 是否改為 AUTO 產出？ | (a) 改 AUTO (b) 維持手動 (c) 保留手動 + 補 AUTO 校驗 | 23 流程矩陣每次 PR 都要更新 |
| D8 | Phase 2 開始的 cutoff 日期 / owner / commit window？ | （待 PM 排程） | 此 migration 全程 4-8 週 |

---

## §7 風險與緩解

| 風險 | 嚴重度 | 緩解 |
| :-- | :-- | :-- |
| Wikilink 大量斷掉 | HIGH | 用 grep + sed 批次 rewrite + Phase 6 前舊路徑保留 redirect stub |
| PR/Issue 引用舊路徑 404 | MEDIUM | git mv 保留 history；加 `.github/REDIRECT.md` 對照表 |
| 遷移期 AI 讀到舊+新版本不一致 | HIGH | 舊版本立刻加 `status: superseded` + `superseded-by: <new-path>` frontmatter；`.claude/rules/change-governance.md` 已會跳過 superseded |
| `_audit/` 自身被遷走會破壞當前審查工具 | LOW | 本檔的 follow-up CR 應在 4-exploration/ 落地；舊 _audit/ 留 90 天再刪 |
| Pipeline 遷移影響前端工程師日常 | MEDIUM | 前端 owner 必須加入 D5 決策；可考慮 phase 5 後做 |
| F-XXX → BF/UF/SF rename 影響 `_SSOT-alignment-matrix` 與 PR title | HIGH | D6 選 (b) — 不重編號，只補 mapping legacy 文件 |

---

## §8 下一步

1. **使用者讀本檔** → 對 §6 八條決策表達偏好（或使用 AskUserQuestion 蒐集）
2. AI 依拍板結果產 `4-exploration/CR-0001-vibecoding-migration-2026-05-10.md`（正式 CIA 格式）
3. CR-0001 §8 鎖定 → 進入 Phase 2 骨架建置
4. 同時產 `vibecoding-mapping-table-2026-05-10.md`（254 個檔案逐一對應，作為 Phase 2-5 的 to-do tracker）

> **本檔自身的歸宿**：完成 migration 後，本檔搬到 `docs/4-exploration/audits/vibecoding-migration-analysis-2026-05-10.md`，標 `status: shipped, shipped-as: docs/ 全 reorg`。

---

## §9 變更紀錄

| 日期 | 內容 |
| :--- | :--- |
| 2026-05-10 18:30 | 初版 — Phase 0 完整盤點 + slop 模式 + 高層 mapping + 目標結構草案 + 8 條待決策 |
