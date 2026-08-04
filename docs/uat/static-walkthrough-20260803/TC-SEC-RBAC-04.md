# TC-SEC-RBAC-04

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另以本機 Docker 測試庫實跑既有測試） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/core/deps.py:114-188`、`api/core/auth.py:117-226`、`api/services/auth_service.py:380-414`、`api/services/platform_admin_service.py:80-131`、`api/tests/test_account_security_phase1.py`、`api/tests/test_cr_0141_oidc.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

TC 判定基準三條在程式碼中皆有落點且錯誤碼與狀態碼字面相符：停權回 403 `ACCOUNT_DISABLED`（`api/core/deps.py:167-172`）、改密回 401 `TOKEN_STALE`（`api/core/deps.py:175-180`）、每請求安全狀態重查由 `load_user_security_state` 在 `get_current_user` 內執行（`api/core/deps.py:165`），而 `get_current_user` 是 `require_tenant` → `role_required` 的共同上游（`api/core/deps.py:204`、`:319`）。兩個錯誤碼在 `api/tests/test_account_security_phase1.py:134`、`:158` 有直接斷言，本次實跑通過。走查另記錄 `load_user_security_state` 對「DB 不可用／查無此使用者」為 fail-open（回 `None` → 維持 claims-only，`api/core/auth.py:174-182`），technician 於雙庫模式為例外的 fail-closed（`api/core/auth.py:159-165`）——此為程式碼行為陳述，非判定條件。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 8. 權限與 RBAC 案例（TC-SEC-RBAC） |
| 前置 | 帳號被停權 / 改密後 |
| 步驟 | 用舊 token 打 API |
| 預期結果（判定基準） | 停權 → 403 ACCOUNT_DISABLED；改密 → 401 TOKEN_STALE（每請求安全狀態重查） |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-PLT-02、NFR-Sec-003 |
| 屬於哪條旅程腳本 | — |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:333`。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 停權 → 403 | `api/core/deps.py:167-172`（`status_code=403`） | 一致 |
| 停權錯誤碼 `ACCOUNT_DISABLED` | `api/core/deps.py:169` 字面值 | 一致 |
| 改密 → 401 | `api/core/deps.py:175-180`（`status_code=401`） | 一致 |
| 改密錯誤碼 `TOKEN_STALE` | `api/core/deps.py:177` 字面值 | 一致 |
| 每請求安全狀態重查 | `api/core/deps.py:165` `await load_user_security_state(...)`，位於 `get_current_user` 內 | 一致 |
| 重查涵蓋所有受保護 HTTP 端點 | `require_tenant`（`api/core/deps.py:204`）、`role_required`（`:319`）皆經 `get_current_user` | 一致 |
| refresh 路徑同樣重查 | `api/services/auth_service.py:396-403` | 一致 |
| platform_admin 路徑同樣重查 | `api/services/platform_admin_service.py:126-130`；連線路由 `api/core/auth.py:124-128` | 一致 |
| 判定依據（改密）為 token `iat` 與 `password_changed_at` 比較 | `api/core/deps.py:173-180` | 一致 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 被停權使用者 | 帶舊 access token 打受保護端點 | `RequestRejected(403)` | 每請求重查 `is_active` | `api/core/deps.py:165-172` | `ACCOUNT_DISABLED`，403 |
| 改密後使用者 | 帶改密前簽發的 token 打受保護端點 | `RequestRejected(401)` | `iat < password_changed_at` | `api/core/deps.py:173-180` | `TOKEN_STALE`，401 |
| 被停權使用者 | 用舊 refresh token 換新 access | `RequestRejected(403)` | refresh 亦重查 | `api/services/auth_service.py:398-399` | `ACCOUNT_DISABLED`，403 |
| 改密後使用者 | 用舊 refresh token 換新 access | `RequestRejected(401)` | 同上 | `api/services/auth_service.py:402-403` | `TOKEN_STALE`，401 |
| 系統 | DB 不可用時重查 | — | fail-open（一般端點） | `api/core/auth.py:185-187`、`api/core/deps.py:166` | 回 `None` → 跳過重查，維持 claims-only |
| 系統 | DB 不可用時重查（關鍵金流／派工白名單端點） | `RequestRejected(503)` | fail-closed | `api/core/deps.py:326-334` | `SECURITY_STATE_UNAVAILABLE`，503 |
| technician（雙庫模式） | 權威庫不可讀時重查 | `RequestRejected(503)` | fail-closed | `api/core/auth.py:159-165` | `SECURITY_STATE_UNAVAILABLE`，503 |

---

## 逐層走查

### 步驟 1 — 每請求安全狀態重查的位置

`api/core/deps.py:162-180`：

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
        pwd_changed = state["password_changed_at"]
        iat = payload.get("iat")
        if pwd_changed and iat is not None and int(iat) < int(pwd_changed.timestamp()):
            raise ApiError(
                error_code="TOKEN_STALE",
                message="Session invalidated by password change; please log in again",
                status_code=401,
            )
```

