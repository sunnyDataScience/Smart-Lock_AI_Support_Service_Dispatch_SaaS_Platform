---
id: FR-0018
title: 客服接管對話（三層解決機制）
tier: 2
priority: P0
status: ⚠ partial（LINE Push API 整合 TODO）
last-synced-with: pending
sync-source: doc
synced-at: 2026-05-10
legacy_id: REQ-018
trace_to_flow: F-018
related:
  - "../../0-principles/id-mapping-legacy.md §A.3 (REQ→FR)"
  - "../../0-principles/product-principles.md"
  - "../flows/business/"
  - "../api/openapi.yaml"
---

# FR-0018 — 客服接管對話（三層解決機制）

> 從 `docs/_flows-bdd-test/north-star-requirements.md REQ-018` 抽出，升級為 4-digit FR ID。

## §1 Description

客服接管對話（三層解決機制）

## §2 Priority

**P0** (Must-have for V1)

## §3 Acceptance Criteria

AI confidence < 閾值 → 自動轉人工；客服可從後台介入回覆

## §4 Trace

| Aspect | Reference |
| :-- | :-- |
| Legacy ID | REQ-018 |
| Legacy F-XXX flow | F-018 |
| Implementation status | ⚠ partial（LINE Push API 整合 TODO） |

## §5 Change Log

| Date | Change |
| :--- | :--- |
| 2026-05-10 | 從 north-star-requirements REQ-018→FR-0018 split |
