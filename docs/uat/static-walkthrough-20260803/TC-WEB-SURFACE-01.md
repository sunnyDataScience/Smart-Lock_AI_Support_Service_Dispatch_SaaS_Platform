# TC-WEB-SURFACE-01 — 四站台 build 的路徑白名單與跨站導向

> ## 🔄 判定更正（2026-08-05 回程式碼查證）
>
> **原判定「部分實作」→ 更正為「一致」。以下原文保留未改動。**
>
> 判定基準「只呈現白名單路徑**或**安全導向」是**選言**，兩層機制都齊：
> ①安全導向：`crossModeRedirect` 對四種 APP_MODE 都有完整規則，由 AuthGuard 於 effect 首行呼叫；未配置 PEER/DISPATCH_PORTAL_URL 時退回站內登入頁，不會導到空 URL。
> ②不得載入非本站頁面：四站的 `src/app` 是四棵**實體獨立**的檔案樹，brand-portal 下根本不存在 tech/platform 的頁面檔——沒有「非本站頁面」可載。
> （查證期間另發現 tech-portal 與 platform-console 的 `/auth/sso-complete` 未列入放行清單，導致該兩站 SSO 回跳被自家 guard 擋掉，已於 commit `5b5f7f2a` 修復。）
>
> 更正依據：對本文件引用的每個 `檔案:行號` 逐一開檔覆核、對宣稱「零命中」的識別碼
> 以多種命名寫法重跑 grep。走查基準 commit 與查證當下 HEAD 之間，
> `api/` `agent/` `web/` `SQL/` 原始碼零差異，故原引用仍然有效。
>
> **此更正不需要改動任何 code。**

---

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | 四站台各自的 `src/lib/appMode.ts`、`src/lib/rolePolicy.ts`、`src/components/layout/AuthGuard.tsx`、`src/app/**/page.tsx` 清單、`src/app/not-found.tsx`、`docker-compose.yml`；另 `web/brand-portal/src/lib/serverApiProxy.ts:11-56`、`web/platform-console/src/lib/safeHref.ts:16-36`、`web/platform-console/src/app/page.tsx:8-14` |
| 優先級 / 路徑類型 | P0 / failure |

「本站外路徑」有兩層機制且兩層都存在：**第一層是實體路由裁剪**（四站台 `src/app/` 各自只含自己的 `page.tsx`，landing 只有 `/` 一支），未命中即落 Next 的 `not-found.tsx`；**第二層是 `crossModeRedirect`**（`appMode.ts:64-97`）依 `NEXT_PUBLIC_APP_MODE` 決定導向站內路由或對方 portal 絕對 URL，由 `AuthGuard` 於 effect 首行呼叫（`AuthGuard.tsx:61-69`）。跨站 CTA 集中在 `appMode.ts:102-124` 三個 href helper。判定為「部分實作」的兩個依據：其一，**登入後的角色路由政策是 allow-by-default 而非白名單**——`rolePolicy.ts:83` 明寫「未列到 → 放行」，與 TC 判定基準的「只呈現白名單路徑」在語意上不同；其二，`AuthGuard.tsx:140` 對 `isPublic` 路徑在 effect 執行前即直接回傳 `children`，`crossModeRedirect` 屬 `useEffect` 內的 client 端跳轉，非 server 端阻擋。實際 production-like build 開啟各路徑時畫面上呈現什麼（是否有 404 閃現、導向是否成功）屬執行期觀測，本次未取得。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT） |
| 前置 | dispatch/tech/platform/landing production-like build |
| 步驟 | 各 build 直接開啟本站外路徑、deep link、跨站 CTA 與不存在路徑 |
| 預期結果（判定基準） | 只呈現白名單路徑或安全導向；不得把非本站頁面當已授權內容載入 |
| 路徑類型 | failure |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-WEB-01 |
| 屬於哪條旅程腳本 | SC-12、SC-17 |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:429`。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 四個 build 模式存在 | `appMode.ts:10-16`（`all` / `dispatch` / `tech` / `landing` / `platform`）；compose 各自指定（見步驟 2） | 一致 |
| 本站外路徑有導向 | `appMode.ts:64-97` `crossModeRedirect`；`AuthGuard.tsx:61-69` | 一致 |
| 不存在路徑有落點 | 四站各有 `src/app/not-found.tsx` | 一致 |
| 跨站 CTA 以絕對 URL 外導 | `appMode.ts:102-124`（`techRegisterHref` / `dispatchLoginHref` / `brandApplyHref`） | 一致 |
| 只呈現白名單路徑 | tech build 為顯式白名單（`appMode.ts:46-53` `TECH_BUILD_ALLOWED`）；dispatch build 為黑名單式（`appMode.ts:76-92` 逐條 deny 後 `return null`） | 部分實作 |
| 登入後路由政策為白名單 | `rolePolicy.ts:83` `if (matches.length === 0) return true; // 未列到 → 放行` | 不一致 |
| 不把非本站頁面當已授權內容載入 | 實體路由裁剪（各站 `src/app/` 內容不同）＋ `AuthGuard.tsx:113-119`；但 `:140` 對 `isPublic` 先渲染 | 部分實作 |
| deep link 帶 token 的公開頁 | `AuthGuard.tsx:42-47`（brand）／`:38-44`（tech，多 `/upload-docs/`） | 一致 |

