# TC-SEC-WEB-01

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另以本機 Docker 測試庫實跑既有測試） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `web/*/src/lib/rolePolicy.ts`、`web/brand-portal/src/components/layout/AuthGuard.tsx`、`api/core/deps.py`、`api/routers/*.py`、`scripts/ci/endpoint-guard-audit.py`、`api/tests/test_sec_legacy_endpoint_guards.py`、`test_cr_0182_portal_guard.py`、`test_cr_0183_intra_portal_guards.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

TC 判定基準三段。「後端 role_required 一律擋下」在 383/517 個 route handler 上有對應實作（`api/core/deps.py:307-336`），且 v2／legacy 孿生路徑的守衛對稱性由 `scripts/ci/endpoint-guard-audit.py` 守門（本次執行 exit 0）。「前端 gate 僅為 UX，非授權邊界」與程式碼一致：`web/brand-portal/src/lib/rolePolicy.ts:5` 註解自述「以『能否載入頁面』為 gate;唯讀差異（如 cs 看工單）由後端 role_required 把關」，且該 gate 由 client component `AuthGuard`（`web/brand-portal/src/components/layout/AuthGuard.tsx:1` `"use client"`）在瀏覽器端執行，`web/` 四站台皆無 `middleware.ts`（伺服器端攔截）。「未登記路由 deny-by-default」與程式碼相反：`web/brand-portal/src/lib/rolePolicy.ts:88` 對未列到的路由 `return true`（放行），檔頭 `:10` 亦明寫「未列到的路由 → 預設放行」；後端側則有 47 個端點僅掛 `require_tenant`、4 個僅 `get_current_user`（見「逐層走查／步驟 4」）。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 8. 權限與 RBAC 案例（TC-SEC-RBAC） |
| 前置 | 停用 JS 或直接帶 token 呼叫 api |
| 步驟 | 繞過前端路由 gate |
| 預期結果（判定基準） | 後端 role_required 一律擋下——前端 gate 僅為 UX，非授權邊界；未登記路由 deny-by-default |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-WEB-02 |
| 屬於哪條旅程腳本 | — |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:336`。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 前端路由 gate 存在 | `web/brand-portal/src/lib/rolePolicy.ts:25-71`（`ROUTE_POLICY`）＋`AuthGuard.tsx:48-` | 一致 |
| 前端 gate 為 client-side（可繞過） | `AuthGuard.tsx:1` `"use client"`；`web/` 四站台無 `middleware.ts` | 一致 |
| 前端 gate 自述僅為 UX | `web/brand-portal/src/lib/rolePolicy.ts:5`、`:11` | 一致 |
| 後端以 `role_required` 擋下 | `api/core/deps.py:307-336`；383/517 端點掛載 | 部分實作 |
| v2／legacy 孿生路徑守衛一致 | `scripts/ci/endpoint-guard-audit.py`（本次 exit 0）；`api/tests/test_sec_legacy_endpoint_guards.py:29-70` | 一致 |
| 跨面 token 不得打他面端點 | `api/core/deps.py:142-150`（`CROSS_PORTAL_FORBIDDEN` 403） | 一致 |
| 前端未登記路由 deny-by-default | `web/brand-portal/src/lib/rolePolicy.ts:88` `return true` | 不一致（為 allow-by-default） |
| 後端未掛角色守衛的端點 | 47 個 `require_tenant`-only、4 個 `get_current_user`-only、29 個無認證依賴 | 部分實作 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 攻擊者 | 停用 JS 直接開受限頁面 URL | （前端不再是判準） | 前端 gate 僅 UX | `AuthGuard.tsx:1`（client component）；無 `middleware.ts` | 頁面殼可載入；資料需打 API |
| 攻擊者 | 帶 technician token 直打後台寫入 API | `RequestRejected(403)` | `role_required` | `api/core/deps.py:320-325` | `FORBIDDEN`，403 |
| 攻擊者 | 改打 legacy `/api/v1/*` 孿生路徑 | `RequestRejected(403)` | 等價路徑守衛一致 | `api/tests/test_sec_legacy_endpoint_guards.py:29-70`；`scripts/ci/endpoint-guard-audit.py` | 兩條路徑一致 403 |
| 攻擊者 | 用 tech 面 token 打 brand 面服務 | `RequestRejected(403)` | `ALLOWED_TOKEN_PORTALS` | `api/core/deps.py:142-150` | `CROSS_PORTAL_FORBIDDEN`，403 |
| 前端 | 判定未列於 `ROUTE_POLICY` 的路由 | `AccessDenied` | deny-by-default | `web/brand-portal/src/lib/rolePolicy.ts:88` | **相反**：`return true`（放行） |
| 攻擊者 | 打僅掛 `require_tenant` 的寫入端點（8 個） | — | — | 見步驟 4 清單 | 同租戶任一登入角色可通過角色層 |

