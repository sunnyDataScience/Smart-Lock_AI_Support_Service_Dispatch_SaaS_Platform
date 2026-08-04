# TC-ONSITE-03 — 加價 NTD 501–2000 自動建 quote v+1 並待客戶 LIFF 確認

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，requote／分級／pending gate 相關 16 項全數通過（見步驟 6） |
| 走查時間 | 2026-08-03 20:55（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/work_order_service.py:2890-2921`、`:2992-3009`、`:1585-1591`、`api/services/requote_service.py:39-131`、`api/services/quote_engine_service.py:29-42`、`:450-455`、`:527-545`、`api/routers/consumer_v2.py:270-329`、`api/services/scope_change_service.py:125-210`、`SQL/migrations/097-requote-requests.sql` |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | 「建 quote v+1 → 客戶確認」的鏈路確實存在，但入口是 requote command（`requote_service.submit_requote`，`:97-104`），與金額分級無關——該路徑對任何金額都建 v+1，且技師端不填金額。分級函式 `_classify_scope_tier`（`standard_max=2000`）僅作用於 `record_scope_change`，而該函式**不建任何 quote**、對所有 tier 一律 `status='pending'`。程式碼中找不到「delta 落在 501–2000 → 自動建 quote v+1」的分支；`scope_changes` 與 `quote` 兩張表在程式碼中無互相建立的呼叫。 |

**TC 原文**｜前置：加價 NTD 501–2000｜步驟：發起 scope change｜判定基準：自動建 quote v+1 → 客戶 LIFF 確認後才可續作｜需求：FR-API-08｜旅程：SC-07

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 技師 | 發起 scope change（501–2000） | `ScopeChangeRequested(standard)` | 501–2000 → standard | `work_order_service.py:2912-2913` | tier=`standard`；`requires_supervisor=False` |
| 系統 | 自動建 quote v+1 | `QuoteVersionCreated` | standard 觸發 | — | **找不到**；`record_scope_change` 全函式無 quote 相關呼叫 |
| 技師 | 發起 requote command | `RequoteCommandReceived` | assignee＋in_progress | `requote_service.py:63-104` | 建 v+1 draft＋`supersedes_quote_id` 串鏈（不看金額） |
| 小編 | `:send` | `QuoteSent` | 分層核可 | `quote_engine_service.py:527-545` | delta > 2000 且非主管 → 403；501–2000 無額外限制 |
| 客戶 | LIFF accept | `QuoteAccepted` | sent → accepted | `consumer_v2.py:303-328` | `transition(action="accept")` |
| 系統 | 續作放行 | `WorkResumed` | 確認後才可續作 | `work_order_service.py:1585-1591` | 擋的是**完工**（pending scope → 409），非「續作」 |

---

## 走查紀錄

### 步驟 1 — 501–2000 的分級判定

- **動作**：讀 `_classify_scope_tier`
- **預期**：delta 落 501–2000 → standard
- **實際**：一致

`api/services/work_order_service.py:2908-2915`

```python
    delta = max(0.0, (new_price or 0.0) - (original_price or 0.0))
    pct = (delta / original_price) if original_price and original_price > 0 else (1.0 if delta else 0.0)
    if delta > float(policy["standard_max"]) or pct >= float(policy["major_pct"]):
        tier = "major"
    elif delta > float(policy["minor_max"]):
        tier = "standard"
    else:
        tier = "minor"
```

`test_cr_0038_bucket4.py:30-34` 對此有斷言（實跑通過，見步驟 6）。

### 步驟 2 — standard tier 是否觸發 quote v+1

- **動作**：通讀 `record_scope_change` 全文（`work_order_service.py:2924-3075`）
- **預期**：standard 自動建 quote v+1
- **實際**：函式內無任何 `quote` 表操作

該函式的全部寫入動作依序為：

1. `SELECT technician_id, estimated_price FROM work_orders`（`:2958-2961`）
2. `INSERT INTO scope_changes ... 'pending'`（`:2992-3009`）
3. `public_token.generate_token(..., purpose="scope_change", ttl_days=7)`（`:3017-3022`）
4. `_insert_wo_event(event_type="scope_change")`（`:3035-3038`）
5. `UPDATE work_orders SET updated_at = NOW()`（`:3039-3042`）
6. `line_push_outbox_service.enqueue(push_kind="scope_change_proposal")`（`:3056-3069`）

`quote` / `create_quote` / `supersedes_quote_id` 在 `:2924-3075` 區段的搜尋結果為零命中。

- TC 判定基準：501–2000 → **自動建 quote v+1**
- 程式碼：`record_scope_change` 建的是 `scope_changes` 提案列，客戶確認頁為 `/scope-change/{token}`（`web/brand-portal/src/app/scope-change/[token]/page.tsx:92`），非 quote 頁

此處僅並陳，不裁定。

### 步驟 3 — 實際建 quote v+1 的唯一路徑

- **動作**：找 `supersedes_quote_id` 的寫入點
- **預期**：由金額分級觸發
- **實際**：唯一寫入點在 requote command，與金額無關

`api/services/requote_service.py:84-104`

```python
    # 找現行最新版報價(supersedes 串鏈上一環)
    cur = await db_module._conn.execute(
        "SELECT id FROM quote WHERE work_order_id=%s::uuid "
        "ORDER BY version DESC LIMIT 1", (work_order_id,))
    prev = await cur.fetchone()
    prev_quote_id = str(prev[0]) if prev else None

    # 品牌報價引擎建 v+1 draft(金額由小編後續定價——技師零定價權)。
    ...
    quote = await quote_engine_service.create_quote(
        tenant_id=tenant, work_order_id=work_order_id,
        created_by=tech_user_id)
    new_quote_id = str(quote["id"])
    if prev_quote_id:
        await db_module._conn.execute(
            "UPDATE quote SET supersedes_quote_id=%s::uuid WHERE id=%s::uuid",
            (prev_quote_id, new_quote_id))