---

## Event Storming

本案例為前端路由行為，無 domain event。改列 build 模式與路徑處置對照：

| build（`NEXT_PUBLIC_APP_MODE`） | 站內實際存在的路由 | 本站外路徑處置 | 程式碼落點 |
|---|---|---|---|
| `dispatch`（brand-portal） | 74 支 `page.tsx`（見步驟 1） | `/` → `/login`；`/platform*` → `/login`；`/tech-register`、`/home`、`/pool`、`/my-orders`、`/account` → `PEER_PORTAL_URL` + 同路徑（未配置則 `/login`）；其餘 `return null`（放行） | `appMode.ts:76-92` |
| `tech`（tech-portal） | 23 支 `page.tsx` | 不在 `TECH_BUILD_ALLOWED` 者 → `PEER_PORTAL_URL` + 同路徑（未配置則 `/tech-login`） | `appMode.ts:46-53`、`:94-96` |
| `landing` | 1 支（`/`） | 非 `/` 一律 → `DISPATCH_PORTAL_URL` + 同路徑（未配置則 `/`） | `appMode.ts:71-75` |
| `platform`（platform-console） | 9 支 `page.tsx` | 非 `/platform*` 一律 → `/platform/login` | `appMode.ts:66-70` |
| `all`（未設 env） | 依該 build 的實體檔案 | `crossModeRedirect` 恆 `null` | `appMode.ts:65` |

---

## 逐層走查

### 步驟 1 — 實體路由清單（四站台各自 build 出的頁面）

```
for d in brand-portal tech-portal landing platform-console; do
  (cd web/$d/src/app && find . -name "page.tsx" | ...)
done
```

| 站台 | `page.tsx` 支數 | 特徵路由 |
|---|---|---|
| brand-portal | 74 | `/dashboard`、`/work-orders*`、`/admin/*`、`/accounting/*`、`/knowledge-base/*`、`/conversations*`、`/problem-cards*`、`/consent/[token]`、`/quotes/[token]`、`/scope-change/[token]`、`/track/[token]`、`/vendor`、`/auth/sso-complete` |
| tech-portal | 23 | `/home`、`/pool*`、`/my-orders*`、`/account*`、`/tech-login`、`/tech-register`、`/upload-docs/[token]`、`/auth/sso-complete` |
| landing | 1 | 只有 `/` |
| platform-console | 9 | `/platform`、`/platform/login`、`/platform/apply`、`/platform/tenants`、`/platform/technicians*`、`/platform/requestors`、`/auth/sso-complete`、`/` |

brand-portal 不含任何 `/home`、`/pool`、`/my-orders`、`/account`、`/platform` 路由；tech-portal 不含任何 `/admin`、`/dashboard`、`/work-orders` 路由；landing 除 `/` 外無任何頁面。四站台的 `src/app/` 是各自獨立的檔案樹，不是同一份程式碼以旗標裁剪。

### 步驟 2 — build 模式如何被設定

```
web/brand-portal/docker-compose.yml:171:        NEXT_PUBLIC_APP_MODE: "dispatch"
web/brand-portal/docker-compose.yml:172:        NEXT_PUBLIC_PEER_PORTAL_URL: "${TECH_PORTAL_URL:-http://localhost:3001}"
web/tech-portal/docker-compose.yml:104:        NEXT_PUBLIC_APP_MODE: "tech"
web/tech-portal/docker-compose.yml:105:        NEXT_PUBLIC_PEER_PORTAL_URL: "${DISPATCH_PORTAL_URL:-http://localhost:3000}"
web/landing/docker-compose.yml:30:        NEXT_PUBLIC_APP_MODE: "landing"
web/platform-console/docker-compose.yml:96:        NEXT_PUBLIC_APP_MODE: "platform"
```