---

## 逐層走查

### 步驟 1 — 前端路由 gate 的定義與自述定位

`web/brand-portal/src/lib/rolePolicy.ts:1-12`：

```ts
/**
 * rolePolicy.ts — 前端 route → role 存取政策（CR-0021 §8 Q3）。
 *
 * 單一真相源：AuthGuard（route gate）與 Sidebar（nav 過濾）共用。
 * 以「能否載入頁面」為 gate;唯讀差異（如 cs 看工單）由後端 role_required 把關。
 *
 * 原則：
 *   - admin → 全放行（避免誤擋管理員）。tenant_admin / super_admin 為死角色
 *     （CR-0114 裁決不活化；13_Security §3.1），已自 FULL_ACCESS 移除（SA-06）。
 *   - 未列到的路由 → 預設放行（demo 安全;敏感頁已明列，如 /accounting /admin/roles）。
 *   - 對應表對齊後端 role_required 守衛（前端不比後端寬/嚴，避免 confusing UX）。
 */
```

### 步驟 2 — 前端 gate 的判定函式

`web/brand-portal/src/lib/rolePolicy.ts:74-90`：

```ts
export function canAccessRoute(pathname: string, role: string | null): boolean {
  // CR-0114 平台方 console:必須在 FULL_ACCESS 早退**之前**特例 —— console 只屬
  // platform_admin,品牌 admin 亦不放行
  // (deny-by-default 雙向對稱;放 ROUTE_POLICY 會被下一行早退繞過)。
  // /platform/login 為公開頁,由 AuthGuard PUBLIC_PATHS 承接,不會走到這裡。
  if (pathname === "/platform" || pathname.startsWith("/platform/")) {
    return role === "platform_admin";
  }
  if (!role || FULL_ACCESS_ROLES.has(role)) return true;
  const matches = ROUTE_POLICY.filter(
    (p) => pathname === p.prefix || pathname.startsWith(p.prefix + "/"),
  ).sort((a, b) => b.prefix.length - a.prefix.length);
  if (matches.length === 0) return true; // 未列到 → 放行
  return matches[0].roles.includes(role);
}
```

第 82 行對 `role` 為 `null` 時亦 `return true`。第 88 行為未列到路由的分支。唯一 deny-by-default 的分支是 `/platform` 前綴（第 80 行）。

TC 判定基準寫「未登記路由 deny-by-default」（出處 `smartlock-docs/enterprise/20_Test_Cases.md:336`）／前端 `canAccessRoute` 在 `web/brand-portal/src/lib/rolePolicy.ts:88` 對未登記路由 `return true`。此處僅並陳，不裁定。

### 步驟 3 — 前端 gate 的執行位置

`web/brand-portal/src/components/layout/AuthGuard.tsx:1-11`：

```tsx
"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { auth, bootstrapSession, getCurrentSession } from "@/lib/api";
import { crossModeRedirect } from "@/lib/appMode";
import { canAccessRoute, fallbackRouteForRole } from "@/lib/rolePolicy";
```

其判定在 `useEffect` 內執行（`AuthGuard.tsx:57-`），未登入時導向登入頁（`AuthGuard.tsx:76-79`）：

```tsx
    if (!session && !isPublic) {
      void bootstrapSession()
        .then((restored) => {
          if (!restored) {
            router.replace(
              pathname.startsWith("/platform") ? "/platform/login" : "/login",
            );
```

