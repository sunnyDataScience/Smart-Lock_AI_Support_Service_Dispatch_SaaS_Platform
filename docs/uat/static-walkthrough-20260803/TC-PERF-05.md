# TC-PERF-05 — outbox 1000 mutations 的事件 lag p99 ≤ 30s

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/realtime/line_push_outbox_worker.py`、`api/realtime/commission_outbox_worker.py`、`api/core/event_bus.py`、`api/routers/lifespan_health.py`、`api/realtime/job_registry.py`、`SQL/Schema_v2_extensions.sql`、`SQL/migrations/119-commission-event-outbox.sql` |
| 優先級 / 路徑類型 | P1 / ⚠ 未標註 |

判定理由：**機制面**——p99 lag 的量測機制存在且直接標註對應本 NFR：`api/realtime/line_push_outbox_worker.py:33-39` 的註解明寫「audit NFR-Perf-009 / FR-API-05b：outbox 送達延遲取樣（enqueue created_at → sent 秒）」「全體 outbox：p50/p95/p99（NFR-Perf-009 p99 ≤ 30s）」，`_percentile()`（`:59-62`）與 `get_outbox_lag_metrics()`（`:80-90`）為實作。**但**該 p99 取樣為 in-process `deque(maxlen=2000)`（`:39`），且 `get_outbox_lag_metrics()` 在 `api/` 中除測試外零呼叫點（`:37` 註解自述「OPS 由 get_outbox_lag_metrics() 讀出，不新增對外端點」）；對外可查的積壓指標是另一組 `get_job_sli()` 的 `oldest_pending_seconds` / `retry_exhausted_total`（`:180-195`、`api/routers/lifespan_health.py:117-133`），且僅接了 commission outbox 一支。**數值面**——「1000 mutations 下 p99 是否 ≤ 30s」為執行期量測，靜態不可得。另查得兩支 worker 的輪詢間隔與批量常數（LINE push 10s/20 筆、commission 20s/50 筆）。

**TC 原文**｜章節：10. 非功能案例（TC-PERF / TC-SEC-INJ / TC-A11Y）｜前置：（空）｜步驟：outbox 1000 mutations｜判定基準：事件 lag p99 ≤ 30s｜路徑類型：⚠ 未標註｜驗證面向：功能｜優先級：P1｜驗證哪些需求：NFR-Perf-009｜旅程：—

---

## 逐條驗收條件對照

| 條件 | 類型 | 程式碼落點 | 狀態 |
|---|---|---|---|
| 存在 outbox 表 | 機制存在 | `SQL/Schema_v2_extensions.sql:421-439`、`SQL/migrations/119-commission-event-outbox.sql:32-51` | 兩張（`line_push_outbox`、`commission_event_outbox`） |
| worker poll 索引 | 機制存在 | `SQL/Schema_v2_extensions.sql:446-448`、`SQL/migrations/119:60-62` | 兩張皆有 partial index `(next_attempt_at) WHERE status='pending'` |
| lag 取樣 | 機制存在 | `api/realtime/line_push_outbox_worker.py:39`、`:46-53`、`:453` | 存在（in-process deque，maxlen=2000） |
| p99 計算 | 機制存在 | `api/realtime/line_push_outbox_worker.py:59-62`、`:65-78` | 存在（`_percentile` / `_bucket_metrics`） |
| p99 ≤ 30s 門檻入碼 | 機制存在 | `api/realtime/line_push_outbox_worker.py:33-36`（註解）、`:42` | 30 存在於 `_DISPATCH_SLO_SECONDS = {"normal": 30.0, ...}`；全體 outbox 的 `slo_met` 依 **p95** 判（`:78`） |
| p99 指標可對外讀取 | 機制存在 | `api/realtime/line_push_outbox_worker.py:37`、`:80` | **無對外端點**（`get_outbox_lag_metrics` 除測試外零呼叫） |
| 積壓可觀測 | 機制存在 | `api/routers/lifespan_health.py:117-141` | 存在（`oldest_pending_seconds`／`retry_exhausted_total`／`backlog_stalled`） |
| 積壓門檻常數 | 機制存在 | `api/routers/lifespan_health.py:130` | `backlog_stalled = oldest > 900`（15 分鐘），非 30s |
| commission outbox lag 取樣 | 機制存在 | `api/realtime/commission_outbox_worker.py` | **零命中**（該檔無 `record_outbox_lag_seconds`） |
| 事件骨幹（Kafka）投遞 | 機制存在 | `api/core/event_bus.py:36-37`、`:88-100` | opt-in（`KAFKA_BOOTSTRAP` 未設 → 回 False、outbox 留 pending） |
| 1000 mutations 實測 p99 | 數值達標 | — | **無法靜態判定** |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 業務 service | 寫入 mutation | `OutboxRowEnqueued` | 與業務同交易 | `SQL/migrations/119-commission-event-outbox.sql:32`（表）、`api/realtime/commission_outbox_worker.py:3-5`（docstring） | settlement 與 outbox 同交易；commit 後立即嘗試 publish |
| worker | 輪詢待送 | `OutboxRowPicked` | 依 `next_attempt_at` 排序 | `api/realtime/line_push_outbox_worker.py:163-173`、`api/realtime/commission_outbox_worker.py:103-113` | `LIMIT BATCH_SIZE`；LINE push 版帶 `FOR UPDATE SKIP LOCKED`，commission 版刻意不帶 |
| worker | 投遞成功 | `OutboxDelivered` | 記 lag 樣本 | `api/realtime/line_push_outbox_worker.py:453` | `record_outbox_lag_seconds((now - ca).total_seconds(), push_kind, urgency)` |
| worker | 投遞失敗 | `OutboxRetryScheduled` | 指數退避 | `api/realtime/line_push_outbox_worker.py:466-487` | backoff 30/120/480/1800/7200s；達 `max_attempts` → `_mark_dead` |
| worker | 重試耗盡 | `OutboxDeadLettered` | DLQ | `api/realtime/line_push_outbox_worker.py:489-495` | `status='dead' + last_error` |
| 監控 | 讀 SLI | `BacklogObserved` | 可告警 | `api/routers/lifespan_health.py:117-141` | 回 `oldest_pending_seconds` / `needs_manual_replay` / `backlog_stalled` / `alert` |
| 多實例 | 避免重複送 | `LeaderElected` | 單一 leader | `api/realtime/line_push_outbox_worker.py:136`、`api/realtime/commission_outbox_worker.py:78` | `ensure_leader(...)` |

---

## 逐層走查

### 第 1 層 — 兩張 outbox 表與 poll 索引

`SQL/Schema_v2_extensions.sql:421-439`（`line_push_outbox`）節錄

```sql
CREATE TABLE IF NOT EXISTS line_push_outbox (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL,
    push_kind       VARCHAR(40) NOT NULL,
    ...
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts        INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 5,
    next_attempt_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ...
);
```

`SQL/Schema_v2_extensions.sql:445-448`

```sql
-- Worker poll 主索引
CREATE INDEX IF NOT EXISTS idx_outbox_pending_next
    ON line_push_outbox (next_attempt_at)
    WHERE status = 'pending';
