# TC-QUOTE-02 — AI 不得送出最終報價

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 5） |
| 走查時間 | 2026-08-03 17:38（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/services/quote_engine_service.py:506-515`、`api/routers/quote_v2.py:24-25`、`:217-221`、`api/tests/test_cr_0152_ai_quote_gate.py:65-75`、`agent/lockcore/skills/locksmith-cs-sop/SKILL.md:33-34`、`:64` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 403 `AI_FORBIDDEN_FINAL_QUOTE` 確實存在且在 `send` 動作最前段擋下；但判定依據的參數名是 `actor_role` 而非 TC 寫的 `sender_role`，且「AI 僅可告知『客服已備好報價』並附範圍價」的話術在 agent skill 與 gateway 中**找不到**——skill 現行規則是金錢相關一律 `transfer_to_human` 且「不報價」。 |

**TC 原文**｜前置：AI 對話中｜步驟：AI 嘗試以 sender_role=ai_agent 送出 final quote｜判定基準：403 AI_FORBIDDEN_FINAL_QUOTE；AI 僅可告知「客服已備好報價」並附範圍價｜⚠ 未標註｜P0｜FR-API-02｜SC-04

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| AI | `:send`（actor_role=ai_agent） | `QuoteSendRejected(403)` | AI 永不可送最終報價 | `quote_engine_service.py:509-515` | 403 `AI_FORBIDDEN_FINAL_QUOTE` |
| AI | 打 `:send` 端點 | `RequestRejected(403)` | router RBAC 第一層 | `quote_v2.py:219` | `role_required(*OPS_ROLES)` |
| AI | 客戶問價格 | `TransferToHuman` | 金錢相關轉真人 | `locksmith-cs-sop/SKILL.md:33-34` | 「呼叫 `transfer_to_human`，**不報價、不追問**」 |
| AI | 告知範圍價 | `RangePriceQuoted` | TC 要求可給範圍價 | — | **找不到**對應實作或話術 |

---

## 走查紀錄

### 步驟 1 — service 層的 AI 閘

- **動作**：讀 `transition` 的 send 前置檢查
- **預期**：403 `AI_FORBIDDEN_FINAL_QUOTE`
- **實際**：一致

`api/services/quote_engine_service.py:506-515`

```python
    # CR-0152（ADR-025 憲章，server-side enforce）：AI 雙閘——
    # ①ai_agent 永不可對客戶送出最終報價；②保固案件（warranty_claims 關聯）
    # 僅人類 staff 角色可送（fail-closed：未知/未帶角色一律擋；建案判定記遺留）。
    if action == "send":
        if (actor_role or "") == "ai_agent":
            raise ApiError(
                "AI_FORBIDDEN_FINAL_QUOTE",
                "AI 不得對客戶送出最終報價（ADR-025 話術邊界憲章）",
                403,
            )
```

此檢查位於 send 分支最前，排在保固閘（`:516-527`）、分層核可（`:531-546`）、核准門檻（`:550-559`）之前。

### 步驟 2 — 參數名稱

- **動作**：對照 TC 的 `sender_role` 與程式碼的入參
- **預期**：以 `sender_role=ai_agent` 判定
- **實際**：判定依 `actor_role`

`api/services/quote_engine_service.py:459-462`

```python
async def transition(
    *, tenant_id: str, quote_id: str, action: str, actor_id: str | None = None,
    comment: str | None = None, actor_role: str | None = None,
) -> dict:
```

router 以登入者角色帶入：

`api/routers/quote_v2.py:197-201`

```python
    _xt(user, tenantId)
    # actor_role 供 CR-0150 requote 分層核可（send 時 delta>2000 限主管角色）
    result = {"data": await qe.transition(
        tenant_id=tenantId, quote_id=id, action=action, actor_id=user.user_id,
        comment=comment, actor_role=user.role)}
