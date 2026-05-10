---
title: extras — 工具方法論 / Pipeline / Design cloning
status: active
last_updated: 2026-05-10
---

# extras/ — 輔助資產

> **不被 6-tier 治理**。屬團隊工具與方法論，與本專案產品邏輯弱耦合。

## 子目錄

| 子目錄 | 內容 | 來源 |
| :-- | :-- | :-- |
| `web-frontend/pipeline/` | Prompt Architect Pipeline 工具方法論 | `web_design_spec_prompt_pipeline/{README.md, lovable_組裝.md, guides/, modules/, references/, assembly/PIPELINE_ORCHESTRATOR.md}` |
| `web-frontend/design-cloning/` | 設計複製方法論（Stripe-style 競品 reverse engineering） | `web_design_spec_prompt_pipeline/design-system-specs/cloning/*` |
| `web-frontend/images/` | 設計範例圖片 | `web_design_spec_prompt_pipeline/design-system-specs/images/` |

## 規則

- extras 不影響工程契約；變更不需走 CR
- 屬本專案專屬實例（如 `02_smartlock_dispatch_brand_system.md`）→ 應該屬 `2-contracts/frontend-design-system.md`，不放這裡
