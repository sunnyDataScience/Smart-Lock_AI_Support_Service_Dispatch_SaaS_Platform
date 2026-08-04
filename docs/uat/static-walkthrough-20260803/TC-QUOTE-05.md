# TC-QUOTE-05 — 報價逾期的 cron 過期與舊連結處置

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **不一致** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 7） |
| 走查時間 | 2026-08-03 18:16（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/realtime/job_registry.py:83-256`、`api/realtime/sla_monitor.py:52`、`:126-155`、`api/services/quote_engine_service.py:44-60`、`:561-566`、`:704-741`、`api/routers/consumer_v2.py:270-329`、`web/brand-portal/src/app/quotes/[token]/page.tsx:73-79` |
| 優先級 / 路徑類型 | P1 / timeout |
| 事實結論 | 沒有把報價改為 `expired` 的排程作業；job registry 14 個 job 中無報價過期 job，`sla-monitor` 只發告警不改狀態。過期是 lazy 判定——客戶按 accept 當下才寫 `expired`。audit action `expired_by_cron` 在全 repo **找不到**。舊連結不回 410，回 200 帶狀態或 404（token 本身逾期）。有效期為 7 天而非 48h。 |

**TC 原文**｜前置：quote customer_sent 超過 48h｜步驟：cron tick｜判定基準：quote expired + audit expired_by_cron；客戶點舊連結 → 410 引導重新報修｜timeout｜P1｜FR-API-02、FR-API-03、FR-WEB-06｜SC-04

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| Cron | tick | `QuoteExpired` | 逾期自動過期 | — | **找不到**報價過期 job |
| Cron | tick | `AuditLogged(expired_by_cron)` | 留稽核軌跡 | — | **找不到** `expired_by_cron` |
| SLA monitor | 60s 掃描 | `QuoteExpiringAlert` | 送出逾 1440 分鐘告警 | `sla_monitor.py:52`、`:126-155` | 只 append alert，不改 quote.state |
| 客戶 | 逾期後按同意 | `QuoteExpired` + `Rejected(409)` | 過期不可接受 | `quote_engine_service.py:562-566` | lazy 寫 `expired` 後 raise 409 |
| 客戶 | 開舊連結 | `Rejected(410)` | 引導重新報修 | `routers/consumer_v2.py:270-294` | token 有效 → 200 帶 state；token 逾期 → 404 |

---

## 走查紀錄

### 步驟 1 — 是否存在報價過期 cron

- **動作**：讀 job registry 全表
- **預期**：有報價過期 job
- **實際**：**找不到**

`api/realtime/job_registry.py:83-256` 定義的 `JOB_SPECS` 共 14 個 job：`inventory-monitor`、`sla-monitor`、`line-push-outbox`、`commission-outbox`、`reconciliation-exception-detector`、`dispute-escalation`、`config-canary-advance`、`statement-auto-approval`、`statement-generate`、`gdpr-hard-delete`、`media-retention`、`auto-confirm`、`webhook-idempotency-cleanup`、`family-review-sla`。其中與報價相關者僅 `sla-monitor`：

`api/realtime/job_registry.py:96-107`

```python
    _job(
        "sla-monitor",
        "realtime.sla_monitor:monitor",
        kind="continuous",
        schedule="every 60s",
        scope="brand work-order/quote SLA",
        idempotency="alert_type + target_id in active runtime",
        timeout=55,
        retry="next poll",
        compensation="re-run scan and inspect notification audit",
        run_once="_scan_once",
    ),