```

repo 中 `sender_role` 僅出現在對話訊息 metadata（例：`api/services/conversation_service.py:266`、`:275`、`:437-443`），其值域為 `system` / `line_user` / `ai` / `agent_human`，與 quote send 無關聯。搜 quote 路徑上的 `sender_role`：**找不到**。

此處僅並陳，不裁定。

### 步驟 3 — router 層 RBAC

- **動作**：確認端點的角色守衛
- **預期**：TC 未指定
- **實際**：`:send` 限 `OPS_ROLES`，成本可視角色另有白名單

`api/routers/quote_v2.py:217-221`

```python
@router.post("/tenants/{tenantId}/quotes/{id}:send", operation_id="sendQuoteV2", summary="送客戶 v2（凍結 snapshot）", tags=["M04 Quote"])
async def send_quote_v2(tenantId: str = Path(...), id: str = Path(...),
                        user: CurrentUser = Depends(role_required(*OPS_ROLES)),
                        idem: IdempotencyContext | None = Depends(idempotency_guard)) -> dict:
    return await _transition(tenantId, id, "send", user, idem=idem)
```

即 service 層的 `ai_agent` 檢查為縱深防禦（測試 docstring 亦如此描述：`api/tests/test_cr_0152_ai_quote_gate.py:6`）。

### 步驟 4 — AI 側的報價話術

- **動作**：查 agent skill 與 LINE gateway 是否有「客服已備好報價 + 範圍價」話術
- **預期**：AI 可告知範圍價
- **實際**：**找不到**；現行 skill 規則為不報價、轉真人

`agent/lockcore/skills/locksmith-cs-sop/SKILL.md:33-34`

```markdown
2. **明確要求真人 / 金錢相關(報價·費用·退費·發票·付款) / 急迫派工 / 連續不滿**
   → 呼叫 `transfer_to_human`,**不報價、不追問**。**該工具回傳的核對表單請原封不動回覆給客戶,不要改寫**。
```

`agent/lockcore/skills/locksmith-cs-sop/SKILL.md:64`

```markdown
   且引用須加免責(「網路資料顯示…」)。**報價/保固/售後/付款/客戶私人資料一律 transfer_to_human**
```

搜「客服已備好」「範圍價」「價格區間」「參考價」於 `agent/lockcore/skills/` 與 `agent/lockcore/channels/line_gateway.py`：**找不到**。

此處僅並陳，不裁定。

### 步驟 5 — 執行既有測試

- **動作**：跑 AI 雙閘測試
- **預期**：取得執行證據
- **實際**：第一輪無資料庫全數失敗；建立本機測試庫後重跑，三檔 22 項全數通過，含 AI 送出報價被擋的斷言

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

該檔對本 TC 有直接斷言，第二輪執行通過：

`api/tests/test_cr_0152_ai_quote_gate.py:66-75`

```python
async def test_ai_agent_never_sends_final_quote():
    wid, pid, qid = await _mk_quote()
    try:
        with pytest.raises(ApiError) as ei:
            await qe.transition(tenant_id=TID, quote_id=qid, action="send",
                                actor_role="ai_agent")
        assert ei.value.error_code == "AI_FORBIDDEN_FINAL_QUOTE"
        assert ei.value.status_code == 403
```

---

## 觀測到的其他事實

- 「AI 送出報價」的實際攻擊面在 repo 中無對應呼叫端：agent 側對 API 的報價互動只有 `/internal/quotes/{quote_id}:customer-respond`（`agent/lockcore/channels/line_gateway.py:900`），未見任何呼叫 `:send` 的 agent 程式碼。
- `AI_FORBIDDEN_FINAL_QUOTE` 未出現在 `web/brand-portal/src/lib/apiError.ts` 的中文映射字典中（搜尋結果為空）。
- 送客戶後的 LINE 推播由 outbox 發送（`quote_engine_service.py:640-657`，`push_kind="quote_proposal"`），觸發者為 send 動作本身，非 AI。
