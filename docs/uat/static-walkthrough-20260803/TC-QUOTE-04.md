# TC-QUOTE-04 — 客戶拒絕後的報價版本鏈

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 5） |
| 走查時間 | 2026-08-03 18:02（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/services/quote_engine_service.py:36`、`:96-152`、`:722-741`、`api/services/requote_service.py:84-104`、`api/routers/quote_v2.py:67-93`、`api/routers/consumer_v2.py:270-294`、`web/brand-portal/src/app/quotes/[token]/page.tsx:194-195`、`SQL/migrations/041-quote-engine.sql:26` |
| 優先級 / 路徑類型 | P1 / happy |
| 事實結論 | `supersedes_quote_id` 欄位存在且會被寫入，但唯一寫入點是技師現場修正（`requote_service`）；客服在後台建 v2（`create_quote`）只遞增 `version`，**不寫** `supersedes_quote_id`。舊版連結在後端與前端皆無導向最新版的邏輯，客戶端頁面對非 `sent` 狀態僅停用操作按鈕。 |

**TC 原文**｜前置：quote customer_sent｜步驟：客戶 LIFF 拒絕 → 客服建 v2 → 客戶確認 v2｜判定基準：版本鏈 supersedes_quote_id 完整 v1→v2；舊版按鈕導向最新版｜happy｜P1｜FR-API-02、FR-API-03、FR-WEB-06｜SC-04、SC-07、SC-08

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | LIFF 拒絕 v1 | `QuoteDeclined` | sent → rejected | `quote_engine_service.py:36` | `"decline": ({"sent"}, "rejected")` |
| 客服 | 建 v2 | `QuoteVersionCreated(v2, supersedes=v1)` | 串鏈前版 | `quote_engine_service.py:138-151` | 只算 `MAX(version)+1`，INSERT 欄位清單**不含** `supersedes_quote_id` |
| 技師 | 現場修正 command | `QuoteVersionCreated(v+1, supersedes=v)` | 串鏈前版 | `requote_service.py:85-104` | 建 quote 後 UPDATE `supersedes_quote_id` |
| 客戶 | 開舊版連結 | `RedirectToLatestQuote` | 舊版導向最新版 | — | **找不到**導向邏輯 |
| 客戶 | 確認 v2 | `QuoteAccepted` | sent → accepted | `quote_engine_service.py:35` | transition("accept") |

---

## 走查紀錄

### 步驟 1 — 客戶拒絕

- **動作**：讀 decline 轉換
- **預期**：v1 進終態
- **實際**：一致，落點為 `rejected`（非 `superseded`）

`api/services/quote_engine_service.py:35-36`

```python
    "accept":  ({"sent"}, "accepted"),
    "decline": ({"sent"}, "rejected"),
```

客戶端入口：`api/routers/consumer_v2.py:316-328`（decision `reject` → action `decline`）與 `api/routers/internal_ingest.py:191-194`（LINE postback 旁路）。

### 步驟 2 — 客服建 v2 是否串鏈

- **動作**：讀 `create_quote` 的 INSERT
- **預期**：v2 的 `supersedes_quote_id` 指向 v1
- **實際**：INSERT 欄位清單不含 `supersedes_quote_id`

`api/services/quote_engine_service.py:137-152`

```python
    if work_order_id:
        next_version = (await (await conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM quote WHERE work_order_id = %s::uuid",
            (work_order_id,),
        )).fetchone())[0]
    else:
        next_version = (await (await conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM quote WHERE problem_card_id = %s::uuid",
            (problem_card_id,),
        )).fetchone())[0]
    row = await (await conn.execute(
        "INSERT INTO quote (work_order_id, problem_card_id, state, expiry_at, tenant_id, created_by, version) "
        "VALUES (%s, %s, %s, %s, %s::uuid, %s, %s) RETURNING id",
        (work_order_id, pc_id, initial_state, expiry, tenant_id, created_by, next_version),
    )).fetchone()