該段位於 `get_current_user`（`api/core/deps.py:114`）函式體內，且在 jti 撤銷檢查（`:155-160`）之後。

### 步驟 2 — 重查的覆蓋範圍

`require_tenant` 呼叫 `get_current_user`（`api/core/deps.py:198-212`）：

```python
async def require_tenant(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> CurrentUser:
    """同時驗 JWT + 比對 X-Tenant-ID 與 claim 一致。"""
    user = await get_current_user(request, authorization)
```

`role_required` 呼叫 `require_tenant`（`api/core/deps.py:319`）：

```python
        user = await require_tenant(request, authorization, x_tenant_id)
```

`require_platform_admin` 亦呼叫 `get_current_user`（`api/core/deps.py:236`）；`require_keeper_role` 同（`:505`）。`api/core/deps.py:140-141` 註解記載此設計的覆蓋範圍：

```python
    # 掛在 get_current_user 單點即涵蓋所有受保護 HTTP 端點（含 F2 目標 bare require_tenant）。
    # 範圍＝HTTP-only；WS 授權由 verify_ws_token/authorize_channel 另行把關。
```

### 步驟 3 — 安全狀態查詢的實作

`api/core/auth.py:171-199`：

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
    ...
    cur = await conn.execute(
        "SELECT is_active, password_changed_at FROM users WHERE id = %s::uuid LIMIT 1",
        (user_id,),
    )
```

technician 雙庫模式的 fail-closed 分支在 `api/core/auth.py:159-165`：

```python
    except Exception as exc:  # noqa: BLE001 — 權威庫不可讀＝安全狀態不可驗
        logger.error("技師安全狀態查詢失敗（權威庫）：%s", exc)
        raise ApiError(
            "SECURITY_STATE_UNAVAILABLE",
            "技師安全狀態不可驗（權威庫離線）——拒絕請求（fail-closed）",
            503,
        ) from exc
```

### 步驟 4 — 關鍵端點的 fail-closed 白名單

`api/core/deps.py:326-334`：

```python
        if fail_closed:
            from core.auth import security_state_verifiable

            if not await security_state_verifiable(user.role):
                raise ApiError(
                    error_code="SECURITY_STATE_UNAVAILABLE",
                    message="安全狀態不可驗（撤銷/停權查核離線）——關鍵金流/派工寫入拒絕執行（SA-05 fail-closed）",
                    status_code=503,
                )
```

`api/core/deps.py:310-312` 記載此參數的取捨：

```python
    fail_closed（SA-05 / CR-0131 關鍵金流/派工寫入白名單）：安全狀態不可驗
    （DB 不可用 → revoked_jti / is_active 查不到）時拒絕請求（503），不退
    claims-only。一般端點維持 C-05 fail-open 取捨（可用性換安全）。
```

### 步驟 5 — refresh 與 platform 路徑

`api/services/auth_service.py:393-403`：

```python
    # A2/A3：refresh 也重查使用者狀態（停權即時失效 + 改密碼後撤 session），
    # 否則被停用/改密碼後仍能用舊 refresh 換新 access 達 30 天。fail-open（查無回 None）。
    # UAT-0718 R2：帶 role 讓 technician 於雙庫模式路由到權威庫（fail-closed）。
    state = await load_user_security_state(payload["sub"], payload.get("role"))
    if state is not None:
        if not state["is_active"]:
            raise ApiError("ACCOUNT_DISABLED", "Account is disabled", 403)
        pwd_changed = state["password_changed_at"]
        iat = payload.get("iat")
        if pwd_changed and iat is not None and int(iat) < int(pwd_changed.timestamp()):
            raise ApiError("TOKEN_STALE", "Refresh token invalidated by password change", 401)
