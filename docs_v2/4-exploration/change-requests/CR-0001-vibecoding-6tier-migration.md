---
id: CR-0001
title: docs/ + web_design_spec_prompt_pipeline/ → docs_v2/ (VibeCoding 6-tier 全面遷移)
date: 2026-05-10
status: accepted
phase: 4-exploration / change-request
owners: [AI Architect+PM (autonomous), Project Owner pending review]
related:
  - "../audits/vibecoding-migration-2026-05-10.md"
  - "../audits/vibecoding-mapping-table-2026-05-10.md"
supersedes: []
---

# CR-0001 — VibeCoding 6-tier 全面遷移

> **執行模式**：在 `docs_v2/` 並列重建，`docs/` 完全不動。Phase 6 才標 superseded → 90 天觀察 → 刪除。
>
> **Hard Gate**：本 CR 涵蓋 `architecture boundary` + `flow contract` + `data` + `test plan`，依 `.claude/rules/change-governance.md` 必須先有 CIA 才能動 code/docs。本檔即 CIA。
>
> **§8 已由 AI 以 Architect+PM 雙角色 auto-mode 拍板**。Project Owner 後續可推翻任一決策，啟動 follow-up CR。

---

## §1 Context

`docs/` 166 檔 + `web_design_spec_prompt_pipeline/` 88 檔 = 254 檔文件，三套並行 taxonomy（5D + TR-gate / VibeCoding 6-tier / Pipeline）導致 AI slop 與認知負擔。

完整 Phase 0 分析：
- [`vibecoding-migration-analysis-2026-05-10.md`](../audits/vibecoding-migration-2026-05-10.md)
- [`vibecoding-mapping-table-2026-05-10.md`](../audits/vibecoding-mapping-table-2026-05-10.md)

---

## §2 Trigger 面向（依 change-governance）

| 面向 | 影響 | 嚴重度 |
| :-- | :-- | :-- |
| Architecture boundary | 並列建立 docs_v2/ 6-tier 樹 | HIGH |
| Flow contract | `_flows-bdd-test/v-model-left/E5x--workflow-*` 拆 BF/UF/SF | HIGH |
| API contract | `02-design/specs/openapi.yaml` → `2-contracts/api/`；CI 路徑更新 | MEDIUM |
| Domain model / data | `_domain-knowledge/` 拆 4 向 | MEDIUM |
| Test plan | `_flows-bdd-test/v-model-right/*` 整合到 `3-process/test-plan.md` | MEDIUM |

---

## §3 Affected Artifacts

詳見 mapping table。本 §3 列受影響的 SSOT 文件：

| 類別 | 數量 | 主要動作 |
| :-- | --: | :-- |
| ADR | 9 | copy + rename 4-digit |
| API/AsyncAPI yaml | 2 | copy to `2-contracts/api/` |
| Module specs | 24 | copy + restructure to `2-contracts/modules/` |
| Flow workflows | 3 | SPLIT to BF/UF/SF + state-machine |
| Frontend arch | 2 | SPLIT 4-way per VibeCoding ADR-0001 |
| Pages | 24 | SPLIT 22 spec → 52 page-contract |
| Domain knowledge | 19 | 拆 4 向 |
| Audits | 7 | copy to `4-exploration/audits/` |
| _MOC.md | 9 | 不再生成（README.md 取代）|
| Pipeline assembly | 13 | DELETE + .gitignore（未來 CI 產出）|

---

## §4 API contract 變動

無 API behaviour 變動，純檔案位置遷移：

- `docs/02-design/specs/openapi.yaml` → `docs_v2/2-contracts/api/openapi.yaml`（先複製，docs/ 暫保留）
- `docs/02-design/specs/asyncapi.yaml` → `docs_v2/2-contracts/api/asyncapi.yaml`

CI 腳本路徑更新（Phase 3）：
- `scripts/ci/generate-api-types.sh`
- `scripts/ci/mock-server.sh`
- `scripts/ci/check-operationid-orphans.sh`
- `.github/workflows/{spec-lint, api-types-sync, orphan-check, mock-smoke}.yml`

過渡期策略：兩個位置都存在 yaml，但以 `docs_v2/` 為新 SSOT；CI 同時驗證兩邊一致（lint script）。

---

## §5 Data / DB 變動

無 schema 變動，僅 docs 中 master data 重組：

