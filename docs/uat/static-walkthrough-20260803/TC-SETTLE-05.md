# TC-SETTLE-05 — 同 Idempotency-Key 重送退款執行

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；正式機金流環境不可用，本批不做執行期驗證。後續以本機 Docker 測試庫實跑既有測試，含 HTTP-key 回放的退款決策測試通過（見步驟 5） |
| 走查時間 | 2026-08-03（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/core/idempotency.py:41-347`、`api/config.toml:29-32`、`api/routers/refunds_v2.py:36-204`、`api/routers/refunds.py:64-148`、`api/services/refund_service.py:242-283`、`:588-612`、`api/main.py:292`、`api/tests/test_refund_decision_v2_endpoint.py:155-174` |
| 優先級 / 路徑類型 | P0 / 例外 |
| 事實結論 | `Idempotency-Key` 的 24h 去重與回放機制完整存在（reserve-first 佔位 → completed 回放原始 status/body；TTL 由 `config.toml` 的 `ttl_hours = 24` 提供），退款的四個寫入端點皆掛 `idempotency_guard`，回放經 `IdempotencyReplay` 由全域 exception handler 回原 status。但 TC 步驟指名的「退款**執行**」端點在 repo 中**不存在**——退款沒有任何 `:execute` 路徑，`status='executed'` 在 `api/` 中無任何寫入點；因此「不重複出帳」這條在程式碼中沒有對應的出帳動作可被觀測。另外守衛在缺 `X-Tenant-ID` 或 DB 不可用時回 `None`（放行不去重）。 |

**TC 原文**｜前置：同 Idempotency-Key 重送退款執行｜步驟：重送 POST｜判定基準：冪等回放（TTL 24h），不重複出帳｜需求：FR-API-11｜旅程：SC-08

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶端 | 首送（帶 key） | `ReservationAcquired` | reserve-first | `core/idempotency.py:241-244` | INSERT 佔位列 `status='in_progress'` |
| 客戶端 | 重送同 key 同 body | `IdempotentReplay` | 回放原回應 | `core/idempotency.py:273-275`、`:346-347` | 拋 `IdempotencyReplay` → 回原 status + body |
| 客戶端 | 重送同 key 異 body | `Rejected(409)` | hash 比對 | `core/idempotency.py:266-271` | 409 `IDEMPOTENCY_KEY_MISMATCH` |
| 客戶端 | 前一請求仍在跑 | `Rejected(409)` | 併發保護 | `core/idempotency.py:277-282` | 409 `IDEMPOTENCY_IN_PROGRESS` |
| 客戶端 | TTL 過後同 key | `ReservationTakenOver` | 24h TTL | `core/idempotency.py:74-86`、`config.toml:30` | 原子接管重佔 |
| system | 退款執行出帳 | `RefundExecuted` | 不重複出帳 | — | **找不到**退款執行端點或 `status='executed'` 寫入 |

---

## 走查紀錄

### 步驟 1 — 冪等機制與 TTL

- **動作**：讀 guard 與設定
- **預期**：TTL 24h、命中回放
- **實際**：一致

`api/config.toml:29-32`

```toml
[idempotency]
ttl_hours = 24
# 適用 method
applies_to = ["POST", "PATCH", "PUT", "DELETE"]
```

`api/core/idempotency.py:230-251`

```python
    ttl_hours = int(cfg.get("ttl_hours", 24))
    reserve_ttl = int(cfg.get("reserve_ttl_seconds", _DEFAULT_RESERVE_TTL_SECONDS))
    ctx = IdempotencyContext(
        tenant_id=x_tenant_id,
        key=idempotency_key,
        method=request.method,
        path=request.url.path,
        request_hash=request_hash,
    )

    # reserve-first：先佔 → 成功者才執行 handler
    if await _try_insert_reservation(
        x_tenant_id, idempotency_key, request.method, request.url.path, request_hash
    ):
        return ctx

    # 撞既有列：接管逾期列 → 否則依 status 回放 / 409
    if await _try_takeover(
```

TTL 條件寫在接管 SQL 中：`api/core/idempotency.py:79-82`

```python
        "WHERE tenant_id = %s::uuid AND key = %s "
        "  AND ( created_at <= NOW() - (%s * INTERVAL '1 hour') "
        "        OR (status = 'in_progress' "
        "            AND created_at <= NOW() - (%s * INTERVAL '1 second')) ) "
```

回放路徑：`api/core/idempotency.py:273-275`

```python
    if existing["status"] == "completed":
        # Replay
        raise IdempotencyReplay(existing["response_status"], existing["response_body"])
```

處理器：`api/core/idempotency.py:346-347` + `api/main.py:292`

```python
async def handle_idempotency_replay(request: Request, exc: IdempotencyReplay) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=exc.body)
```

```python
app.add_exception_handler(IdempotencyReplay, handle_idempotency_replay)
```

回放的 status 是首次成功時 `idem.save(...)` 存入的值，故 200 存 200、201 存 201（`routers/refunds_v2.py:77`、`:203`）。

### 步驟 2 — 退款端點的掛載狀況

- **動作**：檢查各退款寫入端點是否掛 guard
- **預期**：全掛
- **實際**：四個寫入端點全掛

| 端點 | 位置 | guard |
|---|---|---|
| `POST /tenants/{tid}/refunds` | `routers/refunds_v2.py:47` | `Depends(idempotency_guard)` |
| `POST /tenants/{tid}/refunds/{rid}/decision` | `routers/refunds_v2.py:92` | 同上 |
| `POST /tenants/{tid}/refunds:agent-initiate` | `routers/refunds_v2.py:167` | 同上 |
| `POST /api/v1/refunds`（legacy） | `routers/refunds.py:77` | 同上 |
| `POST /api/v1/refunds/{id}/decision`（legacy） | `routers/refunds.py:133` | 同上 |

`api/routers/refunds_v2.py:87-93`

```python
async def submit_refund_decision_v2(
    body: RefundDecision,
    tenantId: str = Path(...),
    refundId: str = Path(...),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES, fail_closed=True)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
