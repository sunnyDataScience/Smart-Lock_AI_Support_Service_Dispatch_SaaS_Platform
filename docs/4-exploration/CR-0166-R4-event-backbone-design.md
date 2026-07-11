# CR-0166 R4 — Kafka 事件骨幹設計（待業主 D2 選型後實作）

- **日期**：2026-07-12
- **狀態**：✅ **已實作**（業主 2026-07-12 裁決 D2=Redpanda）。branch `feat/m3-r4-kafka`。

## §0 as-built（2026-07-12 實作）

| WBS | 交付 | 檔案 |
|---|---|---|
| S1 | Kafka client（opt-in／fail-soft，KAFKA_BOOTSTRAP 未設=no-op）＋Redpanda compose（profile events）＋main.py producer 生命週期 | `api/core/event_bus.py`、`web/brand-portal/docker-compose.yml`、`api/pyproject.toml`（aiokafka） |
| S2 | dual-write producer：`workorder.lifecycle`（_publish_and_return，全生命週期轉移共用點）＋`commission.accrued`（reconciliation approve→settlement 建立點） | `api/services/work_order_service.py`、`api/services/reconciliation_service.py` |
| S3 | 技師平台 CQRS 投影 consumer（欄位最小化＋event_id 冪等）＋投影 schema | `api/realtime/event_consumer.py`、`SQL/tech_authority/Schema_cqrs_projection.sql` |
| S4 | Settlement consumer（commission.accrued→佣金投影） | `api/realtime/event_consumer.py`（handle_commission_accrued） |
| S5 | 期末對帳閘門（品牌 settlements vs 技師佣金投影對平，C4 mismatch=0）＋ops 端點 | `api/services/event_reconcile_service.py`、`api/routers/reconciliations_v2.py`（commissionReconcileGateV2） |
| S6 | 單測 7＋**真 Redpanda E2E**（producer→broker→consumer→兩投影寫入驗證）＋api 全套 1847 綠 | `api/tests/test_cr_0166_event_backbone.py` |

**驗證**：真 Redpanda broker E2E——2 事件發送→consumer 處理→WO 投影（status=assigned/
district）＋佣金投影（1500.00）正確寫入；冪等（同 event_id skip）；api 1847 passed（no-op
預設路徑零回歸）。**outbox 保底仍在**（雙寫過渡：DB 路徑不變，Kafka 為新增解耦路徑）。

> outbox 退役（§3 步驟 3）＝Kafka prod 穩定運行＋對帳閘門零異常後執行——列後續輪，本輪保留雙寫。
- **依據**：ADR-006（即時高併發骨幹）、ADR-017（技師平台佣金邊界＋工單 CQRS 投影）、17_AsyncAPI.yaml。
- **範圍**：WBS 3.1.1（事件骨幹）／3.1.2（技師工作台 CQRS 投影）／3.2.1（期末對帳閘門）。

> ⚠️ 本文件為**設計**，不含實作。引入 message broker 屬承重架構變更＋新增基礎設施
> ＋運維承諾，須業主先拍板 D2 選型才建置——避免在假設預設上把 broker 接到金流事件路徑。

## §1 D2 選型建議：Redpanda

| 面向 | Redpanda（建議） | Apache Kafka |
|---|---|---|
| 協定相容 | ✅ Kafka wire protocol 相容（producer/consumer 程式碼可換） | 正典 |
| 本機/dev | 單一 binary、無 ZooKeeper/KRaft 額外元件、compose 一容器 | 重（broker＋協調） |
| 運維 | 內建 schema registry、單 process | 需多元件維運 |
| 遷移風險 | 介面走標準 Kafka protocol → 未來可換原生 Kafka | — |

建議 **Redpanda**：ADR 記錄「相容性承諾」，實作走 `confluent-kafka`/`aiokafka` 標準 client，
未來規模證實需原生 Kafka 可換 broker、程式不動。**per-brand vs 集中**＝集中共用（ADR-006 §重評觸發建議）。

