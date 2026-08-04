# TC-WO-09 — 同 Idempotency-Key 重送建單

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑 `test_pc_convert_to_wo.py` / `test_wo_numbering.py` / `test_cr_0165_register_idempotency.py`，14 項全數通過（見步驟 6） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（＋既有測試實跑） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/routers/work_orders_v2.py:405-432`、`api/core/idempotency.py:197-282`、`:338-347`、`api/services/work_order_service.py:568-651`、`SQL/migrations/110-idempotency-reserve-first.sql:44-52`、`SQL/migrations/031-wo-region-numbering.sql:50-63`、`SQL/Schema_doc_numbering.sql:51-55`、`api/tests/test_pc_convert_to_wo.py:144-163` |
| 優先級 / 路徑類型 | P0 / 例外 |

TC 判定基準三條在程式碼中皆有對應實作，且各有兩層以上落點：①「冪等回放」由 `idempotency_guard` 在 handler 執行前先佔位、命中已完成列時拋 `IdempotencyReplay` 直接回放原 response（`api/core/idempotency.py:271-275` → `:346-347`），handler 不再進入；②「不重複建單」除 Idempotency-Key 一層外，service 另有以 `problem_card_id` 為準的業務層冪等（`api/services/work_order_service.py:569-580` 回既有單且 `created=False`），DB 端再有 partial UNIQUE 兜底（`SQL/migrations/110-idempotency-reserve-first.sql:45-49`）；③「單號不重複」由 `document_number` 欄的 UNIQUE 約束（`SQL/Schema_doc_numbering.sql:52`）加 `generate_wo_number()` 的 per-region 原子遞增（`SQL/migrations/031-wo-region-numbering.sql:56-61`）保證。既有測試 `test_convert_idempotent` 直接斷言重送回同一張工單 id。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 4. 工單生命週期案例（TC-WO） |
| 前置 | 同 Idempotency-Key 重送建單 |
| 步驟 | 重送 POST |
| 預期結果（判定基準） | 冪等回放，不重複建單、單號不重複 |
| 路徑類型 | 例外 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | ⚠ 未被任何需求指定 |
| 屬於哪條旅程腳本 | — |

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 建單端點吃 `Idempotency-Key` | `api/routers/work_orders_v2.py:417`（`Depends(idempotency_guard)`）；缺 key 的 POST → 400 `MISSING_IDEMPOTENCY_KEY`（`api/core/idempotency.py:198-205`） | 有落點 |
| 重送同 key + 同 body → 回放 | `api/core/idempotency.py:272-275` 拋 `IdempotencyReplay`；`:346-347` 由 exception handler 直接回原狀態碼與 body | 有落點 |
| 回放時 handler 不執行 | `IdempotencyReplay` 於 dependency 階段拋出，FastAPI 不進入 `create_work_order_v2` | 有落點 |
| 不重複建單（跨 key 亦然） | `api/services/work_order_service.py:569-580`：同 `problem_card_id` 已有工單 → 回既有單、`created=False` | 有落點 |
| 併發下不重複建單 | `SQL/migrations/110-idempotency-reserve-first.sql:45-49` partial UNIQUE；`work_order_service.py:632-651` 撞 UNIQUE → 回既有單 | 有落點 |
| 單號不重複 | `SQL/Schema_doc_numbering.sql:52` `document_number VARCHAR(30) UNIQUE`；號碼由 `generate_wo_number()` 原子發（`031-wo-region-numbering.sql:56-61`） | 有落點 |
| 回放時的狀態碼 | `api/routers/work_orders_v2.py:430-431`：`created` 為真存 201，否則存 200 | 有落點 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 後台使用者 | 首發 `POST /tenants/{id}/work-orders` + `Idempotency-Key` | `ReservationCreated` | reserve-first | `api/core/idempotency.py:240-244` → `:51-63` | `INSERT ... ON CONFLICT (tenant_id, key) DO NOTHING`，status `in_progress` |
| 系統 | handler 成功 | `WorkOrderCreated` | 建單 | `api/services/work_order_service.py:614-628` | `INSERT INTO work_orders ... 'created' ... generate_wo_number(%s)` |
| 系統 | 存回應 | `IdempotencyCompleted` | 佔位補完 | `api/routers/work_orders_v2.py:430-431` | `idem.save(201 if created else 200, payload)` |
| 後台使用者 | 重送同 key 同 body | `ResponseReplayed` | 不重複寫 | `api/core/idempotency.py:272-275` → `:346-347` | 拋 `IdempotencyReplay`，回原 response，handler 不執行 |
| 後台使用者 | 重送同 key 異 body | `RequestRejected(409)` | hash 比對 | `api/core/idempotency.py:266-271` | `IDEMPOTENCY_KEY_MISMATCH` 409 |
| 後台使用者 | 重送**不同** key、同一張卡 | `ExistingWorkOrderReturned` | 一卡一原始單 | `api/services/work_order_service.py:569-580` | 回既有單、`created=False` → 200 |
| 系統 | 併發兩發同時 miss 業務層檢查 | `ConstraintViolated` → 回既有單 | DB backstop | `SQL/migrations/110-...sql:45-49`、`work_order_service.py:632-651` | 撞 `uq_work_orders_problem_card` → 查回既有單 |
| DB | 發單號 | `DocumentNumberIssued` | per-region 原子遞增 | `SQL/migrations/031-wo-region-numbering.sql:56-61` | `INSERT ... ON CONFLICT DO UPDATE SET last_serial = last_serial + 1 RETURNING` |

---

## 逐層走查

### 第 1 層 — API 路由：建單端點的冪等依賴

`api/routers/work_orders_v2.py:405-418`

```python
@router.post(
    "/tenants/{tenantId}/work-orders",
    operation_id="createWorkOrderV2",
    summary="從已確認 ProblemCard 建立工單 v2（tenant-scoped；idempotent）",
    response_model=WorkOrderEnvelope,
    status_code=201,
    tags=["M06 WorkOrder"],
)
async def create_work_order_v2(
    body: WorkOrderCreateRequest,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
```

回應存檔於 handler 尾端，`api/routers/work_orders_v2.py:429-432`：

```python
    payload = {"data": WorkOrder(**wo).model_dump(mode="json")}
    if idem is not None:
        await idem.save(201 if created else 200, payload)
    return payload
```

同一張問題卡另有一支等價端點 `POST /tenants/{tenantId}/problem-cards/{id}/convert-to-work-order`（`api/routers/problem_cards_v2.py:413` 同樣掛 `idempotency_guard`），兩者共用同一個 service 函式（見第 3 層）。

### 第 2 層 — 冪等 guard：重送同 key 的三種分支

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

回放不經 handler，由 exception handler 產生 response，`api/core/idempotency.py:338-347`：

```python
class IdempotencyReplay(Exception):
    """命中 idempotency cache → 由 main.py 的 exception handler 回放。"""

    def __init__(self, status: int, body: dict):
        self.status = status
        self.body = body


async def handle_idempotency_replay(request: Request, exc: IdempotencyReplay) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=exc.body)
```

「不重複寫」的第一道是 handler 執行**前**先佔位，`api/core/idempotency.py:240-244`：

```python
    # reserve-first：先佔 → 成功者才執行 handler
    if await _try_insert_reservation(
        x_tenant_id, idempotency_key, request.method, request.url.path, request_hash
    ):
        return ctx
