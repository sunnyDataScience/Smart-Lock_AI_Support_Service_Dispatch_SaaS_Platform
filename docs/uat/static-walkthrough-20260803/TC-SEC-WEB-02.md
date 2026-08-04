# TC-SEC-WEB-02

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另以本機 Docker 測試庫實跑既有測試） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `web/{brand-portal,tech-portal,platform-console,landing}/src/lib/api.ts`、`web/brand-portal/src/components/layout/AuthGuard.tsx`、`api/core/tenant.py`、`api/core/deps.py:198-212`、`api/tests/test_auth_guards.py`、`test_cross_tenant_error_code_class.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

TC 判定基準有兩段。程式碼中存在**兩條**取得 tenant 的路徑，兩條的行為不同：`resolveTenantId()`（頁面層）在無 session tenant 時呼叫 `handleSessionExpired()` 清 session 並 `window.location.replace` 到登入頁，再回傳 `FALLBACK_TENANT_ID`（四站台皆同，`web/brand-portal/src/lib/api.ts:297-313`），該段註解直接引用本 TC 編號與日期（`:300-301`）；`auth.getTenantId()`（送出 `X-Tenant-ID` header 與 `tenantPath()` 組路徑用）則在無 claims cookie 時直接回 `FALLBACK_TENANT_ID`，無任何導向（`web/brand-portal/src/lib/api.ts:149`），其上方 `:140-142` 的 TODO 註解記載該行為未變更。後端側：缺 `X-Tenant-ID` header 回 400 `MISSING_TENANT`（`api/core/tenant.py:16-24`），header 與 token claim 不符回 403 `TENANT_MISMATCH`（`api/core/deps.py:206-211`），但 token 的 `tenant_id` claim 為空字串時該比對被短路跳過（`api/core/deps.py:206` 的 `if user.tenant_id and ...`）。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 8. 權限與 RBAC 案例（TC-SEC-RBAC） |
| 前置 | 無有效 tenant 的 session |
| 步驟 | 發任意 API 請求 |
| 預期結果（判定基準） | 擋下並導回登入，不得靜默 fallback 至預設租戶 |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-PLT-01、FR-WEB-02 |
| 屬於哪條旅程腳本 | SC-12、SC-17 |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:337`。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 無 session 時前端導回登入 | `web/brand-portal/src/components/layout/AuthGuard.tsx:76-81` | 一致 |
| 頁面層取 tenant 缺 session → 導回登入 | `web/brand-portal/src/lib/api.ts:311`（`handleSessionExpired()`）；四站台皆同 | 一致 |
| header 層取 tenant 缺 claims → 導回登入 | `web/brand-portal/src/lib/api.ts:149`：直接回 `FALLBACK_TENANT_ID`，無導向 | 不一致 |
| 不得靜默 fallback 至預設租戶（頁面層） | `web/brand-portal/src/lib/api.ts:311-312`：導向後仍回 `FALLBACK_TENANT_ID`（同檔 `:308-310` 說明理由） | 部分實作 |
| 不得靜默 fallback 至預設租戶（header 層） | `web/brand-portal/src/lib/api.ts:149`、`:205-208`（`tenantPath`） | 不一致 |
| 預設租戶常數存在且四站台一致 | `brand-portal:144`、`landing:127`、`platform-console:134`、`tech-portal:134`，值皆為 `00000000-0000-0000-0000-000000000001` | 一致（常數存在） |
| 後端缺 `X-Tenant-ID` → 擋下 | `api/core/tenant.py:16-24`：400 `MISSING_TENANT` | 一致 |
| 後端 header 與 claim 不符 → 擋下 | `api/core/deps.py:206-211`：403 `TENANT_MISMATCH` | 一致 |
| token 無 tenant claim 時的比對 | `api/core/deps.py:206`：`if user.tenant_id and user.tenant_id != tenant` — claim 為空則不比對 | 部分實作 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 未登入者 | 開受保護頁面 | `RedirectToLogin` | AuthGuard | `AuthGuard.tsx:76-81` | `router.replace("/login")`（或 `/platform/login`） |
| session 存在但無 tenant claim | 頁面呼叫 `resolveTenantId()` | `RedirectToLogin` | 不得靜默 fallback | `web/brand-portal/src/lib/api.ts:311` | 清 session ＋ `window.location.replace` 至登入頁；回傳值仍為 `FALLBACK_TENANT_ID` |
| claims cookie 遺失 | client 送出任意 API 請求 | `RedirectToLogin` | 同上 | `web/brand-portal/src/lib/api.ts:149`、`:393` | `X-Tenant-ID` 直接帶 `FALLBACK_TENANT_ID`，無導向 |
| client | 送出不帶 `X-Tenant-ID` 的請求 | `RequestRejected(400)` | header 必填 | `api/core/tenant.py:18-23` | `MISSING_TENANT`，400 |
| client | `X-Tenant-ID` ≠ token claim | `RequestRejected(403)` | tenant 綁定 | `api/core/deps.py:206-211` | `TENANT_MISMATCH`，403 |
| client | token claim 為空 + `X-Tenant-ID` 任意值 | — | — | `api/core/deps.py:206` | 比對被 `if user.tenant_id and ...` 短路，不擋 |

