# TC-ONSITE-07 — 現場報價修正（requote）建 v+1 串鏈與客戶確認續工

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，requote 通道與分層核可 9 項全數通過（見步驟 6） |
| 走查時間 | 2026-08-03 22:35（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/requote_service.py:1-131`、`api/routers/requote_requests.py:32-117`、`api/services/quote_engine_service.py:29-42`、`:456-556`、`api/routers/consumer_v2.py:270-328`、`api/services/work_order_service.py:915-923`、`:1585-1591`、`SQL/migrations/097-requote-requests.sql`、`web/tech-portal/src/app/my-orders/[id]/scope-change/page.tsx` |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | 鏈路的中段完整：技師發起 → 建 quote v+1 且 `supersedes_quote_id` 串鏈（`requote_service.py:97-104`）→ `:send` → 客戶 LIFF accept（`consumer_v2.py:303-328`）→ `state='accepted'`。落差在兩端的狀態語彙：TC 寫「工單 on_site → quoted」，但工單狀態機七值（`work_order_service.py:915-923`）既無 `on_site` 也無 `quoted`，`submit_requote` 的前置條件是 `status == 'in_progress'`（`requote_service.py:23`、`:72-74`），且成功後**不變更工單狀態**。TC 所述「approved 續工 / 拒絕 → 按原報價完工或走取消分流」在程式碼中找不到對應分支——quote accept／decline 皆不回寫工單或 `requote_requests`，`requote_requests.status` 的第三個合法值 `closed` 全 repo 無寫入者。 |

**TC 原文**｜前置：線上報價與現場不符（估價誤差 / 漏項）｜步驟：師傅發起現場報價修正（requote）｜判定基準：工單 on_site → quoted；建 quote v+1（supersedes_quote_id 串鏈）→ 客戶 LIFF 確認 → approved 續工；拒絕 → 按原報價完工或走取消分流｜需求：FR-TEC-07｜旅程：SC-07

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 技師 | 送出修正請求 | `RequoteCommandReceived` | assignee＋現場中 | `requote_service.py:63-82` | 非 assignee → 403；非 `in_progress` → 403；同單 open → 409 |
| 系統 | 工單轉 `quoted` | `WorkOrderQuoted` | on_site → quoted | — | **找不到**；狀態機無 `quoted`，函式無 `UPDATE work_orders` |
| 系統 | 建 quote v+1 | `QuoteVersionCreated` | supersedes 串鏈 | `requote_service.py:97-104` | `create_quote` + `UPDATE quote SET supersedes_quote_id` |
| 小編／主管 | `:send` | `QuoteSent` | delta>2000 限主管 | `quote_engine_service.py:538-545` | 403 `REQUOTE_SUPERVISOR_REQUIRED` |
| 客戶 | LIFF accept | `QuoteAccepted` | sent → accepted | `consumer_v2.py:322-326` | `transition(action="accept")` |
| 系統 | 續工 | `WorkResumed` | approved 後放行 | — | **找不到**；accept 不改工單狀態 |
| 客戶 | LIFF reject | `QuoteRejected` | 按原報價完工 or 取消 | `quote_engine_service.py:36` | `decline` → `rejected`；無後續分流程式碼 |

---

## 走查紀錄

### 步驟 1 — 前置狀態：TC 的 `on_site` 與程式碼的 `in_progress`

- **動作**：讀 `requote_service` 的狀態常數
- **預期**：工單 `on_site` 可發起
- **實際**：程式碼要求 `in_progress`，且原始碼註解明寫此差異

`api/services/requote_service.py:21-23`

```python
_REASONS = {"estimate_error", "scope_add", "scope_change"}
# 工單狀態機無 on_site(ADR-027 語彙)——現場作業對映 in_progress
_ALLOWED_WO_STATUS = {"in_progress"}
```

`api/services/requote_service.py:69-74`

```python
    wo_tech, wo_status = (str(wo[0]) if wo[0] else None), wo[1]
    if not wo_tech or wo_tech != technician_id:
        raise ApiError("FORBIDDEN", "technician 非本工單 assignee(ADR-027)", 403)
    if wo_status not in _ALLOWED_WO_STATUS:
        raise ApiError("FORBIDDEN",
                       f"工單狀態 {wo_status} 不可發起現場修正(須 in_progress)", 403)
