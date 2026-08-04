# TC-CS-AI-09 — LINE webhook 重送去重

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 4） |
| 走查時間 | 2026-08-03 15:22（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/agent/user_memory/postgres_store.py:162-191`、`channels/line_gateway.py:1213-1217`、`app_config.py:207-216` |
| 優先級 / 路徑類型 | P0 / 例外 |
| 事實結論 | 去重以 `event_id` 為主鍵、於業務分派前寫入（reserve-first／mark-first），使用 `INSERT ... ON CONFLICT DO NOTHING` 原子操作；turn 失敗後程式碼無任何釋放已保留 ID 的路徑。 |

**TC 原文**｜前置：WebhookIdempotencyStore 已啟用｜步驟：LINE 平台重送同一 webhook event id｜判定基準：reserve-first 永久主鍵去重，不重複回覆、不重複建卡；失敗重試不釋放已保留 ID｜需求：FR-AGT-10｜旅程：SC-01、SC-02

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| LINE 平台 | 送 webhook event | `WebhookEventReserved` | 入口即保留 event_id | `line_gateway.py:1213-1217` | 在所有業務分派前呼叫 `mark_seen` |
| 系統 | 保留 event_id | `WebhookEventReserved` | 永久主鍵、原子操作 | `postgres_store.py:180-185` | `INSERT ... ON CONFLICT (event_id) DO NOTHING`，`rowcount==0` 即重複 |
| LINE 平台 | 重送同一 event | （不應發生）`TurnStarted` | 重複即跳過 | `line_gateway.py:1215-1217` | `mark_seen` 回 True → `continue`，不進 turn |
| 系統 | turn 處理失敗 | （不應發生）`WebhookEventReleased` | 失敗不釋放已保留 ID | `line_gateway.py:1165-1167` | 只 catch 並回兜底話術，無 delete／rollback |

---

## 走查紀錄

### 步驟 1 — 去重的主鍵與寫入方式

- **動作**：讀 store 實作
- **預期**：以 event id 為永久主鍵
- **實際**：`event_id` 為 PK，用 `ON CONFLICT DO NOTHING` 判重複

`agent/lockcore/agent/user_memory/postgres_store.py:162-188`

```python
class PostgresWebhookIdempotencyStore:
    """LINE webhook 重送去重（CR-0166 R1，跨實例/重啟防護）。

    表 public.webhook_idempotency（event_id PK）由 SQL/Schema_cr0001_integration_gaps.sql
    建立。mark_seen 用 INSERT ON CONFLICT DO NOTHING 原子操作——rowcount==0 即重複
    （優於 SELECT-then-INSERT，跨實例 race-safe）。mark-first 語意（入口即寫）＝
    at-most-once（CR-0001 §8 Q5 規格）。任何 DB 例外 → fail-open 回 False（不擋 webhook，
    與 gateway 全檔 fail-soft 哲學一致）。
    """
    ...
    def mark_seen(self, event_id: str, tenant: str = "default", source: str = "line") -> bool:
        """回 True＝已見過（重複，caller 應 skip）；False＝首見（放行）或 DB 失敗（fail-open）。"""
        if not event_id:
            return False
        try:
            cur = self._db.conn().execute(
                "INSERT INTO webhook_idempotency (event_id, tenant_id, source) "
                "VALUES (%s, %s, %s) ON CONFLICT (event_id) DO NOTHING",
                (event_id, tenant, source),
            )
            return cur.rowcount == 0
```

### 步驟 2 — reserve-first 的位置

- **動作**：確認 `mark_seen` 相對於業務處理的呼叫順序
- **預期**：入口即保留，先於任何回覆或建卡
- **實際**：在事件分派迴圈最前段，重複即 `continue`

`agent/lockcore/channels/line_gateway.py:1213-1217`

```python
                if idempotency_store is not None:
                    eid = getattr(event, "webhook_event_id", None)
                    if eid and idempotency_store.mark_seen(eid, tenant):
                        logger.info("LINE webhook 重送 event %s 已去重跳過", eid)
                        continue
```

因跳過發生在 turn 之前，「不重複回覆」與「不重複建卡」由同一個 `continue` 保證。

### 步驟 3 — 失敗重試是否釋放已保留 ID

- **動作**：搜尋去重表的刪除／回滾路徑
- **預期**：無釋放路徑
- **實際**：turn 失敗只被 catch 並回兜底話術，程式碼無 delete／rollback

`agent/lockcore/channels/line_gateway.py:1165-1167`

```python
        except Exception:
            logger.exception("LINE turn 失敗")
            reply = "不好意思,系統忙線中,請稍後再試,或留言由專員與您聯繫 🙏"
```

`postgres_store.py:167-168` 的 docstring 明載此為 at-most-once 取捨。

### 步驟 4 — 執行既有測試

- **動作**：跑 `tests/test_webhook_idempotency.py`
- **預期**：取得執行證據
- **實際**：第一輪 3 項全數 skip；接上本機測試庫後重跑，3 項全過

第一輪（無資料庫）：

```
cd agent && python -m pytest tests/test_webhook_idempotency.py ... -q -rs
SKIPPED [1] tests\test_webhook_idempotency.py:24: 需 POSTGRES_URI（scratch webhook_idempotency 表）
SKIPPED [1] tests\test_webhook_idempotency.py:38: 需 POSTGRES_URI（scratch webhook_idempotency 表）
SKIPPED [1] tests\test_webhook_idempotency.py:51: 需 POSTGRES_URI（scratch webhook_idempotency 表）
```

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」）：

```
cd agent && python -m pytest -p winloop_plugin tests/test_webhook_idempotency.py -q -rs
...                                                                      [100%]
3 passed in 3.25s
```

三項測試分別為 `test_first_seen_false_repeat_true`（首見回 False、同 event_id 再送兩次皆回 True）、`test_distinct_events_both_pass`（不同 event_id 各自放行）、`test_empty_event_id_fail_open`（空／None event_id 回 False 且不寫庫），於實際 Postgres 連線下全數通過。

---

## 觀測到的其他事實

- 主鍵為單欄 `event_id`，不含 tenant；`tenant_id` 與 `source` 為附帶欄位。
- DB 例外時 `mark_seen` 回 `False`（fail-open），該次 webhook 照常處理，去重在該時段失效（`postgres_store.py:186-188`）。
- 去重 store 僅在 Postgres backend 下建立；sqlite backend 回 `None`，即不啟用去重（`agent/lockcore/app_config.py:207-216`）。
- 資料表建立於 `SQL/Schema_cr0001_integration_gaps.sql`。