`web/` 四站台目錄下無 `middleware.ts`：

```
$ find web -name "middleware.ts" -not -path "*/node_modules/*"
（無輸出）
```

### 步驟 4 — 後端守衛的覆蓋度

`api/core/deps.py:307-336` 為唯一的角色強制點（見 TC-SEC-RBAC-01 步驟 1）。以與 `scripts/ci/endpoint-guard-audit.py:26-28` 相同的裝飾器切分規則普查 `api/routers/*.py`（探針腳本寫於 scratchpad，**不在 repo 內**）：

```
== 全部端點守衛分佈 == 517
  role                 383
  tenant_only          47
  platform_admin       45
  no_dep               29
  s2s                  8
  authenticated_only   4
  keeper               1
```

其中僅掛 `require_tenant` 的寫入端點 8 條：

```
  [tenant_only] PATCH  /tenants/{tenantId}/devices/{deviceId}/warranty   (device_warranty.py)
  [tenant_only] PATCH  /notifications/{id}                               (notifications.py)
  [tenant_only] POST   /notifications/bulk                               (notifications.py)
  [tenant_only] POST   /notifications/mark-all-read                      (notifications.py)
  [tenant_only] PATCH  /tenants/{tenantId}/notifications/{notificationId}(notifications_v2.py)
  [tenant_only] POST   /tenants/{tenantId}/notifications:bulk            (notifications_v2.py)
  [tenant_only] POST   /tenants/{tenantId}/notifications:mark-all-read   (notifications_v2.py)
  [tenant_only] POST   /tenants/{tenantId}/work-orders:search            (work_orders_v2.py)
```

29 條無認證依賴的端點全部為 login / refresh / register / password-reset / webhook / consumer 簽章 token / 公開申請類（清單見 TC-SEC-RBAC-01 步驟 2）。

### 步驟 5 — 等價路徑繞道的守門

`api/tests/test_sec_legacy_endpoint_guards.py:1-13` 記載此類繞道的形態：

```python
"""CR-0183 補漏（2026-07-27）：legacy `/api/v1` 孿生端點與明細/stats 的角色守衛。

**發現**：CR-0183 為 v2 tenant-scoped 端點補了角色守衛，但同義的 legacy `/api/v1`
端點（兩者皆掛載於 main.py）與 v2 自己的 stats／明細端點漏掛 → 低權限角色只要改打
legacy 路徑或明細路徑即可**完全繞過** v2 的守衛，讀到金流（refunds）與 PII（customers）。

驗收：同一個低權限角色打「v2 路徑」與「legacy／明細路徑」必須得到**一致**的 403，
不得有任一條路徑放行（防止「新路徑上鎖、舊路徑沒鎖」這類繞道復發）。
"""
```

CI 稽核腳本 `scripts/ci/endpoint-guard-audit.py:1-14` 檢查兩類不對稱，本次執行：

```
$ python scripts/ci/endpoint-guard-audit.py
✅ 端點守衛稽核：無 v2/legacy 或 list/detail 不對稱
EXIT=0
```

該腳本列有 4 條人工例外（`scripts/ci/endpoint-guard-audit.py:32-40`）：

```python
# 經人工判定的合法例外（Category B：技師於 tech surface 合法讀，CR-0182 已擋跨面）。
# 技師由自己的工單取得問題卡 ID 直接讀明細，不瀏覽 list —— 故 list 有守衛、detail 無，
# 屬刻意設計而非漏洞。新增例外必須在此註明理由。
EXEMPT_DETAIL: set[tuple[str, str]] = {
    ("problem_cards.py", "/problem-cards/{id}"),
    ("problem_cards.py", "/problem-cards/{id}/export"),
    ("problem_cards_v2.py", "/problem-cards/{id}"),
    ("problem_cards_v2.py", "/problem-cards/{id}/export"),
}
```

### 步驟 6 — 跨面 token 的攔截

`api/core/deps.py:137-150`：

