# TC-QUOTE-08 — 同 Idempotency-Key 重送客戶確認

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，冪等測試失敗（見步驟 5） |
| 走查時間 | 2026-08-03 18:43（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/routers/internal_ingest.py:162-199`、`api/routers/consumer_v2.py:297-329`、`api/routers/quote_v2.py:193-228`、`api/services/quote_engine_service.py:782-810`、`:611-627`、`api/core/idempotency.py:190-308`、`api/config.toml:29-32` |
| 優先級 / 路徑類型 | P0 / 例外 |
| 事實結論 | 客戶確認的兩個入口（`/internal/quotes/{id}:customer-respond`、`/consumer/quotes/{token}` POST）**都沒有掛 `idempotency_guard`**，`Idempotency-Key` 在這兩條路徑上不被讀取；重放保護改由 service 層的「同決定 → 回既有終態」業務冪等提供，且該保護只存在於 internal 路徑，consumer 路徑會落到 409 `STATE_CONFLICT`。accept 不觸發工單建立；報價狀態機全程無 audit 寫入。**實跑補充**：該業務冪等分支所在的函式在讀取現況 state 時即拋 `TypeError`（`quote_engine_service.py:785-788`），`test_customer_respond_accept_twice_idempotent` 實跑失敗。 |

**TC 原文**｜前置：同 Idempotency-Key 重送 customer-confirm｜步驟：重送 POST｜判定基準：200 冪等回放；不重觸發工單建立、audit 不重複｜例外｜P0｜FR-API-02、FR-WEB-06｜SC-04

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | 重送 POST（帶同 key） | `IdempotentReplay(200)` | HTTP 層 key 去重 | `routers/internal_ingest.py:168-174` | 端點簽章**無** `idempotency_guard` |
| 客戶 | 重送同決定（internal 路徑） | `IdempotentReplay(200)` | 業務層去重 | `quote_engine_service.py:784-791` | 回 `idempotent_replay: True` |
| 客戶 | 重送同決定（consumer token 路徑） | `IdempotentReplay(200)` | 業務層去重 | `routers/consumer_v2.py:326-329` | 直呼 `transition` → 409 `STATE_CONFLICT` |
| 系統 | accept 成功 | `WorkOrderCreated` | TC 稱不應重觸發 | `quote_engine_service.py:611-627` | accept 完全不建工單（只 best-effort 開發票） |
| 系統 | accept 成功 | `AuditLogged` | 不重複 | — | 報價狀態機**找不到**任何 audit 寫入 |

---

## 走查紀錄

### 步驟 1 — 客戶確認端點是否掛冪等守衛

- **動作**：讀兩個客戶確認端點的簽章
- **預期**：有 `Idempotency-Key` 處理
- **實際**：**找不到**；兩端點皆無 `idempotency_guard` 依賴

`api/routers/internal_ingest.py:162-179`

```python
@router.post(
    "/internal/quotes/{quote_id}:customer-respond",
    operation_id="customerRespondQuoteInternal",
    summary="內部：客戶經 LINE postback 同意/拒絕報價（CR-0095，agent gateway 用）",
    tags=["internal"],
)
async def customer_respond_quote(
    quote_id: str,
    body: dict,
    auth: ServicePrincipalContext = Depends(
        service_credential_required("quotes:write")
    ),
) -> dict:
```

`api/routers/consumer_v2.py:297-307`

```python
@router.post(
    "/consumer/quotes/{token}",
    operation_id="respondConsumerQuoteV2",
    summary="消費者匿名回覆報價 v2（CR-0032 Phase C；同意/拒絕）",
    tags=["M16 Consumer"],
)
async def respond_consumer_quote(
    body: dict,
    request: Request,
    token: str = Path(..., min_length=32, max_length=512),
) -> dict:
```

對照有掛守衛的後台端點：

`api/routers/quote_v2.py:224-228`

```python
@router.post("/tenants/{tenantId}/quotes/{id}:accept", operation_id="acceptQuoteV2", summary="客戶接受 v2", tags=["M04 Quote"])
async def accept_quote_v2(tenantId: str = Path(...), id: str = Path(...),
                          user: CurrentUser = Depends(role_required(*OPS_ROLES)),
                          idem: IdempotencyContext | None = Depends(idempotency_guard)) -> dict:
    return await _transition(tenantId, id, "accept", user, idem=idem)
