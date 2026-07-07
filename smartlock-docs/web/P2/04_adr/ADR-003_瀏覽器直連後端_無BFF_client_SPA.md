# ADR-003: 瀏覽器直連後端，無 BFF；掛在 App Router 上的 client SPA

## 狀態

**已接受（記錄現況）** | 2026-07-07

> 本 ADR 為現況（as-is）決策記錄。固化「無 BFF / 無 server component、瀏覽器直連 api」的動機與代價。此決策是 web 安全缺口的架構根源，須誠實記載。

---

## 背景與問題

Next.js App Router 提供兩種可讓前端「不直接把後端暴露給瀏覽器」的機制：

- **Server Components（RSC）**：在 server 端抓資料、渲染，只把 HTML/最小 JS 送瀏覽器。
- **Route Handlers / BFF**：`src/app/api/*` 作為同源代理，注入認證、隱藏 token、集中錯誤轉換（如 acme 的 `/api/[...slug]`）。

web **兩者皆未採用**：

- `src/app` 內 `export default async` 零命中——**無 async server component 抓資料**；全部 94 個 `page.tsx` 標 `"use client"`。
- `find src/app -name route.ts` 零命中——**無 BFF / route handler**。

結果：web 是**掛在 App Router 檔案系統路由之上的 client-side SPA**，瀏覽器**直連後端 api**（`lib/api.ts` 從瀏覽器直接 fetch 到 :8001/:8002/:8003）。本 ADR 記錄此決策。

---

## 考量的選項

### 選項 A：RSC + BFF（Next 官方推薦）
| 面向 | 評估 |
|---|---|
| 優點 | token 可存 httpOnly cookie、在 server 端用；敏感抓取移 server；首屏 SSR；BFF 集中認證/錯誤/rate limit；前端可成安全邊界 |
| 缺點 | 需區分 server/client component（心智負擔）；BFF 多一層 hop；串流代理需處理 Web Streams |
| 風險 | 中（架構複雜度）|

### 選項 B：純 client SPA + BFF（有 BFF 無 RSC）
| 面向 | 評估 |
|---|---|
| 優點 | 保留 client 心智；BFF 仍可隱藏 token / 集中認證 |
| 缺點 | BFF 一層要維護；仍無 SSR 首屏 |
| 風險 | 低-中 |

### 選項 C：純 client SPA，瀏覽器直連後端，無 BFF【選定】
所有頁 client component；`lib/api.ts` 從瀏覽器直接打後端；token 存 localStorage；錯誤格式相容轉換在 client（`lib/apiError.ts`）。
| 面向 | 評估 |
|---|---|
| 優點 | 最單純：無 server/client 邊界、無 BFF hop；一份 fetch client 打天下；開發快 |
| 缺點 | token/tenant 全暴露瀏覽器（localStorage）；授權無法在 web 端 enforce；無 SSR 首屏；CORS 依賴後端設定 |
| 風險 | 高（安全）|

---

## 決策

**選擇選項 C：純 client SPA + 瀏覽器直連後端，無 BFF。**

具體：

- **無 RSC**：全部 `page.tsx` 為 `"use client"`；資料在頁面掛載後於瀏覽器抓（`useEffect` + `api.get`）。
- **無 BFF**：`lib/api.ts` 的 `rawRequest`（`api.ts:280-339`）直接 `fetch(buildUrl(path))`，base = `NEXT_PUBLIC_API_BASE_URL`（瀏覽器直連後端 host）。
- **認證在 client**：token 存 localStorage（`api.ts:109-118`）；header 注入 Bearer + X-Tenant-ID（`api.ts:288-292`）；401 refresh 在 client（`api.ts:316-324`）。
- **錯誤轉換在 client**：`ApiError` 相容 RFC7807 / legacy（`api.ts:45-86`），友善訊息在 `lib/apiError.ts`。
- **客戶公開頁**：`/track /quotes /consent /scope-change` 各自 inline 讀 `NEXT_PUBLIC_API_BASE_URL` 直打 public 端點（未登入，不經 api client）。

