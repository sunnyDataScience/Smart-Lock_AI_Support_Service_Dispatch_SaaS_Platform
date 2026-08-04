# TC-NFR-SCAL-01 — 多實例階梯負載、限流降級與跨租戶隔離

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **無法靜態判定** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 9） |
| 走查時間 | 2026-08-03 20:18（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/realtime/ws_hub.py`、`api/core/db.py`、`api/core/distributed_lock.py`、`api/core/config.py`、`api/config.toml`、`api/services/technician_kyc_service.py`、`api/realtime/commission_outbox_worker.py`、`api/realtime/event_consumer.py` |
| 優先級 / 路徑類型 | P1 / failure＋recovery |
| 事實結論 | 判定基準（容量指標、限流與降級是否符合 NFR）為執行期量測，無程式碼可據以判定。靜態查得：全域限流開關 `[rate_limit] enabled = false` 且註記「僅回 header 不真擋」，實際生效的限流只有兩處 per-IP in-memory 桶（KYC 上傳、品牌申請查詢），註記明載多 replica 失準；WS 跨實例 fanout 有 Redis 橋（opt-in，失敗退單機）；雙重排程由 `pg_try_advisory_lock` 抑制，但 DB 不可用時 `ensure_leader` 回 `True`（退單機語意照跑）；DB 連線池上限由 `DB_POOL_MAX`（預設 10）控制；`NFR-Scal-003~008` 的具體容量數值在 `api` 中無對應常數。 |

**TC 原文**｜前置：多實例、WS/Redis、技師與租戶階梯負載 fixture｜步驟：逐段增加租戶、技師、WS、queue 與 DB connection 負載，並模擬單一實例離線｜判定基準：容量指標、限流與降級符合 NFR；無跨租戶事件、雙重排程或無聲遺失｜failure＋recovery｜P1｜NFR-Scal-003～008｜SC-05

---

## 為何無法靜態判定

判定基準是「在階梯負載與單一實例離線下，容量指標／限流／降級符合 NFR，且無跨租戶事件、雙重排程或無聲遺失」。這需要多實例部署、Redis、資料庫與可施加階梯負載的 fixture，並在過程中取樣指標。原始碼可以顯示是否**存在**限流實作、鎖機制與降級分支，但無法產生「在 N 租戶 / M 技師 / K WS 連線下的實際表現」。本批走查的前提是不啟動服務，故此條無法取得判定所需事實。

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 壓測 fixture | 階梯增加負載 | `CapacityMeasured` | 符合 NFR-Scal-003~008 | — | 不可觀察（需執行期數據） |
| 系統 | 超過限流 | `RequestThrottled` | 限流生效 | `core/config.py:21`、`config.toml:38-41` | 全域限流 `enabled = false` |
| 系統 | WS 跨實例廣播 | `MessageFanout` | 多實例一致 | `realtime/ws_hub.py:113-128` | Redis pub/sub 橋，opt-in；失敗退單機 |
| 系統 | 單一實例離線 | `LeaderFailover` | 無雙重排程 | `core/distributed_lock.py:37-55` | `pg_try_advisory_lock`；DB 不可用 → 回 `True` |
| 系統 | 跨租戶存取 | `CrossTenantDenied` | 無跨租戶事件 | `routers/dispatch_v2.py:67-73` | 403 `CROSS_TENANT_READ` / `CROSS_TENANT_WRITE` |
| 系統 | queue 積壓 | `BacklogObserved` | 無無聲遺失 | `realtime/commission_outbox_worker.py:119-133` | `get_job_sli` 回 `oldest_pending_seconds` / `retry_exhausted_total` |

---

## 走查紀錄

### 步驟 1 — 全域限流的實際狀態

- **動作**：讀限流設定與消費點
- **預期**：有生效的限流
- **實際**：`config.toml` 中 `enabled = false`，註記「僅回 header 不真擋」

`api/config.toml:38-41`

```toml
[rate_limit]
# in-memory token bucket（先簡化，僅回 header 不真擋）
enabled = false
requests_per_minute = 120
```

`api/core/config.py:21` 與 `:48` 只是把該段讀進 `rate_limit: dict`。`api/main.py:248` 於 CORS 設定中 expose `RateLimit-Limit` / `RateLimit-Remaining` / `RateLimit-Reset` header。

### 步驟 2 — 實際生效的限流

- **動作**：搜尋真正會 raise 429 的限流
- **預期**：多處限流
- **實際**：兩處 per-IP in-memory 桶

`api/services/technician_kyc_service.py:69-89`

```python
# 公開端點 per-IP 限流(in-memory,單實例;多 replica 失準已記 CR-0114 已知取捨)
_RATE_WINDOW_SEC = 15 * 60
_RATE_MAX_UPLOADS = 30
_rate_buckets: dict[str, deque[float]] = {}