```

此設計的來由記於檔頭 `api/core/idempotency.py:15-16`：「舊版 check-then-act（先 SELECT 再事後 INSERT）在同 key 併發 2 發時雙雙 miss → handler 執行兩次（UAT R3-6：同一張問題卡兩張工單＋發票錯亂）」。（TTL 與 hash 組成的細節見 TC-SEC-IDEM-01 走查。）

### 第 3 層 — service：與 key 無關的業務層冪等

`api/services/work_order_service.py:568-580`

```python
    # 2. Idempotency: existing WO with same problem_card_id?
    cur = await db_module._conn.execute(
        "SELECT id FROM work_orders "
        "WHERE problem_card_id = %s::uuid "
        "ORDER BY created_at ASC LIMIT 1",
        (pc_id,),
    )
    existing = await cur.fetchone()
    if existing:
        wo = await get_order(tenant_id=tenant_id, wo_id=str(existing[0]))
        return wo, False
```

併發下的 DB 兜底，`api/services/work_order_service.py:631-651`：

```python
    except _pg_errors.UniqueViolation as exc:
        constraint = getattr(getattr(exc, "diag", None), "constraint_name", None)
        if constraint in (None, "uq_work_orders_problem_card"):
            cur = await db_module._conn.execute(
                "SELECT id FROM work_orders "
                "WHERE problem_card_id = %s::uuid "
                "ORDER BY created_at ASC LIMIT 1",
                (pc_id,),
            )
            existing = await cur.fetchone()
            if existing:
                logger.info(
                    "convert 併發撞 UNIQUE(problem_card_id) → 回既有單 pc=%s wo=%s",
                    pc_id, existing[0],
                )
                wo = await get_order(tenant_id=tenant_id, wo_id=str(existing[0]))
                return wo, False
        raise
