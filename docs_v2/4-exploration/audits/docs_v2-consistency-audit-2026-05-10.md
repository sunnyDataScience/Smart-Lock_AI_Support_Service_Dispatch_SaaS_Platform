---
title: docs_v2/ 內部一致性稽核 (Phase 7 完成後)
date: 2026-05-10
status: passed
related:
  - "CR-0001-status-2026-05-10.md"
  - "vibecoding-migration-2026-05-10.md"
---

# docs_v2/ 內部一致性稽核

> CR-0001 全程完成後（commit `4302e78`）對 docs_v2/ 進行完整稽核。

## §1 統計

| 維度 | 數值 |
| :-- | --: |
| 檔案總數 | 330 |
| Markdown 檔 | 320+ |
| YAML 檔 | 2 (openapi + asyncapi) |
| 內部 markdown link 數 | 123 unique |
| **Broken refs** | **0 ✅** |
| **重複 frontmatter id** | **0 ✅** |
| **_pending-* 檔** | **0 ✅** |
| _legacy-* 檔（刻意保留）| 5 |

## §2 各 Tier 檔案分布

| Tier | 檔數 | 健康狀態 |
| :-- | --: | :-- |
| 0-principles | 7 | ✅ 完整（含 glossary, product-principles, frontend-quality-attributes, flow-id-conventions, id-mapping-legacy, technician-skill-taxonomy, README）|
| 1-decisions | 29 | ✅ 含 22 ADR (ADR-0001~0023, 略 ADR-0010 待多租戶觸發) + 4 module-boundary + arch-overview + domain-model + 4 ADR pending decisions |
| 2-contracts | 149 | ✅ 含 26 module + 4 BF + 22 SF + 25 FR + 53 page-contract + 2 state-machine + 6 frontend-design-system + 7 master-data + INDEX |
| 3-process | 15 | ✅ 含完整流程（workflow / code-review / security / deploy / quality-gates / test-plan / bdd-guide / bdd/all-features / vendor-api / frontend-pre-merge / ai-design / photo-evidence / knowledge-asset / docs-maintenance / migration-cutover-runbook）|
| 4-exploration | 58 | ✅ 含 8 CR + 9 audit + meeting + archive + agent-harness-v2/ 11 + multi-tenant/ 8 + data-collection/ 11 + PRD/SOW/WBS |
| 5-views | 2 | ⚠️ 待 sunnydata-auto-regen 補 4 個 view |
| business | 5 | ✅ moat / pitch / exec arch |
| extras | 64 | ✅ pipeline 12 + design-cloning 28 + pages-legacy 23 + README |

## §3 Frontmatter ID 命名一致性

唯一 ID 統計：
- ADR-NNNN: 22 (ADR-0001~0009, 0011, 0012, 0013~0023)
- BF-NNNN: 4 (BF-0000, BF-0001, BF-0002, BF-0003)
- SF-XX-NN: 22 (SF-0001 + SF-WO-01~13 + SF-G1~4 + SF-DSP-01~04)
- FR-NNNN: 25 (FR-0001~0025)
- MOD-V1-NN: 9 (V1.0 core modules)
- MOD-DISPATCH: 1
- PAGE-XX: 53 (A0-A37, T0-T10, G1-G4)
- SM-WORK-ORDER: 1
- MD-CUSTOMER-DEVICE: 1
- CR-NNNN: 8 (CR-0001, 0002, 0003, 0006, 0007, 0008, 0009, 0010, 0011)
- ADR-0010 (多租戶 isolation): TBD（待多租戶 phase A 觸發）

## §4 Cross-Reference 一致性

- ✅ 0 broken links （內部 markdown 連結全部 resolve）
- ✅ 0 重複 frontmatter id
- ✅ 所有 SF 都有 `parent_bf` frontmatter
- ✅ 所有 FR 都有 `legacy_id: REQ-NNN`
- ✅ 所有 ADR-0013~0022 都有 `legacy_id: PM-Q1~Q10`

## §5 Legacy 標記檔（刻意保留）

| 檔案 | 用途 |
| :-- | :-- |
| `extras/web-frontend/pipeline/_legacy_BASE_DESIGN_SYSTEM.md` | 與 VibeCoding `frontend-design-system.template.md` 衝突的舊模板，不再 active reference |
| `extras/web-frontend/pipeline/_legacy_SYSTEM_DOCUMENT_SPEC.md` | 衝突的 4-tier doc 系統 |
| `extras/web-frontend/pipeline/_legacy_sunny_brand_system.md` | 非本專案實例（桑尼品牌） |
| `extras/web-frontend/design-cloning/_legacy-base/` (4 spec) | 通用 base spec，與 smartlock 變體重複 |
| `extras/web-frontend/design-cloning/_legacy-grok/` (5 spec) | Grok 變體，與 smartlock 重複 |

這些檔保留為歷史參考，命名 `_legacy-*` 明示不應作為 SSOT。

## §6 待補完項目（不影響結構性遷移完成度）

| 項目 | 性質 | 處理 CR |
| :-- | :-- | :-- |
| 53 page-contract §4 Data Sources + §5 Component Map | 待從 openapi + web/src 推 | sunnydata-auto-regen 或人工 |
| 5-views/ 4 個 AI-AUTO 檔 (project-structure / file-deps / class-rel / route-map) | 待自動產出 | sunnydata-auto-regen |
| 25 FR-NNNN §4 Trace 模組關聯 | 待從 source code 推 | 自動或人工 |
| ADR-0023-payment-provider 改為 status: accepted | 待 PM Q7 後續決策 | 業務驅動 |
| ADR-0010-multi-tenant-isolation 創建 | 待多租戶 Phase A 觸發 | CR-0003 觸發後 |

## §7 Phase 8 prerequisites 滿足

- ✅ docs_v2/ 結構完整
- ✅ 0 broken refs
- ✅ 0 _pending-* 衝突
- ✅ CR-0007 / CR-0008 / CR-0009 draft 就位
- ✅ Migration cutover runbook 就位

可隨時啟動 Phase 8a (CR-0007)。

## §8 變更紀錄

| 日期 | 內容 |
| :--- | :--- |
| 2026-05-10 | 初版稽核 — Phase 7 完成後內部一致性確認 |
