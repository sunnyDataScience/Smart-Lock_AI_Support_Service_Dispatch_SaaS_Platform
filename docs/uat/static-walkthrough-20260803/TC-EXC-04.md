# TC-EXC-04 — DB 連線抖動下的 fail-open 讀取與 fail-closed 關鍵寫入

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑 `test_cr_0131_surface_failclosed.py` 等三檔，19 項全數通過（見「既有測試證據」） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（＋既有測試實跑） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/core/deps.py:161-180`、`:307-338`、`api/core/auth.py:110-131`、`:134-168`、`:170-201`、`:203-217`、`api/core/db.py:40-62`、`api/core/idempotency.py:226-228`、`api/tests/test_cr_0131_surface_failclosed.py:44-125` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

TC 判定基準的兩半在程式碼中各有對應且用詞一致。①「一般讀取退回 claims-only（fail-open）」：`load_user_security_state` 在 DB 不可用時回 `None`（`api/core/auth.py:186-188` 經 `_security_conn` `:129-131`），`require_tenant` 路徑上 `state is None` 即跳過 `is_active` / `password_changed_at` 檢查（`api/core/deps.py:163-165`、`:180`），註解字面即為「fail-open：查無/無 DB → None → 維持 claims-only」。②「金流/派工等關鍵寫入拒絕（503）而非放行」：`role_required(..., fail_closed=True)` 在 `security_state_verifiable()` 為假時拋 503 `SECURITY_STATE_UNAVAILABLE`（`api/core/deps.py:330-337`），白名單為 20 個端點，涵蓋退款、爭議雙簽、發票、三種對帳單的 approve/mark-paid、以及派工 assign/reassign/auto-match（`api/tests/test_cr_0131_surface_failclosed.py:47-69` 的正典清單；`git grep -c fail_closed=True -- api/routers` 合計 20 處）。該清單另有一支反射式測試釘住「runtime 實際掛旗標的端點集 == 文件化清單」（`:76-92`）。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 9.1 系統例外 |
| 前置 | DB 連線抖動 |
| 步驟 | 已登入使用者持續操作 |
| 預期結果（判定基準） | 一般讀取退回 claims-only（fail-open 可用性取捨）；金流/派工等關鍵寫入拒絕（503）而非放行（fail-closed 白名單為上線前條件） |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | NFR-Avail-010 |
| 屬於哪條旅程腳本 | — |

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| DB 不可用時連線層回假 | `api/core/db.py:45-47`（`uri` 未設 → `logger.error` + `return False`）、`:59-62`（連線失敗 → `logger.error` + `return False`） | 有落點 |
| 安全狀態查不到 → 回 `None` | `api/core/auth.py:129-131`（`_security_conn` 回 None）、`:186-188` | 有落點 |
| 一般端點維持 claims-only | `api/core/deps.py:162-165`（註解字面「fail-open … 維持 claims-only」）、`:166-180`（`state is not None` 才做檢查） | 有落點 |
| 撤銷檢查亦 fail-open | `api/core/auth.py:219-224` `is_jti_revoked`：無連線 → `return False` | 有落點 |
| 冪等去重亦 fail-open | `api/core/idempotency.py:226-228`：DB 不可用 → `return None`（不去重） | 有落點 |
| fail-closed 開關 | `api/core/deps.py:307-311`（`role_required(..., fail_closed=False)` 預設）、`:330-337` | 有落點 |
| 拒絕碼與狀態碼 | `api/core/deps.py:332-336`：`SECURITY_STATE_UNAVAILABLE` / 503 | 有落點 |
| 白名單涵蓋金流 | `test_cr_0131_surface_failclosed.py:48-62`：退款 4、爭議 2、發票 1、對帳單 6 | 有落點 |
| 白名單涵蓋派工 | `test_cr_0131_surface_failclosed.py:63-68`：`dispatch/assign`、`dispatch/auto-match`、`dispatch:plan`、`dispatch:auto-match`、`work-orders/{id}:assign`、`:reassign` | 有落點 |
| 白名單不漂移 | `test_cr_0131_surface_failclosed.py:76-92` 反射式對帳測試 | 有落點 |
| 技師角色另有 fail-closed | `api/core/auth.py:141-146`、`:158-165`（權威庫不可讀 → 503 `SECURITY_STATE_UNAVAILABLE`） | 有落點（超出 TC 範圍的額外行為） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 已登入使用者 | 一般讀取（DB 抖動中） | `TokenAcceptedClaimsOnly` | fail-open | `api/core/auth.py:186-188` → `api/core/deps.py:166` | `state is None` → 不做 `is_active` / `password_changed_at` 檢查 |
| 已登入使用者 | 一般讀取（DB 抖動中，走到業務層） | `RequestRejected(503)` | 業務層需連線 | `api/services/work_order_service.py:219` 等 90 檔共用樣式 | `ApiError("DB_UNAVAILABLE", "Database unavailable", 503)` |
| 已登入使用者 | 退款決策 / 對帳單核准（DB 抖動中） | `RequestRejected(503)` | fail-closed 白名單 | `api/core/deps.py:330-337` | `SECURITY_STATE_UNAVAILABLE` 503 |
| 已登入使用者 | 派工 assign / auto-match（DB 抖動中） | `RequestRejected(503)` | fail-closed 白名單 | `api/routers/work_orders_v2.py:513`、`api/routers/dispatch_v2.py:122` 等 | 同上 |
| 已登入使用者 | 建問題卡（DB 抖動中） | （不 fail-closed） | 一般端點取捨 | `api/tests/test_cr_0131_surface_failclosed.py:118-125` | 斷言 `status_code != 503`（走到業務層） |
| 技師 | 任一端點（雙庫模式、權威庫離線） | `RequestRejected(503)` | fail-closed | `api/core/auth.py:158-165` | `SECURITY_STATE_UNAVAILABLE` 503，不退 claims-only |
| 被停權使用者 | 任一端點（DB 抖動中） | `TokenAcceptedClaimsOnly` | fail-open 的代價 | `api/core/deps.py:162-165` 註解 | 停權即時失效在 DB 不可用時不生效 |
| Client | 寫入帶 Idempotency-Key（DB 抖動中） | `DeduplicationSkipped` | fail-open | `api/core/idempotency.py:226-228` | 不去重直接放行 |

---

## 逐層走查

### 第 1 層 — 連線層：抖動如何被表達

`api/core/db.py:40-62`

```python
async def _ensure_conn() -> bool:
    global _shared_conn
    # getattr 防禦:單元測試以假連線(無 closed/broken 屬性)monkeypatch _conn,
    # 視為健康直接沿用(真 psycopg 連線兩屬性必存在)。
    if _shared_conn is not None and not getattr(_shared_conn, "closed", False) and not getattr(_shared_conn, "broken", False):
        return True
    uri = os.getenv(_uri_env)
    if not uri:
        logger.error("環境變數 %s 未設定", _uri_env)
        return False
    try:
        if _shared_conn is not None:
            try:
                await _shared_conn.close()
            except Exception as e:
                logger.warning("[DB] close 既有連線失敗（將以新連線取代）: %s", e, exc_info=True)
        _shared_conn = await AsyncConnection.connect(uri, autocommit=True)
        logger.info("[DB] 已連線（autocommit=True, env=%s）", _uri_env)
        return True
    except Exception as e:
        logger.error("[DB] 連線失敗：%s", e)
        _shared_conn = None
        return False
