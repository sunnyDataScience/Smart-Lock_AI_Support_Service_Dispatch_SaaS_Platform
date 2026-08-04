# TC-WO-14 — 免責簽署連結的發送、重送、越權與 public token 三段同意

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，consent 相關三檔 18 項全數通過（見步驟 6） |
| 走查時間 | 2026-08-03 20:55（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/consent_service.py:55-181`、`api/routers/work_orders_v2.py:71-76`、`:327-372`、`api/routers/consumer_v2.py:64-78`、`:339-380`、`api/services/public_token.py:141-249`、`api/services/line_push_service.py:252-277`、`web/brand-portal/src/components/work-orders/DispatchOrderView.tsx:363-389`、`api/tests/test_cr_0180_consent_send_link.py`、`api/tests/test_cr_0033_consent.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 四項判定條件皆有對應實作：`send_sign_link` 推 LINE 並固定回傳 `public_path`（未綁 LINE 時 `channel='none'`、`notification_sent=False`，連結仍回傳供複製）；重送每次鑄新 token、皆指向同一工單且同意寫入為 `ON CONFLICT ... DO UPDATE` upsert；跨租戶由 `_cross_tenant_write`（403）與 `_assert_wo_in_tenant`（404）兩層擋，越權由 `_DISPATCH_ALLOWED_ROLES` 白名單（不含 technician / vendor）擋；事件留痕只寫 `token_hash_for_audit(token)`，完整 token 不落庫。 |

**TC 原文**｜前置：有/無 LINE 綁定工單、不同租戶與角色、既有 consent 狀態｜步驟：發送簽署連結、重送、跨租戶/越權，並以 public token 完成三段同意｜判定基準：合法操作推送 LINE 或回傳可複製連結；重送語意安全；跨租戶/越權拒絕；token 只存 hash 稽核且可正確 upsert 同意狀態｜⚠ 未標註｜P0｜FR-WEB-06｜SC-06

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 後台 | 按「發送簽署連結」 | `ConsentLinkSent` | 角色白名單 + 同租戶 | `routers/work_orders_v2.py:355-372` | `role_required(*_DISPATCH_ALLOWED_ROLES)` + `_cross_tenant_write` |
| 系統 | 鑄 token | `PublicTokenMinted` | HMAC 簽章、30 天 TTL | `consent_service.py:142-147` | `generate_token(wo_id, purpose="work_order_status", tenant_id=...)` |
| 系統 | 推 LINE | `LinePushAttempted` | 未綁 LINE 不視為失敗 | `line_push_service.py:265-277` | 無 `line_user_id` → `(False, "none")` |
| 系統 | 留痕 | `WorkOrderEventInserted` | 只存 hash | `consent_service.py:158-171` | `event_type='other'`，payload `kind='consent_link_sent'` + `token_hash` |
| 客戶 | GET/POST `/consumer/consents/{token}` | `ConsentsRecorded` | token purpose 須符 | `routers/consumer_v2.py:64-78`、`:355-380` | 不符 → 404；值非 bool → 422 |
| 系統 | 寫同意 | `ConsentUpserted` | UNIQUE(work_order_id, consent_type) | `consent_service.py:114-122` | `ON CONFLICT ... DO UPDATE` |
| 技師 / 他租戶 | 呼叫 send-link | `Forbidden / NotFound` | 白名單 + 租戶守衛 | `work_orders_v2.py:71-76`、`:153-159`、`consent_service.py:55-71` | 403 / 404 |

---

## 走查紀錄

### 步驟 1 — 發送簽署連結：LINE 推播與可複製連結

- **動作**：讀 `send_sign_link`
- **預期**：推 LINE；未綁定時回連結
- **實際**：一致，`public_path` 為無條件回傳

`api/services/consent_service.py:139-181`（節錄）

```python
    conn = await _conn()
    await _assert_wo_in_tenant(conn, work_order_id, tenant_id)

    token = public_token.generate_token(
        work_order_id, purpose="work_order_status", tenant_id=tenant_id,
    )
    # WEB_BASE_URL 同 line_flex/builders.py SSOT（部署 parity：CR-0180 §8-3 已烤入 api.sh）
    base = os.getenv("WEB_BASE_URL", "https://lock-ai-web.example.com")
    url = f"{base}/consent/{token}"
    text = (
        "【施工免責同意】您好，請於施工前點擊以下連結，"
        f"閱讀並勾選施工免責同意書：\n{url}\n（連結 30 天內有效）"
    )
    sent, channel = await line_push_service.push_to_work_order_customer(
        tenant_id=tenant_id, work_order_id=work_order_id, text=text,
        actor_user_id=actor_user_id,
    )
```