```

`SQL/migrations/119-commission-event-outbox.sql:60-62` 為同型（`idx_commission_outbox_pending`）；`:56-57` 另有 `uniq_commission_outbox_recon` 唯一索引（`tenant_id, reconciliation_id`）。

### 第 2 層 — 輪詢間隔與批量

`api/realtime/line_push_outbox_worker.py:28-31`

```python
DEFAULT_INTERVAL = int(os.getenv("LINE_PUSH_WORKER_INTERVAL", "10"))  # seconds
BATCH_SIZE = int(os.getenv("LINE_PUSH_WORKER_BATCH", "20"))
# Exponential backoff seconds 對應 attempts=1..5：30s / 2min / 8min / 30min / 2hr
_BACKOFF_SECONDS_BY_ATTEMPT = [30, 120, 480, 1800, 7200]
```

`api/realtime/commission_outbox_worker.py:34-39`

```python
DEFAULT_INTERVAL = int(os.getenv("COMMISSION_OUTBOX_WORKER_INTERVAL", "20"))  # seconds
BATCH_SIZE = int(os.getenv("COMMISSION_OUTBOX_WORKER_BATCH", "50"))
# Exponential backoff seconds 對應 attempts=1..6：30s / 2min / 8min / 30min / 2hr / 6hr
# max_attempts 預設 8（migration 119）→ 末兩次沿用 6hr，總覆蓋約 21 小時。
_BACKOFF_SECONDS_BY_ATTEMPT = [30, 120, 480, 1800, 7200, 21600]
```

以預設值計：`line_push_outbox` 每輪最多取 20 筆、輪距 10 秒；`commission_event_outbox` 每輪最多取 50 筆、輪距 20 秒。兩支 worker 皆為單 leader 序列處理（見第 6 層），`_poll_once` 內對取出的每一列 `await self._process_row(row)` 逐筆處理（`api/realtime/line_push_outbox_worker.py:177-178`、`api/realtime/commission_outbox_worker.py:115-116`）。TC 步驟指定 1000 筆 mutations，本文件僅陳述上述常數與逐筆序列處理的事實，實際完成時間需執行期量測。

### 第 3 層 — poll 查詢

`api/realtime/line_push_outbox_worker.py:163-173`

```python
        cur = await db_module._conn.execute(
            "SELECT id, tenant_id, push_kind, target_line_id, reference_id, "
            "       reference_table, payload, attempts, max_attempts, created_at "
            "FROM line_push_outbox "
            "WHERE status = 'pending' AND next_attempt_at <= NOW() "
            "ORDER BY next_attempt_at ASC "
            "LIMIT %s "
            "FOR UPDATE SKIP LOCKED",
            (BATCH_SIZE,),
        )