```

檔頭 `api/core/db.py:3` 記載模式來源：「CloudSQL 閒置斷線可透明重連」。即抖動時每次呼叫都會嘗試重連，失敗回 `False`。

### 第 2 層 — 認證層：fail-open 的兩處

`api/core/auth.py:110-131`（安全庫連線取得）

```python
    if role == "platform_admin":
        try:
            return await db_module.require_platform_conn()
        except RuntimeError:
            return None
    if not await _ensure_conn():
        return None
    return db_module._conn
```

`api/core/auth.py:170-188`

```python
async def load_user_security_state(user_id: str, role: str | None = None) -> dict | None:
    """回 {is_active, password_changed_at} 供每請求 token 驗證重查（A2/A3）。

    **Fail-open 設計**（對齊 is_jti_revoked）：DB 不可用、user_id 非合法 uuid、或查無此
    使用者 → 回 None（呼叫端維持 claims-only 行為）。這是刻意的：
      - 既有大量元件測試用「未 seed 的假 user_id」（token 驗證只看 claims）→ 查無回 None 不破測試。
      - 真實「停權（is_active=False）」或「改密碼後（password_changed_at）」的既存帳號 → 撈得到 → 失效。
    role 供 CR-0114 路由：platform_admin 查平台庫，其餘查主連線。

    **例外（UAT-0718 R2）**：role=technician 且雙庫模式時改讀權威庫且 fail-closed
    （見 _load_technician_security_state）；單庫 fallback 行為與舊版完全相同。
    """
    if role == "technician" and db_module.tech_db_enabled():
        return await _load_technician_security_state(user_id)
    conn = await _security_conn(role)
    if conn is None:
        return None
