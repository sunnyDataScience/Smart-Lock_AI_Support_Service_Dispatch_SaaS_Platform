# TC-SEC-IDEM-01 — Idempotency-Key 重送回放

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑 `api/tests/test_cr_0165_register_idempotency.py`，4 項全數通過（見步驟 4） |
| 走查時間 | 2026-08-03（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/core/idempotency.py:1-348`、`api/config.toml:28-32`、`SQL/Schema_api_phase1.sql:83-98`、`SQL/migrations/110-idempotency-reserve-first.sql:29-41`、`api/tests/test_cr_0165_register_idempotency.py:56-124` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | TC 判定基準兩條皆有對應實作：同 `Idempotency-Key` + 同 request hash 重送時拋 `IdempotencyReplay` 回放已存 response，handler 不再執行（`api/core/idempotency.py:273-275`、`:346-347`）；TTL 為 `api/config.toml:30` 的 `ttl_hours = 24`，由 `_try_takeover` 的 `created_at <= NOW() - (ttl * INTERVAL '1 hour')` 條件生效（`:74-86`）。去重鍵為 `(tenant_id, key)` 主鍵（`SQL/Schema_api_phase1.sql:85-95`），並在 handler 執行前先佔位（reserve-first），同 key 併發第二發回 409 `IDEMPOTENCY_IN_PROGRESS`。 |

**TC 原文**｜前置：寫入端點 + Idempotency-Key｜步驟：重送同 key｜判定基準：回放不重複寫（TTL 24h）｜需求：FR-API-10｜旅程：SC-08

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| Client | 首發寫入，帶 `Idempotency-Key` | `ReservationCreated` | reserve-first | `api/core/idempotency.py:51-63` | `INSERT ... ON CONFLICT DO NOTHING`，status `in_progress` |
| Handler | 成功回應 | `IdempotencyCompleted` | 佔位補完 | `api/core/idempotency.py:109-133` | `UPDATE ... status='completed'` + 存 response |
| Client | 重送同 key 同 body | `ResponseReplayed` | 不重複寫 | `api/core/idempotency.py:273-275` → `:346-347` | 拋 `IdempotencyReplay`，由 exception handler 直接回原 response，handler 不執行 |
| Client | 重送同 key 異 body | `RequestRejected(409)` | hash 比對 | `api/core/idempotency.py:266-271` | `IDEMPOTENCY_KEY_MISMATCH` |
| Client | 同 key 併發第二發 | `RequestRejected(409)` | 佔位互斥 | `api/core/idempotency.py:277-282` | `IDEMPOTENCY_IN_PROGRESS` |
| 系統 | 列已逾 24h | `ReservationTakenOver` | TTL 24h | `api/core/idempotency.py:74-86` + `api/config.toml:30` | 原子 `UPDATE` 重佔，視同新請求 |
| Handler | 拋錯未 save | `ReservationReleased` | 錯誤不快取 | `api/core/idempotency.py:138-151`、`:304-308` | `DELETE ... status='in_progress'` |

---

## 走查紀錄

### 步驟 1 — 「回放不重複寫」的實作

- **動作**：讀 `_guard_impl` 撞列後的分支
- **預期**：命中已完成列時不進 handler
- **實際**：以 exception 中斷 dependency，FastAPI 不會進入 handler

`api/core/idempotency.py:266-282`

```python
    if existing["request_hash"] != request_hash:
        raise ApiError(
            error_code="IDEMPOTENCY_KEY_MISMATCH",
            message="Same Idempotency-Key used with different request payload",
            status_code=409,
        )

    if existing["status"] == "completed":
        # Replay
        raise IdempotencyReplay(existing["response_status"], existing["response_body"])

    # in_progress（未逾時）→ 客戶端稍後重試
    raise ApiError(
        error_code="IDEMPOTENCY_IN_PROGRESS",
        message="相同 Idempotency-Key 的請求正在處理中，請稍後重試",
        status_code=409,
    )
