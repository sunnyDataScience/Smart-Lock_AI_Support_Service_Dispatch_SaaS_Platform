---
title: "ADR-023: 單一 codebase 以 APP_MODE build 多 portal"
version: 1.0
status: active
owner: web 系統 tech lead
last-updated: 2026-07-07
upstream:
  - smartlock-docs/web/P2/04_adr/ADR-001_單一codebase_APP_MODE_多portal.md
---

# ADR-023: 單一 codebase 以 APP_MODE build 多 portal

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 系統級（web）|
| 關聯 ADR | [ADR-022](./ADR-022_API_SURFACE單體多面塑形.md) · [ADR-024](./ADR-024_client_SPA_無BFF_Context狀態_OIDC.md) |

## Context（背景與問題）

平台需要多個角色差異極大的前端：品牌營運後台（dispatch）、師傅工作台（tech，PWA）、平台 console（platform）、導入行銷頁（landing）。各 portal 服務不同角色、連不同 api surface（:8001 / :8002 / :8003）、各自獨立 origin 與 port（dispatch :3000 / tech :3001 / landing :3002 / platform :3003）、token 需隔離——但**共用大量元件、gate 邏輯、api client、即時訂閱、設計系統**。拆 4 個獨立專案會讓共用邏輯複製 4 份，gate 漂移、UI 不一致、型別重複。

## Decision（決策）

**單一 Next.js codebase + `NEXT_PUBLIC_APP_MODE` build-time 塑形**：

- `APP_MODE = process.env.NEXT_PUBLIC_APP_MODE || "all"`（`src/lib/appMode.ts`），型別 `all | dispatch | tech | landing | platform`，非白名單退 `all`。
- `crossModeRedirect(pathname)`：判定當前 build 是否服務此路徑，否則導向站內路由或對方 portal 絕對 URL；`all` 模式恆 `null`（未設 env 時零行為變化，單庫部署與多 portal 部署共存）。
- gate 由 root layout 的 `AuthGuard` 呼叫（client-side）。
- 4 個 compose 用**同一份 `web/Dockerfile`**，只換 build ARG（`APP_MODE` + API base + 跨端 `PEER/TECH/DISPATCH/PLATFORM_PORTAL_URL`）。

## Alternatives（考量的選項）

- **A：4 個獨立前端專案** — 完全隔離、bundle 最小；但共用元件 / gate / api client 複製 4 份，長期漂移風險高。
- **B：Monorepo + 共用套件（turborepo + packages/ui）** — 共用集中，但引入工具鏈、4 個 app 殼仍要維護，現階段 overkill。
- **C：單一 codebase + build-time 旗標塑形（採用）** — 零程式碼重複；元件 / gate / api client / 型別 / 設計系統單一真相源。

## Consequences（後果）

**正面**：共用元件、gate、api client、`types/api.generated.ts`、設計系統零重複；一份 Dockerfile → 4 portal；新增 portal 只需擴 `AppMode` 型別 + `crossModeRedirect` 分支。
**風險**：
- **build-time env 烤入**：8 個 `NEXT_PUBLIC_*` 於 `next build` 烤進 bundle，同一 image 無法 runtime 切 API base / portal URL——每環境每 portal 各一 build，改後端網域須 rebuild 全部 web image。
- **gate 為 client-side，非安全邊界**：未授權 portal 的頁 bundle 仍下載到瀏覽器；分站是 UX 隔離，授權主防線在 api RBAC（[ADR-005](./ADR-005_四方RBAC模型與enforce.md)）。
- **無 portal 粒度 code-split**：單一 build 的 bundle 含全部頁程式碼（tree-shake 後）。
- 跨端連結靠絕對 URL 烤入，漏配退回站內路由（可能導錯）。
**影響範圍**：`src/lib/appMode.ts`、`AuthGuard.tsx`、`web/Dockerfile`、4 個 compose。
**重評觸發**：portal 數量 / 差異顯著增長、bundle 過大 → monorepo + 共用 package；需 runtime 切環境 → runtime env 注入（`__ENV.js` / 反代改寫）；gate 需成真安全邊界 → server-side gate（[ADR-024](./ADR-024_client_SPA_無BFF_Context狀態_OIDC.md) 重評觸發連動）。

## Status 附註

- 🔜 規劃中：`crossModeRedirect` 4 mode × 邊界路徑單元測試；runtime env 注入評估。
