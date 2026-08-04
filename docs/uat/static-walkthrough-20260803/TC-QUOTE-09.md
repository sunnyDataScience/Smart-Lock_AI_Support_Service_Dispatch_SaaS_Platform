# TC-QUOTE-09 — 客戶回覆報價的狀態轉移與 LINE 話術分流

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；agent 側話術測試離線通過（見步驟 6），API 側改以本機 Docker 測試庫實跑，衝突碼三項失敗（見步驟 7） |
| 走查時間 | 2026-08-03 18:58（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/services/quote_engine_service.py:764-810`、`agent/lockcore/channels/line_gateway.py:837-919`、`api/core/errors.py:1-27`、`api/tests/test_cr_0095_quote_line_approval.py:254-305`、`agent/tests/test_quote_postback_msgs.py` |
| 優先級 / 路徑類型 | P0 / 例外＋狀態轉移 |
| 事實結論 | 五種 fixture 的分支在 service 層皆有對應原始碼：同決定回放（`idempotent_replay`）、相反終態 409 `QUOTE_ALREADY_DECIDED`、過期 409 `QUOTE_EXPIRED`（含首擊收斂）、查無 404、非本人 403；LINE gateway 側的話術分流離線測試 8 項全過。但以本機測試庫實跑時，取現況 state 的 `quote_engine_service.py:785-788` 拋 `TypeError: 'coroutine' object is not subscriptable`，該行位於 404／403 之後、其餘三條分支之前，對應三項測試失敗、同檔其餘 9 項通過。 |

**TC 原文**｜前置：customer_sent、已同意、已拒絕、已過期與不存在/無權報價 fixture｜步驟：先送同決定重播，再送相反決定、過期、404、403 與非 JSON 錯誤｜判定基準：同決定安全回放；相反終態 409 QUOTE_ALREADY_DECIDED、過期 409 QUOTE_EXPIRED；LINE 依 error_code 顯示精確話術，未知格式走友善 fallback｜例外＋狀態轉移｜P0｜FR-API-02｜SC-04

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | 重送同決定 | `IdempotentReplay(200)` | 已在對應終態即回放 | `quote_engine_service.py:789-791` | 回 `idempotent_replay: True` |
| 客戶 | 送相反決定 | `Rejected(409)` | 終態不可反轉 | `quote_engine_service.py:794-799` | 409 `QUOTE_ALREADY_DECIDED` + `details.current_state` |
| 客戶 | 對已 `expired` 報價回覆 | `Rejected(409)` | 過期不可回覆 | `quote_engine_service.py:800-801` | 409 `QUOTE_EXPIRED` |
| 客戶 | 對逾期但仍 `sent` 的報價首擊 | `QuoteExpired` + `Rejected(409)` | 首擊收斂同碼 | `quote_engine_service.py:803-809` | 攔 `STATE_CONFLICT`/"expired" → 改 `QUOTE_EXPIRED` |
| 客戶 | 回覆不存在報價 | `Rejected(404)` | 查無即拒 | `quote_engine_service.py:775-777` | 404 `NOT_FOUND` |
| 他人 | 回覆非本人報價 | `Rejected(403)` | 歸屬驗證 | `quote_engine_service.py:778-781` | 403 `FORBIDDEN`，不洩歸屬細節 |
| Gateway | 依 error_code 回話術 | `ReplySelected` | 精確分流 | `line_gateway.py:864-869` | 查 `_QUOTE_FAIL_MSGS` / `_QUOTE_DECIDED_MSGS` |
| Gateway | body 非 JSON | `FallbackReplySelected` | 友善 fallback | `line_gateway.py:910-912` | `err_body = {}` → fallback 句 |

> 上表「程式碼實際行為」為靜態閱讀所得。實跑補充：第 1、2、3、4 列（`quote_engine_service.py:789` 之後的分支）在本機測試庫下未被執行到——請求先在 `:785-788` 拋 `TypeError`（見步驟 7）；第 5、6 列（404／403）位於該行之前。

---

## 走查紀錄

### 步驟 1 — 歸屬驗證（404 / 403 fixture）

- **動作**：讀 `customer_respond_to_quote` 前半
- **預期**：不存在 404、無權 403
- **實際**：一致

`api/services/quote_engine_service.py:773-781`

```python
    if decision not in {"accept", "reject"}:
        raise ApiError("VALIDATION_ERROR", "decision must be 'accept' or 'reject'", 422)
    owner = await resolve_customer_line_uid(tenant_id=tenant_id, quote_id=quote_id)
    if owner is None:
        raise ApiError("NOT_FOUND", "quote not found", 404)
    if owner != line_user_id:
        # 不洩露歸屬細節，但 log 供稽核
        logger.warning("quote %s respond denied: line_user mismatch", quote_id)
        raise ApiError("FORBIDDEN", "this LINE user does not own the quote", 403)
