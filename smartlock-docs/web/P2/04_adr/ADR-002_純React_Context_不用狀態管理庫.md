# ADR-002: 純 React Context + 自製 hooks，不用狀態管理/資料抓取庫

## 狀態

**已接受（記錄現況）** | 2026-07-07

> 本 ADR 為現況（as-is）決策記錄。固化「不引入 redux/zustand/react-query/swr」的動機與代價。

---

## 背景與問題

web 需要管理兩類前端狀態：

1. **全域 UI 狀態**：主題（深/淺）、語系、Toast 通知、Sidebar 開合。
2. **伺服器資料狀態**：列表分頁、快取、去重、即時更新——大量頁面 `useEffect` + fetch。

主流做法會引入狀態管理庫（Redux Toolkit + Saga，如 acme-pro-web）或資料抓取庫（react-query / swr）。本 ADR 記錄 web **刻意不引入任何此類套件**的決策（`web/package.json` 無 redux/zustand/jotai/recoil/react-query/swr）。

---

## 考量的選項

### 選項 A：Redux Toolkit + Redux-Saga（如 acme）
| 面向 | 評估 |
|---|---|
| 優點 | 複雜非同步流（WS、token refresh、並發）可測試側效果；成熟生態 |
| 缺點 | 大量樣板（slice/saga/api/types 四文件 × N 域）；學習曲線；bundle 增重；本專案 WS/refresh 已在 lib 層封裝，不需 saga |
| 風險 | 中（過度工程）|

### 選項 B：react-query / swr（資料抓取庫）
| 面向 | 評估 |
|---|---|
| 優點 | 內建快取、去重、重試、背景更新，省自製 |
| 缺點 | 仍需額外依賴；與現有 `lib/api` fetch client + 自製 cache 重疊；遷移成本 |
| 風險 | 低-中 |

### 選項 C：純 React Context + 自製 hooks + 自製 cache【選定】
全域 UI 走 Context；資料抓取走 `lib/api` fetch client + 自製 `lib/cache.ts`（GET 共享 in-flight + 30s staleTime）+ 自製 hooks（`usePaginatedFetch`/`useBroadcast`/`useRealtimeChannel`）。
| 面向 | 評估 |
|---|---|
| 優點 | 零額外依賴；心智模型單純（Context + useEffect）；快取/去重需求已被 `lib/cache.ts` 覆蓋；WS/refresh 已在 lib 層封裝 |
| 缺點 | 快取失效靠約定（廣域 `cacheInvalidate("GET:")`）；跨頁一致性靠紀律；無 devtools；重複的 useEffect 抓取樣板 |
| 風險 | 中（約定成本）|

---

## 決策

**選擇選項 C：純 React Context + 自製 hooks + 自製 cache。**

具體：

- **全域 UI 狀態**：4 個 Context Provider，root layout 嵌套 Theme→Locale→Toast→AuthGuard（`layout.tsx:74-80`）；Sidebar Context 掛在 AuthGuard 認證後 subtree（`AuthGuard.tsx:119`）。
- **資料抓取**：頁面 `useEffect` + `api.get(...).then(setState)` + cancelled flag（如 `platform/page.tsx:23-36`）；列表封裝在 `usePaginatedFetch`。
- **快取/去重**：`lib/cache.ts`——GET 共享 in-flight promise + 30s staleTime，key = `GET:${fullUrl}:${tenant}`（`api.ts:355-360`）；mutation 後 caller 用 `cacheInvalidate("GET:")` 廣域清除（`api.ts:18-21`）。
- **跨 tab 同步**：`useBroadcast`（BroadcastChannel）；登出走 `storage` 事件（`AuthGuard.tsx:95-110`）。

**選擇理由**：web 的非同步需求（WS 訂閱、401 refresh、GET 去重）已由 lib 層集中封裝（`lib/api`/`realtime`/`cache`），不需 saga 的側效果機制；資料抓取的快取/去重需求由自製 30s cache 覆蓋。引入 redux 或 react-query 只會增加依賴與樣板，邊際效益低。純 Context 保持最小依賴與單純心智模型。

---

## 後果

### 正面收益
- 零狀態/抓取庫依賴，bundle 更小、升級面更少。
- 心智模型單純：全域走 Context、資料走 useEffect + lib/api，新人易懂。
- 快取/去重/WS/refresh 皆單一真相源在 lib 層。

### 負面代價（誠實記載）
- **快取失效粗粒度**：cache key 含完整 URL + tenant，path-prefix 對不上，故 mutation 後只能廣域 `cacheInvalidate("GET:")` 清全部 GET 快取（`api.ts:18-21` 註解），非精準失效。
- **抓取樣板重複**：每頁 `useEffect + cancelled flag` 重複；靠 `usePaginatedFetch` 部分收斂，但非全面。
- **無 devtools / 時間旅行**：除錯靠 console，無 redux devtools 的狀態可視化。
- **跨頁一致性靠約定**：無強制的 store 結構，狀態散在各頁 `useState`。
- **staleTime 固定 30s**：非可配置的 per-query 策略（react-query 可 per-key 設定）。

### 影響範圍
- **受影響檔案**：`src/components/{theme,i18n,ui,layout}` Context、`src/hooks/*`、`src/lib/{api,cache}.ts`。
- **與 acme 對比**：acme 有 `src/store/`（20 域 slice/saga）；web 完全無，是刻意的架構分歧。

### 重新評估觸發條件
- 跨頁共享的複雜狀態顯著增加，Context prop-drilling / re-render 成本過高 → 評估 zustand（輕量）或 react-query（抓取）。
- 需要精準快取失效（per-entity invalidation）→ 引入 react-query 或自建 tag-based cache。
- 團隊規模擴大，需狀態 devtools / 可預測性 → 評估 Redux Toolkit。

---

## 執行計畫（現況已落地 + 後續）

1. **已落地**：4 Context Provider、`lib/cache.ts` 30s GET cache、`usePaginatedFetch`/`useBroadcast`、廣域 cacheInvalidate 約定。
2. **後續**：若引入抓取庫，先評估 react-query 逐頁遷移（保留 `lib/api` 作 fetcher）；補 `lib/cache.ts` 與 401 refresh 單元測試。

---

## 選用影響區段

### 架構影響
- 無新增 Container / 依賴。影響 L3 狀態層元件佈局（P1-05 §5）：狀態層 = Context + 自製 hooks + 自製 cache，取代 acme 的 Redux store。

### 效能影響
- 省去狀態庫 bundle；GET 30s cache 減重複 fetch。代價：無背景重新驗證（stale-while-revalidate 需自製），列表變動需手動 invalidate。
</content>