```python
    return {
        "notification_sent": sent,
        "channel": channel,
        # 照 quote mint_view_token 慣例回 path，前端以 origin 拼完整連結（LINE 失敗備援）
        "public_path": f"/consent/{token}",
    }
```

未綁 LINE 的分支：

`api/services/line_push_service.py:258-277`

```python
    """Convenience: resolve customer then push.

    Returns (notification_sent, channel) where:
      - channel='line' when push attempted (success or transient retry exhausted)
      - channel='none' when customer is not a LINE user (V1.0 拒收非 LINE)
    """
    line_user_id = await resolve_customer_line_user_id(
        tenant_id=tenant_id, work_order_id=work_order_id
    )
    if not line_user_id:
        return (False, "none")
```

前端把 `channel` 與 `public_path` 一併存入 state 供顯示／複製（`web/brand-portal/src/components/work-orders/DispatchOrderView.tsx:371-390`）：

```tsx
  const sendLink = useCallback(async () => {
    setSending(true);
    setSendError(null);
    try {
      const res = await api.post<{
        data: { notification_sent: boolean; channel: string; public_path: string };
      }>(
        tenantPath(`/work-orders/${encodeURIComponent(workOrderId)}/consents:send-link`),
        {},
      );
      setSendResult({
        channel: res.data.channel,
        publicPath: res.data.public_path,
      });
```

### 步驟 2 — 重送的語意

- **動作**：追重送時的 token 與同意狀態行為
- **預期**：重送不造成狀態損壞
- **實際**：每次鑄新 token（含隨機 nonce），舊 token 不撤銷；同意寫入為 upsert

`api/services/public_token.py:168-180`

```python
    expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)
    payload = {
        "sub": subject_id,
        "purpose": purpose,
        "exp": int(expires_at.timestamp()),
        "nonce": secrets.token_urlsafe(8),
        "tenant_id": tenant_id,
    }
```

端點註解明載設計意圖（`api/routers/work_orders_v2.py:361-365`）：

```python
    """派工單模組 4：後台按鈕主動推簽署連結（客戶未綁 LINE 時回連結供複製）。

    冪等防連點重推；token 為 stateless HMAC，重發產生並存有效 token
    （皆指向同一工單的 consent upsert，語意無害；稽核靠事件 token_hash）。
    """
```

同意寫入端為 upsert：

`api/services/consent_service.py:114-122`

```python
    for ctype, accepted in consents.items():
        await conn.execute(
            "INSERT INTO work_order_consents "
            "  (work_order_id, consent_type, accepted, accepted_at, text_version, ip_address) "
            "VALUES (%s::uuid, %s, %s, %s, %s, %s) "
            "ON CONFLICT (work_order_id, consent_type) DO UPDATE SET "
            "  accepted = EXCLUDED.accepted, accepted_at = EXCLUDED.accepted_at, "
            "  text_version = EXCLUDED.text_version, ip_address = EXCLUDED.ip_address",
            (work_order_id, ctype, bool(accepted), now if accepted else None, TEXT_VERSION, ip_address))
```

### 步驟 3 — 跨租戶與越權

- **動作**：列出所有守衛
- **預期**：兩者皆拒
- **實際**：三層

角色白名單（不含 technician / vendor / line_user）：

`api/routers/work_orders_v2.py:71-76`

```python
_DISPATCH_ALLOWED_ROLES = (
    "admin",
    "operations_manager",
    "dispatcher",
    "customer_service",
)
```

`api/routers/work_orders_v2.py:355-366`（節錄）

```python
async def send_work_order_consent_link_v2(
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required(*_DISPATCH_ALLOWED_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
```

```python
    _cross_tenant_write(user, tenantId)
```

`_cross_tenant_write` 回 403（`api/routers/work_orders_v2.py:153-159`）：

```python
def _cross_tenant_write(user: CurrentUser, tenant_id: str) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )
```

