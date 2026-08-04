# TC-EXC-01 — webhook 重送去重與 DLQ 人工 review

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務；webhook 去重測試需 Postgres 而 skip |
| 走查時間 | 2026-08-03 16:40（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/agent/user_memory/postgres_store.py:162-191`、`api/realtime/commission_outbox_worker.py`、`api/routers/lifespan_health.py:112-143`、`api/routers/line_webhook.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 去重部分與 TC-CS-AI-09 同一實作，一致；DLQ 以 outbox `status='dead'` 形式存在並有人工重放提示，但「1h 內人工 review」的期限機制找不到，且該 outbox 不涵蓋 LINE webhook 路徑。 |

**TC 原文**｜前置：LINE webhook 首次處理失敗｜步驟：LINE 平台重送同一 event id｜判定基準：reserve-first 永久 PK 去重，重試不重複建卡；持續失敗入 DLQ，1h 內人工 review｜需求：FR-AGT-10、FR-API-15｜旅程：SC-02、SC-09、SC-11、SC-19

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| LINE 平台 | 重送同一 event id | （不應發生）`ProblemCardDrafted` ×2 | 永久 PK 去重 | `postgres_store.py:175-185` | `INSERT ... ON CONFLICT (event_id) DO NOTHING` |
| 系統 | 事件持續失敗 | `EventMovedToDLQ` | 入 DLQ | `api/realtime/commission_outbox_worker.py:174-201` | 重試耗盡 → `status='dead'` |
| OPS | 1h 內人工 review | `DLQReviewed` | 期限內處理 | — | **找不到**期限機制；只有布林旗標與 log |
| LINE webhook | postback 處理失敗 | `EventMovedToDLQ` | 不遺失 | `api/routers/line_webhook.py:216-219` | 只記 log 並回 200，無 DLQ |

---

## 走查紀錄

### 步驟 1 — reserve-first 去重

- **動作**：讀去重實作
- **預期**：永久主鍵去重、重試不重複建卡
- **實際**：一致。實作與呼叫位置詳見 TC-CS-AI-09；主鍵為 `event_id`，寫入位於所有業務分派之前（`agent/lockcore/channels/line_gateway.py:1213-1217`），故重送不會重跑 turn，也就不會重複建卡

### 步驟 2 — DLQ 的形式

- **動作**：搜尋 DLQ 機制
- **預期**：有 dead letter 佇列
- **實際**：無名為 `dead_letter` 的表；等價機制為 outbox 的 `status='dead'`

`SQL/migrations/119-commission-event-outbox.sql:41-50`

```sql
    status            VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts          INTEGER NOT NULL DEFAULT 0,
    max_attempts      INTEGER NOT NULL DEFAULT 8,
    CONSTRAINT chk_commission_outbox_status CHECK (status IN ('pending','sent','failed','dead')),
```

`api/realtime/commission_outbox_worker.py:174-201`

```python
    new_attempts = current_attempts + 1
    if new_attempts >= max_attempts:
        await self._mark_dead(outbox_id, err)
...
async def _mark_dead(self, outbox_id: str, err: str) -> None:
    """耗盡重試 → dead。... 由 OPS 撈 status='dead' 人工重放（保留 event_id 故重放仍冪等）。"""
```

退避序列 `commission_outbox_worker.py:36-37`（30s／2m／8m／30m／2h／6h，8 次約覆蓋 21 小時）。同型的 LINE push worker 在 `api/realtime/line_push_outbox_worker.py:469-493`。

### 步驟 3 — 「1h 內人工 review」

- **動作**：找 review 期限的實作或告警
- **預期**：有 1 小時期限機制
- **實際**：**找不到**期限。現有的是布林旗標、15 分鐘積壓判斷與一行 error log

`api/routers/lifespan_health.py:112-143`

```python
outbox["needs_manual_replay"] = dead > 0
outbox["backlog_stalled"] = oldest > 900   # 15 分鐘
outbox["replay_hint"] = ("SELECT id, event_id, reconciliation_id, last_error FROM "
    "commission_event_outbox WHERE status = 'dead';") if dead > 0 else None
if dead > 0:
    logger.error("commission outbox 有 %d 筆 dead 事件待人工重放（佣金投影未同步）", dead)
```

無 timer、無 escalation、無 review 期限欄位。

### 步驟 4 — LINE webhook 路徑是否有 DLQ

- **動作**：確認 DLQ 是否涵蓋本 TC 所述的 webhook 情境
- **預期**：webhook 持續失敗會進 DLQ
- **實際**：現有 outbox 為佣金事件與 LINE push，不涵蓋 inbound webhook。`api/routers/line_webhook.py:216-219` 的 postback 失敗只記 log 並回 200

TC 判定基準的前半（去重）與後半（DLQ + 1h review）分別對應不同機制，前者一致、後者部分存在。此處僅並陳，不裁定。

### 步驟 5 — 執行既有測試

- **動作**：跑去重與 outbox 測試
- **預期**：取得執行證據
- **實際**：去重測試 3 項因需 `POSTGRES_URI` 而 skip；outbox 測試通過

```
cd agent && python -m pytest tests/test_webhook_idempotency.py ... -q -rs
SKIPPED [1] tests\test_webhook_idempotency.py:24: 需 POSTGRES_URI（scratch webhook_idempotency 表）
SKIPPED [1] tests\test_webhook_idempotency.py:38: 需 POSTGRES_URI（scratch webhook_idempotency 表）
SKIPPED [1] tests\test_webhook_idempotency.py:51: 需 POSTGRES_URI（scratch webhook_idempotency 表）

cd api && python -m pytest tests/test_cr_0017_outbox_worker.py tests/test_cr_0175_outbox_idempotency.py ... -q --tb=no -rf
22 failed, 25 passed in 5.36s
```

`api/tests/test_cr_0189_commission_outbox.py:379` 有斷言 `status = 'dead'` 的測試；找不到「1h 人工 review」或 webhook DLQ 的測試。

---

## 觀測到的其他事實

- `status='dead'` 的重放保留 `event_id`，故重放仍冪等（`commission_outbox_worker.py:_mark_dead` docstring）。
- 去重 store 僅在 Postgres backend 下建立，sqlite backend 不啟用（`agent/lockcore/app_config.py:207-216`）。
- 去重的 DB 例外為 fail-open（`postgres_store.py:186-188`），該時段去重失效。
