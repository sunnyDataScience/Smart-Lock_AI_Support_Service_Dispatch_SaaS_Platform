---
title: Class Relationships (AI-AUTO)
tier: 5
status: active
last_regenerated: 2026-05-10
generator: manual (Phase 8 後改 UML extractor); from grep "^class " over agent/, api/
DO_NOT_EDIT: |
  Tier 5 = AI-AUTO 視圖。手動編輯會在下次 regen 被覆寫。
related:
  - "../1-decisions/domain-model.md"
  - "../1-decisions/module-boundary/"
  - "../2-contracts/modules/"
---

# Class Relationships

> Top-level class catalog by module. 完整 UML 待 Phase 8 跑 pyreverse / pylint。

## agent/ classes

### harness/

| Class | File | Role |
| :-- | :-- | :-- |
| `BufferEntry` | harness/buffer.py | Immutable buffer item |
| `BufferStore` | harness/buffer.py | Per-user buffer 容器 |
| `PendingState` | harness/buffer.py | Pending message 狀態 enum |
| `PendingStore` | harness/buffer.py | Per-user pending 容器 |
| `BrandModelState` | harness/quick_reply.py | Brand collection state machine |
| `QuickReplyContext` | harness/quick_reply.py | Quick Reply 暫存 context |
| `InterceptResult` | harness/quick_reply.py | 攔截結果 enum |

### memory/

| Class | File | Role |
| :-- | :-- | :-- |
| `InProcessSaver` | memory/in_process.py | dict-based checkpointer (dev only) |
| `SqliteSaver` | memory/sqlite_saver.py | SQLite checkpointer |
| `PostgresSaver` | memory/postgres_saver.py | PostgreSQL checkpointer (prod) |

### storage/

| Class | File | Role |
| :-- | :-- | :-- |
| `SqliteAuditStorage` | storage/sqlite_impl.py | Local audit log |
| `PostgresAuditStorage` | storage/postgres_impl.py | Prod audit log |

### profiles/

| Class | File | Role |
| :-- | :-- | :-- |
| `ProfileManager` | profiles/manager.py | Hard facts SCD2 + soft facts CRUD |

### notifications/

| Class | File | Role |
| :-- | :-- | :-- |
| `NotificationRouter` | notifications/router.py | 中央派發器 |
| `Notification` | notifications/base.py | 訊息 DTO |
| `DeliveryResult` | notifications/base.py | 送出結果 DTO |
| `ChannelType` (Enum) | notifications/base.py | LINE / FCM / Email / SMS |
| `ChannelAdapter` (ABC) | notifications/base.py | Adapter 抽象基底 |
| `LineChannelAdapter` | notifications/adapters/line.py | LINE Push 實作 |
| `FcmStubAdapter` | notifications/adapters/fcm.py | FCM Push (stub) |
| `EmailStubAdapter` | notifications/adapters/email.py | Email (stub) |
| `SmsStubAdapter` | notifications/adapters/sms.py | SMS (stub) |

### harness/media_storage/

| Class | File | Role |
| :-- | :-- | :-- |
| `BaseMediaStorage` | harness/media_storage/base.py | 媒體 storage 抽象 |
| `LocalMediaStorage` | harness/media_storage/local_impl.py | 本機檔案 |
| `GCSMediaStorage` | harness/media_storage/gcs_impl.py | Google Cloud Storage |

### integrations/

| Class | File | Role |
| :-- | :-- | :-- |
| `AdminAPIClient` | integrations/admin_api.py | HTTP client → api/（含 30 min cache）|

### evals/

| Class | File | Role |
| :-- | :-- | :-- |
| `EvalResult` | evals/runner.py | Single eval run 結果 |
| `RunnerDataclassTest` | evals/tests/test_smoke.py | Smoke test |
| `JudgePromptTest` | evals/tests/test_smoke.py | Judge prompt smoke |
| `ReporterTest` | evals/tests/test_smoke.py | Reporter smoke |
| `FixtureTest` | evals/tests/test_smoke.py | Fixture smoke |

### quality/

| Class | File | Role |
| :-- | :-- | :-- |
| `TestCase` | quality/quality_check.py | LLM-as-Judge test case |

### core/

| Class | File | Role |
| :-- | :-- | :-- |
| `AppConfig` | core/config.py | TOML config DTO |

## api/ classes

待 Phase 8 grep 補完。主要 service classes 對應 module-contract:

- `WorkOrderService` → `2-contracts/modules/`（待建）
- `DispatchEngine` → `2-contracts/modules/dispatch-engine.md`
- `RefundService` → `2-contracts/modules/refund-service.md`
- `ScopeChangeService` → `2-contracts/modules/`（待建）
- `RbacService` → `2-contracts/modules/rbac.md`
- `AuditLogger` → `2-contracts/modules/audit-logger.md`
- `WarrantyService` → `2-contracts/modules/warranty-claim.md`
- `ProblemCardService` → `2-contracts/modules/problem-card-engine.md`
- `ConversationService` → `2-contracts/modules/conversation-manager.md`
- `LinePushService` → `2-contracts/modules/realtime-messaging.md` (相關)
- `PricingEngine` → `2-contracts/modules/`（待建）
- `SlaMonitor` → `2-contracts/modules/sla-monitor.md`

## DDD aggregate roots（per `1-decisions/domain-model.md`）

- `Conversation` (aggregate of Messages)
- `ProblemCard` (aggregate)
- `WorkOrder` (aggregate of WorkOrderEvents, has 16 states)
- `Technician` (aggregate of Skills, Schedule)
- `Customer` (aggregate of Devices)
- `Refund`、`WarrantyClaim`、`Dispute` 各為獨立 aggregate
- `User` + `Role` (RBAC aggregate)
- `AuditEvent`（cross-cutting；hash chain TBD V3）

## 變更紀錄

| 日期 | 變更 |
| :--- | :--- |
| 2026-05-10 | 初版 — 從 grep 與 module list 整理，待 Phase 8 UML 工具補完 |