```

`api/realtime/commission_outbox_worker.py:99-113`

```python
        # 刻意不用 FOR UPDATE SKIP LOCKED：共用連線是 autocommit，列鎖在語句結束即釋放，
        # 寫了也擋不住任何東西（既有 line_push_outbox_worker 就是這個誤導性寫法）。
        # 真正的互斥來自上方 ensure_leader；殘餘重複由消費端 event_id dedup 承接。
        cur = await db_module._conn.execute(
            "SELECT id, event_id, topic, event_key, payload, attempts, max_attempts "
            "FROM commission_event_outbox "
            "WHERE status = 'pending' AND next_attempt_at <= NOW() "
            "ORDER BY next_attempt_at ASC "
            "LIMIT %s",
            (BATCH_SIZE,),
        )
```

兩支查詢的 `WHERE status='pending' AND next_attempt_at <= NOW() ORDER BY next_attempt_at` 與第 1 層的 partial index `(next_attempt_at) WHERE status='pending'` 對應。

### 第 4 層 — lag 取樣與 p99 計算

`api/realtime/line_push_outbox_worker.py:33-43`

```python
# audit NFR-Perf-009 / FR-API-05b：outbox 送達延遲取樣（enqueue created_at → sent 秒）。
# 每筆帶 (seconds, is_dispatch, urgency)，供兩層 SLO 度量：
#   · 全體 outbox：p50/p95/p99（NFR-Perf-009 p99 ≤ 30s）
#   · 派工通知（is_dispatch）依 urgency 分級：normal P95 ≤ 30s、emergency P95 ≤ 15s（FR-API-05b）
# in-process 滾動視窗；OPS 由 get_outbox_lag_metrics() 讀出，不新增對外端點。
_LAG_SAMPLES: deque[tuple[float, bool, str]] = deque(maxlen=2000)

