# TC-DISPATCH-07 — 技師平台 requote command 的權限、冪等與保固案件阻擋

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，requote／分層核可／AI 雙閘 12 項全數通過（見步驟 6） |
| 走查時間 | 2026-08-03 23:05（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/routers/requote_requests.py:32-117`、`api/services/requote_service.py:39-131`、`api/core/deps.py:421-461`、`api/services/quote_engine_service.py:450-556`、`api/routers/quote_v2.py:196-241`、`SQL/migrations/097-requote-requests.sql` |
| 優先級 / 路徑類型 | P0 / 例外 |
| 事實結論 | TC 列舉的四項斷言中，三項有對應實作：①`/internal/requote-requests` 收 `request_id`＋`item_diffs` 且 body 無金額欄位（`requote_requests.py:32-40`），v+1 金額由 `quote_engine_service.create_quote` 產生；②非 assignee → 403（`requote_service.py:70-71`）；③同 `request_id` 重送 → 200 冪等回放（`:54-60`、`requote_requests.py:66-67`）。第四項「保固/建案案件自動送出 → 403」的 gate 存在，但落點在**報價 `:send`**（`quote_engine_service.py:509-524`，403 `AI_FORBIDDEN_WARRANTY_PROJECT`），不在 requote command 入口——`submit_requote` 全函式無 `warranty_claims` 查詢，保固案件的 requote command 本身可成功建立 v+1 draft。TC 註記的分層核可（501-2000/>2000）僅 `>2000` 一條有 enforcement。 |

**TC 原文**｜前置：技師平台 requote command（ADR-027）｜步驟：tech-api 呼叫品牌 api /internal/requote-requests（含 request_id + item_diffs 不含金額）｜判定基準：品牌引擎建 quote v+1 金額由引擎算；非 assignee → 403；同 request_id 重送 → 冪等回放；保固/建案案件自動送出 → 403（註：分層核可（501-2000/>2000）與保固建案自動送出 403 兩斷言＝CR-0150 落地範圍，遺留〔標注 2026-07-10：分層核可已落地（CR-0150，5 測）；保固建案 403 歸 CR-0152〕）｜需求：FR-TEC-07｜旅程：SC-07

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| tech-api | POST `/internal/requote-requests` | `RequoteCommandReceived` | S2S 憑證＋scope | `requote_requests.py:52-59` | `service_credential_required("requotes:write")`＋`assert_tenant_scope` |
| 品牌引擎 | 建 v+1 | `QuoteVersionCreated` | 金額由引擎算 | `requote_service.py:97-104` | `create_quote` 建 draft；command body 無金額欄 |
| 系統 | 非 assignee 拒絕 | `CommandRejected(403)` | ADR-027 | `requote_service.py:70-71` | 403 `FORBIDDEN` |
| 系統 | 同 request_id 重送 | `CommandReplayed` | UNIQUE(tenant, request_id) | `requote_service.py:54-60` | 回既有列，HTTP 200 |
| 系統 | 保固案件自動送出 | `SendRejected(403)` | 僅人類 staff | `quote_engine_service.py:509-524` | 403 `AI_FORBIDDEN_WARRANTY_PROJECT`（發生在 `:send`，非 command） |
| 小編 | 送出 delta>2000 | `SendRejected(403)` | 分層核可 | `quote_engine_service.py:538-545` | 403 `REQUOTE_SUPERVISOR_REQUIRED` |

---

## 走查紀錄

### 步驟 1 — command 契約：request_id + item_diffs 不含金額

- **動作**：讀 `RequoteBody`
- **預期**：帶 request_id 與 item_diffs，無金額
- **實際**：一致

`api/routers/requote_requests.py:32-40`

```python
class RequoteBody(BaseModel):
    request_id: str = Field(min_length=1, max_length=100)
    work_order_id: str
    technician_id: str
    reason: str
    # CR-0150:收緊為必填非空(16_API required;空修正單無語意)
    item_diffs: list = Field(min_length=1)
    initiated_via: str = "technician_command"
    tenant_id: str | None = None  # 單品牌 stack 可省略(退 AGENT_TENANT_ID)
```

無 `amount` / `price` / `total` 欄位。技師端 UI 亦刻意不收金額（`web/tech-portal/src/app/my-orders/[id]/scope-change/page.tsx:1-5`、`:100-103`）。

金額由品牌引擎產生：`api/services/requote_service.py:91-99`

```python
    # 品牌報價引擎建 v+1 draft(金額由小編後續定價——技師零定價權)。
    # created_by FK 指向 users:由 technicians.user_id 反查(technician_id 是技師主檔 id)
    ...
    quote = await quote_engine_service.create_quote(
        tenant_id=tenant, work_order_id=work_order_id,
        created_by=tech_user_id)
