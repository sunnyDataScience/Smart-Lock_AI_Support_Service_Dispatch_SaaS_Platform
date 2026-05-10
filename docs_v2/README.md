---
title: Smart Lock AI SaaS — Documentation Hub v2 (VibeCoding 6-tier)
status: active
version: v2.0-bootstrap
last_updated: 2026-05-10
related:
  - "../docs/HOME.md（legacy 5D + TR-gate hub，遷移期內並存）"
  - "../VibeCoding_Workflow_Templates/INDEX.md"
  - "../VibeCoding_Workflow_Templates/OWNERSHIP-MATRIX.md"
  - "../.claude/rules/context-stability.md"
  - "../.claude/rules/change-governance.md"
---

# Smart Lock AI SaaS — Documentation v2

> **本目錄並列於 `docs/`，採 VibeCoding 6-tier 架構從零重建**。
> 遷移完成後 `docs/` 將標 superseded → 90 天後刪除 → `docs_v2/` 改名為 `docs/`。
>
> tier 編號越小 = 越穩定 / 越權威 / AI 越早載入。

---

## 6-tier 結構

| Tier | 目錄 | 角色 | 更新頻率 | AI 載入順序 |
| :--: | :-- | :-- | :-- | :-- |
| **0** | [`0-principles/`](./0-principles/) | 不變定律 — Mission, glossary, quality bars, ID 慣例 | 半年-年 | 最先 |
| **1** | [`1-decisions/`](./1-decisions/) | append-only 判斷 — ADR、架構總覽、模組邊界、Domain Model | 變更才寫新檔 | 提案前 |
| **2** | [`2-contracts/`](./2-contracts/) | 介面契約 — OpenAPI、AsyncAPI、Module、Flow、FR、State machine、Page contract | **必與 code 同步** | 改 API 前 |
| **3** | [`3-process/`](./3-process/) | 工作流程 — Workflow、code review、quality gate、test plan、deployment runbook | 半年 | 進入該類工作前 |
| **4** | [`4-exploration/`](./4-exploration/) | 一次性意圖 — PRD、WBS、CIA/CR、audit、meeting、gap analysis | per-task | 找動機時 |
| **5** | [`5-views/`](./5-views/) | code 衍生視圖 — project structure、file deps、class graph、route map | refactor 後 AUTO | 幾乎不直接讀 |

**特例分類（非 6-tier 治理）**：
- [`business/`](./business/) — 商業/募資/簡報素材（非工程文件）
- [`extras/`](./extras/) — 工具方法論、Pipeline orchestrator、design cloning（屬輔助）

---

## 遷移狀態（CR-0001）

🎉 **CR-0001 全程完成（2026-05-10，17 commits、339 檔、0 _pending-*、0 broken refs）**

| Phase | 範圍 | 狀態 |
| :--: | :-- | :-- |
| Phase 0 | 完整盤點 + 10 slop 模式 + 254 檔對應表 | ✅ |
| Phase 1 | CR-0001 CIA + AI Architect+PM 拍板 8 條決策 | ✅ |
| Phase 2 | docs_v2/ 骨架 + 9 tier README + ID legacy + 9 ADR rename | ✅ `a2a2201` |
| Phase 3 | API + 14 module + V2/V3 blueprints | ✅ `cbb1473` |
| Phase 4 | process + audits + explorations + business + flow placeholders | ✅ `a190a4d` |
| Phase 5 | pipeline 88 檔三向拆 | ✅ `5fba15c` |
| Phase 6 | _domain-knowledge 33 檔 + PII 警示 | ✅ `573f3c2` |
| Phase 7-1 | tier-0 anchors（glossary + product-principles）+ 4 module-boundary + rbac MERGE | ✅ `2970aff` |
| Phase 7-2 | PM Q1-Q10 → 10 ADRs (ADR-0013~0022) | ✅ `7c09556` |
| Phase 7-3 | v1-core-modules → 9 module + REQ→25 FR | ✅ `845bae8` |
| Phase 7-4 | 9 MERGE operations + 新 dispatch-engine | ✅ `87b2da7` |
| Phase 7-5 | frontend-quality-attributes + CR-0006 stub | ✅ `644dbf7` |
| Phase 7-6 | SF-0001 + BF-0003 | ✅ `1cc60c9` |
| Phase 7-7 | 3 大 BF flows → 4 BF + 21 SF + state machine | ✅ `e009090` |
| Phase 7-8 | 0 個 _pending-* 達成 | ✅ `5721d63` |
| Phase 7-9 | 22 page spec → 53 thin page-contracts + INDEX | ✅ `4302e78` |
| Phase 7-10 | Phase 8 prep: CR-0007/8/9 + cutover runbook + 一致性 audit | ✅ `a2a4e42` |
| Phase 7-11 | 5-views 4 個 AUTO 視圖手動 regen | ✅ `f3ecb61` |
| **結構性遷移 + 細工 + Phase 8 prep** | **339 檔 / 0 broken refs / 0 _pending-***  | **✅ 完成** |
| Phase 8 (CR-0007) | docs/ 標 superseded + wikilinks rewrite + 90 天觀察 | ⏸ 待 PM 拍板（draft 已就位）|
| Phase 8b (CR-0009) | CI 路徑雙寫過渡 | ⏸ 待 PM 拍板（draft 已就位）|
| Phase 9 (CR-0008) | docs/ 刪除 + docs_v2/ rename → docs/ + bdd → tests/bdd/ | ⏸ Phase 8a 觀察期後 |
| Follow-up CR-0006 | 4 _pending-move-to → agent/skills + data + SQL/seed | ⏸ 待 ops 對齊 |