```

`api/services/platform_admin_service.py:126-130` 為同型（平台庫）。

### 步驟 6 — DB 欄位

安全狀態的兩個欄位為 `users.is_active` 與 `users.password_changed_at`，由 `api/core/auth.py:192-195` 的 SELECT 讀出；`api/tests/test_account_security_phase1.py:151-153`、`:170-172` 直接以 `UPDATE users SET password_changed_at = ...` 構造測試前置。

### 步驟 7 — 前端錯誤碼對應

四個站台的錯誤碼字典均登記這兩碼，例如 `web/brand-portal/src/lib/apiError.ts:39`、`:49`：

```ts
  TOKEN_STALE: "登入已逾時，請重新登入。",
  ...
  ACCOUNT_DISABLED: "此帳號已停用，請聯絡管理員。",
```

`web/tech-portal/src/lib/apiError.ts:144` 另將 `TOKEN_STALE` 與 `UNAUTHENTICATED` 排除於一般 toast 之外：

```ts
    if (mapped && e.errorCode !== "UNAUTHENTICATED" && e.errorCode !== "TOKEN_STALE") {
```

---

## 既有測試證據

```
cd api && POSTGRES_URI=<本機測試庫> PYTHONPATH=<scratchpad> uv run pytest \
  tests/test_account_security_phase1.py tests/test_cr_0166_config_governance.py \
  tests/test_config_m18.py tests/test_cr_0182_portal_guard.py \
  tests/test_cr_0183_intra_portal_guards.py tests/test_cross_tenant_error_code_class.py \
  tests/test_work_order_read_ownership.py tests/test_auth_guards.py \
  tests/test_cr_0131_surface_failclosed.py -p winloop_plugin -q
82 passed in 12.22s
```

對到 TC 兩個判定基準的測試：

`api/tests/test_account_security_phase1.py:115-135`（停權）：

```python
async def test_a2_suspended_user_token_rejected(client):
    """A2-1：既簽 token 的帳號被停權（is_active=FALSE）→ 受保護端點 403。"""
    ...
        await db_module._conn.execute(
            "UPDATE users SET is_active = FALSE WHERE id = %s::uuid", (user_id,)
        )
        token2 = _access_token(user_id)
        r = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token2}"})
        assert r.status_code == 403, r.text
        assert r.json()["error_code"] == "ACCOUNT_DISABLED"
```

`api/tests/test_account_security_phase1.py:141-159`（改密）：

```python
async def test_a3_token_before_password_change_rejected(client):
    """A3-1：token iat 早於 password_changed_at → 401 TOKEN_STALE。"""
    ...
        await db_module._conn.execute(
            "UPDATE users SET password_changed_at = NOW() + interval '5 seconds' WHERE id = %s::uuid",
            (user_id,),
        )
        r = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401, r.text
        assert r.json()["error_code"] == "TOKEN_STALE"
```

`api/tests/test_account_security_phase1.py:162-179` 為控制組（`password_changed_at` 早於 token `iat` → 204）。

另外 `api/tests/test_cr_0141_oidc.py:175` 對 OIDC（RS256）路徑同樣斷言 `403 / ACCOUNT_DISABLED`；`api/tests/test_technician_login_status_gate.py:150` 對技師終止狀態斷言 `ACCOUNT_DISABLED`。

---

## 事實結論

1. 停權判定與錯誤碼在 `api/core/deps.py:167-172`，狀態碼 403、錯誤碼 `ACCOUNT_DISABLED`，與 TC 判定基準字面相同。
2. 改密判定與錯誤碼在 `api/core/deps.py:175-180`，狀態碼 401、錯誤碼 `TOKEN_STALE`，與 TC 判定基準字面相同。
3. 判定資料由 `load_user_security_state` 於每次請求向 `users` 表查詢 `is_active` 與 `password_changed_at`（`api/core/auth.py:192-195`），呼叫點在 `get_current_user` 內（`api/core/deps.py:165`）。
4. 該重查涵蓋 `require_tenant` / `role_required` / `require_platform_admin` / `require_keeper_role` 四條依賴鏈，因四者皆經 `get_current_user`。
5. 重查在 DB 不可用或查無此 user 時回 `None` 並跳過（`api/core/auth.py:174-182`、`api/core/deps.py:166`）；關鍵金流／派工寫入端點以 `fail_closed=True` 改為 503（`api/core/deps.py:326-334`）；technician 雙庫模式為 503 fail-closed（`api/core/auth.py:159-165`）。
6. refresh（`api/services/auth_service.py:396-403`）與 platform_admin refresh（`api/services/platform_admin_service.py:126-130`）走相同的兩個錯誤碼與狀態碼。
7. 兩個錯誤碼各有一支既有測試直接斷言，本次實跑通過。