```

`api/core/deps.py:161-180`

```python
    # A2/A3：每請求重查使用者狀態（停權即時失效 + 改密碼後撤既有 session）。
    # fail-open：查無/無 DB → None → 維持 claims-only（見 load_user_security_state）。
    # 例外（UAT-0718 R2）：technician 於雙庫模式讀權威庫且 fail-closed（503）。
    state = await load_user_security_state(payload["sub"], token_role)
    if state is not None:
        if not state["is_active"]:
            raise ApiError(
                error_code="ACCOUNT_DISABLED",
                message="Account has been disabled",
                status_code=403,
            )
```

撤銷檢查亦同型，`api/core/auth.py:219-224`：

```python
async def is_jti_revoked(jti: str, role: str | None = None) -> bool:
    conn = await _security_conn(role)
    if conn is None:
        return False
```

### 第 3 層 — fail-closed 白名單機制

`api/core/deps.py:307-338`

```python
def role_required(*roles: str, fail_closed: bool = False):
    """Dependency factory 限制角色。

    fail_closed（SA-05 / CR-0131 關鍵金流/派工寫入白名單）：安全狀態不可驗
    （DB 不可用 → revoked_jti / is_active 查不到）時拒絕請求（503），不退
    claims-only。一般端點維持 C-05 fail-open 取捨（可用性換安全）。
    """
    async def _dep(
        ...
    ) -> CurrentUser:
        user = await require_tenant(request, authorization, x_tenant_id)
        if roles and user.role not in roles:
            raise ApiError(
                error_code="FORBIDDEN",
                message=f"Requires one of roles: {', '.join(roles)}",
                status_code=403,
            )
        if fail_closed:
            from core.auth import security_state_verifiable

            if not await security_state_verifiable(user.role):
                raise ApiError(
                    error_code="SECURITY_STATE_UNAVAILABLE",
                    message="安全狀態不可驗（撤銷/停權查核離線）——關鍵金流/派工寫入拒絕執行（SA-05 fail-closed）",
                    status_code=503,
                )
        return user
    return _dep
```

`api/core/auth.py:203-217`

```python
async def security_state_verifiable(role: str | None = None) -> bool:
    """安全狀態是否可驗（SA-05 / CR-0131）：能取得對應安全庫連線＝可查 revoked_jti
    與 users.is_active。DB 不可用 → False——關鍵金流/派工寫入端點（fail_closed=True
    白名單）此時拒絕請求（503），不退 claims-only；一般端點維持 fail-open（C-05 取捨）。

    UAT-0718 R2：technician 於雙庫模式須權威庫也可達（is_active/password_changed_at
    讀權威庫；revoked_jti 仍在品牌庫）——兩庫任一不可達＝不可驗。
    """
    if role == "technician" and db_module.tech_db_enabled():
        try:
            await db_module.require_tech_conn()
        except Exception:  # noqa: BLE001 — RuntimeError(Tech DB unavailable) 等
            return False
    return (await _security_conn(role)) is not None