```

回應寫入快取：`api/routers/refunds_v2.py:112-115`

```python
    payload = {"data": RefundRequest(**refund).model_dump(mode="json")}
    if idem is not None:
        await idem.save(200, payload)
    return payload
```

### 步驟 3 — TC 指名的「退款執行」

- **動作**：搜尋退款執行端點
- **預期**：有 `:execute` 或同義端點
- **實際**：找不到

```
git grep -n "refunds.*execute\|:execute" -- api/routers
（無輸出）
```

```
git grep -n "'executed'" -- api | grep -v tests
api/models/generated.py:392:    executed = 'executed'
api/services/refund_service.py:61:    "executed",
api/services/refund_service.py:468:_VALID_TERMINAL_REFUND_STATES = {"rejected", "executed"}
```

三處皆為 enum／常數宣告；`refund_requests.status` 的實際 UPDATE 只出現在 `services/refund_service.py:395-400`，寫入值域為 `approved / csm_approved / rejected / escalated`（`:368-381`）。`executed_at` 欄位只有讀取（`:106`、`:116`）。

- TC 步驟：「重送 POST（退款執行）」，判定基準「不重複出帳」
- 程式碼：退款流程止於 `approved`；repo 中沒有把退款推進到 `executed`／實際出帳的端點或 service 函式

此處僅並陳，不裁定。

### 步驟 4 — 另一層業務冪等

- **動作**：查非 HTTP-key 的重複防護
- **預期**：不重複建立
- **實際**：兩條，分屬兩個建立路徑

`api/services/refund_service.py:242-255`（legacy `create_refund_request`）

```python
    # 2. Idempotency check: 同 WO 同 reason_code 已存在 active row?
    cur = await db_module._conn.execute(
        "SELECT id FROM refund_requests "
        "WHERE work_order_id = %s::uuid AND reason_code = %s "
        "  AND status NOT IN ('rejected', 'cancelled') "
        "ORDER BY created_at ASC LIMIT 1",
        (work_order_id, reason_code),
    )
    existing = await cur.fetchone()
    if existing:
        refund = await get_refund_request(
            tenant_id=tenant_id, refund_id=str(existing[0]),
        )
        return refund, False
