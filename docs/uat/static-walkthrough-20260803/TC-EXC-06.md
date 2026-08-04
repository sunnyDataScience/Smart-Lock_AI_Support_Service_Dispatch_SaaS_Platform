# TC-EXC-06 — Consumer 停擺後的事件重播與冪等

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 8） |
| 走查時間 | 2026-08-03 19:10（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/realtime/event_consumer.py`、`api/realtime/commission_outbox_worker.py`、`api/core/event_bus.py`、`api/services/work_order_service.py`、`SQL/migrations/119-commission-event-outbox.sql`、`SQL/Schema_work_order_events.sql`、`SQL/tech_authority/Schema_cqrs_projection.sql` |
| 優先級 / 路徑類型 | P1 / ⚠ 未標註 |
| 事實結論 | 事件冪等的實際載體是 **`event_id`**（`event_consumer_dedup` 表 + `commission_event_outbox.event_id` 穩定重送），兩個 handler 皆為 `ON CONFLICT DO UPDATE` 冪等 upsert。TC 判定基準指名的 `seq` 存在於 `work_order_events`（per-工單連號、UNIQUE 約束），但**不在 Kafka 事件 payload 中**，consumer 側不使用 seq；`idempotency_keys` 表為 API 寫操作去重（24h），非事件層。重播路徑：consumer 用 group offset + `auto_offset_reset="earliest"`；結算側有 `commission_event_outbox` 退避重送與 `dead` 狀態，工單生命週期事件則無 outbox（發布 fail-soft）。 |

**TC 原文**｜前置：consumer 停擺 30 分鐘後恢復｜步驟：事件重播｜判定基準：投影/結算最終一致補齊；事件冪等（seq + idempotency key）不重複入帳｜⚠ 未標註｜P1｜FR-API-14、FR-DAT-05、FR-PLT-04、FR-TEC-04、FR-TEC-05｜SC-05、SC-13、SC-14

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| Consumer | 停擺後恢復 | `ConsumerResumed` | 續讀未處理事件 | `realtime/event_consumer.py:184-192` | `group_id` + `enable_auto_commit=True` + `auto_offset_reset="earliest"` |
| Consumer | 處理事件 | `EventProcessed` | 冪等，不重複 | `realtime/event_consumer.py:123-140` | `event_id` 唯讀查 dedup → handler → 成功後才標記 |
| Consumer | 更新投影 | `ProjectionUpserted` | 最終一致 | `realtime/event_consumer.py:77-95` | `ON CONFLICT (work_order_id) DO UPDATE` |
| Outbox worker | 重送佣金事件 | `CommissionEventRepublished` | 結算補齊 | `realtime/commission_outbox_worker.py:139-149` | 帶原 `event_id` 重送，退避 30s→6hr |
| 系統 | 事件序號 | `SeqAssigned` | `seq` 冪等 | `SQL/Schema_work_order_events.sql:52-53` | per-工單連號，**未進 Kafka payload** |

---

## 走查紀錄

### 步驟 1 — 重播的機制

- **動作**：讀 consumer 的 Kafka 設定
- **預期**：停擺期間事件可補讀
- **實際**：consumer group + auto-commit + earliest

`api/realtime/event_consumer.py:183-192`

```python
        try:
            self._consumer = AIOKafkaConsumer(
                *_TOPICS,
                bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP"),
                group_id=_CONSUMER_GROUP,
                enable_auto_commit=True,
                auto_offset_reset="earliest",
                value_deserializer=lambda v: json.loads(v.decode()),
            )
            await self._consumer.start()