service 層再驗一次工單歸屬（404）：

`api/services/consent_service.py:55-71`

```python
async def _assert_wo_in_tenant(conn, work_order_id: str, tenant_id: str | None) -> None:
    """defense-in-depth：驗 work_order 屬該租戶（除 token HMAC 綁定外的 DB 層守門）。

    沿 work_orders→problem_cards→conversations→users.tenant_id JOIN 鏈（同 invoice_service）。
    tenant_id 為 None（舊 token 無 scope）→ 跳過（依賴 token 簽章）。
    """
    if not tenant_id:
        return
    row = await (await conn.execute(
        "SELECT 1 FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE wo.id = %s::uuid AND COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid",
        (work_order_id, tenant_id))).fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "work order not found", 404)
```

`_assert_wo_in_tenant` 同時被 `get_consents`（`:77`）、`record_consents`（`:112`）與 `send_sign_link`（`:140`）呼叫，即 token 攜帶的 `tenant_id` 也會與工單比對。

### 步驟 4 — token 只存 hash

- **動作**：讀留痕 payload 與 hash 函式
- **預期**：完整 token 不落庫
- **實際**：一致

`api/services/consent_service.py:156-171`

```python
    # 事件留痕（照 notify_delay pattern；event_type CHECK 未含專屬值 → 'other'+kind，
    # 免 migration；完整 token 禁落庫，只留 hash 供稽核比對）
    payload = {
        "kind": "consent_link_sent",
        "channel": channel,
        "notification_sent": sent,
        "token_hash": public_token.token_hash_for_audit(token),
    }
    # CR-0193：改走 work_order_service._insert_wo_event 唯一出口取 per-工單連號 seq。
    # 直接 INSERT 會因 seq NOT NULL 寫不進去（DB 端刻意的兜底）。
    from services.work_order_service import _insert_wo_event

    await _insert_wo_event(
        wo_id=work_order_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="other", payload=payload,
    )
```

`api/services/public_token.py:141-143`、`:247-249`

```python
def _token_hash(token: str) -> str:
    """Token 雜湊（供 audit log / 撤銷清單使用，不洩露原 token）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```

```python
def token_hash_for_audit(token: str) -> str:
    """供 audit log 使用的 token 雜湊（永遠不要寫完整 token）。"""
    return _token_hash(token)
```

### 步驟 5 — 以 public token 完成三段同意

- **動作**：讀消費者端兩個端點與 token 驗證
- **預期**：token 驗簽 + purpose 檢查 + 三段 upsert
- **實際**：一致

`api/routers/consumer_v2.py:64-78`

```python
def _verify_consumer_token(token: str):
    """驗證 consumer tracking token；失敗一律 404，不洩露原因。"""
    try:
        payload = verify_token(token)
    except (TokenInvalidError, TokenExpiredError) as exc:
        logger.info("consumer_v2 token verify failed: %s", exc)
        raise ApiError("NOT_FOUND", "token invalid or expired", 404)

    if payload.purpose != "work_order_status":
        logger.info(
            "consumer_v2 token purpose mismatch: got=%s expected=work_order_status",
            payload.purpose,
        )
        raise ApiError("NOT_FOUND", "token purpose mismatch", 404)
    return payload
```

`api/routers/consumer_v2.py:361-380`

```python
async def submit_consumer_consents(
    body: dict,
    request: Request,
    token: str = Path(..., min_length=32, max_length=512),
) -> dict:
    """客戶勾選同意三段免責 —— body: {"consents": {"new_installation": true, ...}}。"""
    from services import consent_service

    payload = _verify_consumer_token(token)
    consents = (body or {}).get("consents")
    if not isinstance(consents, dict) or not consents:
        raise ApiError("VALIDATION_ERROR", "consents map required", 422)
    # 嚴格 bool（防 JSON 字串/數字被 bool() 誤判為同意）
    if any(not isinstance(v, bool) for v in consents.values()):
        raise ApiError("VALIDATION_ERROR", "consent values must be boolean", 422)
    client_ip = request.client.host if request.client else None
    return await consent_service.record_consents(
        work_order_id=payload.subject_id, consents=consents, ip_address=client_ip,
        tenant_id=payload.tenant_id,
    )
```