**選擇理由**：本階段以開發速度與心智單純為先——無 server/client 邊界、無 BFF 維護。後端 api 已有 `role_required` 作為授權主防線，故前端不做真正 gate（gate 只為 UX）。此決策讓前端保持「純消費層」定位。

---

## 後果

### 正面收益
- 最單純的前端心智：所有東西在瀏覽器跑，一份 fetch client。
- 無 BFF 層維護、無 server/client component 分類負擔、無串流代理複雜度。
- 開發與 debug 直接（瀏覽器 devtools 看完整請求）。

### 負面代價（誠實記載 — 這是 web 安全缺口的架構根源）
- **token 全暴露瀏覽器**：localStorage 存 access/refresh token（`api.ts:109-118`），**XSS 可竊**（見 P3-13 B-03，頭號問題）。改 httpOnly cookie 需要 BFF 或 server 端才能用。
- **授權無法在 web enforce**：client-side gate（appMode/rolePolicy）只是 UX，未授權頁 bundle 仍下載，可直接呼叫 api 繞過（見 P3-13 C-03）。真正授權完全依賴後端。
- **多租戶 fallback 在 client**：無 tenant 靜默退 1 號租戶（`api.ts:120-135`，資料外洩 TODO），server 端無法攔截。
- **無 SSR 首屏**：首屏靠 client bundle 下載 + 執行，白屏窗口較 RSC 大；SEO 不適用（後台系統影響小）。
- **CORS 依賴後端**：瀏覽器直連跨 origin，須後端正確設 CORS。
- **JWT 走 WS query param**：因無 BFF 中轉，WS 認證只能 query param（`realtime.ts:67-68`），token 可能被反代 log。

### 影響範圍
- **受影響檔案**：`src/lib/api.ts`（fetch client）、`realtime.ts`/`sse.ts`（直連 WS/SSE）、全部 `page.tsx`（client component）、token 公開頁。
- **對齊平台**：對應平台 L1 缺口 G-11「前端認證全 client-side」（`00_platform/P1/05` §5）。

### 重新評估觸發條件（強）
- **安全要求升級**：需消除 XSS 竊 token / 讓授權成為前端可信邊界 → 導入 BFF（httpOnly cookie）+ server-side gate（見 P3-13 ACT-01/ACT-05）。
- 需要 SSR 首屏 / 降 client bundle → 導入 RSC。
- 需要集中 rate limiting / 請求日誌 / SSRF 防護 → BFF 層。

---

## 執行計畫（現況已落地 + 後續遷移路徑）

1. **已落地**：`lib/api.ts` 直連 fetch client、401 refresh、client 錯誤轉換、token 公開頁 inline fetch。
2. **後續遷移路徑（與 ADR-001 build-time 烤入、P3-13 安全連動）**：
   - Step 1：抽薄 BFF（Next route handler）承接 login/refresh，token 改 httpOnly cookie（server 端寫）。
   - Step 2：路由保護改 Next middleware / RSC 在 server 端驗簽 + gate（deny-by-default）。
   - Step 3：敏感資料抓取逐頁移 RSC；client 只保留互動狀態。
   - 每步走 CIA（涉及認證/授權/契約邊界）。

---

## 選用影響區段

### 架構影響
- 無新增 Container（單一 Next runtime）。影響 L3：**無 BFF/route.ts 元件、無 server component 抓取**（P1-05 §5）；ACL 缺席（P1-05 §6.1 標「無 ACL」）。
- 若未來導入 BFF，新增 route handler 層，token 處理點從 client 移 server。

### 部署影響
- 無新增服務；瀏覽器直連後端須後端 CORS 正確、published port 對外可達（本機 :8001/:8002/:8003；雲端 api https 網域）。
- 同步更新：P1-05 §4（無 BFF 直連）、P2-06 §1.5、P3-13 B/C 節、ADR-001（build-time env 為直連 base 來源）。
</content>