```

`submit_requote` 的參數（`:39-43`）為 `request_id / work_order_id / technician_id / reason / item_diffs / initiated_via / tenant_id`，**無金額欄位**；驗證條件只有 reason 白名單、assignee、`status == 'in_progress'`、同工單無 open 修正（`:45-82`）。

### 步驟 4 — 客戶 LIFF 確認的實際端點

- **動作**：讀消費者報價回覆端點
- **預期**：客戶確認後 quote 轉 accepted
- **實際**：一致

`api/routers/consumer_v2.py:297-328`

```python
@router.post(
    "/consumer/quotes/{token}",
    operation_id="respondConsumerQuoteV2",
    summary="消費者匿名回覆報價 v2（CR-0032 Phase C；同意/拒絕）",
    tags=["M16 Consumer"],
)
async def respond_consumer_quote(
    ...
    decision = (body or {}).get("decision")
    if decision not in {"accept", "reject"}:
        raise ApiError("VALIDATION_ERROR", "decision must be 'accept' or 'reject'", 422)
    action = "accept" if decision == "accept" else "decline"
    ...
    result = await quote_engine_service.transition(
        tenant_id=payload.tenant_id, quote_id=payload.subject_id, action=action,
    )
```

狀態機：`api/services/quote_engine_service.py:29-42`

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

v+1 由 requote 建立時為 `draft`（`requote_service.py:97-99`），須經 `:send` 才進 `sent`，客戶方能 accept。

### 步驟 5 — 「確認後才可續作」的實際落點

- **動作**：找阻擋續作的 gate
- **預期**：未確認前不可續作
- **實際**：找到的是「未確認前不可**完工**」，未找到阻擋現場繼續施工的 gate

`api/services/work_order_service.py:1585-1591`（完工硬閘內）

```python
    # CR-0049 / BR-M08-02：報價變更未經客戶確認（pending scope）→ 不可完工（安全閘，admin override 路徑可繞）
    if await _has_pending_scope_change(wo_id):
        raise ApiError(
            "PENDING_SCOPE_CHANGE",
            "有未經客戶確認的範圍/加價變更，須客戶確認或主管覆寫後才可完工",
            409,
        )
```

該 gate 的條件是 `scope_changes.status='pending'`（`:1471-1477`），**不查 quote 版本**。即：走 requote 路徑（建 v+1）而未建 scope_changes 列時，此 gate 不成立。

`requote_requests.status` 的 CHECK 為 `received/quoted/closed`（`SQL/migrations/097-requote-requests.sql:21-22`），而全 repo 中對該表的寫入只有 `requote_service.py:107-113` 一處，狀態固定寫入 `'quoted'`；**找不到**任何把它推進 `closed` 的程式碼，也找不到 quote accept 後回寫 `requote_requests` 的呼叫。

TC 所述的暫停狀態 `pending_quote_v2`（見 `smartlock-docs/enterprise/02_BRD.md:219`）在程式碼零命中：

```
$ grep -rn "pending_quote_v2" --include=*.py --include=*.sql --include=*.ts --include=*.tsx api SQL web agent
（0 筆）
```

此處僅並陳，不裁定。

### 步驟 6 — 執行既有測試

- **動作**：跑 requote／分級／pending gate 測試
- **預期**：取得執行證據
- **實際**：16 項全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0144_requote_channel.py tests/test_cr_0150_tiered_approval.py \
  tests/test_cr_0038_bucket4.py tests/test_cr_0049_pending_scope_gate.py \
  -q -p winloop_plugin --tb=line
16 passed
```

`test_cr_0144_requote_channel.py::test_supersedes_chain_on_existing_quote`（`:86-102`）斷言 v+1 串鏈：

```python
        assert d["supersedes_quote_id"] == str(q1["id"]), "v+1 須串鏈前版"
        ...
        assert row[0] == str(q1["id"]) and row[1] == q1["version"] + 1
```

該測試建單時未帶任何金額，v+1 建立與加價區間無關。

---

## 觀測到的其他事實

- `quote_engine_service.py:450-453` 的分層核可註解記載「≤500 逕送；501–2000 小編核可（OPS 角色執行送出即核可）；>2000 主管覆核」，其 enforcement 只有 `>2000` 一條（`:538-545`），501–2000 無獨立判斷式。
- `test_cr_0150_tiered_approval.py:61-64` 註記 router 層 `:send` 的 RBAC 已收斂為 `admin/operations_manager`，故「小編核可 501-2000」在 API 面「暫不可行使」。
- `record_scope_change` 端點（`work_orders_v2.py:771-798`）在 `web/` 中找不到呼叫端（詳見 TC-ONSITE-02 步驟 5）。
- 客戶對 scope_changes 提案 accept 時，工單由 `accepted`/`in_progress` 推至 `in_progress` 並寫 `resumed` 事件（`scope_change_service.py:189-207`）；該路徑與 quote 無關。
