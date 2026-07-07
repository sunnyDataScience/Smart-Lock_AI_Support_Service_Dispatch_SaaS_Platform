---
title: "ADR-024: web 為 client SPA（無 BFF）+ React Context 狀態 + OIDC 認證"
version: 1.0
status: active
owner: web 系統 tech lead
last-updated: 2026-07-07
upstream:
  - smartlock-docs/web/P2/04_adr/ADR-002_純React_Context_不用狀態管理庫.md
  - smartlock-docs/web/P2/04_adr/ADR-003_瀏覽器直連後端_無BFF_client_SPA.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P003_Casdoor_統一IdP_租戶_License.md
---

# ADR-024: web 為 client SPA（無 BFF）+ React Context 狀態 + OIDC 認證

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 系統級（web）|
| 關聯 ADR | [ADR-023](./ADR-023_單一codebase_APP_MODE多portal.md) · [ADR-004](./ADR-004_Casdoor統一IdP租戶License.md) · [ADR-005](./ADR-005_四方RBAC模型與enforce.md) |

## Context（背景與問題）

web 是後台營運系統（非 SEO 導向），需要決定三件事：(1) 前端形態——RSC / BFF / 純 client SPA；(2) 狀態管理——是否引入 redux / react-query 類套件；(3) 認證——token 如何取得與儲存。目標是開發速度與心智單純，同時不把授權與 token 安全押在前端。

## Decision（決策）

### 形態：掛在 App Router 上的 client SPA，資料 API 瀏覽器直連

- 全部頁面 `"use client"`；資料在頁面掛載後於瀏覽器抓（`useEffect` + `api.get`）。
- **無資料代理 BFF**：`lib/api.ts` 的 fetch client 直接打後端（base = `NEXT_PUBLIC_API_BASE_URL`）；錯誤轉換在 client（`ApiError` 相容 RFC7807 / legacy）。
- 前端定位為**純消費層**：授權主防線在 api 每端點 RBAC（[ADR-005](./ADR-005_四方RBAC模型與enforce.md)）；前端 gate（appMode / rolePolicy）只為 UX。
- 客戶公開頁（`/track` `/quotes` `/consent` `/scope-change`）直打 public 端點（未登入，不經 api client）。

### 認證：Casdoor OIDC 授權碼流 + httpOnly cookie

- 登入走 **OIDC 授權碼流**（Casdoor，[ADR-004](./ADR-004_Casdoor統一IdP租戶License.md)）；token 由**薄認證回調 handler** 寫入 **httpOnly cookie**（JS 不可讀），前端不自解 token、不持有簽章驗證責任。
- 路由 gate 讀 OIDC role claim，**deny-by-default**；401 refresh 由 client 統一觸發。
- 薄認證回調是唯一的 server-side handler——**不是**全功能 BFF，資料 API 仍瀏覽器直連。

### 狀態：純 React Context + 自製 hooks + 自製 cache（零狀態庫）

- **全域 UI 狀態**：4 個 Context Provider（Theme → Locale → Toast → AuthGuard），Sidebar Context 掛認證後 subtree。
- **資料抓取**：`lib/api` fetch client + `usePaginatedFetch` / `useBroadcast` / `useRealtimeChannel`。
- **快取 / 去重**：`lib/cache.ts`——GET 共享 in-flight promise + 30s staleTime，key = `GET:${fullUrl}:${tenant}`；mutation 後廣域 `cacheInvalidate("GET:")`。
- **跨 tab 同步**：BroadcastChannel；登出走 `storage` 事件。
- 不引入 redux / zustand / react-query / swr——WS 訂閱、401 refresh、GET 去重已由 lib 層集中封裝，引入套件只增依賴與樣板。

## Alternatives（考量的選項）

- **A：RSC + 全功能 BFF** — token 治理最強、可 SSR；但 server/client 邊界心智負擔 + BFF hop + 串流代理複雜度，對後台系統收益有限。
- **B：client SPA + 全功能 BFF** — BFF 一層要維護，仍無 SSR 收益。
- **C：client SPA 直連 + OIDC httpOnly cookie + 薄認證回調（採用）** — 心智最單純；token 安全交給 OIDC 流與 cookie，授權交給後端。
- **狀態庫選項**：Redux Toolkit + Saga（樣板重、過度工程）/ react-query（與自製 cache 重疊）均不採。

## Consequences（後果）

**正面**：一份 fetch client 打天下、開發與 debug 直接；token 不落 localStorage、JS 不可讀；零狀態庫依賴，bundle 小、心智單純。
**風險**：
- CORS 依賴後端正確設定（瀏覽器跨 origin 直連）。
- WS 認證經 query param 傳遞（瀏覽器 WS 不支援 custom header）→ 反代 log 需遮罩。
- 快取失效粗粒度（廣域清除非 per-entity）；抓取樣板部分重複；無狀態 devtools。
- 無 SSR 首屏（後台系統影響小）。
**影響範圍**：`src/lib/{api,cache}.ts`、`realtime.ts` / `sse.ts`、認證回調 handler、全部 page。
**重評觸發**：需要精準快取失效 / 複雜跨頁狀態 → react-query 或 zustand 逐頁遷移（保留 `lib/api` 作 fetcher）；需要 SSR 首屏 / 集中 rate limiting → 導入 RSC / 全功能 BFF；每步涉認證 / 授權 / 契約邊界者走 CIA。

## Status 附註

- 🔜 規劃中：OIDC 授權碼流 + httpOnly cookie 接線（隨 Casdoor 部署，[ADR-004](./ADR-004_Casdoor統一IdP租戶License.md)）；`lib/cache.ts` 與 401 refresh 單元測試。