`appMode.ts:8` 的註解說明「NEXT_PUBLIC_* 於 next build 時烤入 bundle(web/Dockerfile ARG),runtime 不可改」；`:12-16` 對未知值退回 `all`：

```ts
const raw = process.env.NEXT_PUBLIC_APP_MODE || "all";
export const APP_MODE: AppMode =
  raw === "tech" || raw === "dispatch" || raw === "landing" || raw === "platform"
    ? raw
    : "all";
```

### 步驟 3 — `crossModeRedirect` 的逐模式邏輯

`web/brand-portal/src/lib/appMode.ts:64-97`

```ts
export function crossModeRedirect(pathname: string): string | null {
  if (APP_MODE === "all") return null;
  if (APP_MODE === "platform") {
    // 平台 console 只服務 /platform 頁群;其餘一律導 console 登入頁。
    if (matchPrefix(pathname, "/platform")) return null;
    return "/platform/login";
  }
  if (APP_MODE === "landing") {
    // 行銷容器只服務 `/`;其餘一律導派工 portal(未配置則回站內首頁)。
    if (pathname === "/") return null;
    return DISPATCH_PORTAL_URL ? `${DISPATCH_PORTAL_URL}${pathname}` : "/";
  }
  if (APP_MODE === "dispatch") {
    ...
    if (pathname === "/") return "/login";
    // /platform 屬平台 console 部署,品牌 build 不服務(deny-by-default 回登入)。
    if (matchPrefix(pathname, "/platform")) return "/login";
    ...
    if (matchPrefix(pathname, "/tech-register")) {
      return PEER_PORTAL_URL ? `${PEER_PORTAL_URL}${pathname}` : "/login";
    }
    if (TECH_APP_PREFIXES.some((p) => matchPrefix(pathname, p))) {
      return PEER_PORTAL_URL ? `${PEER_PORTAL_URL}${pathname}` : "/login";
    }
    return null;
  }
  // tech build(/platform 不在 TECH_BUILD_ALLOWED → 自然導出)
  if (TECH_BUILD_ALLOWED.some((p) => matchPrefix(pathname, p))) return null;
  return PEER_PORTAL_URL ? `${PEER_PORTAL_URL}${pathname}` : "/tech-login";
}
```

`matchPrefix`（`:55-58`）對 `/` 要求完全相等，其餘要求相等或帶 `/` 前綴，因此 `/my-orders-x` 不會被 `/my-orders` 誤匹配：

```ts
function matchPrefix(pathname: string, prefix: string): boolean {
  if (prefix === "/") return pathname === "/";
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}
```

**tech build 為顯式白名單**（`web/tech-portal/src/lib/appMode.ts:46-54`）：

```ts
const TECH_BUILD_ALLOWED = [
  "/",
  "/tech-login",
  "/tech-register", // CR-0115 師傅 KYC 註冊獨立頁
  "/upload-docs", // W3-6 師傅補件連結公開頁(師傅身分歸 tech 站,同 /tech-register)
  "/forgot-password",
  "/reset-password",
  ...TECH_APP_PREFIXES,
];
```

**dispatch build 為逐條 deny 後放行**（`:76-92` 最後 `return null`），非列舉白名單。

四站台 `appMode.ts` 的差異僅三處：landing 與 brand-portal 完全相同（`diff` 無輸出）；tech-portal 多 `/upload-docs` 白名單條目與對應 deny 分支；platform-console 只有註解文字不同。

### 步驟 4 — 導向的執行時機

`web/brand-portal/src/components/layout/AuthGuard.tsx:58-69`

```tsx
  useEffect(() => {
    // CR-0112 雙 stack 拆分:本 build(dispatch/tech)不服務的路由,導向對方
    // portal(絕對 URL 用 window.location,站內用 router)。all 模式恆為 null。
    const crossTarget = crossModeRedirect(pathname);
    if (crossTarget) {
      if (crossTarget.startsWith("http")) {
        window.location.assign(crossTarget);
      } else {
        router.replace(crossTarget);
      }
      return;
    }
```

同檔 `:140-141` 的渲染閘門：

```tsx
  if (isPublic) return <>{children}</>;
  if (!checked) return null;
```

