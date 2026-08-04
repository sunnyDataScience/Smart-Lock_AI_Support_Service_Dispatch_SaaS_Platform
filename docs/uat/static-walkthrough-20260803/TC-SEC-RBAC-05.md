# TC-SEC-RBAC-05

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另以本機 Docker 測試庫實跑既有測試） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/routers/auth.py:226-246`、`api/services/auth_service.py:417-439`、`api/core/auth.py:218-237`、`api/core/deps.py:152-160`、`SQL/Schema_api_phase1.sql:69-79`、`api/tests/test_account_security_phase1.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

TC 判定基準「401（jti 撤銷表命中）」在程式碼中有完整鏈路：登出端點取 token 的 `jti` 交給 `auth_service.logout`（`api/routers/auth.py:237-243`），後者呼叫 `revoke_jti` 寫入 `revoked_jti` 表（`api/services/auth_service.py:428`、`api/core/auth.py:229-237`）；後續任一受保護請求在 `get_current_user` 內以 `is_jti_revoked` 查該表，命中即拋 401 `TOKEN_REVOKED`（`api/core/deps.py:154-160`）。撤銷表為 `SQL/Schema_api_phase1.sql:71-79` 的 `revoked_jti`（`jti UUID PRIMARY KEY`）。走查另記錄兩項程式碼行為：`is_jti_revoked` 在取不到連線時回 `False`（`api/core/auth.py:219-221`），以及 `api/tests/` 中無「登出後重放同一 token 斷言 401」的直接測試（`TOKEN_REVOKED` 字面值在 `api/tests/` 零命中）——後者為測試覆蓋事實，不改變上述程式碼路徑的判定。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 8. 權限與 RBAC 案例（TC-SEC-RBAC） |
| 前置 | 已登出 token |
| 步驟 | 重放 |
| 預期結果（判定基準） | 401（jti 撤銷表命中） |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-PLT-02、NFR-Sec-003 |
| 屬於哪條旅程腳本 | — |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:334`。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 存在登出端點 | `api/routers/auth.py:226-246`（`POST /api/v1/auth/logout`，204） | 一致 |
| 登出寫入 jti 撤銷表 | `api/services/auth_service.py:420-428` → `api/core/auth.py:229-237` | 一致 |
| 存在 jti 撤銷表 | `SQL/Schema_api_phase1.sql:71-79` `revoked_jti` | 一致 |
| 每請求查撤銷表 | `api/core/deps.py:154-155` `await is_jti_revoked(jti, token_role)` | 一致 |
| 命中 → 401 | `api/core/deps.py:156-160`（`status_code=401`） | 一致 |
| refresh token 亦撤銷 | `api/services/auth_service.py:430-439` | 一致 |
| refresh 端點查撤銷表 | `api/services/auth_service.py:389-391`（401 `TOKEN_REVOKED`） | 一致 |
| refresh rotate 時撤銷舊 jti | `api/services/auth_service.py:405-408` | 一致 |
| platform console 登出 | `api/routers/platform_auth.py:76`；連線路由 `api/core/auth.py:124-128` | 一致 |
| 前端登出清除本機 session | `web/brand-portal/src/lib/api.ts:178-185` `auth.clear()` | 一致 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 已登入使用者 | `POST /api/v1/auth/logout` | `TokenRevoked(jti)` | 撤銷 access（＋refresh） | `api/services/auth_service.py:420-439` | `INSERT INTO revoked_jti ... ON CONFLICT DO NOTHING` |
| 攻擊者／同一使用者 | 帶已登出的 access token 打受保護端點 | `RequestRejected(401)` | jti 撤銷表命中 | `api/core/deps.py:154-160` | `TOKEN_REVOKED`，401 |
| 攻擊者 | 帶已登出的 refresh token 換 access | `RequestRejected(401)` | 同上 | `api/services/auth_service.py:389-391` | `TOKEN_REVOKED`，401 |
| 使用者 | 正常 refresh | `TokenRotated` | 舊 jti 立即撤銷 | `api/services/auth_service.py:405-408` | 寫入 `revoked_jti` 後發新對 |
| 系統 | 撤銷表查詢時取不到連線 | — | 取不到連線即視為未撤銷 | `api/core/auth.py:219-221` | `return False` |
| 維運 | 清理過期列 | — | `expires_at` 過期可清 | `SQL/Schema_api_phase1.sql:77-79` | 有 `idx_revoked_jti_expires` 與表註解 |

---

## 逐層走查

### 步驟 1 — 前端登出呼叫端

`web/brand-portal/src/lib/api.ts:803`：

```ts
    await request("POST", "/api/v1/auth/logout", {
```

同型呼叫存在於另外三站台：`web/tech-portal/src/lib/api.ts:776`、`web/platform-console/src/lib/api.ts:788`、`web/landing/src/lib/api.ts:754`。

前端本機 session 的清除在 `web/brand-portal/src/lib/api.ts:178-185`：

```ts
  clear() {
    accessTokenMemory = null;
    removeLegacySessionStorage();
    writeClaimsCookie(null);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("smartlock.session_event", `logout:${Date.now()}`);
    }
  },
```

### 步驟 2 — 登出端點

`api/routers/auth.py:226-246`：

```python
@router.post(
    "/auth/logout",
    operation_id="logout",
    summary="登出",
    status_code=204,
)
async def logout(
    request: Request,
    body: LogoutBody | None = None,
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    await auth_service.logout(
        access_jti=user.jti,
        access_user_id=user.user_id,
        access_exp_iso=None,
        refresh_token=(body.refresh_token if body else None)
        or request.cookies.get(REFRESH_COOKIE),
    )
    resp = Response(status_code=204)
    clear_session_cookies(resp)
    return resp
```

`user.jti` 來自 `get_current_user` 回傳的 `CurrentUser`（`api/core/deps.py:182-188`），其值即 JWT payload 的 `jti` claim。

### 步驟 3 — service 層撤銷

`api/services/auth_service.py:417-439`：

```python
async def logout(*, access_jti: str, access_user_id: str, access_exp_iso: str | None,
                 refresh_token: str | None) -> None:
    """登出：撤銷 access jti 與（如有）refresh jti。"""
    if access_jti and access_user_id:
        # access token 過期前內阻擋
        from datetime import timedelta
        # 若不知 exp，預設 1h 後過期清除
        try:
            exp = datetime.fromisoformat(access_exp_iso) if access_exp_iso else datetime.now(timezone.utc) + timedelta(hours=1)
        except (ValueError, TypeError):
            exp = datetime.now(timezone.utc) + timedelta(hours=1)
        await revoke_jti(access_jti, access_user_id, exp)

    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            jti = payload.get("jti")
            if jti and payload.get("type") == "refresh":
                exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                await revoke_jti(jti, payload["sub"], exp)
        except (JWTError, KeyError, ValueError, TypeError):
            # refresh decode / payload 缺欄位 / timestamp 解析失敗 → 忽略（只撤 access）
            pass
```

### 步驟 4 — 撤銷表寫入與查詢

`api/core/auth.py:218-237`：

```python
async def is_jti_revoked(jti: str, role: str | None = None) -> bool:
    conn = await _security_conn(role)
    if conn is None:
        return False
    cur = await conn.execute(
        "SELECT 1 FROM revoked_jti WHERE jti = %s::uuid",
        (jti,),
    )
    return await cur.fetchone() is not None


async def revoke_jti(jti: str, user_id: str, expires_at: datetime, role: str | None = None) -> None:
    conn = await _security_conn(role)
    if conn is None:
        raise RuntimeError("DB unavailable")
    await conn.execute(
        "INSERT INTO revoked_jti (jti, user_id, expires_at) VALUES (%s::uuid, %s::uuid, %s) "
        "ON CONFLICT (jti) DO NOTHING",
        (jti, user_id, expires_at),
    )
```

連線路由在 `api/core/auth.py:117-131`：

```python
async def _security_conn(role: str | None):
    """token 安全狀態/jti 的查詢連線路由（CR-0114）。

    platform_admin 的 users/revoked_jti 住平台庫（require_platform_conn；未配置
    平台庫時 fallback 主連線 → 行為同舊版）。其餘角色維持主連線。
    連不上回 None（呼叫端各自維持 fail-open / fail-closed 語意）。
    """
```

### 步驟 5 — 重放請求的攔截點

`api/core/deps.py:152-160`：

```python
    # CR-0114：platform_admin 的 revoked_jti/users 住平台庫 → 依 token role 路由查詢
    # （未配置平台庫時 fallback 主連線，行為同舊版）。
    jti = payload.get("jti")
    if jti and await is_jti_revoked(jti, token_role):
        raise ApiError(
            error_code="TOKEN_REVOKED",
            message="Token has been revoked",
            status_code=401,
        )
```

`ApiError` 的 `status_code` 為顯式參數（`api/core/errors.py:91-101`），不經 `_CODE_MAP` 推導，故 `TOKEN_REVOKED` 回 401。

此檢查位於停權／改密重查（`api/core/deps.py:165-180`）之前，且在跨面 portal 守衛（`:142-150`）之後。

### 步驟 6 — DB schema

`SQL/Schema_api_phase1.sql:69-79`：

```sql
-- [3] revoked_jti — JWT 撤銷清單（logout）
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS revoked_jti (
    jti         UUID PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    revoked_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_revoked_jti_expires ON revoked_jti(expires_at);

COMMENT ON TABLE revoked_jti IS 'JWT 撤銷清單；過期後（expires_at < now）可清除';
```

平台庫另有同名表，見 `SQL/platform/Schema_platform.sql`（`api/tests/test_platform_auth.py:49` 於清理時對其執行 `DELETE FROM revoked_jti WHERE user_id = ...`）。

### 步驟 7 — refresh 路徑的撤銷檢查與輪替

`api/services/auth_service.py:389-408`：

```python
    jti = payload.get("jti")
    if jti and await is_jti_revoked(jti):
        raise ApiError("TOKEN_REVOKED", "Refresh token has been revoked", 401)
    ...
    # Rotate：撤銷舊 jti，發新對
    if jti:
        exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        await revoke_jti(jti, payload["sub"], exp_dt)
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

`TOKEN_REVOKED` 字面值在 `api/tests/` 全樹零命中：

```
$ rg -n "TOKEN_REVOKED" api/tests/
（無輸出）
```

登出行為被間接使用於 `api/tests/test_account_security_phase1.py:123-132`——該測試以 logout 端點當受保護端點的探針，並於註解記錄「舊的已因 logout 撤銷」：

```python
        # 控制組：active → logout 204
        r = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 204, r.text

        # 停權後，重簽一顆新 token（舊的已因 logout 撤銷）→ 應被擋
```

`api/tests/test_platform_auth.py:21` 定義 `LOGOUT = "/api/v1/platform/auth/logout"` 並於 fixture 清理時清空 `revoked_jti`（`:49`）。

`scripts/ci/smoke-api.sh:107` 對登出端點做 204 煙霧檢查：

```
check "POST /auth/logout"                     "204" req POST /api/v1/auth/logout 204 "${AUTH_HEAD[@]}"
```

---

## 事實結論

1. 登出端點為 `POST /api/v1/auth/logout`，回 204 並清除 session cookie（`api/routers/auth.py:226-246`）。
2. 登出時對 access token 的 `jti` 呼叫 `revoke_jti` 寫入 `revoked_jti` 表；若請求帶 refresh token 且型別為 refresh，其 `jti` 一併寫入（`api/services/auth_service.py:420-439`）。
3. 每個受保護請求在 `get_current_user` 內查撤銷表，命中回 401 `TOKEN_REVOKED`（`api/core/deps.py:154-160`）；狀態碼由 `ApiError` 顯式指定（`api/core/errors.py:91-101`）。
4. 撤銷表 `revoked_jti` 的主鍵為 `jti UUID`，另有 `expires_at` 與其索引（`SQL/Schema_api_phase1.sql:71-77`）。
5. `is_jti_revoked` 在 `_security_conn` 回 `None`（取不到對應安全庫連線）時回 `False`（`api/core/auth.py:219-221`）；`role_required(fail_closed=True)` 的端點在此情況改回 503（`api/core/deps.py:326-334`）。
6. refresh 端點同樣查撤銷表（401 `TOKEN_REVOKED`，`api/services/auth_service.py:389-391`），且每次 rotate 會撤銷舊 jti（`:405-408`）。
7. `api/tests/` 中無斷言 `TOKEN_REVOKED` 的測試；登出行為在 `api/tests/test_account_security_phase1.py:123-132` 與 `scripts/ci/smoke-api.sh:107` 被間接執行。
