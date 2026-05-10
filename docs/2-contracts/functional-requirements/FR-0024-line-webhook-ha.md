---
id: FR-0024
title: LINE Webhook 高可用（ack < 200ms）
tier: 2
priority: P0
status: ✅ Live
last-synced-with: pending
sync-source: doc
synced-at: 2026-05-10
legacy_id: REQ-024
trace_to_flow: F-001
related:
  - "../../0-principles/id-mapping-legacy.md §A.3 (REQ→FR)"
  - "../../0-principles/product-principles.md"
  - "../flows/business/"
  - "../api/openapi.yaml"
---

# FR-0024 — LINE Webhook 高可用（ack < 200ms）

> 從 `docs/_flows-bdd-test/north-star-requirements.md REQ-024` 抽出，升級為 4-digit FR ID。

## §1 Description

LINE Webhook 高可用（ack < 200ms）

## §2 Priority

**P0** (Must-have for V1)

## §3 Acceptance Criteria

LINE webhook 收訊後 < 200ms 回 200 OK；非同步處理長任務

## §4 Trace

| Aspect | Reference |
| :-- | :-- |
| Legacy ID | REQ-024 |
| Legacy F-XXX flow | F-001 |
| Implementation status | ✅ Live |

## §5 Change Log

| Date | Change |
| :--- | :--- |
| 2026-05-10 | 從 north-star-requirements REQ-024→FR-0024 split |
