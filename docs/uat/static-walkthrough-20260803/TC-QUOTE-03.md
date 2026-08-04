# TC-QUOTE-03 — 保固／建案案件的報價送出限制

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 5） |
| 走查時間 | 2026-08-03 17:49（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/services/quote_engine_service.py:455-456`、`:509-527`、`api/tests/test_cr_0152_ai_quote_gate.py:78-105` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 403 `AI_FORBIDDEN_WARRANTY_PROJECT` 存在，判定條件為「該報價的工單有 `warranty_claims` 關聯」且送出者角色不在人類 staff 白名單；「建案」判定在程式碼註解中明記為遺留、**找不到**任何 project／建案的判定邏輯，且工單尚未綁定（PC 階段報價）時整段檢查被略過。 |

**TC 原文**｜前置：保固期內 / 建案案件｜步驟：AI 嘗試觸發報價送客｜判定基準：403 AI_FORBIDDEN_WARRANTY_PROJECT；必由客服手動 approve send｜⚠ 未標註｜P0｜FR-API-02、FR-API-17｜SC-04

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| AI | `:send`（保固單） | `QuoteSendRejected(403)` | AI 先被第一閘擋 | `quote_engine_service.py:509-515` | 403 `AI_FORBIDDEN_FINAL_QUOTE`（非 WARRANTY 碼） |
| 未帶角色的呼叫端 | `:send`（保固單） | `QuoteSendRejected(403)` | fail-closed | `quote_engine_service.py:522-527` | 403 `AI_FORBIDDEN_WARRANTY_PROJECT` |
| 客服／主管 | `:send`（保固單） | `QuoteSentToCustomer` | 人類 staff 白名單 | `quote_engine_service.py:456`、`:522` | `("customer_service","operations_manager","admin")` 放行 |
| 任一 actor | `:send`（建案案件） | `QuoteSendRejected(403)` | 建案同保固 | — | **找不到**建案判定 |
| 任一 actor | `:send`（PC 階段報價，無工單） | `QuoteSendRejected(403)` | TC 未區分 | `quote_engine_service.py:516-518` | `wo_row[0]` 為 NULL → 整段保固檢查跳過 |

---

## 走查紀錄

### 步驟 1 — 保固閘的完整條文

- **動作**：讀 send 的第二閘
- **預期**：保固／建案案件 403 `AI_FORBIDDEN_WARRANTY_PROJECT`
- **實際**：僅以 `warranty_claims` 表關聯判定

`api/services/quote_engine_service.py:509-527`

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

白名單常數：

`api/services/quote_engine_service.py:455-456`

```python
# CR-0152（ADR-025）：保固案件送出的人類 staff 白名單（AI/未知角色 fail-closed）
_HUMAN_STAFF_SEND_ROLES = ("customer_service", "operations_manager", "admin")
```

### 步驟 2 — 「建案」判定

- **動作**：找 project／建案的判定條件
- **預期**：建案案件同樣觸發 403
- **實際**：**找不到**；程式碼註解自述為遺留

`api/services/quote_engine_service.py:506-508`

```python
    # CR-0152（ADR-025 憲章，server-side enforce）：AI 雙閘——
    # ①ai_agent 永不可對客戶送出最終報價；②保固案件（warranty_claims 關聯）
    # 僅人類 staff 角色可送（fail-closed：未知/未帶角色一律擋；建案判定記遺留）。
