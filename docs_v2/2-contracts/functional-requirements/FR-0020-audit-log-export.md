---
id: FR-0020
title: 稽核日誌完整性與匯出
tier: 2
priority: P0
status: ✅ Live
last-synced-with: pending
sync-source: doc
synced-at: 2026-05-10
legacy_id: REQ-020
trace_to_flow: F-020
related:
  - "../../0-principles/id-mapping-legacy.md §A.3 (REQ→FR)"
  - "../../0-principles/product-principles.md"
  - "../flows/business/"
  - "../api/openapi.yaml"
---

# FR-0020 — 稽核日誌完整性與匯出

> 從 `docs/_flows-bdd-test/north-star-requirements.md REQ-020` 抽出，升級為 4-digit FR ID。

## §1 Description

稽核日誌完整性與匯出

## §2 Priority

**P0** (Must-have for V1)

## §3 Acceptance Criteria

所有寫入操作留 audit log；可由後台 exportAuditEvents 匯出

## §4 Trace

| Aspect | Reference |
| :-- | :-- |
| Legacy ID | REQ-020 |
| Legacy F-XXX flow | F-020 |
| Implementation status | ✅ Live |

## §5 Change Log

| Date | Change |
| :--- | :--- |
| 2026-05-10 | 從 north-star-requirements REQ-020→FR-0020 split |