```

建單事件刻意排在回放路徑之後（`api/services/work_order_service.py:653-656` 註解）：「刻意放在 UNIQUE 回放路徑（上方 `return wo, False`）之後——併發撞號時事件已由贏家寫過，回放路徑再寫一筆會讓同一次轉換出現兩筆 'created'」。

### 第 4 層 — DB schema：不重複建單與單號唯一

`SQL/migrations/110-idempotency-reserve-first.sql:44-52`

```sql
-- [2] work_orders — 一卡一原始工單 partial UNIQUE（併發 convert DB 兜底）
CREATE UNIQUE INDEX IF NOT EXISTS uq_work_orders_problem_card
    ON work_orders (problem_card_id)
    WHERE problem_card_id IS NOT NULL
      AND parent_work_order_id IS NULL
      AND rework_of_id IS NULL;

COMMENT ON INDEX uq_work_orders_problem_card IS
    '一張問題卡至多一張「原始」工單（UAT R3-6 併發 convert 兜底）；reopen 子單/rework 排除在外';
```

單號欄位的唯一性，`SQL/Schema_doc_numbering.sql:51-55`：

```sql
ALTER TABLE work_orders
    ADD COLUMN IF NOT EXISTS document_number VARCHAR(30) UNIQUE;
COMMENT ON COLUMN work_orders.document_number IS
'WorkOrder 編號 (WO-YYYYMMDD-NNNN)';
```

實際發號函式，`SQL/migrations/031-wo-region-numbering.sql:50-63`：

```sql
CREATE OR REPLACE FUNCTION generate_wo_number(addr TEXT)
RETURNS TEXT AS $$
DECLARE
    v_region TEXT := wo_region_code(addr);
    v_serial BIGINT;
BEGIN
    INSERT INTO wo_region_counter (region, last_serial)
    VALUES (v_region, 1)
    ON CONFLICT (region) DO UPDATE
        SET last_serial = wo_region_counter.last_serial + 1
        RETURNING last_serial INTO v_serial;
    RETURN v_region || '-' || LPAD(v_serial::TEXT, 6, '0');
END;
$$ LANGUAGE plpgsql;
```

- `SQL/Schema_doc_numbering.sql:53-54` 的欄位註解寫格式為 `WO-YYYYMMDD-NNNN`
- `SQL/migrations/031-wo-region-numbering.sql:2-4` 與 `:61` 的實作產出格式為 `{2碼地區}-{6碼流水}`（如 `TP-000001`），且 `031` 檔頭自述「地區前綴『僅用工單』（Q6）；RM/WC/SOP 維持既有類型前綴 `generate_doc_number`」
- `api/services/work_order_service.py:621` 建單時呼叫的是 `generate_wo_number(%s)`

此處僅並陳，不裁定。兩者對「唯一性」的保證無差異——UNIQUE 約束在同一欄位上。

### 第 5 層 — 前端呼叫端

brand-portal 的轉單流程走 `convert-to-work-order`（見 TC-WO-01 走查步驟 2 的 `web/brand-portal/src/app/problem-cards/[id]/page.tsx:457-467`），該呼叫未於 request 帶 `Idempotency-Key`；header 由共用 client 決定。`api/core/idempotency.py:198-205` 對 POST 缺 key 一律 400，故該路徑的 key 供給發生在 client 層。

---

## 既有測試證據

實跑（本機 Docker 測試庫，`POSTGRES_URI=postgresql://lock:0000@localhost:5433/lock_scratch_test`，Windows 加 `-p winloop_plugin`）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_pc_convert_to_wo.py tests/test_wo_numbering.py \
  tests/test_cr_0165_register_idempotency.py -q -p winloop_plugin