- `docs/_domain-knowledge/locksmith-checklist/02_品牌與型號完整清單.md` → `docs_v2/2-contracts/master-data/brand-model.md`（同時抽結構化資料到 `data/master/brand-model.yaml`，Phase 4）
- `03_故障碼*` → `docs_v2/2-contracts/master-data/fault-codes.md` + `data/master/fault-codes.yaml`
- `13_合作師傅名冊.md`：**含 PII，從 docs 完全移除**，改寫為 `SQL/seed/technicians.example.sql`（範例資料；真實名冊改入 ops repo / Secret Manager）

---

## §6 Test plan 變動

`docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md` → `docs_v2/3-process/test-plan.md`，吸收 `integration-test-matrix.md` + `performance-baseline.md` + `security-checklist.md` 為 sub-sections。

---

## §7 並列遷移策略（核心設計）

```
docs/                           docs_v2/
├── HOME.md          ──────►   ├── README.md            (新 hub)
├── GATE-MAP.md      ──────►   │
├── 00-discover/     ──────►   ├── 0-principles/        (Phase 2-3)
├── 01-define/       ──────►   ├── 1-decisions/         (Phase 2-3)
├── 02-design/       ──────►   ├── 2-contracts/         (Phase 3)
├── 03-develop/      ──────►   ├── 3-process/           (Phase 4)
├── 03-plan/         ──────►   ├── 4-exploration/       (Phase 4)
├── 04-deliver/      ──────►   ├── 5-views/             (Phase 4 AUTO)
├── _audit/          ──────►   ├── business/            (Phase 3)
├── _domain-...      ──────►   └── extras/              (Phase 5)
├── _flows-bdd...    ──────►
├── _gap-analysis/   ──────►
├── _meeting-...     ──────►
└── _superseded/     ──────►
                    並列存在
```