def rate_limit_check(client_ip: str | None) -> None:
    """同 IP 15 分鐘內最多 30 次上傳;超過 → 429。無 IP(測試)不擋。
    ...
    """
    if not client_ip:
        return
    now = time.monotonic()
    bucket = _rate_buckets.setdefault(client_ip, deque())
    while bucket and now - bucket[0] > _RATE_WINDOW_SEC:
        bucket.popleft()
    if len(bucket) >= _RATE_MAX_UPLOADS:
        raise ApiError("RATE_LIMITED", "上傳過於頻繁,請稍後再試", 429)
    bucket.append(now)
```

另一處為 `api/services/brand_application_service.py:156`（`_lookup_rate_limit_check`）。派工／媒合端點（`routers/dispatch_v2.py`、`routers/work_orders_v2.py`）未呼叫任何限流函式。

### 步驟 3 — WS 跨實例 fanout 與降級

- **動作**：讀 WS hub 的 Redis 橋
- **預期**：多實例一致廣播
- **實際**：opt-in；Redis 失敗記 `[WS_BRIDGE_ALERT]` ERROR 並退單機

`api/realtime/ws_hub.py:96-98`

```python
# CR-0134 / SA-02：跨實例 WS fanout —— REDIS_URL 設定時，publish 經 Redis pub/sub
# 複寫到所有實例（各實例把訊息送給自己本地的 WS 連線）；未設定＝單機 in-memory
# 行為完全不變。Redis 斷線＝本地照送＋ERROR 告警（跨實例遺失風險可觀測）。
```

`api/realtime/ws_hub.py:113-128`

```python
    async def start_redis(self) -> bool:
        """REDIS_URL 設定時啟動跨實例橋；回是否啟用。失敗＝退單機（fail-soft）。"""
        url = os.environ.get("REDIS_URL", "").strip()
        if not url:
            return False
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(url, decode_responses=True)
            await self._redis.ping()
            self._redis_task = asyncio.create_task(self._redis_reader())
            logger.info("ws hub Redis 橋啟用（跨實例 fanout）instance=%s", self._instance_id[:8])
            return True
        except Exception as e:  # noqa: BLE001 — Redis 不可用退單機，不擋啟動
            logger.error("[WS_BRIDGE_ALERT] Redis 橋啟動失敗，退單機 fanout: %r", e)
            self._redis = None
            return False
```

`smartlock-docs/enterprise/05_NFR.md:91`（NFR-Scal-008）記載「WS 走 Redis pub/sub 水平擴展（🔜 規劃中）」，`:286` 記載「NFR-Scal-008 多技師併發水平擴展（Redis 橋已備，水平擴展待部署）」。

### 步驟 4 — 雙重排程的抑制

- **動作**：讀分散式鎖
- **預期**：多實例不重複排程
- **實際**：`pg_try_advisory_lock`；DB 不可用或鎖異常時回 `True`（所有實例都會跑）

`api/core/distributed_lock.py:37-55`

```python
async def ensure_leader(job: str) -> bool:
    """本實例是否為 job 的 leader（詳見模組 docstring）。絕不 raise。"""
    if job in _held:
        return True
    try:
        if not await _ensure_conn():
            return True  # DB 不可用 → 單機 degraded，照跑
        cur = await db_module._conn.execute(
            "SELECT pg_try_advisory_lock(%s, %s)", (_LOCK_NS, _job_key(job)),
        )
        row = await cur.fetchone()
        got = bool(row and row[0])
        if got:
            _held.add(job)
            logger.info("cron leader acquired: %s（本實例接手排程）", job)
        return got
    except Exception:  # noqa: BLE001 — 鎖機制故障不可癱瘓 cron；退單機語意
        logger.exception("ensure_leader(%s) 異常——退單機語意照跑", job)
        return True
```

使用者：`realtime/sla_monitor.py:100`、`realtime/commission_outbox_worker.py:79`、`realtime/family_review_sla_cron.py:71` 等。

### 步驟 5 — DB connection 上限

- **動作**：讀連線池設定
- **預期**：有容量上限
- **實際**：`DB_POOL_MIN` / `DB_POOL_MAX` 環境變數，預設 1 / 10；WS 長連線不進池

`api/core/db.py:316-326`

```python
        from psycopg_pool import AsyncConnectionPool

        pool = AsyncConnectionPool(
            ...
            min_size=int(os.getenv("DB_POOL_MIN", "1")),
            max_size=int(os.getenv("DB_POOL_MAX", "10")),
            ...
        )
        await pool.open(wait=True, timeout=30)
        _pool = pool
        ...
            "[DBPool] 連線池已開（min=%s, max=%s）", pool.min_size, pool.max_size
```

`api/core/db.py:361-362` 註記「純 ASGI：http 請求包 pool_scope。websocket 不包（長連線佔池；WS 面…）」。開池失敗時 `_pool = None`（`:331`），退回共用單一連線。

### 步驟 6 — 跨租戶隔離點

- **動作**：確認租戶邊界檢查
- **預期**：無跨租戶事件
- **實際**：端點層 guard 與投影表的 `tenant_id` 欄位

`api/routers/dispatch_v2.py:67-73`

```python
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )
```

`SQL/tech_authority/Schema_cqrs_projection.sql:12`

```sql
    tenant_id         UUID NOT NULL,                 -- 租戶標記（防跨租戶外洩）
