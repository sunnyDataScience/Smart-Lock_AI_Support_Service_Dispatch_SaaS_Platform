---
id: FR-0002
title: ProblemCard 智能分診
tier: 2
priority: P0
status: active
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
sync-source: doc
synced-at: 2026-05-15
legacy_id: REQ-002
trace_to_flow: F-001 / F-002
related:
  - "../../0-principles/id-mapping-legacy.md §A.3 (REQ→FR)"
  - "../../0-principles/PRIN-0001-product-principles.md"
  - "../flows/business/"
  - "../api/openapi.yaml"
---

# FR-0002 — ProblemCard 智能分診

> 從 `docs/_flows-bdd-test/north-star-requirements.md REQ-002` 抽出，升級為 4-digit FR ID。

## §1 Description

ProblemCard 智能分診

## §2 Priority

**P0** (Must-have for V1)

## §3 Acceptance Criteria

### §3.1 SLO（正常路徑）

ProblemCard 自動生成完整度 ≥ 0.85（合約 9.3 條），缺欄位觸發追問。

### §3.2 邊界案例

- 停產型號 → 降級至品牌層級 diagnostics + 標 escalate
- 重複生成同 conversation_id → 回傳既有 card（冪等）

### §3.3 異常處理

- 空對話訊息列表 → 422 invalid_input
- LLMGateway 5xx → fallback 最低門檻 (brand+symptoms) 後繼續

### §3.4 TC Coverage

涵蓋之 TC（per `docs/2-contracts/test-cases/registry.yaml`）: BDD-0007~0011 (ProblemCard 智慧分診), IT-0017~0022 (problem-card-engine), IT-0135~0140 (problem-card-review-engine)

## §4 Trace

| Aspect | Reference |
| :-- | :-- |
| Legacy ID | REQ-002 |
| Legacy F-XXX flow | F-001 / F-002 |
| Implementation status | ✅ Live |

## §5 Change Log

| Date | Change |
| :--- | :--- |
| 2026-05-10 | 從 north-star-requirements REQ-002→FR-0002 split |