即：非公開路徑在 `checked` 為 true 前渲染 `null`；公開路徑（`AUTH_PAGES` 與 `CUSTOMER_PUBLIC_PREFIXES`，`:27-47`）則在 effect 尚未執行的第一個 render 就輸出 `children`。`crossModeRedirect` 全程在 client 端執行，四站台皆無 `middleware.ts`（`ls web/*/src/middleware.ts web/*/middleware.ts` 無檔案）。

TC 判定基準寫「不得把非本站頁面當已授權內容載入」（出處：`smartlock-docs/enterprise/20_Test_Cases.md:429`）／程式碼在公開路徑上先渲染 `children` 再於 effect 導向（`AuthGuard.tsx:140`、`:61-69`），且該路徑在各 build 中多半沒有對應 `page.tsx`、落到 `not-found.tsx`。此處僅並陳，不裁定。

### 步驟 5 — 不存在路徑的落點

四站台各有 `src/app/not-found.tsx`。brand-portal 版本（`web/brand-portal/src/app/not-found.tsx:20-48`）為 Server Component，顯示 404 文案與兩個 action：

```tsx
        <h1 className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">
          頁面不存在
        </h1>
...
          <Link
            href="/dashboard"
```

`not-found.tsx` 渲染在 root layout 內，因此仍會經過 `AuthGuard`（`layout.tsx:84` 一帶）。

platform-console 的根路徑另有一支專用重導頁（`web/platform-console/src/app/page.tsx:8-14`）：

```tsx
export default function PlatformRootRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/platform/login");
  }, [router]);
  return null;
}
```

### 步驟 6 — 跨站 CTA

`web/brand-portal/src/lib/appMode.ts:102-124`

```ts
export function techRegisterHref(): string {
  const base =
    APP_MODE === "landing"
      ? TECH_PORTAL_URL
      : APP_MODE === "dispatch"
        ? PEER_PORTAL_URL
        : "";
  // CR-0115：師傅註冊改獨立多步驟頁 /tech-register（原 /tech-login?tab=register 退場）
  return `${base}/tech-register`;
}

// 派工方登入入口:landing → DISPATCH_PORTAL_URL;其餘 → 站內 /login。
export function dispatchLoginHref(): string {
  const base = APP_MODE === "landing" ? DISPATCH_PORTAL_URL : "";
  return `${base}/login`;
}

// 品牌/經銷/鎖店「申請導入平台」入口:landing → PLATFORM_PORTAL_URL 的
// /platform/apply(公開頁,平台方管);平台站內本身用相對路徑;其餘部署退回站內。
export function brandApplyHref(): string {
  const base = APP_MODE === "landing" ? PLATFORM_PORTAL_URL : "";
  return `${base}/platform/apply`;
}
```

三個 base URL 皆由 `NEXT_PUBLIC_*` env 取得並去尾斜線（`:20-40`）；`PLATFORM_PORTAL_URL` 有硬編預設值 `http://localhost:3003`（`:39`），其餘兩者未配置時為空字串、退回站內相對路徑。

外部使用者可控字串進 `<a href>` 的路徑另有 scheme 白名單（`web/platform-console/src/lib/safeHref.ts:17`、`:22-35`）：

```ts
/** 只有這兩個 scheme 可以進 href。其餘（javascript: / data: / vbscript: …）一律擋。 */
const ALLOWED_PROTOCOLS = new Set(["http:", "https:"]);
```

該檔僅存在於 platform-console（`web/{brand-portal,tech-portal,landing}/src/lib/safeHref.ts` 不存在）。

### 步驟 7 — 登入後的路由政策

`web/brand-portal/src/lib/rolePolicy.ts:71-85`（四站台此檔 `diff` 完全相同）

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

檔頭 `:10` 自述「未列到的路由 → 預設放行（demo 安全;敏感頁已明列，如 /accounting /admin/roles）」。`/platform` 為唯一 deny-by-default 的前綴（`:76-78`）；`role` 為 `null` 時亦放行（`:79`）。

TC 判定基準寫「只呈現**白名單**路徑」／`rolePolicy.ts:83` 為 allow-by-default。此處僅並陳，不裁定。

### 步驟 8 — 各 build 內「自己不服務卻仍 build 出來」的頁面

