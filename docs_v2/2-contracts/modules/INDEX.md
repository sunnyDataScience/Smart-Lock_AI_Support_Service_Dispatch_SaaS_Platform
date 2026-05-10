---
title: Module Contracts Index
tier: 2
status: active
last_updated: 2026-05-10
---

# 2-contracts/modules/ — Module Contracts Index

> Phase 3 已從 `docs/02-design/specs/*-spec.md` 直接複製內容；下個 iteration 會逐檔重構為 VibeCoding `module-contract.template.md` 結構（pre/post conditions、invariants、API surface）。
>
> 帶 `_pending-merge_` 前綴的檔案 = 應併入別的 module，等下個 iteration 處理。

## 已複製的 module contracts (12)

| Module | 來源 | 對應 code | 重構狀態 |
| :-- | :-- | :-- | :-- |
| [`audit-logger.md`](./audit-logger.md) | `02-design/specs/audit-log-spec.md` | `agent/storage/audit_*`、API `/api/admin/audit-events` | TODO: pre/post conditions、event schema 結構化 |
| [`consumer-tracking.md`](./consumer-tracking.md) | `02-design/specs/consumer-tracking-entry.md` | API `/api/public/work-orders/{token}` | TODO: HMAC token spec 提到 frontmatter |
| [`data-export.md`](./data-export.md) | `02-design/specs/data-export-spec.md` | API `/api/admin/audit-events?format=csv` | TODO |
| [`dispatch-engine-weights.md`](./dispatch-engine-weights.md) | `02-design/specs/dispatch-weights.md` | `api/services/dispatch_engine.py` | TODO: 併入 `dispatch-engine.md`（待建）或留作 master-data |
| [`e-signature.md`](./e-signature.md) | `02-design/specs/e-signature-spec.md` | TBD | TODO |
| [`inter-agent-messaging.md`](./inter-agent-messaging.md) | `02-design/specs/inter-agent-messaging-spec.md` | `agent/skills/tools.py` (transfer_to_human) | TODO |
| [`inventory.md`](./inventory.md) | `02-design/specs/inventory-management-spec.md` | F-210 規格不全（尚待 PM） | TODO |
| [`problem-card-engine.md`](./problem-card-engine.md) | `02-design/agent-harness/problem-card-spec.md` | `api/services/problem_card_service.py` | TODO |
| [`rbac.md`](./rbac.md) | `02-design/specs/rbac-dynamic-spec.md` | `api/services/rbac_service.py` | TODO: 併入 `_pending-merge_role-matrix.md` 內容 |
| [`realtime-messaging.md`](./realtime-messaging.md) | `02-design/specs/realtime-messaging-spec.md` | `api/realtime/*`（WebSocket）| TODO |
| [`refund-service.md`](./refund-service.md) | `02-design/specs/refund-approval-spec.md` | `api/services/refund_service.py` | TODO |
| [`sla-monitor.md`](./sla-monitor.md) | `02-design/specs/sla-availability-spec.md` | `api/services/sla_monitor.py` | TODO: SPLIT — targets 抽到 `0-principles/frontend-quality-attributes.md §SLA` |
| [`vision-processing.md`](./vision-processing.md) | `02-design/specs/vision-processing-spec.md` | `agent/harness/multimodal.py` | TODO |
| [`warranty-claim.md`](./warranty-claim.md) | `02-design/specs/warranty-dispute-spec.md` | `api/services/warranty_service.py` | TODO |

## 待併入別處（_pending-merge_ 前綴）

| 檔案 | 應併入 | 動作 |
| :-- | :-- | :-- |
| `_pending-merge_role-matrix.md` | `rbac.md §role-matrix` | Phase 3 後段 |
| `../api/_pending-merge_webhooks.md` | `2-contracts/api/asyncapi.yaml §webhooks` | Phase 3 後段 |
| `../../0-principles/_pending-merge_sla-policy.md` | `0-principles/product-principles.md §SLA-policy` | Phase 4 |
| `../../0-principles/_pending-merge_workday-sla-policy.md` | `0-principles/product-principles.md §workday-policy` | Phase 4 |

## 待新建（從 V1.0 module-spec 拆出）

來源：`docs/_flows-bdd-test/v-model-left/E7x--module-spec-v1-core.md`（V1.0 的 5 個核心模組）

| 待建 | 對應 code |
| :-- | :-- |
| `conversation-manager.md` | `agent/harness/debounce.py` + `app.py` |
| `three-layer-resolver.md` | `agent/agent.py` + `harness/safety_gate.py` + `output_validator.py` |
| `pricing-engine.md` | `api/services/pricing_*` |
| `sop-generator.md` | `agent/harness/sop_extractor.py` |
| `dispatch-engine.md` | `api/services/dispatch_engine.py`（與 `dispatch-engine-weights.md` 整合）|

## 待新建（從 _flows-bdd-test 抽 module）

| 待建 | 對應 code |
| :-- | :-- |
| `technician-matcher.md` | `api/services/dispatch_engine.py` (V2.0) |
| `sla-monitor.md` | 已建（Phase 3） |
| `notification.md` | from `1-decisions/ADR-0012-notification-channels.md` 拆 |

## frontmatter 標準（每個 module-contract 必加）

```yaml
---
id: API-NNNN（或 MOD-NNNN）
status: accepted
last-synced-with: <commit-sha>
sync-source: code | doc
source-paths:
  - api/services/X_service.py
  - tests/integration/test_X.py
synced-at: 2026-05-10
related:
  - "../flows/business/BF-NNNN-*"
  - "../api/openapi.yaml#/paths/.../"
---
```