```

`on_site` 全 repo 搜尋結果（唯一命中即上方註解）：

```
$ grep -rn "on_site" --include=*.py --include=*.sql --include=*.ts --include=*.tsx --include=*.yaml api SQL web
api/services/requote_service.py:22:# 工單狀態機無 on_site(ADR-027 語彙)——現場作業對映 in_progress
```

`quoted` 作為工單狀態的搜尋：`_WO_TRANSITIONS`（`work_order_service.py:915-923`）七值為 `created / assigned / accepted / in_progress / completed / confirmed / cancelled`，不含 `quoted`。

- TC 判定基準：工單 `on_site` → `quoted`
- 程式碼：前置為 `in_progress`；`submit_requote` 全函式（`:39-131`）無 `UPDATE work_orders`，工單狀態不因 requote 改變

此處僅並陳，不裁定。

### 步驟 2 — quote v+1 與 supersedes 串鏈

- **動作**：讀建 v+1 的程式碼
- **預期**：串鏈上一版
- **實際**：一致

`api/services/requote_service.py:84-104`

```python
    # 找現行最新版報價(supersedes 串鏈上一環)
    cur = await db_module._conn.execute(
        "SELECT id FROM quote WHERE work_order_id=%s::uuid "
        "ORDER BY version DESC LIMIT 1", (work_order_id,))
    prev = await cur.fetchone()
    prev_quote_id = str(prev[0]) if prev else None

    # 品牌報價引擎建 v+1 draft(金額由小編後續定價——技師零定價權)。
    # created_by FK 指向 users:由 technicians.user_id 反查(technician_id 是技師主檔 id)
    cur = await db_module._conn.execute(
        "SELECT user_id FROM technicians WHERE id=%s::uuid", (technician_id,))
    urow = await cur.fetchone()
    tech_user_id = str(urow[0]) if urow and urow[0] else None
    quote = await quote_engine_service.create_quote(
        tenant_id=tenant, work_order_id=work_order_id,
        created_by=tech_user_id)
    new_quote_id = str(quote["id"])
    if prev_quote_id:
        await db_module._conn.execute(
            "UPDATE quote SET supersedes_quote_id=%s::uuid WHERE id=%s::uuid",
            (prev_quote_id, new_quote_id))
```

新建的 v+1 為 `draft` 狀態，須經 `:send` 方能被客戶看見（狀態機 `quote_engine_service.py:29-42`）。

技師端 UI 對應：`web/tech-portal/src/app/my-orders/[id]/scope-change/page.tsx:30-34`（事由三選一，對齊 `_REASONS`）

```tsx
const REASON_OPTIONS = [
  { value: "scope_add", label: "現場追加項目(如加購鎖芯、耗材)" },
  { value: "scope_change", label: "作業範圍變更(與原報價不符)" },
  { value: "estimate_error", label: "原估價有誤(需重新估價)" },
];
```

TC 前置寫「估價誤差 / 漏項」，對應 `estimate_error` 與 `scope_add` 兩個 reason。

### 步驟 3 — 客戶 LIFF 確認

- **動作**：讀消費者報價回覆端點
- **預期**：accept → approved
- **實際**：accept → `accepted`（狀態名為 `accepted`，非 TC 用字 `approved`）

`api/services/quote_engine_service.py:29-42`

```python
_TRANSITIONS = {
    "submit":  ({"draft"}, "pending_approval"),
    "approve": ({"pending_approval"}, "approved"),
    "reject":  ({"pending_approval"}, "rejected"),
    "send":    ({"approved", "draft", "retrospective_audit_only"}, "sent"),
    "accept":  ({"sent"}, "accepted"),
    "decline": ({"sent"}, "rejected"),
    ...
}
```

`approved` 在此狀態機中是**內部核准**（`submit`→`approve`）的結果，不是客戶同意的結果；客戶同意落 `accepted`。

`api/routers/consumer_v2.py:315-328`

```python
    decision = (body or {}).get("decision")
    if decision not in {"accept", "reject"}:
        raise ApiError("VALIDATION_ERROR", "decision must be 'accept' or 'reject'", 422)
    action = "accept" if decision == "accept" else "decline"
    ...
    result = await quote_engine_service.transition(
        tenant_id=payload.tenant_id, quote_id=payload.subject_id, action=action,
    )
    return {"quote_id": result["id"], "state": result["state"]}
