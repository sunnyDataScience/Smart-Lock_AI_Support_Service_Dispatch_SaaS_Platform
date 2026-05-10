---
title: 0-principles — 不變定律
tier: 0
status: active
last_updated: 2026-05-10
---

# Tier 0 — 不變定律 (Principles)

> 變更頻率：**半年-年**。AI 每次新對話最先載入。
> 寫入：`HUMAN-ONLY`。AI 不得自行修改，必須開 ADR 才能變更。

## 包含

| 檔案 | 角色 | 來源 |
| :-- | :-- | :-- |
| `product-principles.md` | Mission / 非任務 / 品質基準 / 技術硬限制 | 待 Phase 2/3 從 `docs/00-discover/E1` + `north-star-requirements` 抽 NFR/QA |
| `glossary.md` | 業務術語 SSOT | 待 Phase 2/3 整合 `docs/_domain-knowledge/locksmith-checklist/{02,06,07,15}` 的純定義 |
| `flow-id-conventions.md` | BF/UF/SF/FR/NFR/API/TC/ADR/CR 9-prefix Flow ID | copy from `VibeCoding_Workflow_Templates/0-principles/flow-id-conventions.md` |
| `frontend-quality-attributes.md` | 前端 SLO / Core Web Vitals / A11y / 響應式 / 性能 baseline | 整合 `docs/02-design/E5x--frontend-architecture §QA` + `_flows-bdd-test/v-model-right/performance-baseline.md` + `02-design/specs/sla-*` |
| `id-mapping-legacy.md` | 舊 ID（E1/E1x/F-XXX/REQ-NNN）→ 新 BF/UF/SF/FR 對照 | 本 Phase 2 立刻寫，CR-0001 D6 配套 |

## 規則

- 任何 tier 1-5 的內容若與 tier 0 衝突，**tier 0 勝**
- 修 tier 0 = 大事，必須開 ADR + 等 owner 拍板
- AI 不得在 tier 1-5 文件中悄悄違反 tier 0 條款
- `id-mapping-legacy.md` 是**過渡期**唯一允許 AI 自動更新的 tier-0 檔（每次新增 BF/UF/SF/FR 都加一行映射）
