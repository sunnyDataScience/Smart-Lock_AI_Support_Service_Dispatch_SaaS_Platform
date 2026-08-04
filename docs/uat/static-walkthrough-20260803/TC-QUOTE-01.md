# TC-QUOTE-01 — 報價狀態機（建立 → 核准 → 送客戶 → 客戶確認）

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 6） |
| 走查時間 | 2026-08-03 17:26（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/services/quote_engine_service.py:28-42`、`:96-152`、`:288-339`、`:459-666`、`api/routers/quote_v2.py:52-251`、`api/routers/consumer_v2.py:270-329`、`SQL/migrations/041-quote-engine.sql`、`SQL/migrations/037-quote-line-items.sql` |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | 四段流程都有對應端點與狀態轉換，且 quote 確實掛 `quote_line_items`；但實作的狀態名為 `draft → pending_approval → approved → sent → accepted`，與 TC 寫的 `draft → internal_approved → customer_sent → customer_confirmed` 逐一不同名，且實作在 `approved` 與 `sent` 之間多一步、亦允許 `draft` 直送。 |

**TC 原文**｜前置：問題卡確認｜步驟：建報價 → 內部核准 → 送客戶 → 客戶 LIFF 確認｜判定基準：狀態 draft → internal_approved → customer_sent → customer_confirmed；quote 掛 quote_line_items｜happy｜P0｜FR-API-02、FR-API-03、FR-WEB-06｜SC-04

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客服 | 建報價 | `QuoteDrafted` | 綁 PC 或工單 | `quote_engine_service.py:96-152` | INSERT state=`draft`，version 沿綁定對象遞增 |
| 客服 | 加品項 | `QuoteLineAdded` | 價格取 catalog | `quote_engine_service.py:288-339` | INSERT `quote_line_items` + `_recompute_total` |
| 客服 | 送審 | `QuoteSubmitted` | draft → pending_approval | `quote_engine_service.py:30` | `"submit": ({"draft"}, "pending_approval")` |
| 主管 | 核准 | `QuoteApproved` | pending_approval → approved | `quote_engine_service.py:31`、`:596-600` | 轉態 + INSERT `quote_approval` |
| 客服 | 送客戶 | `QuoteSentToCustomer` | approved/draft/急件 → sent | `quote_engine_service.py:34`、`:607-608`、`:631-659` | 轉態 + 凍結 snapshot + 鑄 token + LINE outbox |
| 客戶 | LIFF 同意 | `QuoteAccepted` | sent → accepted | `quote_engine_service.py:35`、`routers/consumer_v2.py:297-329` | transition("accept") |

---

## 走查紀錄

### 步驟 1 — 狀態機定義

- **動作**：讀轉換表
- **預期**：`draft → internal_approved → customer_sent → customer_confirmed`
- **實際**：狀態名與段數皆不同

`api/services/quote_engine_service.py:28-42`

```python
# 允許的狀態轉換（action → (from_states, to_state)）
_TRANSITIONS = {
    "submit":  ({"draft"}, "pending_approval"),
    "approve": ({"pending_approval"}, "approved"),
    "reject":  ({"pending_approval"}, "rejected"),
    # send 亦放行急件補審起點（CR-0129：補明細後走 LIFF 事後確認，沿用送客戶/推播/accept 鏈）
    "send":    ({"approved", "draft", "retrospective_audit_only"}, "sent"),  # draft 可直送（免核門檻內，門檻 esales Q-11 待定）
    "accept":  ({"sent"}, "accepted"),
    "decline": ({"sent"}, "rejected"),
```

schema 註解同樣記錄實作用語：

`SQL/migrations/041-quote-engine.sql:20-21`

```sql
    state               VARCHAR(30) NOT NULL DEFAULT 'draft',
                        -- draft → pending_approval → approved → sent → accepted | rejected | expired | superseded
```

- TC 判定基準：`draft` → `internal_approved` → `customer_sent` → `customer_confirmed`
- 程式碼：`draft` → `pending_approval` →（approve）`approved` →（send）`sent` →（accept）`accepted`
- 全 repo 搜 `internal_approved` / `customer_sent` / `customer_confirmed` 作為 quote state 值：**找不到**

此處僅並陳，不裁定。

### 步驟 2 — 「內部核准」在實作中是兩個動作

- **動作**：對照 TC 的三段箭頭與程式碼的四段轉換
- **預期**：一步從 draft 到「內部已核准」
- **實際**：`submit`（draft→pending_approval）與 `approve`（pending_approval→approved）為兩個獨立端點，另有「draft 可直送」旁路

`api/routers/quote_v2.py:210-235`

```python
@router.post("/tenants/{tenantId}/quotes/{id}:submit", operation_id="submitQuoteV2", summary="送審 v2", tags=["M04 Quote"])
async def submit_quote_v2(...):
    return await _transition(tenantId, id, "submit", user, idem=idem)


@router.post("/tenants/{tenantId}/quotes/{id}:send", operation_id="sendQuoteV2", summary="送客戶 v2（凍結 snapshot）", tags=["M04 Quote"])
async def send_quote_v2(...):
    return await _transition(tenantId, id, "send", user, idem=idem)
```

draft 直送有金額門檻：

`api/services/quote_engine_service.py:550-559`

```python
    if action == "send" and cur[0] == "draft":
        threshold = await _approval_threshold()
        tot = await (await conn.execute(
            "SELECT COALESCE(total_amount, 0) FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
        if float(tot[0]) > threshold:
            raise ApiError(
                "APPROVAL_REQUIRED",
                f"報價總額超過 {threshold:.0f}（discount_policy 門檻），須先送審核准",
                409,
            )
```

門檻 fallback 為 10000（`quote_engine_service.py:63`），實值讀 M18 config `discount_policy.approval_threshold`（`:66-76`）。

核准角色限制在 router：`_APPROVE_ROLES = ("admin", "operations_manager")`（`api/routers/quote_v2.py:25`、`:233`）。

### 步驟 3 — quote 掛 quote_line_items

- **動作**：查 schema 關聯與寫入點
- **預期**：quote 有明細子表
- **實際**：一致

`SQL/migrations/041-quote-engine.sql:34-35`

```sql
-- quote_line_items 升為 quote 層（CR-0027 原為 work_order 層；保留 work_order_id 相容）
ALTER TABLE quote_line_items ADD COLUMN IF NOT EXISTS quote_id UUID REFERENCES quote(id) ON DELETE CASCADE;
```

`api/services/quote_engine_service.py:331-338`

```python
    await conn.execute(
        "INSERT INTO quote_line_items (quote_id, work_order_id, tenant_id, item_name, category, "
        "  unit_price, quantity, customer_price, is_mock, service_code, material_code) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, TRUE, %s, %s)",
        (quote_id, q[1], tenant_id, name, category, unit_cost, quantity, cust_price,
         service_code, material_code),
    )
    await _recompute_total(quote_id)
```

送審／送客戶前另有「空報價」擋閘：

`api/services/quote_engine_service.py:477-488`

```python
    if action in ("submit", "send"):
        empty = await (await conn.execute(
            "SELECT 1 FROM quote q WHERE q.id = %s::uuid "
            "AND COALESCE(q.total_amount, 0) <= 0 "
            "AND NOT EXISTS (SELECT 1 FROM quote_line_items l WHERE l.quote_id = q.id)",
            (quote_id,))).fetchone()
        if empty:
            raise ApiError(
                "QUOTE_NO_LINES",
                "報價單尚無任何品項，不可送審／送客戶（請先加入品項）",
                422,
            )
```

### 步驟 4 — 送客戶時的副作用

- **動作**：讀 send 的後續處理
- **預期**：TC 未指定
- **實際**：凍結 snapshot、鑄客戶端 token、推 LINE outbox

`api/services/quote_engine_service.py:607-608`、`:631-657`

```python
    if action == "send":
        await _freeze_snapshot(quote_id, tenant_id)
...
    if action == "send":
        link = await mint_view_token(tenant_id=tenant_id, quote_id=quote_id)
        result = {**result, **link}
        ...
            await line_push_outbox_service.enqueue(
                tenant_id=tenant_id,
                push_kind="quote_proposal",
```

### 步驟 5 — 客戶確認的兩條入口

- **動作**：找客戶端確認端點
- **預期**：LIFF 確認
- **實際**：兩條——public token 網頁與 LINE postback 旁路

`api/routers/consumer_v2.py:303-329`

```python
async def respond_consumer_quote(
    body: dict,
    request: Request,
    token: str = Path(..., min_length=32, max_length=512),
) -> dict:
    ...
    decision = (body or {}).get("decision")
    if decision not in {"accept", "reject"}:
        raise ApiError("VALIDATION_ERROR", "decision must be 'accept' or 'reject'", 422)
    action = "accept" if decision == "accept" else "decline"
```

前端頁面在 `web/brand-portal/src/app/quotes/[token]/page.tsx`，可操作條件為 `data.state === "sent"`（`:195`）。另一入口為 `api/routers/internal_ingest.py:162-199` 的 `/internal/quotes/{quote_id}:customer-respond`。

accept 後的下游：綁工單者 best-effort 開發票，PC 階段報價延後至 convert（`quote_engine_service.py:611-627`）。走查**未找到** accept 直接建立工單的程式碼。

### 步驟 6 — 執行既有測試

- **動作**：跑報價引擎測試
- **預期**：取得執行證據
- **實際**：第一輪無資料庫全數失敗；建立本機測試庫後重跑，三檔 22 項全數通過

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_cr_0152_ai_quote_gate.py tests/test_cr_0128_quote_gate.py tests/test_cr_0032_quote_engine.py -q -rs --tb=no
FFFFFFFFFFFF..FFFFFFFF                                                   [100%]
20 failed, 2 passed in 2.82s
```

失敗訊息原文 `ERROR api.db:db.py:48 環境變數 POSTGRES_URI 未設定`。

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0152_ai_quote_gate.py -q -p winloop_plugin --tb=no
3 passed in 2.94s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0128_quote_gate.py -q -p winloop_plugin --tb=no
11 passed in 1.09s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0032_quote_engine.py -q -p winloop_plugin --tb=no
8 passed in 3.64s
```

`api/tests/test_cr_0032_quote_engine.py:1-8` 的 docstring 顯示該檔覆蓋「狀態機 submit→approve→send（凍結 snapshot hash）→accept」，該 8 項在第二輪皆通過。

---

## 觀測到的其他事實

- 報價有效期預設 7 天（`quote_engine_service.py:44-46`：`_VALIDITY_DAYS_NORMAL = 7` / `_VALIDITY_DAYS_URGENT = 7`），註解記為「CR-0181 業主裁決，取代 BR-M04-05 的 14d/3d」。
- 可讀報價編號格式 `{公單號}-Q{版本}`（`quote_engine_service.py:83-87`），PC 階段報價無公單號時為 `None`。
- 明細 `unit_price` 只在 `include_cost=True` 時序列化（`quote_engine_service.py:407-408`）。