```

### 步驟 2 — 同決定重播

- **動作**：讀冪等分支
- **預期**：安全回放，不 409
- **實際**：一致

`api/services/quote_engine_service.py:782-791`

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

### 步驟 3 — 相反終態與過期

- **動作**：讀衝突碼分支
- **預期**：409 `QUOTE_ALREADY_DECIDED` 與 409 `QUOTE_EXPIRED`
- **實際**：一致，且過期有兩條進入路徑

`api/services/quote_engine_service.py:792-809`

```python
    # CR-0178 UAT-0720-12 尾巴：語意化衝突碼（供 gateway 話術分流，不再一句
    # 「報價或已失效」誤導）。transition() 本體不動（其他呼叫端不受影響）。
    _opposite = {"accept": "rejected", "reject": "accepted"}
    if cur_state == _opposite[decision]:
        raise ApiError(
            "QUOTE_ALREADY_DECIDED", f"quote already {cur_state}", 409,
            details=[{"current_state": cur_state}],
        )
    if cur_state == "expired":
        raise ApiError("QUOTE_EXPIRED", "quote expired", 409)
    action = "accept" if decision == "accept" else "decline"
    try:
        result = await transition(tenant_id=tenant_id, quote_id=quote_id, action=action)
    except ApiError as e:
        # 真過期首擊（transition 內先改 state='expired' 再 raise STATE_CONFLICT）→ 收斂同碼
        if e.error_code == "STATE_CONFLICT" and "expired" in e.message:
            raise ApiError("QUOTE_EXPIRED", "quote expired", 409) from e
        raise