# 派工通知 push_kind（技師「新工單已派給你」）——FR-API-05b SLO 對象。
_DISPATCH_KINDS = {"tech_dispatch_assigned"}
# FR-API-05b 分級 SLO（秒）：一般派工 30s、急件 15s。
_DISPATCH_SLO_SECONDS = {"normal": 30.0, "emergency": 15.0}
```

`api/realtime/line_push_outbox_worker.py:59-62`

```python
def _percentile(sorted_samples: list[float], p: float) -> float:
    n = len(sorted_samples)
    idx = min(n - 1, max(0, int(round((p / 100.0) * (n - 1)))))
    return sorted_samples[idx]
```

`api/realtime/line_push_outbox_worker.py:65-78`

```python
def _bucket_metrics(values: list[float], slo: float | None = None) -> dict:
    vals = sorted(values)
    n = len(vals)
    if n == 0:
        d = {"count": 0, "p50_seconds": None, "p95_seconds": None, "p99_seconds": None}
    else:
        d = {
            "count": n,
            "p50_seconds": round(_percentile(vals, 50), 3),
            "p95_seconds": round(_percentile(vals, 95), 3),
            "p99_seconds": round(_percentile(vals, 99), 3),
        }
    if slo is not None:
        d["slo_seconds"] = slo
        d["slo_met"] = (n == 0) or (d["p95_seconds"] is not None and d["p95_seconds"] <= slo)
    return d
```

取樣點 `api/realtime/line_push_outbox_worker.py:440-455`

```python
        try:
            now = datetime.now(timezone.utc)
            ca = created_at
            if getattr(ca, "tzinfo", None) is None:
                ca = ca.replace(tzinfo=timezone.utc)
            urgency = "normal"
            ...
            record_outbox_lag_seconds((now - ca).total_seconds(), push_kind, urgency)
        except Exception:  # noqa: BLE001
            pass
```

TC 判定基準為「事件 lag **p99** ≤ 30s」（需求端 `smartlock-docs/enterprise/05_NFR.md:49` NFR-Perf-009 為「p99 ≤ 30s / p99.9 ≤ 2min」）／`api/realtime/line_push_outbox_worker.py:78` 的 `slo_met` 判定式讀的是 `d["p95_seconds"]`，且 `slo` 參數只在 dispatch 分桶傳入（`:83-88`），全體 outbox 桶（`:81`）不帶 `slo` 故無 `slo_met` 欄位。此處僅並陳，不裁定。

`grep -rn "record_outbox_lag_seconds\|get_outbox_lag_metrics" api/ --include=*.py`（排除 `__pycache__`）的非測試命中僅 `api/realtime/line_push_outbox_worker.py` 檔內四處（`:37`、`:46`、`:80`、`:453`）。

### 第 5 層 — 對外可讀的積壓指標

`api/realtime/line_push_outbox_worker.py:180-195`

```python
    async def get_job_sli(self) -> dict[str, float | int]:
        """由 durable outbox 量測 backlog；不是只看本 process 成功樣本。"""
        if not await _ensure_conn():
            return {}
        cur = await db_module._conn.execute(
            "SELECT "
            "COALESCE(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - "
            "  MIN(created_at) FILTER (WHERE status = 'pending'))), 0), "
            "count(*) FILTER (WHERE status = 'dead') "
            "FROM line_push_outbox"
        )
        row = await cur.fetchone()
        return {
            "oldest_pending_seconds": max(0.0, float(row[0] or 0)),
            "retry_exhausted_total": int(row[1] or 0),
        }
