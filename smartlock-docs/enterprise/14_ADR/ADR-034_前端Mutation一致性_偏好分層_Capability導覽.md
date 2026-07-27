---
title: "ADR-034: 前端 Mutation 一致性、偏好分層與 Capability 導覽"
version: 1.0
status: active
owner: web 系統 tech lead
last-updated: 2026-07-27
refines:
  - ./ADR-024_client_SPA_無BFF_Context狀態_OIDC.md
relates:
  - ./ADR-005_四方RBAC模型與enforce.md
  - ./ADR-028_web檔案層拆分_四站獨立專案.md
---

# ADR-034: 前端 Mutation 一致性、偏好分層與 Capability 導覽

| 欄位 | 內容 |
|---|---|
| 狀態 | 已實作（2026-07-27；WBS 3.6.1～3.6.3 code／本機驗證完成） |
| 層級 | 系統級（web / api） |
| 關聯 ADR | refines [ADR-024](./ADR-024_client_SPA_無BFF_Context狀態_OIDC.md) · [ADR-005](./ADR-005_四方RBAC模型與enforce.md) · [ADR-028](./ADR-028_web檔案層拆分_四站獨立專案.md) |
| 來源規劃 | [Plane 借鏡架構優化規劃](../規格統控整理/Plane借鏡架構優化規劃_2026-07-27.md) A／B／C |

## Context（背景與問題）

ADR-024 已決定 client SPA、後端授權主防線與自製 GET cache；目前 mutation 成功後多採
`cacheInvalidate("GET:")` 廣域失效。這可降低 stale data，卻沒有跨頁一致的 optimistic
patch、rollback、重送冪等與 `409` 版本衝突體驗。四個 portal 又各自持有前端程式碼，
若沒有契約，錯誤語意會各自演化。

另一方面，theme、locale、sidebar 與 PWA dismissed 等本機偏好，和 saved view、收藏、
通知偏好等跨裝置資料的生命週期不同；登入 token 仍有 localStorage 過渡路徑，更不可與
「偏好」混為一談。品牌後台若新增 Command Palette，也必須沿用後端 capability 與資源
授權，不能形成新的權限來源。

## Decision（決策）

### 1. Mutation 統一契約

- 每個可寫操作明列：`action_id`、optimistic patch、rollback、精準 invalidate key、
  idempotency key、conflict handler 與使用者／audit outcome。
- 只有**低風險、可逆、可明確還原**的 UI 操作可 optimistic，例如已讀、收藏、偏好與
  純導覽狀態。
- 報價核可、工單狀態、派工、結算、退款、角色／權限、同意書一律
  **server-confirmed**；等待期間可顯示 pending，不得先顯示商業結果已完成。
- 同一使用者 action 重送沿用同一 `action_id`／idempotency key，不能在 retry 時重生。
- 可併發編輯的資源以 `version`、ETag 或等價 precondition 做 compare-and-set；衝突回
  `409` 與 machine-readable current version，UI 提供 reload／compare／retry，不 silent overwrite。
- 本決策不強制導入 React Query、Redux 或 Zustand；先把契約固定在現有 `lib/api`／cache
  邊界，狀態庫仍依 ADR-024 的重評觸發另案決定。

### 2. 偏好資料依同步責任分層

| 類別 | 儲存位置 | 例子 | 限制 |
|---|---|---|---|
| 裝置本機偏好 | localStorage / browser storage | theme、locale、sidebar、command history、PWA 提示 | 不得含 PII、角色、tenant 或業務真相 |
| 品牌人員同步偏好 | brand DB | saved view、欄位排序、預設篩選、通知偏好、收藏 | 權威 scope 必含品牌租戶 |
| 技師同步偏好 | technician DB | 工作台排序、服務區／通知偏好、最近操作 | 不複製成品牌使用者資料 |
| 平台人員同步偏好 | platform DB | 治理 dashboard、品牌檢視偏好 | 不接受 UI 傳入 tenant 作越權依據 |

同步偏好的最小欄位為 `principal_id`、`portal`、`preference_key`、`value_json`、
`version`、`updated_at`；key 採 allowlist 並設 schema 與大小上限。登入 token 不屬於偏好，
依 ADR-024 目標移至 HttpOnly cookie；localStorage 雙寫只允許有時限的 migration。

### 3. Capability-driven 導覽

- Command Palette 先只在 brand portal 導入，command registry 至少含
  `command_id`、route/action、required capability、context requirement、analytics event。
- UI 依受信任 session 的 capability 投影決定「顯示」，實際 API 仍執行 tenant、role、
  resource 與 workflow guard。
- 第一批只納入搜尋、跳轉、開啟草稿、切換佇列、通知與 saved view；高風險 mutation
  不做無確認快捷命令。

## Alternatives（考量的選項）

- **A：所有 mutation 都 optimistic** — 操作最快，但會讓報價、派工與金流出現假成功，
  不採。
- **B：所有操作都等整頁重新抓取** — 一致性單純，但高頻後台操作延遲與閃爍明顯，不採。
- **C：風險分級 + 統一 mutation contract（採用）** — 低風險操作流暢，高風險結果仍以
  server 為權威。
- **D：全部偏好只放瀏覽器或集中到單一 user DB** — 前者無跨裝置能力，後者破壞三庫
  owner 邊界，均不採。

## Consequences（後果）

- ＋四站 mutation 的失敗、重送與衝突語意一致；低風險操作可加速，高風險操作不假成功。
- ＋偏好可跨裝置，但不建立第四份通用使用者真相源。
- ＋Command Palette 改善操作效率，又不擴張前端授權邊界。
- －API 需逐步補 idempotency 與 version precondition，現行只清全域 cache 的頁面需盤點。
- －同步偏好會新增三庫 migration／API／資料保留責任。

**完成門檻**：離線、5xx、409、重送四類 E2E 全綠；敏感操作不存在 optimistic 假成功；
localStorage 中無登入 token；直接 URL、palette、直接 API 三條路徑得到一致授權結果。

## 實作與驗證證據（2026-07-27）

- mutation 契約位於 `web/shared-contract/src/mutation.ts`；Brand Portal 通知已讀是低風險
  reference integration，rollback／精準 invalidation／同 action retry 都由
  `NotificationDrawer.tsx` 與 Playwright E2E 驗證。
- migration 120 與 `api/{routers/preferences.py,services/preference_service.py}` 提供品牌、
  技師、平台三個權威庫的 allowlist、16 KiB 上限與 CAS `409`。
- 四站 HTTP 登入改走本站 `/api-proxy` + HttpOnly cookie；cookie-only response 不回傳 token
  JSON。CI `check-browser-token-storage.mjs` 阻擋 token 寫入 storage 或 URL。
- Brand Portal 已有 `CommandPalette.tsx` 與 capability/role-filtered command registry，
  涵蓋搜尋、草稿、派工佇列、通知與 saved view。
- 本地驗證：mutation recovery E2E 3/3、shared contract 3/3、Brand unit 46/46、
  四站 `tsc --noEmit` 與 production build 通過。跨 host WS 僅使用 cookie；若未具同父
  網域／cookie domain，realtime 應保持 disabled，不得退回 URL token。

## 重評觸發

- mutation cache graph 複雜到自製契約無法穩定維護時，另開 ADR 評估 React Query。
- 跨 portal 需要共享實作時，依 [ADR-039](./ADR-039_web共享契約套件_窄例外.md) 的契約層
  邊界處理，不在本 ADR 擴大為共享 UI。