```

`_CONSUMER_GROUP = os.getenv("EVENT_CONSUMER_GROUP", "technician-platform-projection")`（`:23`）。整條 consumer 為 opt-in：`:26-27` `return bool(os.getenv("KAFKA_BOOTSTRAP"))`。

### 步驟 2 — 事件冪等的實際鍵

- **動作**：讀去重邏輯
- **預期**：`seq` + idempotency key
- **實際**：以 `event_id` 為鍵，且標記時機在 handler 成功之後

`api/realtime/event_consumer.py:123-140`

```python
async def process_event(topic: str, event: dict) -> bool:
    """單事件處理（冪等＋dispatch handler）。回 True＝已處理；False＝重複/無 handler/失敗。"""
    handler = _HANDLERS.get(topic)
    if handler is None:
        return False
    event_id = event.get("event_id")
    conn = await _tech_conn()
    try:
        if event_id and await _already_processed(conn, event_id, topic):
            return False  # 重複，skip
        await handler(conn, event)
        # CR-0188：**成功之後**才記 dedup —— 先記會讓失敗事件永久無法重播
        if event_id:
            await _mark_processed(conn, event_id, topic)
        return True
```

`api/realtime/event_consumer.py:60-72`

```python
async def _mark_processed(conn, event_id: str, topic: str) -> None:
    """handler 成功後才記 dedup（CR-0188）。

    與唯讀檢查搭配會有「同一事件並發重投」的競態窗口，但兩個 handler 都是
    `ON CONFLICT ... DO UPDATE` 冪等 upsert（technician_workorder_projection /
    technician_commission_projection），重複套用結果相同 —— 相較於「永久遺失投影」，
    這個取捨明確更安全。ON CONFLICT DO NOTHING 讓並發標記本身也不會炸。
    """
    await conn.execute(
        "INSERT INTO event_consumer_dedup (event_id, topic) VALUES (%s, %s) "
        "ON CONFLICT (event_id) DO NOTHING",
        (event_id, topic),
    )