---

## 逐層走查

### 步驟 1 — 預設租戶常數

`web/brand-portal/src/lib/api.ts:134-144`：

```ts
/**
 * 預設租戶 ID — session/JWT 無 tenant 時的退回值（local dev / 未登入情境）。
 *
 * 收斂前散落在 11+ 個 page / component 內以 inline 字面量重抄此 UUID
 * （`session?.tenantId ?? "00000000-…-0001"`），改為唯一常數 + helper。
 *
 * TODO(安全, 跨頁行為決策)：正式環境理應在無有效 tenant 時擋下並導回登入，
 *   而非靜默退回 1 號租戶（多租戶資料外洩風險）。此為跨 12 頁面的行為變更，
 *   屬業主裁決範圍，本次只做「集中字面量」不改 runtime 行為。
 */
export const FALLBACK_TENANT_ID = "00000000-0000-0000-0000-000000000001";
```

同一常數與同一段 TODO 存在於四個站台：

```
web/brand-portal/src/lib/api.ts:144
web/landing/src/lib/api.ts:127
web/platform-console/src/lib/api.ts:134
web/tech-portal/src/lib/api.ts:134
```

TODO 註解行號：`brand-portal:140`、`landing:123`、`platform-console:130`、`tech-portal:130`。

### 步驟 2 — 路徑 A：header 與 tenantPath 使用的 `auth.getTenantId()`

`web/brand-portal/src/lib/api.ts:146-150`：

```ts
export const auth = {
  getAccessToken: () => accessTokenMemory,
  getRefreshToken: () => null,
  getTenantId: () => readClaimsCookie()?.tenantId ?? FALLBACK_TENANT_ID,
  getEmail: () => readClaimsCookie()?.email ?? null,
```

其消費點：

- `X-Tenant-ID` header 注入：`web/brand-portal/src/lib/api.ts:393`、`:501`、`:535`、`:582`、`:627`

```ts
    headers["X-Tenant-ID"] = auth.getTenantId();
```

- v2 tenant-scoped 路徑組裝：`web/brand-portal/src/lib/api.ts:205-208`

```ts
export function tenantPath(suffix: string): string {
  const s = suffix.startsWith("/") ? suffix : `/${suffix}`;
  return `/tenants/${auth.getTenantId()}${s}`;
}
```

四站台的 `getTenantId` 行號：`brand-portal:149`、`landing:132`、`platform-console:139`、`tech-portal:139`，實作字串完全相同。

### 步驟 3 — 路徑 B：頁面層的 `resolveTenantId()`

`web/brand-portal/src/lib/api.ts:290-313`：

```ts
/**
 * resolveTenantId — 頁面用：取目前 JWT session 的 tenant_id，缺則退回 FALLBACK_TENANT_ID。
 *
 * 收斂 11+ 個 page / component 內 inline 重抄的
 * `getCurrentSession()?.tenantId ?? "00000000-…-0001"`。
 * 來源語意刻意對齊原 caller（session claim，而非任意 request tenant）。
 */
export function resolveTenantId(): string {
  const tenantId = getCurrentSession()?.tenantId;
  if (tenantId) return tenantId;
  // 2026-07-31（TC-SEC-WEB-02）：原本無 session 時靜默退回 1 號租戶。
  // 規格要求「擋下並導回登入，不得靜默 fallback 至預設租戶」。
  //
  // 實測補充（避免把嚴重度講得比實際高）：伺服器端**確實**擋得住跨租戶 ——
  // 帶 A 租戶 token 但 X-Tenant-ID 指向 B，v1 與 v2 路徑實測皆回 403。
  // 所以這裡修的不是資料外洩，而是「claims cookie 掉了的使用者會拿到一串
  // 403 錯誤，而不是被乾淨地送回登入頁」。
  //
  // 仍回傳字串而非 throw：導向是非同步的，呼叫端（24 個頁面/元件）在導向
  // 完成前還會跑完當前這一輪 render，回 null 會讓它們崩在型別上。
  // 這一輪送出的請求由伺服器 403 收尾，不會拿到別人的資料。
  handleSessionExpired();
  return FALLBACK_TENANT_ID;
}
```

同段（含註解文字）存在於四站台：`tech-portal:287-303`、`platform-console:287-303`、`landing:276-292`。

`handleSessionExpired` 的實作在 `web/brand-portal/src/lib/api.ts:372-380`：

```ts
function handleSessionExpired(): void {
  if (typeof window === "undefined" || sessionExpiredHandled) return;
  sessionExpiredHandled = true; // 並發 401 只導一次（full nav 後模組重載自動歸零）
  auth.clear();
  const target = loginPathForCurrentLocation();
  if (window.location.pathname !== target) {
    window.location.replace(target); // replace：不在歷史留下已失效的死頁
  }
}
```

### 步驟 4 — 頁面殼層的導向