## §2 事件契約（Topic Schema，consumer-driven）

| Topic | Producer | Consumer | Payload（欄位最小化） |
|---|---|---|---|
| `workorder.lifecycle` | 品牌 api（工單狀態機） | ①技師平台投影 ②SigNoz | `{event_id, tenant_id, work_order_id, status, technician_id, occurred_at, document_number}` |
| `commission.accrued` | 品牌 api（Billing，完工結算） | 技師平台 Settlement | `{event_id, tenant_id, work_order_id, technician_id, amount, currency, accrued_at, breakdown}` |
| `technician.lifecycle` | 平台 api（生命週期） | 各品牌候選集失效 | `{event_id, technician_id, event_type, occurred_at}` |

- **event_id**＝冪等鍵（consumer 去重，對齊既有 webhook_idempotency/idempotency_keys pattern）。
- **schema registry**＋consumer-driven contract test（ADR-017 §60）——避免 producer 改欄位破 consumer。
- **投影隱私**（ADR-017 §61）：技師視角投影欄位最小化＋租戶標記，防跨租戶技師平台外洩品牌敏感資料。

## §3 outbox → Kafka 遷移路徑（保底不中斷）

現況：`line_push_outbox`＋各 service 的 outbox 輪詢（LinePushOutboxWorker 等 cron）。

1. **雙寫過渡**：producer 端在既有 DB 交易內同時寫 outbox（保底）＋發 Kafka（新路徑），consumer 冪等去重 → 任一路徑重複無害。
2. **consumer 切換**：技師平台投影/Settlement 改訂閱 Kafka；驗證投影一致後，outbox 輪詢降為 fallback。
3. **outbox 退役**：Kafka 穩定運行 N 週＋reconcile 閘門（§4）零異常後，移除輪詢 cron。

> 保底：ADR-006 §49「Kafka 解耦消費」＋outbox 雙寫確保「事件遺失/重複消費」風險由 reconcile 閘門把關金流正確性（roadmap §風險登記）。

## §4 期末對帳閘門（3.2.1）

- 品牌側 per-job 佣金明細（品牌庫）vs 技師平台跨品牌彙總（lock_tech statement）——期末 reconcile 對平。
- **C4 hash mismatch = 0**（27_Roadmap 階段閘條件 3）：對帳單 hash-chain（複用 CR-0166 R1-5 的 advisory-lock append-only pattern）＋mismatch 偵測 → 阻結算。
- 最終一致性容忍（ADR-017 §59）：技師看工單可接受事件延遲；金流結算必經對帳閘門。

## §5 實作 WBS（D2 拍板後）

| 步 | 內容 | 前置 |
|---|---|---|
| S1 | compose 加 Redpanda 容器＋schema registry；`kafka_client.py`（producer/consumer 封裝，fail-soft） | D2 |
| S2 | `workorder.lifecycle`＋`commission.accrued` producer（雙寫過渡，交易內發事件） | S1 |
| S3 | 技師平台投影 consumer（CQRS read-model，lock_tech 自有投影表）＋師傅 web 改讀投影 | S2 |
| S4 | Settlement consumer（訂閱 commission.accrued，跨品牌 statement） | S2 |
| S5 | 期末對帳閘門（reconcile＋hash mismatch gate） | S3/S4 |
| S6 | consumer-driven contract test＋雙實例 e2e＋outbox 退役 | S2-S5 |

## §6 🛑 待業主裁決（動工前）

1. **D2 選型**：Redpanda（建議）vs Apache Kafka。
2. **運維承諾**：確認接受新增 broker 基礎設施（本機 compose＋prod 集中共用元件）的維運成本。
3. **per-brand vs 集中**：建議集中共用（ADR-006 §重評）；確認。
4. **事件量估計**：初期低量（工單/佣金事件非逐訊息熱路徑）——確認不需一開始就叢集化。