```

- TC 前置與步驟：以「同 Idempotency-Key 重送 customer-confirm」為條件
- 程式碼：`customer-respond` 兩條路徑不讀該 header；帶或不帶 key 行為相同

此處僅並陳，不裁定。

### 步驟 2 — 業務層的重放保護（internal 路徑）

- **動作**：讀 `customer_respond_to_quote`
- **預期**：重送回 200
- **實際**：同決定回既有終態，帶 `idempotent_replay: True`

`api/services/quote_engine_service.py:782-801`

```python
    # FR-API-02：冪等——客戶重複點同一決定（已在對應終態）→ 回既有成功，不 409
    # （防 LIFF 連點/重送造成 STATE_CONFLICT；效果等同 Idempotency-Key 對同決定去重）。
    _terminal = {"accept": "accepted", "reject": "rejected"}
    cur_state = ((await (await _conn()).execute(
        "SELECT state FROM quote WHERE id = %s::uuid "
        "AND (tenant_id = %s::uuid OR tenant_id IS NULL)",
        (quote_id, tenant_id))).fetchone() or [None])[0]
    if cur_state == _terminal[decision]:
        return {"quote_id": quote_id, "state": cur_state,
                "decision": decision, "idempotent_replay": True}
```

程式碼註解自述「效果等同 Idempotency-Key 對同決定去重」。router 對此回傳無特別狀態碼設定，走 FastAPI 預設 200（`internal_ingest.py:199` 直接 `return {"data": result, "error": None}`）。

### 步驟 3 — consumer token 路徑無同等保護

- **動作**：比對兩條路徑
- **預期**：兩條皆冪等
- **實際**：consumer 路徑直呼 `transition`，不經業務冪等分支

`api/routers/consumer_v2.py:319-329`

```python
    action = "accept" if decision == "accept" else "decline"

    logger.info(
        "consumer quote response: decision=%s token_hash=%s ip=%s",
        decision, token_hash_for_audit(token),
        request.client.host if request.client else None,
    )
    result = await quote_engine_service.transition(
        tenant_id=payload.tenant_id, quote_id=payload.subject_id, action=action,
    )
    return {"quote_id": result["id"], "state": result["state"]}