`web/brand-portal/src/components/layout/AuthGuard.tsx:74-81`：

```tsx
    if (!session && !isPublic) {
      void bootstrapSession()
        .then((restored) => {
          if (!restored) {
            router.replace(
              pathname.startsWith("/platform") ? "/platform/login" : "/login",
            );
          } else if (!canAccessRoute(pathname, restored.role)) {
```

該判定條件為「無 session」，不含「有 session 但 tenantId 為 null」。

### 步驟 5 — 後端 tenant header 解析

`api/core/tenant.py:1-31`：

```python
"""X-Tenant-ID header 解析與驗證。

login/refresh/register 端點不檢查 tenant（因為還沒登入）；其他端點：
- 必須帶 header
- 必須與 JWT claim 中的 tenant_id 相符
"""

...

async def resolve_tenant_id(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> str:
    if not x_tenant_id:
        raise ApiError(
            error_code="MISSING_TENANT",
            message="X-Tenant-ID header is required",
            status_code=400,
        )
    return x_tenant_id
```

該檔無任何預設租戶字面值，缺 header 一律 400。

### 步驟 6 — 後端 tenant 綁定比對

`api/core/deps.py:198-212`：

```python
async def require_tenant(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> CurrentUser:
    """同時驗 JWT + 比對 X-Tenant-ID 與 claim 一致。"""
    user = await get_current_user(request, authorization)
    tenant = await resolve_tenant_id(x_tenant_id)
    if user.tenant_id and user.tenant_id != tenant:
        raise ApiError(
            error_code="TENANT_MISMATCH",
            message="X-Tenant-ID does not match token claim",
            status_code=403,
        )
    return user
```

`CurrentUser.tenant_id` 的取值在 `api/core/deps.py:185`：

```python
        tenant_id=payload.get("tenant_id", ""),
```

payload 無 `tenant_id` claim 時為空字串，`if user.tenant_id and ...` 為 falsy，比對被跳過。

### 步驟 7 — 路由層的第二道 tenant 比對

多數 v2 router 在 handler 內另比對 path 的 `tenantId` 與 token claim，例如 `api/routers/work_orders_v2.py:144-159`：

```python
def _cross_tenant_read(user: CurrentUser, tenant_id: str) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )


def _cross_tenant_write(user: CurrentUser, tenant_id: str) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )
```

此類守衛在 `api/routers/` 共 206 處字面命中（`CROSS_TENANT_READ` / `CROSS_TENANT_WRITE`），同樣帶 `if user.tenant_id and` 前置條件。

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

`api/tests/test_auth_guards.py:34-42` 覆蓋 header 與 claim 不符：

```python
async def test_tenant_mismatch_returns_403(client, admin_token):
    # 故意傳錯 tenant 不對應的 X-Tenant-ID
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "X-Tenant-ID": "ffffffff-ffff-ffff-ffff-ffffffffffff",
    }
    res = await client.get("/api/v1/work-orders", headers=headers)
    assert res.status_code == 403
```

`web/` 端無對應的自動化測試（四站台無 `middleware.ts`，`resolveTenantId` / `getTenantId` 在 `web/*/src` 下無單元測試檔）。

---

## 事實結論

1. 前端有兩條取得 tenant 的路徑，行為不同：`resolveTenantId()` 在缺 session tenant 時導回登入（`web/brand-portal/src/lib/api.ts:311`）；`auth.getTenantId()` 在缺 claims cookie 時直接回 `FALLBACK_TENANT_ID` 且無導向（`:149`）。
2. `auth.getTenantId()` 是 `X-Tenant-ID` header（`web/brand-portal/src/lib/api.ts:393`、`:501`、`:535`、`:582`、`:627`）與 `tenantPath()` 路徑組裝（`:205-208`）的來源。
3. `FALLBACK_TENANT_ID` 常數值為 `00000000-0000-0000-0000-000000000001`，四站台一致（`brand-portal:144`、`landing:127`、`platform-console:134`、`tech-portal:134`）。
4. `resolveTenantId()` 的修改註解直接引用本 TC 編號與日期「2026-07-31（TC-SEC-WEB-02）」，並記載「仍回傳字串而非 throw」的理由（`web/brand-portal/src/lib/api.ts:300-312`）。
5. `auth.getTenantId()` 上方的 TODO 註解記載「本次只做『集中字面量』不改 runtime 行為」，四站台皆在（`brand-portal:140-142` 等）。
6. 後端缺 `X-Tenant-ID` 回 400 `MISSING_TENANT`（`api/core/tenant.py:18-23`）；header 與 claim 不符回 403 `TENANT_MISMATCH`（`api/core/deps.py:206-211`）。
7. 後端 tenant 比對的前置條件為 `if user.tenant_id`（`api/core/deps.py:206`），token 無 `tenant_id` claim 時該比對不執行；`CurrentUser.tenant_id` 缺 claim 時為空字串（`api/core/deps.py:185`）。
8. `web/` 四站台無 `middleware.ts`，前端所有 tenant 判定在瀏覽器端執行。