```

首擊來源：

`api/services/quote_engine_service.py:562-566`

```python
    if action == "accept":
        exp = await (await conn.execute("SELECT expiry_at FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
        if exp[0] and exp[0] < datetime.now(timezone.utc):
            await conn.execute("UPDATE quote SET state = 'expired', updated_at = NOW() WHERE id = %s::uuid", (quote_id,))
            raise ApiError("STATE_CONFLICT", "quote expired", 409)
```

`decision="reject"` 對逾期但仍 `sent` 的報價，走的是 `decline`（`_TRANSITIONS` 於 `:36`），`transition` 的過期檢查僅套用於 `action == "accept"`（`:562`），故 reject 首擊會成功轉為 `rejected`。

### 步驟 4 — 錯誤 body 的 `error_code` 形狀

- **動作**：確認 gateway 讀得到 `error_code`
- **預期**：扁平欄位
- **實際**：一致，RFC7807 superset 保留 legacy 扁平欄位

`api/core/errors.py:1-18`

```python
"""統一錯誤格式 — RFC7807 problem+json superset。

Response body = RFC7807 fields + legacy extension members（零破壞）:
{
  // RFC7807 fields
  "type":     "urn:smartlock:error:validation_error",
  ...
  // Legacy extension members (RFC7807 §3.2 allows — backward-compat)
  "error_code": "VALIDATION_ERROR",
```

### 步驟 5 — LINE 話術分流

- **動作**：讀 gateway 的話術表與選擇函式
- **預期**：依 error_code 精確話術；未知走 fallback
- **實際**：一致

`agent/lockcore/channels/line_gateway.py:837-869`

```python
_QUOTE_FAIL_FALLBACK = "您的回覆可能未送達（報價或已失效），請稍後再試或洽客服 🙏"
_QUOTE_FAIL_MSGS: dict[str, str] = {
    "QUOTE_EXPIRED": (
        "這份報價單已超過有效期限，無法直接回覆同意/拒絕 🙏 "
        "如仍需服務，請直接留言，客服將為您重新確認報價。"
    ),
    "NOT_FOUND": (...),
    "FORBIDDEN": "這份報價無法由此帳號回覆，若有疑問請直接留言洽客服 🙏",
}
# 相反終態（先同意後拒絕/先拒絕後同意）依客戶這次按的方向給話術
_QUOTE_DECIDED_MSGS: dict[str, str] = {
    "reject": (...),
    "accept": (...),
}


def _quote_fail_reply(status_code: int, body: dict, decision: str) -> str:
    """依 api 錯誤 body 的扁平 error_code 選話術；未知 → fallback。"""
    code = str(body.get("error_code") or "").upper()
    if code == "QUOTE_ALREADY_DECIDED":
        return _QUOTE_DECIDED_MSGS.get(decision, _QUOTE_FAIL_FALLBACK)
    return _QUOTE_FAIL_MSGS.get(code, _QUOTE_FAIL_FALLBACK)
```

非 JSON body 的處理：

`agent/lockcore/channels/line_gateway.py:904-915`

```python
        if resp.status_code >= 400:
            logger.warning("報價回覆轉發回 {}:{}", resp.status_code, resp.text[:160])
            try:
                err_body = resp.json()
                if not isinstance(err_body, dict):
                    err_body = {}
            except Exception:  # noqa: BLE001 — body 非 JSON（proxy 5xx/HTML）→ fallback
                err_body = {}
            return _quote_fail_reply(resp.status_code, err_body, decision)
    except Exception:  # noqa: BLE001 — 轉發絕不可影響客人
        logger.warning("報價回覆轉發失敗（已略過）", exc_info=True)
        return "系統忙線中，請稍後再試或洽客服 🙏"
```

### 步驟 6 — 執行 agent 側測試（離線可跑）

- **動作**：跑話術分流測試
- **預期**：全數通過
- **實際**：8 項全過

```
cd agent && python -m pytest tests/test_quote_postback_msgs.py -q -rs
........                                                                 [100%]
8 passed in 0.10s
```

該檔覆蓋：`QUOTE_EXPIRED` 話術、`QUOTE_ALREADY_DECIDED` 依方向分流、`NOT_FOUND`／`FORBIDDEN`、未知 code fallback、空 body fallback、以及 stub httpx 的整合路徑（含 502 HTML body → fallback）與成功路徑不變（`agent/tests/test_quote_postback_msgs.py:24-127`）。

### 步驟 7 — 執行 API 側測試

- **動作**：跑衝突碼測試
- **預期**：取得執行證據
- **實際**：第一輪無資料庫全數失敗；建立本機測試庫後重跑，衝突碼測試仍失敗，失敗原因由環境改為程式執行時錯誤

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

三項失敗都停在 `quote_engine_service.py:785-788`：

```python
    cur_state = ((await (await _conn()).execute(
        "SELECT state FROM quote WHERE id = %s::uuid "
        "AND (tenant_id = %s::uuid OR tenant_id IS NULL)",
        (quote_id, tenant_id))).fetchone() or [None])[0]
```

`await` 的作用範圍到 `.execute(...)` 為止，`.fetchone()` 未被 await。同檔其他讀取點寫法為 `await (await conn.execute(...)).fetchone()`（例：`:295`、`:345`、`:397`），`await` 在最外層。

位置關係：此段在 `customer_respond_to_quote` 中位於歸屬驗證（`:775-781`，即 404／403 兩條分支）之後，位於同決定回放（`:789-791`）、`QUOTE_ALREADY_DECIDED`（`:794-799`）、`QUOTE_EXPIRED`（`:800-809`）三條分支之前。

該測試對本 TC 的三條分支有直接斷言（實跑未到達斷言即拋錯）：

`api/tests/test_cr_0095_quote_line_approval.py:287-303`

```python
        assert ei.value.error_code == "QUOTE_ALREADY_DECIDED"
        assert ei.value.status_code == 409
...
        assert ei2.value.error_code == "QUOTE_EXPIRED"
        # 二擊（state 已被改為 expired）→ 前置檢查同碼
        with pytest.raises(ApiError) as ei3:
            await quote_engine_service.customer_respond_to_quote(
                tenant_id=TID, quote_id=qid2, line_user_id=owner_line, decision="accept")
        assert ei3.value.error_code == "QUOTE_EXPIRED"
```

---

## 觀測到的其他事實

- 上述分支只作用於 `customer_respond_to_quote`（LINE postback / internal 端點）。走 public token 的 `/consumer/quotes/{token}` POST 直呼 `transition`（`api/routers/consumer_v2.py:326-328`），因此重送同決定回 409 `STATE_CONFLICT`、過期回 409 `STATE_CONFLICT`，不會出現 `QUOTE_ALREADY_DECIDED` / `QUOTE_EXPIRED` 兩碼。
- bridge 未配置（`LOCK_API_BASE_URL` 或憑證缺）時，gateway 直接回「系統忙線中」而不發請求（`agent/lockcore/channels/line_gateway.py:887-894`）。
- 非 `q:a` / `q:r` 前綴的 postback 回 `None` 交由其他 handler（`line_gateway.py:879-885`）。
- `_quote_fail_reply` 只讀 body 的 `error_code`，不讀 `status_code`（參數存在但函式體未使用，`line_gateway.py:864-869`）。
