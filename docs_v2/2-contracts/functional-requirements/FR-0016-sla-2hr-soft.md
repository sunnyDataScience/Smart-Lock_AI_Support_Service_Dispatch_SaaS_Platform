---
id: FR-0016
title: SLA 2hr 到場（Soft 警報）
tier: 2
priority: P0
status: ⚠ partial（Q5=B Soft SLA）
last-synced-with: pending
sync-source: doc
synced-at: 2026-05-10
legacy_id: REQ-016
trace_to_flow: F-016
related:
  - "../../0-principles/id-mapping-legacy.md §A.3 (REQ→FR)"
  - "../../0-principles/product-principles.md"
  - "../flows/business/"
  - "../api/openapi.yaml"
---

# FR-0016 — SLA 2hr 到場（Soft 警報）

> 從 `docs/_flows-bdd-test/north-star-requirements.md REQ-016` 抽出，升級為 4-digit FR ID。

## §1 Description

SLA 2hr 到場（Soft 警報）

## §2 Priority

**P0** (Must-have for V1)

## §3 Acceptance Criteria

派工建立到技師抵達 > 2hr，dashboard 變紅並通知主管，無賠償（V1.0）

## §4 Trace

| Aspect | Reference |
| :-- | :-- |
| Legacy ID | REQ-016 |
| Legacy F-XXX flow | F-016 |
| Implementation status | ⚠ partial（Q5=B Soft SLA） |

## §5 Change Log

| Date | Change |
| :--- | :--- |
| 2026-05-10 | 從 north-star-requirements REQ-016→FR-0016 split |
