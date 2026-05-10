---
title: Module Contracts Index — 26 modules
tier: 2
status: active
last_updated: 2026-05-10
related:
  - "../../1-decisions/module-boundary/"
  - "../api/openapi.yaml"
---

# 2-contracts/modules/ — Module Contracts Index

> 26 個 module contract，覆蓋 V1.0 + V2.0 已實作或設計完成的所有後端模組。
> 每檔 frontmatter 含 `id` (MOD-X) / `source-paths` (code 對應) / `related` (flow/ADR trace)。

## V1.0 Core (9 modules — from E7x--module-spec-v1-core)

| Module | Code | Trace |
| :-- | :-- | :-- |
| [`conversation-manager.md`](./conversation-manager.md) | `agent/harness/debounce.py` + `app.py` | M1 + F-001 |
| [`problem-card-engine.md`](./problem-card-engine.md) | `api/services/problem_card_service.py` | M2 + F-001/002 |
| [`three-layer-resolver.md`](./three-layer-resolver.md) | `agent/agent.py` + `harness/safety_gate.py` + `output_validator.py` | M3 |
| [`knowledge-base-manager.md`](./knowledge-base-manager.md) | `agent/skills/` + `data/pipeline/` | M4 |
| [`sop-generator.md`](./sop-generator.md) | `agent/harness/sop_extractor.py` | M5 |
| [`sentiment-triage-engine.md`](./sentiment-triage-engine.md) | `agent/harness/safety_gate.py` (sentiment) + `api/services/sentiment_*.py` | M6 + F-107 |
| [`proactive-photo-guidance.md`](./proactive-photo-guidance.md) | `agent/harness/multimodal.py` + agent skill | M7 + F-108 |
| [`family-review-engine.md`](./family-review-engine.md) | `api/services/family_review_*.py` | M8 + F-109 |
| [`problem-card-review-engine.md`](./problem-card-review-engine.md) | `api/services/problem_card_review_*.py` | M9 + F-105 |

## V2.0 / Existing Specs (15 modules — from 02-design/specs)

| Module | Code | Source |
| :-- | :-- | :-- |
| [`audit-logger.md`](./audit-logger.md) | `agent/storage/audit_*` + API `/api/admin/audit-events` | audit-log-spec |
| [`consumer-tracking.md`](./consumer-tracking.md) | API `/api/public/work-orders/{token}` | consumer-tracking-entry |
| [`data-export.md`](./data-export.md) | API `/api/admin/audit-events?format=csv` | data-export-spec |
| [`dispatch-engine.md`](./dispatch-engine.md) | `api/services/dispatch_engine.py` | MERGE 3 來源 (triage-rules + business-rules + ADR-0013/0018/0022) |
| [`dispatch-engine-weights.md`](./dispatch-engine-weights.md) | `api/services/dispatch_engine.py` (weights) | dispatch-weights spec |
| [`e-signature.md`](./e-signature.md) | TBD | e-signature-spec |
| [`inter-agent-messaging.md`](./inter-agent-messaging.md) | `agent/skills/tools.py` (transfer_to_human) | inter-agent-messaging-spec |
| [`inventory.md`](./inventory.md) | F-210 規格不全（待 PM） | inventory-management-spec |
| [`rbac.md`](./rbac.md) | `api/services/rbac_service.py` | rbac-dynamic-spec + role-matrix-v1 (MERGE) |
| [`realtime-messaging.md`](./realtime-messaging.md) | `api/realtime/*` (WebSocket) | realtime-messaging-spec |
| [`refund-service.md`](./refund-service.md) | `api/services/refund_service.py` | refund-approval-spec |
| [`sla-monitor.md`](./sla-monitor.md) | `api/services/sla_monitor.py` | sla-availability-spec |
| [`vision-processing.md`](./vision-processing.md) | `agent/harness/multimodal.py` | vision-processing-spec |
| [`warranty-claim.md`](./warranty-claim.md) | `api/services/warranty_service.py` | warranty-dispute-spec |

## Cross-cutting

- `technicians.PII-WARNING.md` (in `../master-data/`) — PII governance reference
- `INDEX.md` — 本檔

## 待新建（low priority）

| Module | Source | 對應 code |
| :-- | :-- | :-- |
| `notification.md` | `1-decisions/ADR-0012-notification-channels.md` 拆 | `agent/notifications/` |
| `pricing-engine.md` | `_flows-bdd-test` 抽 | `api/services/pricing_*.py` |
| `technician-matcher.md` | (V2.0 dispatch 演算法子層) | `api/services/dispatch_engine.py` (V2.0) |
| `technician-management.md` | (對應 PII technicians governance) | `api/services/technicians_*.py` |

## 重構狀態

所有 contracts 目前為「直接複製 + frontmatter 包裝」(thin contract)。
完整重構為 VibeCoding `module-contract.template.md` 結構（pre/post conditions、invariants、API surface 詳細）為 follow-up CR (low priority)。

每 contract 的 `source-paths` frontmatter 已正確標示 code 對應，後續 sunnydata-doc-freshness skill 可據此追 stale。

## frontmatter 標準

```yaml
---
id: MOD-XX
title: <module-name>
tier: 2
status: accepted
last-synced-with: <commit-sha>
sync-source: code | doc
source-paths:
  - api/services/X_service.py
  - tests/integration/test_X.py
synced-at: YYYY-MM-DD
related:
  - "../flows/business/BF-NNNN-*"
  - "../api/openapi.yaml#/paths/.../"
---
```

## Change Log

| Date | Change |
| :-- | :-- |
| 2026-05-10 | 初版 → 完整重整：26 modules（9 V1 core + 15 specs + dispatch-engine MERGE + cross-cutting）+ 4 待新建 |
