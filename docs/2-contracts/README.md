---
title: 2-contracts — 介面契約（必須與 code 同步）
tier: 2
status: active
last_updated: 2026-05-10
---

# Tier 2 — Contracts (Interfaces that MUST track code)

> 變更頻率：**與 code 同步**。任何 contract 變動必須先過 CR-NNNN（CIA）。
> 寫入：HYBRID（AI 草稿 → Human approve）。
> **所有檔案必須帶 `last-synced-with` frontmatter**；post-write hook 自動更新。

## 結構

| 子目錄 | 內容 | 主要來源 |
| :-- | :-- | :-- |
| `api/` | OpenAPI 3.1、AsyncAPI 2.6、API README、error codes index | `docs/02-design/specs/{openapi,asyncapi}.yaml` + `docs/02-design/error-codes.md` |
| `modules/` | 每模組一份 contract（pre/post conditions、invariants、API surface） | `docs/02-design/specs/*-spec.md` (24 份) + `agent-harness/problem-card-spec.md` |
| `flows/business/` | BF-NNNN — 業務能力 E2E flow | `docs/_flows-bdd-test/v-model-left/E5x--workflow-{work-order,dispatch,admin-governance}.md` SPLIT |
| `flows/user/` | UF-NNNN — per-actor flow | from BF SPLIT |
| `flows/sub/` | SF-NNNN — 共享 sub-flow | from BF SPLIT |
| `functional-requirements/` | FR-NNNN — 業務規則 + AC | `docs/_flows-bdd-test/north-star-requirements.md` REQ-NNN 個別化 |
| `state-machines/` | per-entity state transitions（≥5 states 才獨立檔） | `work-order` (16 states) from `E5x--workflow-work-order` + `02-design/specs/work-order-state-machine-extensions.md` |
| `master-data/` | master entity governance（DQ rules、lifecycle、GDPR） | `docs/brand_model_list.md` + `_domain-knowledge/locksmith-checklist/{02,03,07,19}` 結構化部分 |
| `pages/` | 每 page 一份 contract（route、auth、data、CTA、nav） | `docs/02-design/E5x--frontend-information-arch.md` (52 頁) + `docs/legacy/web_design_spec_prompt_pipeline/pages/*` (22 spec) SPLIT |
| `frontend-design-system.md` | tokens、atomic design、API client、auth、frontend security | `docs/02-design/E5x--frontend-architecture` + `docs/legacy/web_design_spec_prompt_pipeline/{global/02_smartlock_*, design-system-specs/smartlock/*}` |
| `flow-index.md` | **AUTO** — 所有 flow 的 frontmatter scan aggregation | `sunnydata-auto-regen` |
| `traceability-matrix.md` | **AUTO** — 跨層 ID 覆蓋率 | `sunnydata-auto-regen`（暫先手動 from `docs/_flows-bdd-test/_SSOT-alignment-matrix.md`，CR-0001 D7 取共識）|

## frontmatter 標準

```yaml
---
id: BF-0001 / UF-0002 / API-0003 / FR-0007 / TC-0042 / etc
status: draft | accepted | deprecated | superseded
last-synced-with: <git-commit-sha>
sync-source: code | doc           # 哪邊是權威
source-paths:
  - src/...
  - tests/...
synced-at: YYYY-MM-DD
related:
  - "../flows/business/BF-NNNN-*"
---
```

## 工具

- `sunnydata-doc-freshness` skill — 檢查 stale / superseded
- `sunnydata-flow-audit` skill — 檢查 broken refs / orphans / layering violations
- `sunnydata-auto-regen` skill — 重生 flow-index、traceability、5-views

## 規則

- 改 API/Flow/Module contract **必須**先跑 `sunnydata-change-impact-analysis` skill
- 不 sync 的 contract = 騙人。`last-synced-with` > 30 commits 即視為 stale
- 新增 BF/UF/SF/FR 同時要 append `0-principles/id-mapping-legacy.md`（如有對應的舊 F-XXX/REQ-NNN）
