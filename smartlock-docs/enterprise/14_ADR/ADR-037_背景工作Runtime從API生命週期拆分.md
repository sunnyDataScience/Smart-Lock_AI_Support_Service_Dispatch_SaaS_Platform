---
title: "ADR-037: 背景工作 Runtime 從 API 生命週期拆分"
version: 1.0
status: active
owner: API Owner / SRE
last-updated: 2026-07-27
refines:
  - ./ADR-006_即時高併發骨幹_Kafka_Redis_讀寫分離.md
relates:
  - ./ADR-003_工程治理排程_API收斂_migration_CD.md
  - ./ADR-021_psycopg3_rawSQL與純SQL_migration.md
---

# ADR-037: 背景工作 Runtime 從 API 生命週期拆分

| 欄位 | 內容 |
|---|---|
| 狀態 | 規劃中（目標與遷移順序定案；依 WBS 3.6.6 逐 job cutover） |
| 層級 | 系統級（api / runtime / operations） |
| 關聯 ADR | refines [ADR-006](./ADR-006_即時高併發骨幹_Kafka_Redis_讀寫分離.md) Phase 0 · [ADR-003](./ADR-003_工程治理排程_API收斂_migration_CD.md) |
| 來源規劃 | [Plane 借鏡架構優化規劃](../規格統控整理/Plane借鏡架構優化規劃_2026-07-27.md) F |

## Context（背景與問題）

`api/main.py` lifespan 目前啟停 LINE outbox、SLA、reconcile、dispute、retention、
statement 等多個背景 worker。PG advisory lock、`API_SURFACE` 與單實例限制降低了重複執行
風險，但 API availability、scale 與排程生命週期仍耦合：新 revision 啟停、scale-to-zero、
多 instance 或 request 壓力都可能影響 job。

ADR-006 的 Phase 0 明確將 in-process worker 定位為單實例起點。本 ADR 定義離開 Phase 0
的 runtime 邊界；不以先導入 Kafka 作為拆分前置。

## Decision（決策）

### 1. 先建立 Job Registry

每個背景工作必須宣告：`job_id`、owner、handler、schedule/trigger、資料 scope、
idempotency key、lock key、timeout、retry/backoff、dead-letter／人工補償方式、
audit event，以及 success、duration、lag、oldest pending、retry exhausted SLI。

### 2. 依工作型態拆分 Runtime

| 工作型態 | 目標 Runtime | 契約 |
|---|---|---|
| 分鐘／小時／每日批次 | Cloud Scheduler 以專用 service account 呼叫 Cloud Run Jobs execute API | 可安全重跑、bounded runtime、有完成狀態 |
| 短週期 outbox／持續消費 | 獨立 worker service entrypoint | transaction + durable outbox、at-least-once、冪等 side effect |
| request path | API service | 只完成同步驗證、權威交易與 outbox 寫入；不等待慢工作 |

- Scheduler 呼叫 Cloud Run Job 管理 API 使用專用 IAM/OAuth 權限；若目標是受保護 HTTP
  worker endpoint，才使用 OIDC audience token。兩者不得共用真人憑證。
- outbox 與業務 mutation 在同一 DB transaction；worker 採 at-least-once，不宣稱
  exactly-once，以 idempotency／unique constraint 防重複 side effect。
- 保留 PG advisory lock 作 cutover 與人工重跑的第二防線，但不能以 lock 取代 durable
  record、retry 與 audit。
- API 與 worker 使用同 repo、共用 domain service，但有獨立 entrypoint、image command、
  service account、resource limit、health/metrics 與部署單位。

### 3. 漸進 Cutover

1. 完成 inventory 與 registry，不改行為。
2. 選一個低風險週期 job 做 Cloud Run Job pilot；以 shadow／dry-run 對帳結果。
3. 切換 trigger，關閉該 job 的 API lifespan 啟動；保留明確 rollback flag。
4. 再遷 outbox worker；逐 job 完成，不做 big-bang。
5. Kafka／Pub/Sub 只有在跨系統事件 owner、replay、PII 與 OD-002／003 定案後才導入，
   不是本 ADR 的完成條件。

## Alternatives（考量的選項）

- **A：永久維持 API lifespan worker** — 單機簡單，但阻斷 API 正常 scale，拒絕作為目標態。
- **B：先全面 Kafka 化** — 增加基礎設施與治理，無助於週期 job 的第一步拆分，拒絕。
- **C：Scheduler/Jobs + 獨立 outbox worker 漸進拆分（採用）** — 依工作型態選 runtime，
  保留現有 PostgreSQL outbox 與冪等資產。

## Consequences（後果）

- ＋API 可用性與背景工作成功率分開量測、部署與擴展。
- ＋job 可重跑、可補償、可追蹤，不依賴某一 API instance 存活。
- ＋不必等待 Kafka production 證據即可先降低 runtime 耦合。
- －新增 worker entrypoint、IAM、Scheduler／Jobs 設定與獨立告警。
- －cutover 期間存在雙跑風險，必須使用 lock、idempotency、shadow evidence 與 rollback flag。

**完成門檻**：API target mode 不再啟動已遷移 job；pilot job 重跑不產生重複 side effect；
lag／retry exhausted 可觀測；API 與 worker 可獨立部署及 rollback。

## 重評觸發

outbox throughput、跨系統 fan-out 或 replay 需求超過 PostgreSQL 輪詢能力時，依 ADR-006
與 OD-002／003 另案評估 Kafka／Pub/Sub，不把 queue 選型混入本 runtime 邊界。
