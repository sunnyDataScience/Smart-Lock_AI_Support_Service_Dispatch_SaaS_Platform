# TC-PAYMENT-01 — 支付拒絕／timeout 重送／已收款後 dispute

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；正式機金流環境不可用，本批不做執行期驗證。後續以本機 Docker 測試庫實跑既有測試，`test_cr_0070_payment_mock.py` 全數通過（見步驟 6） |
| 走查時間 | 2026-08-03（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/payment_service.py:1-215`、`SQL/migrations/069-payments-mock.sql:1-40`、`api/tests/test_cr_0070_payment_mock.py:1-162`、`api/services/voucher_service.py:1-40`、`api/services/dispute_v2_service.py:220-266`、`smartlock-docs/enterprise/04_SRS.md:301` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | 支付骨架存在且明示為 mock（`payments.is_mock DEFAULT true`，正式 provider 串接標為下輪）。可靜態確認的三件事：①webhook 先驗 HMAC 簽章，失敗 401 且**不寫任何 payment 狀態**；②同 `provider_txn_id` 重送直接回既有列不再 confirm，DB 端另有 `uq_payments_provider_txn` 唯一索引，故「至多一筆收款」在資料層被釘住；③`create_payment_intent` 以 `(tenant_id, idempotency_key)` 去重。**找不到**的三件事：provider **拒絕**的處理分支（`handle_linepay_webhook` 不解析任何成功／失敗欄位，驗簽通過即 confirm）；「憑證」與 payment 的關聯（`voucher_service` 與 `payments` 表零關聯）；以及整個 `payment_service` 的 HTTP 入口——全 repo 除自身與其測試外**零引用**，`api/routers/` 中沒有任何端點呼叫它。dispute 側只有現金金額不符一種（`dispute_type='cash_amount_mismatch'`，寫 legacy `disputes` 表），該路徑不觸發任何扣款或退款動作。判定基準中「provider 實際回應」「對帳結果」屬執行期事實，靜態無法觀測。 |

**TC 原文**｜前置：支付 provider webhook stub、可控 idempotency key 與 dispute fixture｜步驟：分別送 provider 拒絕、timeout 後相同 key 重送、已收款後 dispute｜判定基準：拒絕/timeout 不落成功帳；重送至多一筆收款與憑證；dispute 建立可稽核例外且不以重複扣款恢復｜需求：FR-API-10｜旅程：SC-08

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| provider | webhook 送拒絕 | `PaymentFailed` | 不落成功帳 | `services/payment_service.py:116-134` | **找不到**拒絕分支；驗簽通過即 `confirm_payment` |
| provider | webhook 簽章錯 | `Rejected(401)` | fail-closed | `services/payment_service.py:121-122` | 401 `SIGNATURE_INVALID`，不寫狀態 |
| 客戶端 | timeout 後同 key 重送 intent | `IdempotentReplay` | 同 key 不重建 | `services/payment_service.py:69-78` | 回既有列，`deduplicated=True` |
| provider | 同 txn 重送 webhook | `DuplicateWebhookIgnored` | 至多一筆收款 | `services/payment_service.py:125-130` + `SQL/migrations/069-payments-mock.sql:28` | 回既有列 + DB 唯一索引 |
| 系統 | 開立憑證 | `VoucherIssued` | 一筆收款一張憑證 | — | **找不到** payment → voucher 的程式碼 |
| 客服 | 已收款後開 dispute | `PaymentDisputed` | 可稽核例外 | `services/payment_service.py:167-195` | 寫 `disputes` 表；差額 ≥ 門檻才標 payment `disputed` |
| 系統 | 回復方式 | 不重複扣款 | 不以重複扣款恢復 | `services/payment_service.py:191-195` | 該函式只寫 dispute 與狀態，無扣款/退款呼叫 |

---

## 走查紀錄

### 步驟 1 — 支付子系統的定位與接線狀況

- **動作**：查 `payment_service` 的所有引用者
- **預期**：有 API 端點可觸發
- **實際**：除自身與其測試外零引用

```
git grep -n "payment_service" -- api
api/services/payment_service.py:27:logger = logging.getLogger("api.payment_service")
api/tests/test_cr_0070_payment_mock.py:10:from services import payment_service as ps
```

```
git grep -n "payments" -- api/routers
（無輸出）
```

模組 docstring 記載其定位（`api/services/payment_service.py:1-13`）：

```python
"""金流 payment service（CR-0070 / TI-FIN-PAY-01~05；mock-first 骨架）。

會議決議 5 授權 mock-first：本服務落地三軌支付的 intent/confirm/webhook 冪等/
fallback audit/現金爭議與 payment gate 語意，所有 payment 標 is_mock；正式 provider
（真 Line Pay / Apple Pay 簽章金鑰串接）由 Sunny 下輪（決議 6）替換，DB schema 不變。
```

DDL 同樣標註（`SQL/migrations/069-payments-mock.sql:20`、`:31`）：

```sql
    is_mock          BOOLEAN NOT NULL DEFAULT true,
...
COMMENT ON TABLE payments IS 'CR-0070/TI-FIN-PAY mock 金流骨架（is_mock；正式 provider 串接 Sunny 下輪）';
```

- TC 前置：「支付 provider webhook stub」
- 程式碼：webhook 處理函式存在於 service 層（`payment_service.py:116`），但沒有對應的 HTTP 端點；`api/routers/` 中的 webhook 端點只有 `line_webhook.py:223` 與 `technician_line.py:122`，兩者皆為 LINE 訊息通道，不處理支付

此處僅並陳，不裁定。

### 步驟 2 — provider 拒絕

- **動作**：讀 webhook 處理全文，找失敗分支
- **預期**：拒絕不落成功帳
- **實際**：函式不解析任何結果欄位，驗簽通過即 confirm

`api/services/payment_service.py:116-134`

```python
async def handle_linepay_webhook(
    *, payload: str, signature: str, provider_txn_id: str, intent_id: str,
    tenant_id: str, secret: str = _MOCK_LINEPAY_SECRET,
) -> dict:
    """PAY-03：Line Pay webhook —— 驗簽 + provider_txn_id 冪等（重複 webhook 不重複認款）。"""
    if not _verify_linepay_signature(payload, signature, secret):
        raise ApiError("SIGNATURE_INVALID", "Line Pay webhook signature invalid", 401)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    # 冪等：同 provider_txn_id 已認過 → 直接回既有（不重複 confirm）
    cur = await db_module._conn.execute(
        "SELECT id, status FROM payments WHERE provider_txn_id = %s", (provider_txn_id,))
    ex = await cur.fetchone()
    if ex:
        return {"id": str(ex[0]), "status": ex[1], "duplicate_webhook": True}
    out = await confirm_payment(tenant_id=tenant_id, intent_id=intent_id,
                                provider_txn_id=provider_txn_id)
    out["duplicate_webhook"] = False
    return out
```

`payload` 只作為簽章計算的輸入（`:121`），內容未被解析。函式簽章中沒有 `status` / `result` / `return_code` 之類的參數。

`failed` 狀態的唯一寫入點在 fallback 路徑（`:154-155`）：

```python
    await db_module._conn.execute(
        "UPDATE payments SET status='failed', updated_at=NOW() WHERE id=%s::uuid", (str(row[0]),))
```

即「標記失敗」由呼叫端顯式呼叫 `record_payment_fallback` 觸發，不是由 provider 回應驅動。

`confirm_payment` 對非 `pending` 狀態拒絕推進（`:105-108`）：

```python
    if status == "confirmed":
        return {"id": pid, "intent_id": intent_id, "status": "confirmed", "deduplicated": True}
    if status not in ("pending",):
        raise ApiError("STATE_CONFLICT", f"cannot confirm payment in status '{status}'", 409)
```

故已標 `failed` / `disputed` 的 payment 不會被後續 confirm 推回成功。

### 步驟 3 — timeout 後相同 key 重送

- **動作**：讀 intent 冪等與唯一索引
- **預期**：至多一筆收款
- **實際**：service 層去重 + DB 兩條唯一索引

`api/services/payment_service.py:69-78`

```python
    # 冪等：同 key 已有 → 回既有
    if idempotency_key:
        cur = await db_module._conn.execute(
            "SELECT id, intent_id, status, method, amount FROM payments "
            "WHERE tenant_id = %s::uuid AND idempotency_key = %s",
            (tenant_id, idempotency_key))
        ex = await cur.fetchone()
        if ex:
            return {"id": str(ex[0]), "intent_id": ex[1], "status": ex[2], "method": ex[3],
                    "amount": float(ex[4]), "deduplicated": True}
```

`SQL/migrations/069-payments-mock.sql:26-29`

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_idempotency
    ON payments (tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_provider_txn
    ON payments (provider_txn_id) WHERE provider_txn_id IS NOT NULL;
```

註記於 `:6`：「payments 表 + 唯一鍵（idempotency_key 防重複 intent；provider_txn_id 防重複 webhook）」。

「憑證」側：`api/services/voucher_service.py:1-11` 的範圍為 `listVouchers` + `exportVoucher(PDF)`，租戶隔離走 `vouchers.tenant_id`；

```
git grep -n "voucher" -- api/services/payment_service.py
（無輸出）
```

`payments` 與 `vouchers` 兩表之間在 `api/` 中無 JOIN 或外鍵關聯。

- TC 判定基準：「重送至多一筆收款與憑證」
- 程式碼：「至多一筆收款」由唯一索引與 service 去重承載；「憑證」在支付路徑中找不到對應開立動作

此處僅並陳，不裁定。

### 步驟 4 — 已收款後的 dispute

- **動作**：讀 `report_cash_dispute`
- **預期**：可稽核例外，且不以重複扣款恢復
- **實際**：寫 `disputes` 表；不含任何扣款/退款呼叫；限現金金額不符一種

`api/services/payment_service.py:167-195`

```python
async def report_cash_dispute(
    *, tenant_id: str, payment_id: str, filed_by: str, reported_amount: float,
    reason: str, threshold: float = _CASH_DISPUTE_THRESHOLD_DEFAULT,
) -> dict:
    """PAY-05：現金金額不符 → disputes 表。差額 ≥ 門檻 → flag + payment 標 disputed。"""
...
    expected = float(row[0]); wo_id = row[1]
    delta = abs(expected - float(reported_amount))
    flagged = delta >= threshold
    dcur = await db_module._conn.execute(
        "INSERT INTO disputes (work_order_id, filed_by, dispute_type, status, description, "
        "  evidence, sla_deadline) "
        "VALUES (%s, %s::uuid, 'cash_amount_mismatch', 'open', %s, %s::jsonb, NOW()+INTERVAL '24 hours') "
        "RETURNING id",
        (wo_id, filed_by, reason,
         f'{{"expected": {expected}, "reported": {reported_amount}, "delta": {delta}}}'))
    did = str((await dcur.fetchone())[0])
    if flagged:
        await db_module._conn.execute(
            "UPDATE payments SET status='disputed', updated_at=NOW() WHERE id=%s::uuid", (payment_id,))
```

門檻常數 `_CASH_DISPUTE_THRESHOLD_DEFAULT = 500.0`（`:34`），註解記「正式可移入 M18 config」。差額 < 門檻時**不**改 payment 狀態，只建 dispute 列。

該函式寫入的是 legacy `disputes` 表，與 TC-SETTLE-06 的 `saas.dispute` 雙簽流程（`services/dispute_v2_service.py:220-266`）為兩張不同的表、兩套狀態機。

稽核：`payment_service.py` 全檔搜 `audit_log_service`：**零命中**；`audit` 三處出現皆為 docstring 文字（`:4`、`:11`、`:141`）。fallback 的「兩次嘗試 audit」實際落在 `payments` 表的 `attempt_count = 2` 與 `fallback_from` 欄（`:157-161`）。

### 步驟 5 — 需要執行期才能觀測的部分

- **動作**：對照 TC 判定基準，標出靜態不可判定的項目
- **預期**：區分靜態可查與否
- **實際**：以下三項需執行期事實

| TC 判定基準片段 | 靜態可查部分 | 需執行期的部分 |
|---|---|---|
| 「拒絕/timeout 不落成功帳」 | webhook 無拒絕分支、驗簽失敗 401 不寫狀態、`confirm_payment` 對非 pending 拒絕 | 真實 provider 拒絕回應的內容與 timeout 行為 |
| 「重送至多一筆收款與憑證」 | 唯一索引 + service 去重；憑證無關聯 | 併發重送時的實際落庫筆數 |
| 「dispute 不以重複扣款恢復」 | `report_cash_dispute` 無扣款/退款呼叫 | 對帳結果與實際金流帳務 |

正式機金流環境不可用，本批不執行任何上述執行期驗證。

### 步驟 6 — 執行既有測試

- **動作**：跑支付 mock 測試
- **預期**：取得執行證據
- **實際**：通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_disputes_v2.py \
  tests/test_dispute_negative_resolution.py tests/test_cr_0070_payment_mock.py \
  -q -p winloop_plugin --tb=line

43 passed in 3.21s
```

`api/tests/test_cr_0070_payment_mock.py:66-84` 覆蓋壞簽章 401、正確簽章 confirmed、同 txn 重送 `duplicate_webhook=True`，並斷言只有一筆認款：

```python
        cnt = await db_module._conn.execute(
            "SELECT count(*) FROM payments WHERE provider_txn_id=%s", (txn,))
        assert (await cnt.fetchone())[0] == 1   # 只一筆認款
```

`:88-105` 覆蓋 fallback（原 intent 標 `failed`、新 intent `attempt_count=2`）；`:109-131` 覆蓋現金爭議門檻兩側；`:135-162` 覆蓋 payment gate 三態。

**無對應測試**：「provider 拒絕」與「timeout」情境在 `api/tests/` 中零命中（該檔的失敗情境只有壞簽章與 fallback 兩種）。

---

## 觀測到的其他事實

- `smartlock-docs/enterprise/04_SRS.md:301`（FR-API-10）記載輸出事件為「PaymentReceived/Failed/Disputed 事件；voucher 開立」。這三個事件名在 repo 中零命中：

  ```
  git grep -n "PaymentReceived\|PaymentFailed\|PaymentDisputed" -- api
  （無輸出）
  ```

- mock 簽章金鑰硬編於 service（`payment_service.py:31-32`）：

  ```python
  # mock 簽章金鑰（正式環境由 Secret Manager 注入 LINE_PAY_CHANNEL_SECRET 取代）
  _MOCK_LINEPAY_SECRET = "mock-linepay-secret"
  ```

  驗簽使用 `hmac.compare_digest`（`:47`）。
- `assert_payment_gate`（`payment_service.py:198-214`）由 M18 config namespace `payment_gate.require_payment_for_dispatch` 控制，預設不入 active config 即不擋（`SQL/migrations/069-payments-mock.sql:33-40`）；該函式同樣無任何呼叫端。
- `payments.status` 的值域註記為 `pending/confirmed/failed/disputed`（`SQL/migrations/069-payments-mock.sql:15`），無 `refunded` 或 `reversed`。
- `payments` 表無 `tenant_id` 外鍵與 `work_order_id` 外鍵約束（`SQL/migrations/069-payments-mock.sql:9-11` 僅宣告型別），測試中以任意 UUID 建列即可（`test_cr_0070_payment_mock.py:36-40`）。