```

### 第 4 層 — 白名單的實際成員

```
git grep -rn "fail_closed=True" -- api/routers
api/routers/brand_b2b_statement_v2.py:156, :193
api/routers/dispatch.py:82, :112
api/routers/dispatch_v2.py:122, :157
api/routers/dispatcher_commission_v2.py:151, :188
api/routers/disputes_v2.py:231, :272
api/routers/invoices_v2.py:122
api/routers/refunds.py:74, :130
api/routers/refunds_v2.py:91, :166
api/routers/technician_statement_v2.py:166, :208
api/routers/work_orders.py:187
api/routers/work_orders_v2.py:513, :686
```

共 20 處。與正典清單一致，`api/tests/test_cr_0131_surface_failclosed.py:44-69`：

```python
# 金流終局動作＋派工指派（發起/撤回類維持 fail-open 可用性——設計取捨記 CR-0131）
_FAIL_CLOSED_CANON = {
    ("POST", "/api/v1/refunds"),
    ("POST", "/api/v1/refunds/{id}/decision"),
    ("POST", "/tenants/{tenantId}/refunds/{refundId}/decision"),
    ("POST", "/tenants/{tenantId}/refunds:agent-initiate"),
    ("POST", "/tenants/{tenantId}/disputes/{disputeId}:review"),
    ("POST", "/tenants/{tenantId}/disputes/{disputeId}:co-sign"),
    ("POST", "/tenants/{tenantId}/accounting/invoices:from-quote"),
    ("POST", "/tenants/{tenantId}/tech-statements/{statementId}:approve"),
    ("POST", "/tenants/{tenantId}/tech-statements/{statementId}:mark-paid"),
    ("POST", "/tenants/{tenantId}/dispatcher-commissions/{statementId}:approve"),
    ("POST", "/tenants/{tenantId}/dispatcher-commissions/{statementId}:mark-paid"),
    ("POST", "/tenants/{tenantId}/brand-b2b-statements/{statementId}:approve"),
    ("POST", "/tenants/{tenantId}/brand-b2b-statements/{statementId}:mark-paid"),
    ("POST", "/api/v1/dispatch/assign"),
    ("POST", "/api/v1/dispatch/auto-match"),
    ("POST", "/tenants/{tenantId}/dispatch:plan"),
    ("POST", "/tenants/{tenantId}/dispatch:auto-match"),
    ("POST", "/api/v1/work-orders/{id}/assign"),
    ("POST", "/tenants/{tenantId}/work-orders/{id}:assign"),
    ("POST", "/tenants/{tenantId}/work-orders/{id}:reassign"),
}
```

清單註解記載範圍界線：「金流終局動作＋派工指派（發起/撤回類維持 fail-open 可用性——設計取捨記 CR-0131）」。

### 第 5 層 — 業務層在 DB 不可用時的行為

`api/services/work_order_service.py:219`（同一樣式在 `api/services` 中共 90 個檔案出現）：

```python
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
```

即：認證層 fail-open 讓請求「通過身分驗證」，但業務層仍需連線；DB 全斷時一般讀取端點回的是 503 `DB_UNAVAILABLE`（不同於白名單的 503 `SECURITY_STATE_UNAVAILABLE`）。TC 判定基準的「一般讀取退回 claims-only」指的是身分驗證的降級行為，程式碼中對應的即 `api/core/deps.py:163-165`。此處僅並陳兩者的分層，不裁定。

---

## 既有測試證據

實跑（本機 Docker 測試庫，Windows 加 `-p winloop_plugin`）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0041_exception_framework.py tests/test_cr_0153_uri_strict_guard.py \
  tests/test_cr_0131_surface_failclosed.py -q -p winloop_plugin
19 passed in 153.46s (0:02:33)
```