```

回放由 exception handler 直接產生 response（`api/core/idempotency.py:338-347`）：

```python
class IdempotencyReplay(Exception):
    """命中 idempotency cache → 由 main.py 的 exception handler 回放。"""

    def __init__(self, status: int, body: dict):
        self.status = status
        self.body = body


async def handle_idempotency_replay(request: Request, exc: IdempotencyReplay) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=exc.body)
```

「不重複寫」的第一道是 handler 執行**前**先佔位（`api/core/idempotency.py:240-244`）：

```python
    # reserve-first：先佔 → 成功者才執行 handler
    if await _try_insert_reservation(
        x_tenant_id, idempotency_key, request.method, request.url.path, request_hash
    ):
        return ctx
```

`_try_insert_reservation`（`:51-63`）以 `(tenant_id, key)` 主鍵衝突判定：

```python
    cur = await db_module._conn.execute(
        "INSERT INTO idempotency_keys "
        "  (tenant_id, key, method, path, request_hash, status) "
        "VALUES (%s::uuid, %s, %s, %s, %s, 'in_progress') "
        "ON CONFLICT (tenant_id, key) DO NOTHING "
        "RETURNING key",
        (tenant_id, key, method, path, request_hash),
    )
    return (await cur.fetchone()) is not None
```

檔頭 `api/core/idempotency.py:15-16` 記載此設計的來由：「舊版 check-then-act（先 SELECT 再事後 INSERT）在同 key 併發 2 發時雙雙 miss → handler 執行兩次（UAT R3-6：同一張問題卡兩張工單＋發票錯亂）」。

### 步驟 2 — TTL 24h

- **動作**：找 TTL 常數與其生效點
- **預期**：24 小時
- **實際**：`ttl_hours = 24` 於 config，套進 takeover 的 SQL 時間條件

`api/config.toml:28-32`

```toml
[idempotency]
ttl_hours = 24
# 適用 method
applies_to = ["POST", "PATCH", "PUT", "DELETE"]
```

`api/core/idempotency.py:230-231`

```python
    ttl_hours = int(cfg.get("ttl_hours", 24))
    reserve_ttl = int(cfg.get("reserve_ttl_seconds", _DEFAULT_RESERVE_TTL_SECONDS))
```

`api/core/idempotency.py:74-86`（TTL 過的列被原子接管，之後行為等同新請求）

```python
    cur = await db_module._conn.execute(
        "UPDATE idempotency_keys "
        "SET method = %s, path = %s, request_hash = %s, "
        "    status = 'in_progress', response_status = NULL, response_body = NULL, "
        "    created_at = NOW() "
        "WHERE tenant_id = %s::uuid AND key = %s "
        "  AND ( created_at <= NOW() - (%s * INTERVAL '1 hour') "
        "        OR (status = 'in_progress' "
        "            AND created_at <= NOW() - (%s * INTERVAL '1 second')) ) "
        "RETURNING key",
        (method, path, request_hash, tenant_id, key, ttl_hours, reserve_ttl_seconds),
    )
```

另有一個與 TTL 不同語意的常數：`_DEFAULT_RESERVE_TTL_SECONDS = 300`（`api/core/idempotency.py:38`），註解自述為「in_progress 佔位逾時秒數（handler 掛掉殘留的接管窗）」。

儲存結構：`SQL/Schema_api_phase1.sql:85-98`

```sql
CREATE TABLE IF NOT EXISTS idempotency_keys (
    tenant_id        UUID NOT NULL,
    key              TEXT NOT NULL,
    method           TEXT NOT NULL,
    path             TEXT NOT NULL,
    request_hash     TEXT NOT NULL,
    response_status  INTEGER NOT NULL,
    response_body    JSONB NOT NULL,
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, key)
);
CREATE INDEX IF NOT EXISTS idx_idem_created ON idempotency_keys(created_at);

