# ADR-001: 單一 codebase 以 APP_MODE build 出多個 portal

## 狀態

**已接受（記錄現況）** | 2026-07-07

> 本 ADR 為現況（as-is）決策記錄，非新提案。用於固化「一份 codebase → 4 portal」機制的動機、取捨與代價，供後續演進評估。

---

## 背景與問題

Smart Lock 平台需要對外提供多個角色差異極大的前端：品牌營運後台（dispatch）、師傅工作台（tech，PWA）、平台方 console（platform）、導入行銷頁（landing）。這些前端：

- 服務不同角色、連不同的 api surface（dispatch :8001 / tech :8002 / platform :8003）。
- 各自對外獨立 origin、獨立 port（3000 / 3001 / 3003 / 3002），token 需隔離。
- 但**共用大量元件、gate 邏輯、api client、即時訂閱、設計系統**。

若拆成 4 個獨立 repo / 獨立 Next 專案，共用邏輯會複製 4 份，維護與一致性成本高（gate 漂移、UI 不一致、型別重複）。本 ADR 記錄實際採用的解法。

---

## 考量的選項

### 選項 A：4 個獨立前端專案
| 面向 | 評估 |
|---|---|
| 優點 | 各 portal 完全隔離、可獨立演進、bundle 最小 |
| 缺點 | 共用元件/gate/api client 複製 4 份；一致性靠人工紀律；型別/設計系統重複維護 |
| 風險 | 高（長期漂移）|

### 選項 B：Monorepo + 共用套件（如 turborepo + packages/ui）
| 面向 | 評估 |
|---|---|
| 優點 | 共用邏輯集中在 package，各 app 獨立 build |
| 缺點 | 需引入 monorepo 工具鏈；4 個 app 殼仍要維護；overkill for 現階段規模 |
| 風險 | 中（工具鏈成本）|

### 選項 C：單一 codebase + build-time 旗標塑形【選定】
一份 Next.js codebase，用 `NEXT_PUBLIC_APP_MODE` 在 build 時決定「這個 build 是哪個 portal」，client-side gate（`crossModeRedirect`）決定放行哪些頁群，其餘導向對方 portal。
| 面向 | 評估 |
|---|---|
| 優點 | 零程式碼重複；元件/gate/api client/型別/設計系統單一真相源；一份 Dockerfile 換 ARG 即出 4 portal |
| 缺點 | 所有 portal 的頁 bundle 都在同一 codebase（未 code-split 到 portal 粒度）；env build-time 烤入 → 每環境每 portal 重 build；gate 為 client-side（非安全邊界）|
| 風險 | 中 |

---

## 決策

**選擇選項 C：單一 codebase + `NEXT_PUBLIC_APP_MODE` 塑形。**

具體機制（`src/lib/appMode.ts`）：

- `APP_MODE = process.env.NEXT_PUBLIC_APP_MODE || "all"`（`appMode.ts:11`），型別 `all|dispatch|tech|landing|platform`（`appMode.ts:9`），非白名單退 `all`。
- `crossModeRedirect(pathname)`（`appMode.ts:65-98`）：判定當前 build 是否服務此路徑，否則回傳導向目標（站內路由或對方 portal 絕對 URL）。`all` 模式恆 `null`（單庫零行為變化）。
- 由 root layout 的 AuthGuard 呼叫（`AuthGuard.tsx:49`），**無 Next.js middleware**（gate 全 client-side）。
- 4 個 compose 用**同一份 `web/Dockerfile`**，只換 build ARG（`APP_MODE` + API base + 跨端 `*_PORTAL_URL`）。

**選擇理由**：本階段 4 portal 共用邏輯遠大於差異，單 codebase 讓 gate / api client / 型別 / 設計系統維持單一真相源；`all` 模式確保「未設 env 時零行為變化」，讓單庫部署與多 portal 部署共存。相較 monorepo，省去工具鏈成本。

---

## 後果

### 正面收益
- 共用元件、gate、api client、`types/api.generated.ts`、設計系統零重複，一致性內建。
- 一份 Dockerfile → 4 portal，build/部署腳本統一。
- `all` 模式（預設）= 單庫同時服務所有頁，開發與 demo 便利。
- 新增 portal 只需擴 `AppMode` 型別 + `crossModeRedirect` 分支，無新專案。

### 負面代價（誠實記載）
- **build-time env 烤入**：8 個 `NEXT_PUBLIC_*` 於 `next build` 烤進 bundle（`Dockerfile:44-73`），standalone 後不可改。**同一 image 無法 runtime 切 API base / portal URL；每環境每 portal 各一 build**。改後端網域須 rebuild 全部 web image。
- **gate 為 client-side，非安全邊界**：`crossModeRedirect` 在瀏覽器跑，未授權 portal 的頁 bundle 仍下載到瀏覽器，僅靠 client redirect 擋（見 P3-13 C-03）。分站是 UX 隔離，不是安全隔離。
- **無 portal 粒度 code-split**：dispatch build 的 bundle 仍含全部頁的程式碼（tree-shake 後，但未按 portal 切）。
- **跨端連結靠絕對 URL 烤入**：`PEER/TECH/DISPATCH/PLATFORM_PORTAL_URL` 需正確配置，漏配則退回站內路由（可能導錯）。

### 影響範圍
- **受影響檔案**：`src/lib/appMode.ts`（gate 核心）、`src/components/layout/AuthGuard.tsx`（呼叫點）、`src/app/page.tsx`（landing/tech 分歧）、`web/Dockerfile`（ARG）、4 個 `docker-compose.*.yml`。
- **對齊平台**：對應平台通用語言「APP_MODE」「portal / 部署面」（`00_platform/P1/05` §7）。

### 重新評估觸發條件
- portal 數量或差異顯著增長，單 codebase bundle 過大 → 評估 monorepo + 共用 package。
- 需要 runtime 切環境（消除 build-time 烤入僵化）→ 導入 runtime env 注入（`__ENV.js` / 反代改寫）。
- gate 需成為真正安全邊界 → 見 ADR-003（BFF / server-side gate）。

---

## 執行計畫（現況已落地 + 後續）

1. **已落地**：`appMode.ts` gate、4 compose build ARG、`all` 模式零行為變化、跨端 CTA href 集中解析（`techRegisterHref`/`dispatchLoginHref`/`brandApplyHref`）。
2. **後續**：補 `crossModeRedirect` 4 mode × 邊界路徑單元測試；評估 runtime env 注入以解 build-time 烤入。

---

## 選用影響區段

### 架構影響
- 無新增 Container：4 portal 為同一 `smartlock-admin` 容器換 APP_MODE（P1-05 §4 L2）。影響的是 build 產物與 client gate 行為，非容器數量。

### 部署影響
- **一份 Dockerfile → 4 build**（`Dockerfile` 三階段共用）。每 portal 一次 build，env 烤入。雲端為單一 `smart-lock-web`（`all`/monolith），本機才拆 4 portal（對應平台 L1 缺口 G-01 拓撲不對稱）。
- 同步更新：P1-05 §10 部署視圖、P3-13 D-01/D-02（build-time 曝露）。
</content>