```

事件 payload 亦帶 `tenant_id`（`api/services/work_order_service.py:1013`）。

### 步驟 7 — queue 積壓與遺失的可觀測性

- **動作**：找 backlog / dead-letter 指標
- **預期**：無聲遺失可被偵測
- **實際**：佣金 outbox 有 SLI 查詢；工單生命週期事件無 outbox

`api/realtime/commission_outbox_worker.py:119-133`

```python
    async def get_job_sli(self) -> dict[str, float | int]:
        """由 durable outbox 讀 oldest pending 與 dead-letter 累計。"""
        if not await _ensure_conn():
            return {}
        cur = await db_module._conn.execute(
            "SELECT "
            "COALESCE(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - "
            "  MIN(created_at) FILTER (WHERE status = 'pending'))), 0), "
            "count(*) FILTER (WHERE status = 'dead') "
            "FROM commission_event_outbox"
        )
```

`api/services/work_order_service.py:1025-1027` 的工單事件發布失敗只記 log，無 outbox 保底。

### 步驟 8 — NFR-Scal 具體數值是否入碼

- **動作**：搜尋容量門檻常數
- **預期**：程式碼中有容量指標
- **實際**：`NFR-Scal-003~008` 的數值（30 萬戶、50 萬張、600GB、租戶數 1/10/30+）在 `api` 中零命中；只在 `smartlock-docs/enterprise/05_NFR.md:84-91` 出現

```
git grep -rn "NFR-Scal-00" -- api web SQL agent loadtest
（無輸出）
```

### 步驟 9 — 既有測試

- **動作**：找相關測試
- **預期**：能提供容量證據
- **實際**：`api/tests/` 中找不到多實例／階梯負載測試；`smartlock-docs/enterprise/20_Test_Cases.md:158-163` 對 NFR-Scal-003~008 標註「⚠ 完全沒有案例」。本批次實際執行的測試如下，第二輪於本機測試庫重跑後仍不產生容量／併發數據。

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_cr_0017_outbox_worker.py tests/test_cr_0175_outbox_idempotency.py \
  tests/test_cr_0166_event_backbone.py -q --tb=no
3 failed, 15 passed in 0.47s
```

（3 個 failed 皆因 `POSTGRES_URI` 未設。）

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」），逐檔執行 `cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/<檔名> -q -p winloop_plugin --tb=no`：

```
test_cr_0017_outbox_worker.py              7 passed in 0.25s
test_cr_0175_outbox_idempotency.py         4 passed in 0.40s
test_cr_0166_event_backbone.py             3 failed, 4 passed in 0.42s
```

outbox 兩檔 11 項全通過。`test_cr_0166_event_backbone.py` 的 3 項失敗原因為 `technician_workorder_projection`、`technician_commission_projection`、`event_consumer_dedup` 三張表在測試庫不存在。

第三輪：該三表 DDL 位於 `SQL/tech_authority/Schema_cqrs_projection.sql`，套用至品牌測試庫後重跑 → **7 passed in 0.55s**。

> 更正：本文件第二輪原記為「需 `scripts/db/split-tech-db.sh` 建技師庫、本次未建」。該敘述不正確——該腳本搬的是技師身分域表（`:23`），不含這三張投影表；本測試檔取用品牌連線 `db_module._conn`，在 `TECH_POSTGRES_URI` 未設的單庫 fallback 下（`api/core/db.py:244`）投影表本就落於品牌庫。實際所缺僅為該 schema 檔未套用。

上述三輪皆為單實例、單程序執行，無多實例、無 Redis／Kafka、無階梯負載，故仍不提供容量判讀所需的量測，本 TC 判定維持「無法靜態判定」。

---

## 判定所需的前置條件

要把此 TC 從「無法靜態判定」推進到可判定，需要：多實例部署環境、Redis、Kafka（`KAFKA_BOOTSTRAP`）、可施加階梯負載的租戶／技師／WS fixture、容量指標的取樣管道（現有 `api/core/observability.py` 只有 span 匯出、無百分位聚合），以及對單一實例強制離線的授權。

---

## 觀測到的其他事實

- `api/realtime/event_consumer.py:26-27` 顯示 CQRS consumer 為 opt-in（`KAFKA_BOOTSTRAP` 未設即不啟動）；`api/core/event_bus.py:35-36` 的 producer 同為 opt-in。
- `api/realtime/commission_outbox_worker.py:99-102` 註記刻意不用 `FOR UPDATE SKIP LOCKED`：「共用連線是 autocommit，列鎖在語句結束即釋放…真正的互斥來自上方 ensure_leader；殘餘重複由消費端 event_id dedup 承接」。
- `api/services/dispatch_service.py:401-411` 的技師查詢無 LIMIT，候選集大小隨租戶技師數線性成長。