- tech-portal 有 `/auth/sso-complete` 的 `page.tsx`，但 `TECH_BUILD_ALLOWED`（`web/tech-portal/src/lib/appMode.ts:46-54`）不含該路徑，且該站 `AuthGuard` 的 `PUBLIC_PATHS`（`web/tech-portal/src/components/layout/AuthGuard.tsx:26-37`）亦不含（brand-portal 版在 `:38` 有這一條）。依 `appMode.ts:94-96`，該路徑會被導向 `PEER_PORTAL_URL` + 同路徑。
- platform-console 同樣有 `/auth/sso-complete`，`platform` 模式下依 `appMode.ts:66-70` 導向 `/platform/login`。
- brand-portal 有 `/` 的 `page.tsx`，但 dispatch 模式下 `appMode.ts:80` 直接導 `/login`；該行註解記載「2026-07-05 業主裁決:消除 3000 與 3002 landing 重複」。

### 步驟 9 — API proxy 路由

四站台皆有 `src/app/api-proxy/` 與 `src/app/platform-api-proxy/`，共用 `serverApiProxy.ts`。`web/brand-portal/src/lib/serverApiProxy.ts:16-23`

```ts
  const base = process.env[targetEnv]?.trim();
  if (!base || !/^https?:\/\//.test(base)) {
    return Response.json(
      { error_code: "API_PROXY_NOT_CONFIGURED", message: `${targetEnv} is required` },
      { status: 503 },
    );
  }
  const target = new URL(path.map(encodeURIComponent).join("/"), `${base.replace(/\/+$/, "")}/`);
```

`targetEnv` 為 `"API_BASE_URL" | "PLATFORM_API_BASE_URL"` 兩個字面量之一（`:14`），path segment 逐段 `encodeURIComponent` 後以 base 為相對基準組 URL；`redirect: "manual"`（`:37`）。

---

## 既有測試證據

- `git grep -rln "crossModeRedirect\|APP_MODE" -- web/*/tests` 零命中，四站台皆無針對 build 模式路由的測試。
- brand-portal e2e 共 36 支 spec（`admin/` 34、`public/` 2）。其中 `404` 的命中皆為 API 回應層：`admin/customers.spec.ts:220-242`（route mock 回 404 後看頁面 not-found 狀態）、`admin/work-orders-v2.spec.ts:200/229`（同型）、`admin/login.spec.ts:6`（`/login` 路徑可達，無 5xx / 404）、`admin/all-buttons-audit.spec.ts:81` 等三支的 console 訊息過濾。無「本站外路徑 / 跨站 CTA / build 模式」的案例。
- `web/brand-portal/tests/unit/serverApiProxy.test.ts` 存在，為 API proxy 的單元測試。
- 四站台 `node_modules` 均未安裝，本次未實跑任何前端測試。

---

## 事實結論

1. 四站台的 `src/app/` 為四棵獨立檔案樹，頁面數分別為 74 / 23 / 1 / 9 支 `page.tsx`。
2. `crossModeRedirect`（`appMode.ts:64-97`）是唯一的跨 build 路徑判定函式，四站台各有一份，差異僅 tech-portal 的 `/upload-docs` 與註解文字。
3. tech build 用顯式白名單 `TECH_BUILD_ALLOWED`（`appMode.ts:46-54`）；dispatch build 為逐條 deny 後 `return null`（`:76-92`）；landing 只放行 `/`（`:71-75`）；platform 只放行 `/platform*`（`:66-70`）。
4. 導向全部發生在 `AuthGuard` 的 `useEffect` 內（`AuthGuard.tsx:61-69`），四站台皆無 `middleware.ts`。
5. `AuthGuard.tsx:140` 對 `isPublic` 路徑在 effect 執行前即回傳 `children`；非公開路徑則回傳 `null`（`:141`）。
6. 未配置 `PEER_PORTAL_URL` / `DISPATCH_PORTAL_URL` 時，導向退回站內路徑（`appMode.ts:74`、`:87`、`:90`、`:96`）。
7. `PLATFORM_PORTAL_URL` 有硬編預設 `http://localhost:3003`（`appMode.ts:39`）。
8. 登入後的角色路由政策為 allow-by-default（`rolePolicy.ts:83`），唯一 deny-by-default 前綴是 `/platform`（`:76-78`）；四站台此檔內容完全相同。
9. 四站台各有 `not-found.tsx`；platform-console 另有根路徑重導元件（`page.tsx:8-14`）。
10. 跨站 CTA 集中於三個 helper（`appMode.ts:102-124`），皆以 env 提供的絕對 URL 為前綴。
11. `safeHref`（scheme 白名單）僅存在於 platform-console。
12. 無任何既有測試覆蓋 build 模式的路由行為。
13. production-like build 實際開啟各路徑後的畫面（是否 404 閃現、導向是否落到對方 portal）屬執行期觀測，本次未取得。