```

### 步驟 2 — S2S 認證與 tenant scope

- **動作**：讀 internal 端點的 dependency
- **預期**：僅技師平台可呼叫
- **實際**：新憑證優先，舊 `X-Internal-Token` 為 fallback 並記 WARN

`api/routers/requote_requests.py:43-59`

```python
@router.post(
    "/internal/requote-requests",
    operation_id="submitRequoteRequest",
    summary="技師平台發起現場報價修正 command(ADR-027;冪等回放)",
    status_code=201,
)
async def submit_requote_request(
    body: RequoteBody,
    response: Response,
    auth: ServicePrincipalContext = Depends(
        service_credential_required("requotes:write")
    ),
) -> dict:
    tenant_id = body.tenant_id or os.environ.get(
        "AGENT_TENANT_ID", "00000000-0000-0000-0000-000000000001"
    )
    assert_tenant_scope(auth, tenant_id)
```

`api/core/deps.py:444-461`

```python
        if x_service_credential:
            return await authenticate_service_credential(
                x_service_credential,
                audience=audience,
                required_scope=required_scope,
                request_id=request_id,
            )
        await _require_legacy_internal_token(x_internal_token)
        metric_key = f"{request.method} {request.url.path}"
        _LEGACY_INTERNAL_AUTH_USAGE[metric_key] += 1
        logger.warning(
            "LEGACY_INTERNAL_AUTH_FALLBACK method=%s path=%s request_id=%s",
```

### 步驟 3 — 非 assignee → 403

- **動作**：讀 service 驗證段
- **預期**：403
- **實際**：一致；同段另有狀態 403

`api/services/requote_service.py:62-82`

```python
    # 工單驗證:存在/assignee/狀態
    cur = await db_module._conn.execute(
        "SELECT technician_id, status FROM work_orders WHERE id=%s::uuid",
        (work_order_id,))
    wo = await cur.fetchone()
    if not wo:
        raise ApiError("NOT_FOUND", "work order not found", 404)
    wo_tech, wo_status = (str(wo[0]) if wo[0] else None), wo[1]
    if not wo_tech or wo_tech != technician_id:
        raise ApiError("FORBIDDEN", "technician 非本工單 assignee(ADR-027)", 403)
    if wo_status not in _ALLOWED_WO_STATUS:
        raise ApiError("FORBIDDEN",
                       f"工單狀態 {wo_status} 不可發起現場修正(須 in_progress)", 403)

    # 同工單進行中修正 → 409(冪等衝突)
    cur = await db_module._conn.execute(
        "SELECT request_id FROM requote_requests "
        "WHERE work_order_id=%s::uuid AND status IN ('received','quoted')",
        (work_order_id,))
    if await cur.fetchone():
        raise ApiError("STATE_CONFLICT", "已有進行中的修正請求", 409)
```

注意順序：冪等回放（步驟 4）在 assignee 驗證**之前**，故對已存在的 `request_id` 重送不會再驗 assignee。

### 步驟 4 — 同 request_id 冪等回放

- **動作**：讀回放分支與 HTTP 狀態碼
- **預期**：回放同一結果
- **實際**：一致，且以 200 區別於新建的 201

`api/services/requote_service.py:54-60`

```python
    # 冪等回放
    cur = await db_module._conn.execute(
        f"SELECT {_SELECT} FROM requote_requests "
        "WHERE tenant_id=%s::uuid AND request_id=%s", (tenant, request_id))
    row = await cur.fetchone()
    if row:
        return _row_to_dict(row), True
```

`api/routers/requote_requests.py:60-68`

```python
    data, replayed = await requote_service.submit_requote(
        ...
    )
    if replayed:
        response.status_code = 200  # 冪等回放(非新建)
    return {"data": data, "error": None}
```

DB 層保底：`SQL/migrations/097-requote-requests.sql:26`

```sql
    UNIQUE (tenant_id, request_id)
```

回放的 payload 不含 `quote_version` / `supersedes_quote_id`（那兩鍵只在新建路徑補上，`requote_service.py:115-116`），與新建回應的欄位集不同。

### 步驟 5 — 保固／建案案件的 403

- **動作**：找 `AI_FORBIDDEN_WARRANTY_PROJECT` 的觸發點
- **預期**：requote command 對保固案件回 403
- **實際**：gate 存在，但在報價 `:send`，不在 command

`api/services/quote_engine_service.py:505-524`

```python
    if action == "send":
        if (actor_role or "") == "ai_agent":
            raise ApiError(
                "AI_FORBIDDEN_FINAL_QUOTE",
                "AI 不得對客戶送出最終報價（ADR-025 話術邊界憲章）",
                403,
            )
        wo_row = await (await conn.execute(
            "SELECT work_order_id FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
        if wo_row and wo_row[0]:
            wc = await (await conn.execute(
                "SELECT 1 FROM warranty_claims WHERE work_order_id = %s::uuid LIMIT 1",
                (wo_row[0],))).fetchone()
            if wc and (actor_role or "") not in _HUMAN_STAFF_SEND_ROLES:
                raise ApiError(
                    "AI_FORBIDDEN_WARRANTY_PROJECT",
                    "保固／建案案件僅人類客服／主管可送出報價（BR-QUOTE-03／ADR-025）",
                    403,
                )
```

白名單：`api/services/quote_engine_service.py:455`

```python
_HUMAN_STAFF_SEND_ROLES = ("customer_service", "operations_manager", "admin")
```

`requote_service.submit_requote` 全函式（`:39-131`）中 `warranty` / `warranty_claims` / `AI_FORBIDDEN` 皆零命中；保固工單的 requote command 會正常建立 v+1 draft，403 發生在後續送出時。

判定條件的另一項差異：TC 寫「保固/**建案**」，程式碼的判定式只有 `warranty_claims` 關聯一項，建案（專案案件）無獨立判定欄位或查詢。

- TC 判定基準：保固/建案案件**自動送出** → 403
- 程式碼：`actor_role` 不在 `_HUMAN_STAFF_SEND_ROLES` 即 403（含未帶角色的 fail-closed），判定的是「角色」而非「是否自動」

此處僅並陳，不裁定。

### 步驟 6 — 分層核可（TC 註記的 CR-0150 範圍）

- **動作**：讀分層 enforcement
- **預期**：501-2000 與 >2000 兩級皆有 gate
- **實際**：只有 >2000 一條判斷式

`api/services/quote_engine_service.py:450-453`

```python
# CR-0150（ADR-027 Decision 3／16_API:397）：requote v+1 送出分層核可。
# delta=|v+1 總額 − v 總額|：≤500 逕送；501–2000 小編核可（OPS 角色執行送出
# 即核可，身分由 router RBAC 保證）；>2000 主管覆核（僅下列角色可執行送出）。
_REQUOTE_TIER_EDITOR_MAX = 2000.0
```

`api/services/quote_engine_service.py:534-545`

```python
            delta = abs(float(rq[1]) - float(prev[0] if prev else 0))
            if delta > _REQUOTE_TIER_EDITOR_MAX and (actor_role or "") not in _REQUOTE_SUPERVISOR_ROLES:
                raise ApiError(
                    "REQUOTE_SUPERVISOR_REQUIRED",
                    f"修正報價價差 {delta:.0f} 超過 {_REQUOTE_TIER_EDITOR_MAX:.0f}，"
                    "須由主管（operations_manager／admin）執行送出（CR-0150 分層核可）",
                    403,
                )
```

`501–2000` 依註解由 router RBAC 承載；`test_cr_0150_tiered_approval.py:61-64` 記載該層在 API 面「暫不可行使」（`:send` router RBAC 已收斂為 `admin/operations_manager`）。

### 步驟 7 — 執行既有測試

- **動作**：跑 requote／分層／AI 雙閘測試
- **預期**：取得執行證據
- **實際**：12 項全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0144_requote_channel.py tests/test_cr_0150_tiered_approval.py \
  tests/test_cr_0152_ai_quote_gate.py -q -p winloop_plugin --tb=line
12 passed
```

逐項對照 TC 的四個斷言：

| TC 斷言 | 覆蓋測試 | 結果 |
|---|---|---|
| 建 quote v+1、金額由引擎算 | `test_cr_0144_requote_channel.py::test_command_creates_quote_v_plus_1_and_replays`（`:60`）、`::test_supersedes_chain_on_existing_quote`（`:86`） | 通過 |
| 非 assignee → 403 | `::test_403_non_assignee_and_wrong_status`（`:106`） | 通過 |
| 同 request_id 重送冪等回放 | `::test_command_creates_quote_v_plus_1_and_replays`（`:71-76`，斷言 200＋同一 quote id＋quote 表僅 1 列） | 通過 |
| 保固/建案 403 | `test_cr_0152_ai_quote_gate.py::test_warranty_case_fail_closed_for_non_staff`（`:79`） | 通過；該測試以 `qe.transition(action="send")` 觸發，非以 requote command 觸發 |

`test_cr_0152_ai_quote_gate.py:26-52` 的 fixture 顯示保固案件是靠直接 INSERT `warranty_claims` 建立：

```python
    if warranty:
        # customer_id FK → users;借 seed admin(test@lock-ai.com)滿足 NOT NULL
        ...
        await db_module._conn.execute(
            "INSERT INTO warranty_claims (id, work_order_id, customer_id, device_brand, "
```

---

## 觀測到的其他事實

- browser 入口（`/tenants/{tid}/work-orders/{woId}/requote-requests`）的 RBAC 為 `TECH_ACTION_ROLES`；非 technician 角色代發起會標記 `initiated_via='cs_fallback'`（`requote_requests.py:100-107`）。
- `initiated_via` 的合法值只有 `technician_command` / `cs_fallback`（`requote_service.py:47-48` 與 DB CHECK `097-requote-requests.sql:19-20`）。
- `requote_requests` 無 UPDATE 語句，`closed` 狀態在程式碼無寫入者（詳見 TC-ONSITE-07 步驟 4）。
- audit 事件 `requote.command_received` 以 fail-soft 寫入（`requote_service.py:118-130`），失敗僅記 WARN。