COMMENT ON TABLE idempotency_keys IS '24h 寫操作去重；clients 重送同 key + 同 hash 直接回放';
```

`status` 欄與 nullable 化由 `SQL/migrations/110-idempotency-reserve-first.sql:29-41` 追加。

### 步驟 3 — 「寫入端點 + Idempotency-Key」的前置條件在哪裡成立

- **動作**：查 guard 的掛載方式與缺 key 的行為
- **預期**：寫入端點要求 key
- **實際**：`applies_to` 涵蓋四個寫 method，缺 key 回 400；但此強制只在有掛 dependency 的端點生效

`api/core/idempotency.py:197-206`

```python
    cfg = load_config().idempotency
    if not idempotency_key:
        # 強制策略：寫操作必填
        if request.method.upper() in cfg.get("applies_to", []):
            raise ApiError(
                error_code="MISSING_IDEMPOTENCY_KEY",
                message=f"Idempotency-Key header is required for {request.method} requests",
                status_code=400,
            )
        return None
```

掛載統計：

```
cd api && grep -rn "@router\.\(post\|put\|patch\|delete\)" routers/*.py | wc -l
302

cd api && grep -rhno "Depends([a-z_]*idem[a-z_]*)" routers/*.py | sed 's/.*Depends/Depends/' | sort | uniq -c
      1 Depends(_public_register_idem)
    139 Depends(idempotency_guard)
```

即 302 個寫入路由中有 140 個宣告了冪等 dependency。

### 步驟 4 — 執行既有測試

- **動作**：跑重送回放的既有測試
- **預期**：回放同一筆、不重複建立
- **實際**：4 項全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0165_register_idempotency.py -q -p winloop_plugin
4 passed in 3.52s
```

對到 TC 步驟「重送同 key」的是 `api/tests/test_cr_0165_register_idempotency.py:56-83`：

```python
async def test_register_replay_without_tenant_header(client):
    """同 key 同 body 重送（不帶 X-Tenant-ID）→ 回放 201 同 id，token 清洗為 null。"""
    key = str(uuid.uuid4())
    ...
        r1 = await client.post(REGISTER, json=body, headers={"Idempotency-Key": key})
        assert r1.status_code == 201, r1.text
        data1 = r1.json()["data"]
        tech_id = data1["id"]
        ...
        r2 = await client.post(REGISTER, json=body, headers={"Idempotency-Key": key})
        assert r2.status_code == 201, r2.text
        data2 = r2.json()["data"]
        assert data2["id"] == tech_id  # 回放同一位，不重複建帳號
```

同檔另三項覆蓋 `IDEMPOTENCY_KEY_MISMATCH` 409（`:87-104`）、缺 key 400（`:107-112`）、非 UUID tenant header 400（`:115-124`）。

---

## 觀測到的其他事實

- DB 不可用時 guard 直接放行不去重（`api/core/idempotency.py:226-228`）：

```python
    if not await _ensure_conn():
        # DB 不可用 → 無法 dedup（與舊版 _lookup fail-open 行為一致，不擋業務）
        return None
```

- 缺 `X-Tenant-ID` 且未指定 `default_tenant` 時同樣回 `None`（`api/core/idempotency.py:216-219`）；只有經 `make_idempotency_guard` 工廠建立的公開端點 guard 會退到 zero-UUID 公共命名空間（`:179`、`:311-335`）。目前使用該工廠的只有 `api/routers/auth.py:35`（`_public_register_idem = make_idempotency_guard(default_tenant=PUBLIC_TENANT_NAMESPACE)`），掛在 `api/routers/auth.py:370` 一個端點上。
- handler 拋錯時佔位列被刪除、錯誤回應不入快取（`api/core/idempotency.py:138-151`、`:304-308`）；檔頭 `:12-13` 自述「錯誤回應不快取，客戶端可立即用同 key 重試」。
- `idempotency_keys` 表的過期列清理在 `api/jobs` / `api/services` / `api/workers` 中零命中：

```
git grep -rn "idempotency_keys" -- api/jobs api/services api/workers
（無輸出）
```

過期列的處理路徑只有 `_try_takeover` 的就地覆寫（`api/core/idempotency.py:66-86`）。
- request hash 的組成為 `method | path | body`（`api/core/idempotency.py:41-48`），不含 query string 與 header。