```

錯誤訊息字面含「保固／建案案件」（`:525`），但 SQL 條件只有 `warranty_claims`（`:519-521`）。走查 `api/services/quote_engine_service.py` 全檔，**找不到** project / 建案 / site_group 等對應查詢。

- TC 判定基準：「保固期內 / 建案案件」兩類皆須 403
- 程式碼：僅 `warranty_claims` 有關聯即判定

此處僅並陳，不裁定。

### 步驟 3 — AI 觸發時實際收到的碼

- **動作**：模擬 TC 步驟「AI 嘗試觸發報價送客」
- **預期**：403 `AI_FORBIDDEN_WARRANTY_PROJECT`
- **實際**：`actor_role="ai_agent"` 會在第一閘先被擋，回 `AI_FORBIDDEN_FINAL_QUOTE`

既有測試對此明確斷言：

`api/tests/test_cr_0152_ai_quote_gate.py:79-91`

```python
async def test_warranty_case_fail_closed_for_non_staff():
    wid, pid, qid = await _mk_quote(warranty=True)
    try:
        # 未帶角色(legacy/自動化路徑)→ fail-closed
        with pytest.raises(ApiError) as ei:
            await qe.transition(tenant_id=TID, quote_id=qid, action="send")
        assert ei.value.error_code == "AI_FORBIDDEN_WARRANTY_PROJECT"
        # ai_agent 在雙閘第一關就擋
        with pytest.raises(ApiError) as ei2:
            await qe.transition(tenant_id=TID, quote_id=qid, action="send",
                                actor_role="ai_agent")
        assert ei2.value.error_code == "AI_FORBIDDEN_FINAL_QUOTE"
```

即 `AI_FORBIDDEN_WARRANTY_PROJECT` 的實際觸發者是「未帶 `actor_role` 的呼叫端」，而非 `ai_agent`。

### 步驟 4 — 「必由客服手動 approve send」

- **動作**：確認人類 staff 送出路徑
- **預期**：客服可手動送出
- **實際**：白名單放行，但 router 層另有更窄的角色限制

`api/routers/quote_v2.py:24-25`、`:219`

```python
_COST_VISIBLE_ROLES = {"admin", "operations_manager"}  # SA-01：死角色移除
_APPROVE_ROLES = ("admin", "operations_manager")  # SA-01：死角色移除
...
                        user: CurrentUser = Depends(role_required(*OPS_ROLES)),
```

service 白名單含 `customer_service`（`quote_engine_service.py:456`），實際能否到達 service 取決於 `OPS_ROLES` 是否含 `customer_service`（本走查未展開 `api/core/deps.py:OPS_ROLES` 定義）。

`:approve` 端點另限 `_APPROVE_ROLES`（`quote_v2.py:233`），與 `:send` 為兩個獨立動作；TC 文字「approve send」在實作中對應兩個端點。

### 步驟 5 — 執行既有測試

- **動作**：跑 AI 雙閘測試
- **預期**：取得執行證據
- **實際**：第一輪無資料庫全數失敗；建立本機測試庫後重跑，三檔 22 項全數通過

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_cr_0152_ai_quote_gate.py tests/test_cr_0128_quote_gate.py tests/test_cr_0032_quote_engine.py -q -rs --tb=no
FFFFFFFFFFFF..FFFFFFFF                                                   [100%]
20 failed, 2 passed in 2.82s
```

錯誤原文 `ERROR api.db:db.py:48 環境變數 POSTGRES_URI 未設定`。

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0152_ai_quote_gate.py -q -p winloop_plugin --tb=no
3 passed in 2.94s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0128_quote_gate.py -q -p winloop_plugin --tb=no
11 passed in 1.09s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0032_quote_engine.py -q -p winloop_plugin --tb=no
8 passed in 3.64s
```

`test_cr_0152_ai_quote_gate.py` 的 3 項（含步驟 3 引用的保固／建案分支斷言）在第二輪通過。

---

## 觀測到的其他事實

- 保固檢查僅在 `quote.work_order_id` 非 NULL 時執行（`quote_engine_service.py:518`）。CR-0128 報價先行主路徑上，PC 階段報價的 `work_order_id` 為 NULL（`create_quote` 於 `:147-151` 以 `work_order_id=None` INSERT），此時整段保固檢查被跳過。
- `AI_FORBIDDEN_WARRANTY_PROJECT` 未出現在 `web/brand-portal/src/lib/apiError.ts` 的中文映射字典中（搜尋結果為空）。
- FR-API-17 對應的保固功能在 `api/routers/device_warranty.py` 與 `api/services/warranty_service.py`，本走查未展開。