```python
    # CR-0182（UAT-0723-F2）：跨面守衛。缺 portal 的 token（部署後 1h 內舊 access token、
    # 或 SSO token——oidc.verify_oidc_token 不經 create_token）由 role 即時推導（braces）。
    # portal 為 None（空/未知 role）或不在本服務允許集 → 403，不落最敏感的 brand。
    # 掛在 get_current_user 單點即涵蓋所有受保護 HTTP 端點（含 F2 目標 bare require_tenant）。
    # 範圍＝HTTP-only；WS 授權由 verify_ws_token/authorize_channel 另行把關。
    _allowed = _allowed_portals()
    if _allowed is not None:
        portal = payload.get("portal") or portal_for_role(token_role)
        if portal not in _allowed:
            raise ApiError(
                error_code="CROSS_PORTAL_FORBIDDEN",
                message="Token is not valid for this service surface",
                status_code=403,
            )
```

啟用條件為環境變數 `ALLOWED_TOKEN_PORTALS` 非空（`api/core/deps.py:39-43`）；`api/core/deps.py:36-38` 註解記載 env 未設時不強制，並說明雲端三服務各自顯式設定。

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

```
cd api && POSTGRES_URI=<本機測試庫> PYTHONPATH=<scratchpad> uv run pytest \
  tests/test_cr_0092_rbac_hardening.py tests/test_cr_0130_rbac_enforce.py \
  tests/test_rbac_role_isolation.py tests/test_rbac_dynamic.py \
  tests/test_rbac_v2_endpoint.py tests/test_sec_legacy_endpoint_guards.py \
  tests/test_cr_0111_rbac_approve_roles.py tests/test_cr_0111_has_permission_shadow.py \
  -p winloop_plugin -q
1 failed, 78 passed in 6.04s
```

唯一失敗項 `test_sec_legacy_endpoint_guards.py::test_endpoint_guard_audit_clean` 的失敗原因是以 `python3` 呼叫子行程（`api/tests/test_sec_legacy_endpoint_guards.py:175-183`），Windows 本機無此執行檔（回傳碼 9009）；同腳本以 `python` 執行為 exit 0。

`api/tests/test_auth_guards.py:10-22` 覆蓋「無 token → 401」與「壞 token → 401」：

```python
async def test_missing_authorization_returns_401(client):
    res = await client.get("/api/v1/work-orders")
    assert res.status_code == 401


async def test_invalid_token_returns_401(client):
    res = await client.get(
        "/api/v1/work-orders",
        headers={"Authorization": "Bearer not-a-jwt", "X-Tenant-ID": "00000000-0000-0000-0000-000000000001"},
    )
    assert res.status_code == 401
```

---

## 事實結論

1. 前端路由 gate 由 client component `AuthGuard` 呼叫 `canAccessRoute` 執行（`web/brand-portal/src/components/layout/AuthGuard.tsx:1`、`web/brand-portal/src/lib/rolePolicy.ts:74`）；`web/` 四站台無 `middleware.ts`，該 gate 不在伺服器端執行。
2. `web/brand-portal/src/lib/rolePolicy.ts:5` 自述唯讀差異「由後端 role_required 把關」。
3. `canAccessRoute` 對未列於 `ROUTE_POLICY` 的路由回 `true`（`web/brand-portal/src/lib/rolePolicy.ts:88`），對 `role` 為 `null` 亦回 `true`（`:82`）；唯一 deny-by-default 分支為 `/platform` 前綴（`:80`）。
4. 後端角色強制點為 `role_required`（`api/core/deps.py:307-336`），517 個 route handler 中 383 個掛載。
5. 未掛角色守衛者：47 個僅 `require_tenant`（其中寫入 8 條）、4 個僅 `get_current_user`、29 個無認證依賴（login／webhook／consumer token 類）、45 個 `require_platform_admin`、8 個 S2S、1 個 keeper。
6. v2／legacy 與 list/detail 的守衛對稱性由 `scripts/ci/endpoint-guard-audit.py` 稽核，本次執行 exit 0，另有 4 條人工例外登記於腳本內（`:35-40`）。
7. 跨面 token 守衛 `CROSS_PORTAL_FORBIDDEN` 掛在 `get_current_user`（`api/core/deps.py:142-150`），僅在 `ALLOWED_TOKEN_PORTALS` 非空時生效。
