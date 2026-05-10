---
id: FR-0004
title: 手動派工 + audit log
tier: 2
priority: P0
status: ⚠ pending Q1=A / Q6=A
last-synced-with: pending
sync-source: doc
synced-at: 2026-05-10
legacy_id: REQ-004
trace_to_flow: F-004
related:
  - "../../0-principles/id-mapping-legacy.md §A.3 (REQ→FR)"
  - "../../0-principles/product-principles.md"
  - "../flows/business/"
  - "../api/openapi.yaml"
---

# FR-0004 — 手動派工 + audit log

> 從 `docs/_flows-bdd-test/north-star-requirements.md REQ-004` 抽出，升級為 4-digit FR ID。

## §1 Description

手動派工 + audit log

## §2 Priority

**P0** (Must-have for V1)

## §3 Acceptance Criteria

派工員可繞過自動派工，所有 manual override 須留 actor_id + reason

## §4 Trace

| Aspect | Reference |
| :-- | :-- |
| Legacy ID | REQ-004 |
| Legacy F-XXX flow | F-004 |
| Implementation status | ⚠ pending Q1=A / Q6=A |

## §5 Change Log

| Date | Change |
| :--- | :--- |
| 2026-05-10 | 從 north-star-requirements REQ-004→FR-0004 split |