14 passed in 4.37s
```

對到 TC 步驟「重送 POST」的是 `api/tests/test_pc_convert_to_wo.py:144-163`：

```python
async def test_convert_idempotent(client, admin_headers, insert_pc_chain):
    chain = await insert_pc_chain(pc_status="confirmed")
    await seed_accepted_quote(chain["pc_id"])  # CR-0128 報價先行 gate 前置
    res1 = await client.post(
        f"/api/v1/problem-cards/{chain['pc_id']}/convert-to-work-order",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    assert res1.status_code == 201
    wo_id_1 = res1.json()["data"]["id"]

    # 第二次呼叫（不同 idempotency key）— 業務層 idempotency 應回既存 WO
    res2 = await client.post(
        f"/api/v1/problem-cards/{chain['pc_id']}/convert-to-work-order",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={},
    )
    assert res2.status_code == 200
    assert res2.json()["data"]["id"] == wo_id_1
```

該測試用的是**兩個不同 key**，驗的是業務層冪等；「同一個 key 重送回放」的既有斷言在 `api/tests/test_cr_0165_register_idempotency.py:56-83`（技師註冊端點，非建單端點），詳見 TC-SEC-IDEM-01 走查步驟 4。單號唯一與 per-region 遞增由 `api/tests/test_wo_numbering.py:36-49` 覆蓋。

---

## 事實結論

1. 建單端點 `createWorkOrderV2` 掛有 `idempotency_guard`（`api/routers/work_orders_v2.py:417`），回應以 `idem.save()` 存檔（`:430-431`）。
2. 同 key + 同 body 重送時 guard 拋 `IdempotencyReplay`（`api/core/idempotency.py:274`），由 exception handler 回放原 status 與 body（`:346-347`），handler 不執行。
3. 同 key + 異 body → 409 `IDEMPOTENCY_KEY_MISMATCH`（`api/core/idempotency.py:266-271`）；同 key 併發第二發 → 409 `IDEMPOTENCY_IN_PROGRESS`（`:277-282`）。
4. 「不重複建單」另有兩層與 Idempotency-Key 無關的保護：service 的 `problem_card_id` 查回既有單（`api/services/work_order_service.py:569-580`）與 DB 的 partial UNIQUE（`SQL/migrations/110-idempotency-reserve-first.sql:45-49`）。
5. 「單號不重複」由 `work_orders.document_number` 的 UNIQUE 約束（`SQL/Schema_doc_numbering.sql:52`）與 `generate_wo_number()` 的 `ON CONFLICT DO UPDATE ... RETURNING` 原子遞增（`SQL/migrations/031-wo-region-numbering.sql:56-61`）共同保證。
6. `SQL/Schema_doc_numbering.sql:53-54` 註解描述的單號格式（`WO-YYYYMMDD-NNNN`）與實際發號函式產出的格式（`TP-000001`）不同；此處僅並陳，不裁定。
7. 建單事件寫入位置刻意在 UNIQUE 回放路徑之後（`api/services/work_order_service.py:653-656` 註解），使同一次轉換不會出現兩筆 `created` 事件。
8. 相關既有測試 14 項於本機測試庫全數通過；其中直接對到本 TC 的 `test_convert_idempotent` 用的是兩個不同 key，非同一 key。