```

`api/services/refund_service.py:600-612`（SoD 路徑）

```python
    dup = await db_module._conn.execute(
        "SELECT id FROM refund_requests "
        "WHERE work_order_id = %s::uuid AND refund_class = %s "
        "  AND status NOT IN ('rejected', 'cancelled') "
        "LIMIT 1",
        (work_order_id, refund_class),
    )
    if await dup.fetchone():
        raise ApiError(
            "DUPLICATE_REFUND",
            f"該工單已有進行中的「{refund_class}」退款請求，不可重複建立",
            409,
        )
```

同段註解 `:588-599` 記載：DB 端 `uniq_refund_wo_reason_active` 索引因 SoD 路徑不填 `reason_code`（留 NULL，NULL 不參與唯一性比較）而對該路徑不生效，故補 service 層這道。

### 步驟 5 — 執行既有測試

- **動作**：跑退款冪等測試
- **預期**：取得執行證據
- **實際**：通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_refund_decision_v2_endpoint.py \
  tests/test_create_refund_request.py tests/test_refund_sod_endpoint.py \
  tests/test_refund_sod_5tier.py tests/test_refund_dual_sign.py \
  -q -p winloop_plugin --tb=line

66 passed in 3.84s
```

HTTP-key 回放的直接證據：`api/tests/test_refund_decision_v2_endpoint.py:158-174`

```python
async def test_decision_v2_idempotency_replay(
    client, admin_headers, insert_refund_for_decision
):
    """同一 Idempotency-Key 重複送 → 200 冪等回放，不重複改狀態。"""
    rid = await insert_refund_for_decision(amount=600.0, requires_dual_sign=False)
    idem_key = str(uuid.uuid4())
    headers = {**admin_headers, "Idempotency-Key": idem_key}
    body = {"decision": "approve", "reason": "replay test"}

    res1 = await client.post(_decision_path(DEFAULT_TENANT_ID, rid), headers=headers, json=body)
    assert res1.status_code == 200, res1.text

    # 相同 key + 相同 body → replay 回相同 200
    res2 = await client.post(_decision_path(DEFAULT_TENANT_ID, rid), headers=headers, json=body)
    assert res2.status_code == 200, res2.text
    assert res2.json()["data"]["status"] == "approved"
```

該測試的 `admin_headers` 含 `X-Tenant-ID`（`api/tests/conftest.py:115-118`），為 guard 生效的必要條件。

業務冪等的執行證據：`api/tests/test_create_refund_request.py:113-144`（同 WO 同 `reason_code` 第二次回 200 且 id 相同）。

**無對應測試**：TTL 24h 過期後接管、以及「退款執行不重複出帳」，在 `api/tests/` 中零命中。

---

## 觀測到的其他事實

- 缺 `Idempotency-Key` 時，`applies_to` 內的 method 直接 400 `MISSING_IDEMPOTENCY_KEY`（`core/idempotency.py:198-206`）——此檢查只在端點掛了 guard 時才會執行。
- 缺 `X-Tenant-ID` 時 guard 回 `None`（`core/idempotency.py:216-219`），DB 不可用時同樣回 `None`（`:226-228`），兩種情況下請求照常執行但不去重。
- 失敗回應不入快取：handler 未 `save()` 時 dependency 的 `finally` 會刪掉 `in_progress` 佔位列（`core/idempotency.py:138-151`、`:304-308`），客戶端可用同 key 立即重試。
- 模組 docstring `core/idempotency.py:15-16` 記載改為 reserve-first 的動因：舊版 check-then-act 在同 key 併發 2 發時雙雙 miss，導致「同一張問題卡兩張工單＋發票錯亂」。
- `payments` 表另有獨立的 intent 冪等鍵（`SQL/migrations/069-payments-mock.sql:27-28` 的 `uq_payments_idempotency` / `uq_payments_provider_txn`），與 HTTP `Idempotency-Key` 為兩套機制。