```

`transition` 對已在 `accepted` 的報價再 accept：

`api/services/quote_engine_service.py:468-472`

```python
    cur = await (await conn.execute("SELECT state FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
    if not cur:
        raise ApiError("NOT_FOUND", "quote not found", 404)
    if cur[0] not in from_states:
        raise ApiError("STATE_CONFLICT", f"cannot {action} quote in '{cur[0]}'", 409)
```

即 `accept` 的 `from_states` 為 `{"sent"}`（`:35`），第二次呼叫回 409。

### 步驟 4 — 「不重觸發工單建立」與「audit 不重複」

- **動作**：查 accept 的下游副作用
- **預期**：重送不重複建立工單、不重複寫 audit
- **實際**：accept 本身不建工單；報價狀態機無 audit 寫入

`api/services/quote_engine_service.py:611-627`

```python
    if action == "accept":
        # CR-0128 報價先行：PC 階段報價（尚無工單）accept 時**延後開票**——發票錨定
        # work_order_id（UNIQUE 冪等），convert 開單回填綁定後由 create_from_problem_card
        # best-effort 補開。WO 已綁定者維持原路徑（accept 即開票）。
        has_wo = await (await conn.execute(
            "SELECT work_order_id FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
        if has_wo and has_wo[0]:
            try:
                from services import invoice_service
                inv = await invoice_service.create_from_quote(tenant_id=tenant_id, quote_id=quote_id)
                logger.info("quote accepted → invoice %s", inv.get("id"))
            except Exception as exc:  # noqa: BLE001 — best-effort 解耦：開票失敗不阻斷客戶接受報價
```

工單建立在 repo 中的觸發點為客服呼叫 convert 端點（`api/routers/problem_cards_v2.py:397-441`），走查**未找到** accept 直接呼叫 `create_from_problem_card` 的程式碼。

audit：`api/services/quote_engine_service.py` 全檔搜 `audit_log_service` 與 `log_event`：**找不到**。同檔對 accept 的副作用為 conversation 事件註記（`:661-665`），該註記在 internal 路徑的冪等分支中不會執行（因為提早 return）。

### 步驟 5 — 執行既有測試

- **動作**：跑冪等測試
- **預期**：取得執行證據
- **實際**：第一輪無資料庫全數失敗；建立本機測試庫後重跑，冪等測試仍失敗，失敗原因由環境改為程式執行時錯誤

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_pc_convert_to_wo.py tests/test_cr_0095_quote_line_approval.py tests/test_cr_0144_requote_channel.py -q --tb=no -rf
21 failed, 3 passed in 3.58s
```

錯誤原文 `ERROR api.db:db.py:48 環境變數 POSTGRES_URI 未設定`。

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0095_quote_line_approval.py -q -p winloop_plugin --tb=line
3 failed, 9 passed in 3.68s

FAILED tests/test_cr_0095_quote_line_approval.py::test_customer_respond_ownership_and_accept
FAILED tests/test_cr_0095_quote_line_approval.py::test_customer_respond_accept_twice_idempotent
FAILED tests/test_cr_0095_quote_line_approval.py::test_customer_respond_conflict_codes

api/services/quote_engine_service.py:785: TypeError: 'coroutine' object is not subscriptable
```

同檔其餘 9 項通過。三項失敗都停在 `quote_engine_service.py:785-788`：

```python
    cur_state = ((await (await _conn()).execute(
        "SELECT state FROM quote WHERE id = %s::uuid "
        "AND (tenant_id = %s::uuid OR tenant_id IS NULL)",
        (quote_id, tenant_id))).fetchone() or [None])[0]
```

`await` 的作用範圍到 `.execute(...)` 為止，`.fetchone()` 未被 await，回傳的 coroutine 經 `or [None]` 判定為真後被取 `[0]`。同檔其他讀取點的寫法為 `await (await conn.execute(...)).fetchone()`（例：`:295`、`:345`、`:397`），`await` 在最外層。此段落在 `customer_respond_to_quote` 中位於歸屬驗證（`:775-781`）之後、所有冪等與衝突分支（`:789-809`）之前。此處僅陳述實跑觀測與程式碼原文，不裁定。

該測試斷言的是 service 層業務冪等（非 HTTP key）：

`api/tests/test_cr_0095_quote_line_approval.py:254-267`

```python
async def test_customer_respond_accept_twice_idempotent(client):
    """CR-0178 UAT-0720-12 主回歸：客戶連點兩次「同意」→ 第二次冪等回放不 409。"""
    assert await db_module._ensure_conn()
    owner_line = f"Uidem{uuid.uuid4().hex[:8]}"
    wid, pid, uid = await _seed_chain(owner_line)
    try:
        qid = await _make_quote(wid, pid, "sent")
        first = await quote_engine_service.customer_respond_to_quote(
            tenant_id=TID, quote_id=qid, line_user_id=owner_line, decision="accept")
        assert first["state"] == "accepted"
        second = await quote_engine_service.customer_respond_to_quote(
            tenant_id=TID, quote_id=qid, line_user_id=owner_line, decision="accept")
        assert second.get("idempotent_replay") is True
        assert second["state"] == "accepted"
```

---

## 觀測到的其他事實

- 全域冪等設定 `applies_to = ["POST", "PATCH", "PUT", "DELETE"]`（`api/config.toml:32`）；`_guard_impl` 在缺 key 時對這些 method 回 400 `MISSING_IDEMPOTENCY_KEY`（`api/core/idempotency.py:198-206`）——但此邏輯只在端點掛了 guard 時才會執行。
- `idempotency_guard` 需 `X-Tenant-ID` header 才能 dedup，缺 header 時回 `None`（fail-open，`api/core/idempotency.py:216-219`）。
- 冪等列在 DB 不可用時直接放行（`api/core/idempotency.py:226-228`）。
- 錯誤回應不入冪等快取（`api/core/idempotency.py:138-151` 的 `_release_reservation`）。