```

客服建 v2 的端點直接呼叫 `create_quote`，未帶前版資訊：

`api/routers/quote_v2.py:72-80`

```python
async def create_problem_card_quote_v2(
    body: _QuoteCreateBody,
    tenantId: str = Path(...), pcId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    """問題卡階段建報價（work_order_id=NULL）；客戶確認後 convert 開單時自動回填綁定。"""
    _xt(user, tenantId)
    return {"data": await qe.create_quote(
        tenant_id=tenantId, problem_card_id=pcId, created_by=user.user_id, urgent=body.urgent)}
```

### 步驟 3 — `supersedes_quote_id` 的唯一寫入點

- **動作**：全 repo 搜寫入
- **預期**：客服路徑亦寫入
- **實際**：僅技師現場修正路徑寫入

`SQL/migrations/041-quote-engine.sql:26`

```sql
    supersedes_quote_id UUID REFERENCES quote(id) ON DELETE SET NULL,  -- 版本鏈
```

`api/services/requote_service.py:84-104`

```python
    # 找現行最新版報價(supersedes 串鏈上一環)
    cur = await db_module._conn.execute(
        "SELECT id FROM quote WHERE work_order_id=%s::uuid "
        "ORDER BY version DESC LIMIT 1", (work_order_id,))
    prev = await cur.fetchone()
    prev_quote_id = str(prev[0]) if prev else None
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

搜 `SET supersedes_quote_id` 於 `api/`：僅 `requote_service.py:103` 一處。讀取端亦僅一處（`quote_engine_service.py:532-534` 的分層核可 delta 計算）。

- TC 判定基準：「版本鏈 supersedes_quote_id 完整 v1→v2」，前置與步驟是**客服建 v2**
- 程式碼：客服建 v2（`create_quote`）不寫該欄；僅技師 requote command 會寫

此處僅並陳，不裁定。

### 步驟 4 — 舊版連結是否導向最新版

- **動作**：查後端與前端
- **預期**：舊版按鈕導向最新版
- **實際**：**找不到**導向邏輯

後端消費者查詢直接以 token 內的 `subject_id` 取該張報價，無版本查找：

`api/routers/consumer_v2.py:282-294`

```python
    payload = _verify_quote_token(token)
    quote = await quote_engine_service.get_quote(
        tenant_id=payload.tenant_id, quote_id=payload.subject_id, include_cost=False,
    )
    # 客戶端只需金額/明細/狀態/有效期 —— 不回 work_order_id（客戶無用且為最小資料原則）
    return {
        "quote_id": quote["id"],
        "state": quote["state"],
        "total_amount": quote["total_amount"],
        "lines": quote["lines"],  # include_cost=False → 無 unit_price
        "expires_at": quote["expiry_at"],
        "snapshot_hash": quote["snapshot_hash"],
    }
```

前端只依狀態決定按鈕是否可用，無 redirect：

`web/brand-portal/src/app/quotes/[token]/page.tsx:194-195`

```tsx
  const stateColor = STATE_COLOR[data.state] ?? STATE_COLOR["sent"];
  const actionable = data.state === "sent";
```

前端型別 `QuoteState` 列舉為 `draft | pending_approval | approved | sent | accepted | rejected | expired`（`:29-35`、`:61-69`），**不含** `superseded`。

另，`superseded` 狀態值在 `api/services/` 下僅出現於 docstring 與 gate 的說明字串（`quote_engine_service.py:6`、`:166`），**找不到**任何 `state = 'superseded'` 的寫入。

此處僅並陳，不裁定。

### 步驟 5 — 執行既有測試

- **動作**：跑版本鏈測試
- **預期**：取得執行證據
- **實際**：第一輪無資料庫全數失敗；建立本機測試庫後重跑，`test_cr_0144_requote_channel.py` 5 項全數通過（含 `test_supersedes_chain_on_existing_quote`）

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_pc_convert_to_wo.py tests/test_cr_0095_quote_line_approval.py tests/test_cr_0144_requote_channel.py -q --tb=no -rf
FAILED tests/test_cr_0144_requote_channel.py::test_supersedes_chain_on_existing_quote
...
21 failed, 3 passed in 3.58s
```

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0144_requote_channel.py -q -p winloop_plugin --tb=no
5 passed in 3.07s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_pc_convert_to_wo.py -q -p winloop_plugin --tb=no
7 passed in 3.33s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0095_quote_line_approval.py -q -p winloop_plugin --tb=no
3 failed, 9 passed in 3.68s
```

通過的 `test_supersedes_chain_on_existing_quote` 覆蓋的是技師 requote 路徑（`api/tests/test_cr_0144_requote_channel.py:86-100`），走查**未找到**覆蓋「客服建 v2 串鏈」的測試，第二輪亦無此類案例被執行。3 項失敗集中在 `test_cr_0095_quote_line_approval.py` 的客戶回覆路徑（失敗點見 TC-QUOTE-08 步驟 5）。

---

## 觀測到的其他事實

- v1 被拒後，`assert_pc_quote_confirmed` 對「全數 rejected」的 PC 回 409 `QUOTE_STATE_INVALID`（`quote_engine_service.py:184-188`），訊息為「請開新版本報價並取得客戶確認」。
- `mint_view_token` 對 `rejected` 狀態的報價仍會鑄 token（`quote_engine_service.py:735`：允許 `sent/accepted/rejected/expired`），故舊版連結在 v1 被拒後仍可開啟並顯示 `rejected`。
- 前端 `web/brand-portal/src/app/quotes/[token]/page.tsx:73-79` 對 410 與 429 有專用文案分支，對其他 4xx 一律顯示「連結無效或已過期」。