```

`api/realtime/commission_outbox_worker.py:118-133` 為同型。

對外端點 `api/routers/lifespan_health.py:117-141`

```python
    try:
        from realtime.commission_outbox_worker import worker as _cw
        # 方法名是 get_job_sli（不是 metrics）——寫錯會被下面的 except 吞成靜默失效，
        # 故本檔的守線測試會斷言此欄真的有值。
        outbox = dict(await _cw.get_job_sli())
        dead = int(outbox.get("retry_exhausted_total", 0) or 0)
        oldest = float(outbox.get("oldest_pending_seconds", 0) or 0)
        outbox["needs_manual_replay"] = dead > 0
        # 積壓門檻取 15 分鐘：worker 預設輪詢遠短於此，超過即代表重試在打轉
        outbox["backlog_stalled"] = oldest > 900
```

該端點為 `GET /api/v1/admin/lifespan-monitors/health`（`api/routers/lifespan_health.py:97-104`），回傳體只含 `commission_outbox` 一支的 SLI（`:139`），不含 `line_push_outbox` 的 `get_job_sli()` 或任何 p99 欄位。

`api/realtime/job_registry.py:35-42` 將 `lag_seconds`、`oldest_pending_seconds`、`retry_exhausted_total` 列為每個 job 的標準 SLI 欄位集；`:310-323` 以 `getattr(worker, "get_job_sli", None)` 探測並填入。

### 第 6 層 — 多實例序列化

`api/realtime/line_push_outbox_worker.py:134-142`

```python
            # SA-02（CR-0134）分散式鎖：他實例為 leader → 本實例待命（leader 斷線自動接手）
            if not await _ensure_leader("line_push_outbox_worker"):
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                    return
                except asyncio.TimeoutError:
                    continue
```

`api/realtime/commission_outbox_worker.py:76-84` 為同型（job 名 `commission_outbox_worker`）。

### 第 7 層 — 事件骨幹的投遞端

`api/realtime/commission_outbox_worker.py:144-149`

```python
            from core.event_bus import publish_event
            ok = await publish_event(topic, payload, key=event_key, event_id=event_id)
            err = None if ok else "publish_event 回 False（event bus 未啟用或投遞失敗）"
        except Exception as exc:  # noqa: BLE001
            ok, err = False, f"{type(exc).__name__}: {exc}"
```

`api/core/event_bus.py:84-100`

```python
        """發一則事件。回 True＝已送 broker；False＝未啟用/失敗（fail-soft，outbox 保底）。
        ...
        """
        if not enabled():
            return False
        ...
        try:
            await self._producer.send_and_wait(topic, value=body, key=key)
            return True
        except Exception:  # noqa: BLE001 — 發送失敗只 log，業務交易不回滾（雙寫保底）
            logger.warning("event publish 失敗 topic=%s（outbox 保底）", topic, exc_info=True)
            return False
```

`api/core/event_bus.py:36-37` 的 `enabled()` 讀 `KAFKA_BOOTSTRAP`；未設時 `publish_event` 一律回 False，outbox row 保持 `pending` 並持續依 backoff 重試（`api/realtime/commission_outbox_worker.py:151-160` 的 ok/失敗分支）。

### 第 8 層 — 退避與 dead-letter

`api/realtime/line_push_outbox_worker.py:466-495`

```python
    async def _mark_failed(
        self,
        outbox_id: str,
        current_attempts: int,
        max_attempts: int,
        err: str,
    ) -> None:
        new_attempts = current_attempts + 1
        if new_attempts >= max_attempts:
            await self._mark_dead(outbox_id, err)
            return
        # exponential backoff
        backoff_idx = min(new_attempts - 1, len(_BACKOFF_SECONDS_BY_ATTEMPT) - 1)
        backoff = _BACKOFF_SECONDS_BY_ATTEMPT[backoff_idx]
        next_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)
        ...

    async def _mark_dead(self, outbox_id: str, err: str) -> None:
        await db_module._conn.execute(
            "UPDATE line_push_outbox SET "
            "  status = 'dead', last_error = %s, updated_at = NOW() "
            "WHERE id = %s::uuid",
            (err[:500], outbox_id),
        )
