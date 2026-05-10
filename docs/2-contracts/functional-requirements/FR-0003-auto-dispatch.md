---
id: FR-0003
title: 自動派工演算法（規則引擎）
tier: 2
priority: P0
status: 🚧 In Dev
last-synced-with: pending
sync-source: doc
synced-at: 2026-05-10
legacy_id: REQ-003
trace_to_flow: F-003
related:
  - "../../0-principles/id-mapping-legacy.md §A.3 (REQ→FR)"
  - "../../0-principles/product-principles.md"
  - "../flows/business/"
  - "../api/openapi.yaml"
---

# FR-0003 — 自動派工演算法（規則引擎）

> 從 `docs/_flows-bdd-test/north-star-requirements.md REQ-003` 抽出，升級為 4-digit FR ID。

## §1 Description

自動派工演算法（規則引擎）

## §2 Priority

**P0** (Must-have for V1)

## §3 Acceptance Criteria

派工建立 → assigned 狀態 ≤ 30s，匹配條件覆蓋區域/品牌/技能

## §4 Trace

| Aspect | Reference |
| :-- | :-- |
| Legacy ID | REQ-003 |
| Legacy F-XXX flow | F-003 |
| Implementation status | 🚧 In Dev |

## §5 Change Log

| Date | Change |
| :--- | :--- |
| 2026-05-10 | 從 north-star-requirements REQ-003→FR-0003 split |