```

dedup 表：`SQL/tech_authority/Schema_cqrs_projection.sql:40-44`

```sql
CREATE TABLE IF NOT EXISTS event_consumer_dedup (
    event_id      TEXT PRIMARY KEY,
    topic         VARCHAR(64) NOT NULL,
    processed_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

`event_id` 由 producer 補：`api/core/event_bus.py:94`

```python
        body = {"event_id": event_id or str(uuid.uuid4()), **payload}
```

### 步驟 3 — TC 指名的 `seq` 在哪裡

- **動作**：搜尋 `seq`
- **預期**：事件冪等以 seq 判定
- **實際**：`seq` 只存在於品牌庫 `work_order_events`，不在 Kafka payload、不在 consumer 端

```
git grep -n "\"seq\"\|'seq'\|seq_no\|sequence_number" -- api SQL
api/services/work_order_service.py:3481:            "seq": r[5],
api/tests/test_cr_0193_lifecycle_events.py:221 / :273
```

`SQL/Schema_work_order_events.sql:52-53`

```sql
    seq                 INTEGER NOT NULL,
    CONSTRAINT work_order_events_wo_seq_key UNIQUE (work_order_id, seq)
```

`SQL/migrations/122-wo-events-seq-and-lifecycle.sql:15-20` 記載 `seq` 為 per-工單連號，UNIQUE 是「連號的強制點」。

Kafka payload 欄位集合為 9 欄（`api/services/work_order_service.py:1012-1023`），不含 `seq`。TC 判定基準寫「事件冪等（seq + idempotency key）」；程式碼的事件冪等鍵是 `event_id`。此處僅並陳，不裁定。

### 步驟 4 — `idempotency key` 的所在層級

- **動作**：搜尋 idempotency key 的持久化
- **預期**：事件層冪等鍵
- **實際**：`idempotency_keys` 為 API 寫操作去重（24h），另有 `problem_cards.idempotency_key`、`payments.idempotency_key`

```
git grep -rn "idempotency_key" -- SQL
SQL/Schema_api_phase1.sql:85:CREATE TABLE IF NOT EXISTS idempotency_keys (
SQL/Schema_api_phase1.sql:98:COMMENT ON TABLE idempotency_keys IS '24h 寫操作去重；clients 重送同 key + 同 hash 直接回放';
SQL/migrations/065-pc-idempotency-key.sql:8
SQL/migrations/069-payments-mock.sql:18
SQL/migrations/110-idempotency-reserve-first.sql:4
```

consumer 側程式碼未讀取上述任一表。

### 步驟 5 — 投影補齊的冪等寫入

- **動作**：讀 handler
- **預期**：重播不產生重複列
- **實際**：兩個 handler 皆 upsert

`api/realtime/event_consumer.py:82-87`

```python
        "ON CONFLICT (work_order_id) DO UPDATE SET "
        "  technician_id = EXCLUDED.technician_id, status = EXCLUDED.status, "
        "  document_number = EXCLUDED.document_number, district = EXCLUDED.district, "
        "  scheduled_time = EXCLUDED.scheduled_time, "
        "  last_event_type = EXCLUDED.last_event_type, "
        "  occurred_at = EXCLUDED.occurred_at, updated_at = NOW()",
```

`api/realtime/event_consumer.py:105-107`

```python
        "ON CONFLICT (settlement_id) DO UPDATE SET "
        "  amount = EXCLUDED.amount, currency = EXCLUDED.currency, "
        "  accrued_at = EXCLUDED.accrued_at",
```

佣金投影主鍵為 `settlement_id`（`SQL/tech_authority/Schema_cqrs_projection.sql:27`），故同一 settlement 重播為覆寫而非新增。

### 步驟 6 — 結算側的補送耐久性

- **動作**：讀 outbox worker
- **預期**：停擺期間未送達的事件可補
- **實際**：`commission_event_outbox` 依退避重送，帶原 `event_id`；耗盡 → `dead`

`SQL/migrations/119-commission-event-outbox.sql:28-35`（節錄）

```sql
--   欄位比照既有 line_push_outbox（SQL/Schema_v2_extensions.sql）的狀態機慣例，
--   但**多存 event_id**：`core/event_bus.publish_event` 未帶 event_id 時會**每次
--   新生成 uuid**，若 worker 重送時另生新 id，消費端 `_already_processed` 的
--   event_id 去重就完全失效（dedup 表無限成長、重播語意破裂）。故 outbox 必須
--   持有穩定 event_id，worker 重送時原樣帶入。
CREATE TABLE IF NOT EXISTS commission_event_outbox (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id          UUID NOT NULL,                       -- 穩定冪等鍵（重送時原樣帶入）
```

`api/realtime/commission_outbox_worker.py:39-41`

```python
# Exponential backoff seconds 對應 attempts=1..6：30s / 2min / 8min / 30min / 2hr / 6hr
# max_attempts 預設 8（migration 119）→ 末兩次沿用 6hr，總覆蓋約 21 小時。
_BACKOFF_SECONDS_BY_ATTEMPT = [30, 120, 480, 1800, 7200, 21600]
```

`api/realtime/commission_outbox_worker.py:191-201`

```python
    async def _mark_dead(self, outbox_id: str, err: str) -> None:
        """耗盡重試 → dead。**settlement 已存在、款照付**，遺失的只是跨庫投影同步；
        由 OPS 撈 status='dead' 人工重放（保留 event_id 故重放仍冪等）。"""
        await db_module._conn.execute(
            "UPDATE commission_event_outbox SET "
            "  status = 'dead', attempts = attempts + 1, last_error = %s, updated_at = NOW() "
            "WHERE id = %s::uuid",
            (err[:500], outbox_id),
        )
```

### 步驟 7 — 工單生命週期事件的耐久性

- **動作**：確認是否有對應 outbox
- **預期**：停擺期間可補送
- **實際**：無 outbox，發布為 fail-soft

`api/services/work_order_service.py:1025-1027`

```python
    except Exception:  # noqa: BLE001
        logger.exception("event publish work_order lifecycle failed (non-fatal)")
    return order
```

`api/core/event_bus.py:88-100` 中 `publish` 於未啟用時直接回 `False`，發送失敗只 log 回 `False`。既有 outbox 為 `commission_event_outbox`（`SQL/migrations/119`）與 LINE push outbox（`SQL/migrations/111`），不涵蓋此路徑。

### 步驟 8 — 執行既有測試

- **動作**：跑 outbox 與事件骨幹測試
- **預期**：取得執行證據
- **實際**：第一輪 fake-conn outbox 測試通過、投影 upsert 測試因無資料庫失敗；建立本機測試庫後重跑，兩個 outbox 檔 11 項全通過，投影 upsert 三項仍失敗，失敗原因由「無連線」改為「技師庫三張表不存在」

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_cr_0017_outbox_worker.py tests/test_cr_0175_outbox_idempotency.py \
  tests/test_cr_0166_event_backbone.py -q --tb=no
3 failed, 15 passed in 0.47s

cd api && python -m pytest tests/test_cr_0166_event_backbone.py -q --tb=line
ERROR    api.db:db.py:48 環境變數 POSTGRES_URI 未設定
D:\...\api\tests\test_cr_0166_event_backbone.py:42: AttributeError: 'NoneType' object has no attribute 'execute'
3 failed, 4 passed in 0.38s
```

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」），逐檔執行 `cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/<檔名> -q -p winloop_plugin --tb=no`：

```
test_cr_0017_outbox_worker.py              7 passed in 0.25s
test_cr_0175_outbox_idempotency.py         4 passed in 0.40s
test_cr_0166_event_backbone.py             3 failed, 4 passed in 0.42s
```

outbox 退避重送與 `event_id` 冪等（步驟 5-6 引用）11 項全數通過。`test_cr_0166_event_backbone.py` 失敗的是投影 upsert 三項（`test_workorder_projection_upsert`、`test_workorder_projection_status_progression`、`test_commission_projection_upsert`），原因為 `technician_workorder_projection`、`technician_commission_projection`、`event_consumer_dedup` 三張表在測試庫不存在。

第三輪：該三表 DDL 位於 `SQL/tech_authority/Schema_cqrs_projection.sql`，套用至品牌測試庫後重跑：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0166_event_backbone.py -q -p winloop_plugin
7 passed in 0.55s
```

步驟 2 所述 `event_consumer_dedup` 的 dedup 行為因此取得實跑證據：`test_cr_0166_event_backbone.py:37-45` 以 `event_id` 為鍵寫入與清除，7 項全過。

> 更正：本文件第二輪原記為「需 `scripts/db/split-tech-db.sh` 建技師庫、本次未建」。該敘述不正確——該腳本搬的是技師身分域表（`:23`），不含這三張投影表；且本測試檔取用品牌連線 `db_module._conn` 而非技師庫連線，在 `TECH_POSTGRES_URI` 未設的單庫 fallback 下（`api/core/db.py:244`）投影表本就落於品牌庫。實際所缺僅為該 schema 檔未套用。

`api/tests/` 中找不到「consumer 停擺 30 分鐘後恢復」的測試，實跑亦無對應案例被執行。

---

## 觀測到的其他事實

- `api/realtime/event_consumer.py:44-54` 記載 CR-0188 的修正理由：原本 dedup 是「INSERT ON CONFLICT 兼作查詢＋佔位」，在 autocommit 連線下會讓 handler 失敗的事件永久判定為已處理。
- `commission_outbox_worker` 與 `sla_monitor` 皆以 `_ensure_leader(...)` 分散式鎖限單一實例執行（`commission_outbox_worker.py:79`、`sla_monitor.py:100`）。
- `commission_outbox_worker._poll` 刻意不用 `FOR UPDATE SKIP LOCKED`（`:99-102`），互斥來自 leader 鎖，殘餘重複由消費端 `event_id` dedup 承接。
- `status='dead'` 為此專案的 DLQ 等價機制，無獨立 dead-letter topic。