```

客戶端只看得到不含成本的明細：`consumer_v2.py:281-283`（`include_cost=False`）。

### 步驟 4 — 「approved 續工」與「拒絕 → 原報價完工／取消分流」

- **動作**：找 quote 決議後對工單／requote_requests 的回寫
- **預期**：accept 續工、reject 進分流
- **實際**：兩者皆找不到回寫

`submit_requote` 寫入 `requote_requests` 時狀態固定為 `'quoted'`：

`api/services/requote_service.py:106-113`

```python
    cur = await db_module._conn.execute(
        "INSERT INTO requote_requests "
        " (tenant_id, request_id, work_order_id, technician_id, reason, "
        "  item_diffs, initiated_via, status, created_quote_id) "
        "VALUES (%s::uuid, %s, %s::uuid, %s::uuid, %s, %s::jsonb, %s, 'quoted', %s::uuid) "
        f"RETURNING {_SELECT}",
```

該表的合法狀態值：`SQL/migrations/097-requote-requests.sql:21-22`

```sql
    status           VARCHAR(20) NOT NULL DEFAULT 'received'
        CHECK (status IN ('received', 'quoted', 'closed')),
```

全 repo 對 `requote_requests` 的引用：

```
$ grep -rn "requote_requests" --include=*.py --include=*.sql api SQL | grep -v tests
api/main.py:55, api/main.py:346                       （router 掛載）
api/services/requote_service.py:56, :78, :107         （SELECT 冪等 / SELECT open / INSERT）
SQL/migrations/097-requote-requests.sql:10, :30, :31  （DDL）
```

無 UPDATE 語句，`closed` 無寫入者；quote 的 accept／decline 不觸及此表。

工單側：`quote_engine_service.transition`（`:456-556` 及其後）在 `accept` 分支無 `UPDATE work_orders`；完工閘查的是 quote 是否有 `accepted`／急件補審列（`work_order_service.py:1605-1610`），而非 requote 是否收斂。

TC 提到的「拒絕 → 按原報價完工」在文件層對應狀態 `customer_disagreed_partial`（`smartlock-docs/enterprise/02_BRD.md:219`、`04_SRS.md:183`），程式碼零命中：

```
$ grep -rn "customer_disagreed_partial" --include=*.py --include=*.sql --include=*.ts --include=*.tsx api SQL web agent
（0 筆）
```

此處僅並陳，不裁定。

### 步驟 5 — 兩個發起入口與冪等

- **動作**：讀 router
- **預期**：技師本人可發起
- **實際**：兩個入口；browser 入口冪等鍵可退回 `Idempotency-Key`

`api/routers/requote_requests.py:92-113`

```python
    if user.role == "technician":
        # 技師本人:users.id → technicians.id(service 再驗 assignee)
        cur = await db_module._conn.execute(
            "SELECT id FROM technicians WHERE user_id=%s::uuid", (user.user_id,))
        row = await cur.fetchone()
        if not row:
            raise ApiError("FORBIDDEN", "無對應技師主檔", 403)
        technician_id, via = str(row[0]), "technician_command"
    else:
        # 後台代發起(降級):technician_id 取工單 assignee
        ...
        technician_id, via = str(row[0]), "cs_fallback"

    request_id = body.request_id or idempotency_key or f"ui-{_uuid.uuid4().hex}"
```

冪等回放（同 `request_id` 回同結果、HTTP 200 而非 201）：`requote_service.py:54-60` 與 `requote_requests.py:115-116`。

### 步驟 6 — 執行既有測試

- **動作**：跑 requote 通道測試
- **預期**：取得執行證據
- **實際**：9 項全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0144_requote_channel.py tests/test_cr_0150_tiered_approval.py \
  -q -p winloop_plugin --tb=line
9 passed
```

`test_cr_0144_requote_channel.py::test_supersedes_chain_on_existing_quote`（`:86-102`）驗串鏈與版本遞增：

```python
        assert d["supersedes_quote_id"] == str(q1["id"]), "v+1 須串鏈前版"
        ...
        assert row[0] == str(q1["id"]) and row[1] == q1["version"] + 1
```

`test_403_non_assignee_and_wrong_status`（`:106-117`）驗兩個 403，其中「非 in_progress」以 `status="accepted"` 的工單觸發。該檔無任何工單狀態轉 `quoted` 或客戶 accept 後續工的斷言。

---

## 觀測到的其他事實

- `smartlock-docs/enterprise/04_SRS.md:357`（FR-TEC-07）將前置寫為「技師＝工單 assignee 且工單 on_site / in_progress」，其中 `on_site` 一詞在程式碼無對應狀態值。
- `submit_requote` 的 tenant 預設值取自環境變數 `AGENT_TENANT_ID`，缺省為 `00000000-...-0001`（`requote_service.py:51-52`）。
- 同工單同時只能有一筆 open 修正（`received`/`quoted`），第二筆回 409 `STATE_CONFLICT`（`requote_service.py:77-82`）；由於無程式碼把狀態推到 `closed`，一張工單在資料層上只能成功發起一次 requote。
- audit 留痕的 `actor_id` 使用反查得到的 `technicians.user_id`，`technician_id` 移入 payload（`requote_service.py:119-128`）。