三段的定義與未知 type 拒絕：`api/services/consent_service.py:26-46`（`new_installation` / `lock_destruction` / `personal_data`）與 `:104-106`：

```python
    unknown = set(consents) - _VALID_TYPES
    if unknown:
        raise ApiError("VALIDATION_ERROR", f"unknown consent_type: {sorted(unknown)}", 422)
```

驗簽使用常數時間比對（`api/services/public_token.py:200-202`）：

```python
    expected_sig = _sign(payload_bytes)
    if not hmac.compare_digest(expected_sig, sig_bytes):
        raise TokenInvalidError("signature mismatch")
```

### 步驟 6 — 執行既有測試

- **動作**：跑 consent 相關三檔（本機 Docker 測試庫）
- **預期**：取得執行證據
- **實際**：全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0180_consent_send_link.py \
  tests/test_cr_0033_consent.py tests/test_cr_0091_admin_consents.py -q -p winloop_plugin --tb=line
18 passed in 3.72s
```

其中對應 TC 各條件的斷言：

- 推播含連結、token 可驗且指回同一工單、事件只存 hash：`api/tests/test_cr_0180_consent_send_link.py:41-55`

```python
        # 推播文字含簽署連結，token 驗證後指回同一張工單
        text = mp.call_args.kwargs["text"]
        assert "/consent/" in text
        token = text.split("/consent/")[1].split("\n")[0].strip()
        payload = public_token.verify_token(token)
        assert payload.purpose == "work_order_status"
        assert payload.subject_id == woid
        # 事件留痕：other + kind，且不落完整 token（只有 hash）
        row = await (await db_module._conn.execute(
            "SELECT payload FROM work_order_events "
            "WHERE work_order_id = %s::uuid AND event_type = 'other' "
            "ORDER BY created_at DESC LIMIT 1", (woid,))).fetchone()
        assert row is not None
        assert row[0]["kind"] == "consent_link_sent"
        assert row[0]["token_hash"] and token not in str(row[0])
```

- 未綁 LINE 回 `public_path`：`:62-81`（`channel == "none"`、`public_path.startswith("/consent/")`）
- 跨租戶 404：`:84-96`
- upsert 冪等：`api/tests/test_cr_0033_consent.py:150-161`（重覆提交後 `COUNT(*) == 1`、值更新為 False）
- token purpose 不符 404：`api/tests/test_cr_0033_consent.py:62-65`

---

## 觀測到的其他事實

- `send_work_order_consent_link_v2` 掛有 `idempotency_guard` 但**未呼叫 `idem.save`**（`api/routers/work_orders_v2.py:359`、`:369-372`），佔位列在 dependency 的 `finally` 釋放（`api/core/idempotency.py:304-308`），故同 key 重送不會回放前次回應，每次都會鑄新 token。POST 缺 `Idempotency-Key` 時由 `_guard_impl` 回 400 `MISSING_IDEMPOTENCY_KEY`（`api/core/idempotency.py:198-206`）。
- `public_token` 的 secret 在 `PUBLIC_TOKEN_HMAC_SECRET` 未設時使用 process 啟動時隨機產生的金鑰並記 CRITICAL（`api/services/public_token.py:107-125`），該檔註解記載此行為依賴單 instance 部署。
- 撤銷清單為 process 內 in-memory set（`api/services/public_token.py:81`、`:231-244`，TODO 標示改 Redis）；重送舊 token 不會被撤銷。
- token TTL 預設 30 天（`public_token.py:154`），推播文案寫「（連結 30 天內有效）」（`consent_service.py:150`）。
- consent token 沿用 `purpose="work_order_status"`，同一 token 亦可查工單進度（`consent_service.py:133-134` 註解自述為 CR-0033 既定設計）。
- 消費者端兩個 endpoint 無登入守衛，身分完全由 token 承載；`api/core/resource_ownership.py:51` 的豁免 regex 亦涵蓋 `/consumer/` 前綴。
- 免責文本版本為 `blueprint-draft-2026-06`，內容註明「待法務定稿」（`api/services/consent_service.py:22-45`）；`get_consents` 永遠回三段，未紀錄者 `accepted=False`（`:83-90`）。
- 完工前是否強制三段同意由 `completion_policy.require_consents` 控，預設 `False`（`api/services/work_order_service.py:1451-1452`、`:1577-1584`）。