```

### 步驟 2 — `sla-monitor` 對逾期報價做什麼

- **動作**：讀 `quote_expiring` 分支
- **預期**：把 quote 改為 expired
- **實際**：只產生告警，不改狀態

`api/realtime/sla_monitor.py:133-155`

```python
        cur = await db_module._conn.execute(
            "SELECT q.id, q.work_order_id "
            "FROM quote q "
            "LEFT JOIN work_orders wo ON wo.id = q.work_order_id "
            "WHERE q.state = 'sent' "
            "  AND q.total_amount IS NOT NULL "
            "  AND q.audit_due_at IS NULL "
            "  AND (q.work_order_id IS NULL OR wo.status = 'created') "
            "  AND q.updated_at < NOW() - (INTERVAL '1 minute' * %s)",
            (QUOTE_EXPIRING_MINUTES,),
        )
        for r in await cur.fetchall():
            target_id = str(r[0])
            key = ("quote_expiring", target_id)
            active_keys.add(key)
            if key not in self._alerted:
                new_alerts.append(
                    {
                        "alert_type": "quote_expiring",
```

門檻常數：

`api/realtime/sla_monitor.py:52`

```python
QUOTE_EXPIRING_MINUTES = int(os.environ.get("SLA_QUOTE_EXPIRING_MINUTES", "1440"))
```

1440 分鐘 = 24 小時，與 TC 的 48h 不同；且此為告警門檻，非過期門檻。

### 步驟 3 — 實際的過期寫入點

- **動作**：搜 `state = 'expired'` 的寫入
- **預期**：cron 寫入
- **實際**：唯一寫入點在客戶 accept 當下（lazy）

`api/services/quote_engine_service.py:561-566`

```python
    # 過期檢查：sent 後逾 expiry 不可 accept
    if action == "accept":
        exp = await (await conn.execute("SELECT expiry_at FROM quote WHERE id = %s::uuid", (quote_id,))).fetchone()
        if exp[0] and exp[0] < datetime.now(timezone.utc):
            await conn.execute("UPDATE quote SET state = 'expired', updated_at = NOW() WHERE id = %s::uuid", (quote_id,))
            raise ApiError("STATE_CONFLICT", "quote expired", 409)
```

即無人點擊的逾期報價會永遠停留在 `sent`。

### 步驟 4 — audit `expired_by_cron`

- **動作**：全 repo 搜字串
- **預期**：cron 過期時寫此 audit action
- **實際**：**找不到**任何程式碼實作

```
grep -rn "expired_by_cron" --include=*.py --include=*.sql --include=*.md .
smartlock-docs\enterprise\20_Test_Cases.md:281: | TC-QUOTE-05 | FR-0042 | quote `customer_sent` 超過 48h | cron tick | quote `expired` + audit `expired_by_cron`...
```

唯二命中皆在測試案例文件本身。另，`api/services/quote_engine_service.py` 全檔**找不到** `audit_log_service` 的 import 或 `log_event` 呼叫——報價狀態機無任何 audit 寫入。

### 步驟 5 — 舊連結的回應

- **動作**：追客戶端 GET 與 POST 的錯誤碼
- **預期**：410 引導重新報修
- **實際**：**找不到** 410；為 200／404／409 三種

token 驗證失敗統一 404：

`api/routers/consumer_v2.py:248-267`

```python
def _verify_quote_token(token: str):
    """驗 quote_view 用途 token；失敗一律 404 不洩露原因。"""
    try:
        payload = verify_token(token)
    except (TokenInvalidError, TokenExpiredError) as exc:
        logger.info("quote_view token verify failed: %s", exc)
        raise ApiError("NOT_FOUND", "token invalid or expired", 404)
```

token 未逾期時，GET 正常回 200 並帶 `state`（`consumer_v2.py:283-294`）；POST 則由狀態機擋（`quote_engine_service.py:566` 的 409 `STATE_CONFLICT`，或 `:800-808` 收斂為 409 `QUOTE_EXPIRED`）。

全 repo 搜 `410` 於 `api/routers/` 與 `api/services/`：僅三處，皆與報價無關——`services/line_binding_service.py:140`、`services/voucher_void_service.py:140`、`services/work_order_service.py:4122`。

前端有 410 的處理分支，但後端不會產生：

`web/brand-portal/src/app/quotes/[token]/page.tsx:73-79`

```tsx
      if (res.status === 410) return setState({ kind: "error", code: "expired", message: t("errors.expired") });
      if (res.status === 429) return setState({ kind: "error", code: "rate_limit", message: t("errors.rateLimit") });
      // 其餘 4xx（400/404/422 等：token 格式不符 / 不存在）一律視為「連結無效或已過期」，
      // 避免把使用者導向「稍後再試」的暫時性錯誤誤導（UAT W2-5）
      if (res.status >= 400 && res.status < 500)
        return setState({ kind: "error", code: "not_found", message: t("errors.notFound") });
```

此處僅並陳，不裁定。

### 步驟 6 — 48h 的時間常數

- **動作**：找 48h / 172800 的設定
- **預期**：有效期 48h
- **實際**：有效期 7 天；token TTL 上限亦 7 天；程式碼註解自述已修訂 48h

`api/services/quote_engine_service.py:44-46`

```python
# 有效期：一般/急件統一 7d（CR-0181 業主裁決，取代 BR-M04-05 的 14d/3d；config fallback 預設）
_VALIDITY_DAYS_NORMAL = 7
_VALIDITY_DAYS_URGENT = 7
```

`api/services/quote_engine_service.py:704-706`

```python
# confirm_token TTL 上限 7 天（CR-0181 業主裁決，取代 FR-API-02 原 48h）——客戶常隔數日
# 才回應，48h 連結先死造成流程卡住。仍不超過報價有效期（取兩者較小）。
_CONFIRM_TOKEN_MAX_DAYS = 7
```

實值可由 M18 config `quote_validity_policy` 覆蓋（`:49-60`）。全 repo 於報價路徑搜 `172800`：**找不到**。

此處僅並陳，不裁定。

### 步驟 7 — 執行既有測試

- **動作**：跑報價過期相關測試
- **預期**：取得執行證據
- **實際**：第一輪無資料庫全數失敗；建立本機測試庫後重跑，唯一覆蓋「客戶點擊時過期收斂」的 `test_customer_respond_conflict_codes` 仍失敗，失敗原因由環境改為程式執行時錯誤

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_pc_convert_to_wo.py tests/test_cr_0095_quote_line_approval.py tests/test_cr_0144_requote_channel.py -q --tb=no -rf
FAILED tests/test_cr_0095_quote_line_approval.py::test_customer_respond_conflict_codes
...
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

同檔其餘 9 項通過。三項失敗（含本 TC 引用的 `test_customer_respond_conflict_codes`，`api/tests/test_cr_0095_quote_line_approval.py:290-303`）都停在 `customer_respond_to_quote` 讀取現況狀態的 `quote_engine_service.py:785`，未進入該測試對 `expired` 收斂的斷言。此處僅陳述實跑觀測，不裁定。

走查**未找到**任何 cron 過期測試，第二輪亦無此類案例被執行。

---

## 觀測到的其他事實

- `_ttl_days_from`（`quote_engine_service.py:709-719`）對已過期報價仍給最小 1 天 token，註解說明為「供唯讀查看」。
- `mint_view_token` 允許 `expired` 狀態鑄 token（`quote_engine_service.py:735`）。
- `sla_monitor` 的告警去重靠 in-process `self._alerted` 集合（`sla_monitor.py:62`、`:146-150`），程序重啟後會重發。