直接對到 TC 判定基準兩半的測試，`api/tests/test_cr_0131_surface_failclosed.py:95-125`：

```python
async def test_fail_closed_rejects_when_state_unverifiable(client, admin_headers, monkeypatch):
    """安全狀態不可驗 → 白名單端點 503 SECURITY_STATE_UNAVAILABLE；一般寫入維持 fail-open。"""
    import core.auth as core_auth

    async def _no_conn(role=None):
        return None

    monkeypatch.setattr(core_auth, "_security_conn", _no_conn)

    # 白名單（派工指派）→ 503
    res = await client.post(
        f"/api/v1/work-orders/{uuid.uuid4()}/assign",
        json={"technician_id": str(uuid.uuid4()), "reason_code": "manual"},
        headers=admin_headers,
    )
    assert res.status_code == 503, res.text
    assert res.json().get("error_code") == "SECURITY_STATE_UNAVAILABLE"

    # 白名單（金流核准）→ 503
    res = await client.post(
        f"/tenants/{TID}/tech-statements/{uuid.uuid4()}:approve",
        json={}, headers=admin_headers,
    )
    assert res.status_code == 503

    # 非白名單寫入（問題卡建立）→ 維持 fail-open（claims-only），走到業務層非 503
    res = await client.post(
        "/api/v1/problem-cards",
        json={"conversation_id": str(uuid.uuid4()), "brand": "Yale", "model": "X",
              "symptom": "測試", "category": "維修", "urgency": "medium"},
        headers=admin_headers,
    )
    assert res.status_code != 503, f"一般端點不應 fail-closed（{res.status_code}）"
```

同檔 `:76-92` 的 `test_fail_closed_whitelist_canon` 以 FastAPI route 反射抽出所有掛 `fail_closed=True` 的端點，與正典清單做集合相等斷言。

---

## 事實結論

1. DB 不可用時 `_ensure_conn` 回 `False` 並寫 `logger.error`（`api/core/db.py:45-47`、`:59-62`）。
2. 認證層的兩個安全檢查在無連線時皆 fail-open：`load_user_security_state` 回 `None`（`api/core/auth.py:186-188`）、`is_jti_revoked` 回 `False`（`:219-224`）；`require_tenant` 路徑上 `state is None` 即略過停權與改密碼檢查（`api/core/deps.py:166-180`）。註解字面即「維持 claims-only」（`api/core/deps.py:163`）。
3. 冪等去重在 DB 不可用時同樣 fail-open，直接放行不去重（`api/core/idempotency.py:226-228`）。
4. `role_required(..., fail_closed=True)` 在 `security_state_verifiable()` 為假時拋 503 `SECURITY_STATE_UNAVAILABLE`（`api/core/deps.py:330-337`）。
5. 白名單共 20 個端點，涵蓋退款 4、爭議雙簽 2、發票 1、三種對帳單的 approve/mark-paid 共 6、派工相關 6（`git grep -c fail_closed=True -- api/routers` 合計 20；正典清單 `api/tests/test_cr_0131_surface_failclosed.py:47-69`）。
6. 白名單以反射式測試對帳，防止漂移（`api/tests/test_cr_0131_surface_failclosed.py:76-92`）。
7. 退款/派工的「發起、撤回」類端點刻意不在白名單內，設計取捨記於清單註解（`test_cr_0131_surface_failclosed.py:46`）。
8. `technician` 角色在雙庫模式下另有更嚴的行為：權威庫不可讀時所有端點回 503 `SECURITY_STATE_UNAVAILABLE`，不退 claims-only（`api/core/auth.py:141-146`、`:158-165`）。
9. 認證層 fail-open 與業務層 503 分屬兩層：DB 全斷時一般讀取端點仍會在業務層回 503 `DB_UNAVAILABLE`（`api/services` 中 90 個檔案共用該樣式，例 `api/services/work_order_service.py:219`）。此處僅並陳分層事實，不裁定。
10. 三檔測試 19 項於本機測試庫全數通過。