```

`max_attempts` 預設值：`line_push_outbox` 為 5（`SQL/Schema_v2_extensions.sql:432`）、`commission_event_outbox` 為 8（`SQL/migrations/119-commission-event-outbox.sql:44`）。

---

## 既有測試證據

本次於本機 Docker 測試庫實跑（`POSTGRES_URI=postgresql://lock:0000@localhost:5433/lock_scratch_test`，Windows 需 `-p winloop_plugin`）：

```
cd api && python -m pytest tests/test_outbox_lag_metric.py \
  tests/test_cr_0017_outbox_worker.py tests/test_cr_0189_commission_outbox.py \
  tests/test_cr_0189_outbox_ops_visibility.py tests/test_lifespan_health.py \
  -q -p winloop_plugin
38 passed in 150.98s (0:02:30)
```

單獨重跑 lag 指標檔：

```
cd api && python -m pytest tests/test_outbox_lag_metric.py -q -p winloop_plugin
5 passed in 0.26s
```

`api/tests/test_outbox_lag_metric.py:29-31` 以 `record_outbox_lag_seconds(float(i))` 灌入合成樣本後讀 `get_outbox_lag_metrics()`，`:42-48` 與 `:55-62` 分別驗 normal（30s）與 emergency（15s）分級 SLO 的 `slo_met` 翻轉。該測試為純函式層（不經 DB、不經真實 worker 投遞），不產生 1000 筆 mutations 的實際 lag。

`api/tests/` 中無 1000 筆負載的 outbox 測試。

---

## 事實結論

1. outbox 有兩張表：`line_push_outbox`（`SQL/Schema_v2_extensions.sql:421`）與 `commission_event_outbox`（`SQL/migrations/119-commission-event-outbox.sql:32`），皆有 `(next_attempt_at) WHERE status='pending'` 的 partial index 供 worker poll。
2. p50/p95/p99 的計算實作存在於 `api/realtime/line_push_outbox_worker.py:59-78`，取樣點在投遞成功後（`:453`），來源為 `created_at → now` 的秒差。
3. 該 p99 樣本存於 in-process `deque(maxlen=2000)`（`:39`），`get_outbox_lag_metrics()`（`:80`）在 `api/` 非測試程式碼中零呼叫點；`:37` 註解自述「不新增對外端點」。
4. `_bucket_metrics` 的 `slo_met` 判定讀 `p95_seconds`（`:78`），且僅在 dispatch 分桶傳入 `slo`（`:83-88`）；全體 outbox 桶不帶 `slo`。TC 與 NFR-Perf-009 的判定基準為 p99。此處僅並陳，不裁定。
5. `commission_outbox_worker` 無 lag 取樣（該檔無 `record_outbox_lag_seconds` 呼叫），其對外指標為 `get_job_sli()` 的 `oldest_pending_seconds` / `retry_exhausted_total`。
6. 對外健康端點 `GET /api/v1/admin/lifespan-monitors/health`（`api/routers/lifespan_health.py:97`）只納入 commission outbox 的 SLI（`:121`、`:139`），積壓門檻常數為 900 秒（`:130`）。
7. worker 常數：LINE push 輪距 10s／批量 20（`:28-29`）；commission 輪距 20s／批量 50（`:34-35`）。兩者對取出的列逐筆序列處理，且以 `ensure_leader` 限制為單一實例執行。
8. 事件骨幹投遞為 opt-in：`KAFKA_BOOTSTRAP` 未設時 `publish_event` 一律回 False（`api/core/event_bus.py:88-89`），outbox row 留 `pending` 並依 backoff 重試至 `max_attempts`（8）後標 `dead`。
9. 退避序列：LINE push `[30, 120, 480, 1800, 7200]`；commission `[30, 120, 480, 1800, 7200, 21600]`。首次重試間隔 30 秒。
10. 「1000 mutations 下的實際 p99 lag」需執行期量測，本次未取得。