**Phase 6 收尾才動 docs/**：標 `status: superseded` + 90 天觀察 + 刪除。

---

## §8 Human Decisions (AI Architect+PM auto-mode 拍板)

| # | 決策 | 拍板 | 理由 |
| :-- | :-- | :-- | :-- |
| **D1** | 是否採 VibeCoding 6-tier 為唯一 docs taxonomy？ | **(a) 全採用** | `.claude/rules/context-stability.md` 已強制；雙 SSOT = drift；舊 5D 標 superseded 90 天後刪 |
| **D2** | TR0-TR10 與 VibeCoding `quality-gates` reconcile？ | **(b) TR-gate 為 quality-gates 的 instance** | 保留 TR 作為 PM/投資人語言（status report 用），engineering gate 統一 quality-gates；映射在 `3-process/quality-gates.md §TR-mapping` |
| **D3** | `00-discover/E1x--moat-*` + `presentation-blueprint` 處置？ | **(a) 搬到 `docs_v2/business/`** | 不離開 repo（單一專案完整性），但分離工程文件與商業簡報。`business/` 不被 6-tier 治理，自由結構。 |
| **D4** | `_domain-knowledge/locksmith-checklist/` 19 份去處？ | **(a) 拆 4 向**：glossary（純定義）+ 2-contracts/master-data（structured master data）+ 專案根 `data/`（YAML/CSV）+ DB seed example（PII） | 純定義 → 0-principles；master data → 2-contracts；YAML → data/；PII（13_師傅名冊）→ DB seed example，真實資料移至 ops |
| **D5** | `web_design_spec_prompt_pipeline/` 整體處置？ | **(a) 三向拆**：(i) smartlock 實例 → docs_v2/2-contracts/{frontend-design-system, pages}；(ii) 通用框架 → docs_v2/extras/web-frontend/pipeline/；(iii) assembly/_integrated.md → DELETE + .gitignore | 不搬出 repo（pipeline 與 web/ 強綁定）；按 stability 分 tier |
| **D6** | F-001~F-023 / REQ-NNN 重編為 BF/UF/SF/FR？ | **(b) 不動現有 ID + 補 mapping legacy + 新流程才用 BF/UF/SF/FR** | F-XXX 已散在 PR/Issue/commit；重編破壞性極高。`0-principles/id-mapping-legacy.md` 維護映射；新增 flow 一律用 VibeCoding 9-prefix |
| **D7** | `_SSOT-alignment-matrix` 改 AUTO？ | **(c) 保留手動 + 補 AUTO 校驗腳本** | sunnydata-auto-regen generator 尚未實作；先寫 lint script 檢查矩陣與 frontmatter 一致；下個 CR 才完全 AUTO |
| **D8** | Phase 2 cutoff / owner / window？ | **AI auto-mode 立刻開始、分批 commit、每 phase 一個 commit set；預計 5-8 個 /loop iteration 完成** | user 隨時可中斷或推翻；commit message 標 `CR-0001` 便於追蹤 |

---

## §9 Implementation Order（細節）

### Phase 2 — Skeleton + Hub + ADR copy（本 commit set）✅

- ✅ `docs_v2/{0-principles,1-decisions/module-boundary,2-contracts/{api,modules,...},3-process,4-exploration/{...},5-views,business,extras/web-frontend/{pipeline,design-cloning}}` 骨架
- ✅ `docs_v2/README.md` — 新 hub
- ✅ 各 tier README.md（9 份）
- ⬜ `docs_v2/0-principles/{id-mapping-legacy,flow-id-conventions}.md`
- ⬜ `docs_v2/1-decisions/ADR-0001~0009-*.md`（從 `docs/01-define/adrs/` **複製**並 rename）
- ⬜ Phase 0 audit 兩份複製到 `docs_v2/4-exploration/audits/`

### Phase 3 — Contract（後續 1-2 loop）

1. API：`02-design/specs/{openapi,asyncapi}.yaml` → `2-contracts/api/`
2. CI 腳本路徑更新（雙寫過渡）
3. 24 份 `02-design/specs/*-spec.md` → `2-contracts/modules/*.md`（重組為 module-contract 格式）
4. 3 份 `_flows-bdd-test/v-model-left/E5x--workflow-*.md` → SPLIT BF/UF/SF
5. `frontend-architecture.md` SPLIT 4-way
6. `frontend-information-arch.md` → 52 page-contracts
7. `1-decisions/architecture-overview.md` 整合 E3 + diagrams 02-10
8. `domain-model.md` 從 ERD 衍生
9. `module-boundary/{agent,api,data-pipeline,web}.md`

### Phase 4 — Process / Exploration / Views（後續）

1. `04-deliver/E8/E9/E9x` → `3-process/`
2. `02-design/E6x--code-review-and-refactoring` → `3-process/code-review-checklist.md`
3. GATE-MAP + GR6/7/10 → `3-process/quality-gates.md`（含 TR mapping）
4. `_audit/`、`_gap-analysis/`、`_meeting-minutes/`、`_superseded/` → `4-exploration/`
5. agent-harness V2.0 部分 → `4-exploration/agent-harness-v2/`
6. multi-tenant → `4-exploration/multi-tenant-platform/`
7. 5-views 跑 sunnydata-auto-regen

### Phase 5 — Pipeline（後續）

1. `web_design_spec_prompt_pipeline/global/02_smartlock_*` + `design-system-specs/smartlock/*` → `docs_v2/2-contracts/frontend-design-system.md`
2. 22 page specs SPLIT → 52 page-contracts → `docs_v2/2-contracts/pages/`
3. 通用框架 → `docs_v2/extras/web-frontend/pipeline/`
4. `assembly/*_integrated.md` → DELETE + `.gitignore` + CI step
5. `cloning/` → `docs_v2/extras/web-frontend/design-cloning/`

### Phase 6 — 收尾（後續）

1. 舊 `docs/00-discover/` ~ `04-deliver/` + `_*` 全部加 `status: superseded` + `superseded_by` frontmatter
2. wikilink 批次 rewrite（grep + sed script）
3. `docs/HOME.md` / `GATE-MAP.md` 標 legacy + redirect
4. 90 天觀察期後實際刪除舊路徑（git rm）
5. `docs_v2/` rename 為 `docs/`（git mv）
6. `traceability-matrix.md` 跑 lint 確認 BF/UF/SF/FR 覆蓋率

---

## §10 Risks & 緩解

見 [`vibecoding-migration-analysis-2026-05-10.md §7`](../audits/vibecoding-migration-2026-05-10.md)。

並列策略額外緩解：

| 風險 | 緩解 |
| :-- | :-- |
| 雙寫期間兩邊不一致 | post-write hook 在 docs/ 改動時自動標 `synced-to: docs_v2/<path>`；docs_v2/ 改動時反向標。Phase 6 前每週跑 diff 校驗 |
| 外部 PR/Issue 引用 docs/ 舊路徑 | docs/ 路徑 Phase 6 前不刪；`docs/HOME.md` 加大字 redirect notice |
| CI 腳本指向錯路徑 | CI 加 `docs_v2/` 路徑驗證；`scripts/ci/check-operationid-orphans.sh` 同時掃兩邊 |

---

## §11 變更紀錄

| 日期 | 內容 |
| :--- | :--- |
| 2026-05-10 18:25 | CR 建立、§8 8 條決策由 AI auto-mode 拍板、Phase 2 骨架完成；改為 docs_v2/ 並列策略 |