詳見:
- [CR-0001 status](./4-exploration/audits/CR-0001-status-2026-05-10.md)
- [docs_v2 consistency audit](./4-exploration/audits/docs_v2-consistency-audit-2026-05-10.md)
- [migration cutover runbook](./3-process/migration-cutover-runbook.md)

---

## Reading Paths

### Path A — 新人 / 新對話
1. [`0-principles/product-principles.md`](./0-principles/) — Mission / 非任務 / 品質基準
2. [`0-principles/glossary.md`](./0-principles/) — 術語 SSOT
3. [`1-decisions/architecture-overview.md`](./1-decisions/) — 系統 C4
4. [`3-process/workflow-manual.md`](./3-process/) — 怎麼做事

### Path B — 改 API / 改 Flow
1. [`.claude/rules/change-governance.md`](../.claude/rules/change-governance.md) — 是否要 CR
2. [`2-contracts/api/openapi.yaml`](./2-contracts/api/) — REST 契約
3. [`2-contracts/flows/`](./2-contracts/flows/) — BF / UF / SF
4. [`2-contracts/modules/`](./2-contracts/modules/) — 模組 contract

### Path C — 規劃功能
1. [`4-exploration/`](./4-exploration/) — 看現有 PRD / CR / audit
2. 起新 PRD：`vibecoding-write-prd` skill → `4-exploration/prd-YYYY-QN-*.md`
3. 起新 CR：`sunnydata-change-impact-analysis` skill → `4-exploration/change-requests/CR-NNNN-*.md`

### Path D — Operate / Deploy
1. [`3-process/deployment-runbook.md`](./3-process/) — 部署 SOP
2. [`3-process/security-readiness-checklist.md`](./3-process/) — 上線前
3. [`3-process/quality-gates.md`](./3-process/) — TR0-TR10 + GR6/7/10 mapping

### Path E — 投資人 / Stakeholder
1. [`business/`](./business/) — 簡報、moat 分析

---

## 與 legacy `docs/` 的對照

完整 254 檔對應表：[`docs/_audit/vibecoding-mapping-table-2026-05-10.md`](../docs/_audit/vibecoding-mapping-table-2026-05-10.md)

簡表（高層）：

| Legacy 路徑 | docs_v2/ 新位置 |
| :-- | :-- |
| `docs/HOME.md` | `docs_v2/README.md`（本檔） |
| `docs/GATE-MAP.md` | `3-process/quality-gates.md` |
| `docs/00-discover/E1--*` | `4-exploration/prd-*` |
| `docs/00-discover/E1x--moat-*` | `business/` |
| `docs/01-define/adrs/adr-NNN-*` | `1-decisions/ADR-NNNN-*` |
| `docs/01-define/E3--*` + `diagrams/` | `1-decisions/architecture-overview.md` 整合 |
| `docs/02-design/specs/openapi.yaml` | `2-contracts/api/openapi.yaml` |
| `docs/02-design/specs/*-spec.md` | `2-contracts/modules/*.md` |
| `docs/02-design/agent-harness/*` | V1.0 → `1-decisions/module-boundary/agent-harness.md` + `2-contracts/modules/`；V2.0 → `4-exploration/agent-harness-v2/` |
| `docs/02-design/platform-multi-tenant/*` | `4-exploration/multi-tenant-platform/` |
| `docs/_audit/*` | `4-exploration/audits/` |
| `docs/_domain-knowledge/*` | 拆 4 向：`0-principles/glossary.md` + `2-contracts/master-data/` + 專案根 `data/` + DB seed |
| `docs/_flows-bdd-test/*` | 拆 3 向：`2-contracts/flows/` + `2-contracts/functional-requirements/` + `3-process/test-plan.md` |
| `web_design_spec_prompt_pipeline/*` | 拆 3 向：本專案實例 → `2-contracts/{frontend-design-system, pages}`；通用框架 → `extras/web-frontend/`；assembly 中間產物 → DELETE |

---

## 文件治理規則

- **AI 處理規則**：[`.claude/rules/context-stability.md`](../.claude/rules/context-stability.md)
- **變更必經 CR**：[`.claude/rules/change-governance.md`](../.claude/rules/change-governance.md)
- **誰寫誰改**：[VibeCoding OWNERSHIP-MATRIX](../VibeCoding_Workflow_Templates/OWNERSHIP-MATRIX.md)
- **frontmatter 規範**：[VibeCoding HOW-TO-INSTANTIATE](../VibeCoding_Workflow_Templates/HOW-TO-INSTANTIATE.md)
