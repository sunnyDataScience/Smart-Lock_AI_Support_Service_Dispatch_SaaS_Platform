# 08 - 專案結構指南 — web 子系統

| 欄位 | 值 |
|---|---|
| 版本 | v1.0 |
| 日期 | 2026-07-07 |
| 作者 | web 技術文件撰寫者 |
| 狀態 | 草稿（現況 as-is baseline）|
| 服務 | web（smartlock-admin，`web/`）|

---

## 1. 設計原則

### 1.1 本服務實際遵循的原則

| # | 原則 | 說明 |
|---|---|---|
| 1 | **單一 codebase，行為由 build 旗標塑形** | 無 portal 分支目錄；4 個 portal 的差異全由 `NEXT_PUBLIC_APP_MODE` 在 build/runtime 決定（`src/lib/appMode.ts`），程式碼零重複 |
| 2 | **依功能/領域組織，非依類型** | `src/app/` 頁樹依業務域（work-orders / accounting / knowledge-base…）；`src/components/` 亦依域分子目錄（accounting / dashboard / tech / work-orders…）|
| 3 | **lib 層集中橫切關注** | api 消費（`lib/api.ts`）、分站 gate（`lib/appMode.ts`）、RBAC（`lib/rolePolicy.ts`）、即時（`lib/realtime.ts`/`sse.ts`）、快取（`lib/cache.ts`）皆單一真相源 |
| 4 | **gate 單一真相源共用** | AuthGuard（route gate）與 Sidebar（nav 過濾）共用 `rolePolicy.ts`（`rolePolicy.ts:5-6` 註解），避免兩處判定漂移 |
| 5 | **狀態就近 + 輕量 Context** | 無全域 store；跨組件輕量狀態走 React Context（Theme/Locale/Toast/Sidebar），資料狀態就近在頁面 `useEffect` + 自製 hooks |
| 6 | **型別由契約生成** | `types/api.generated.ts` 由 `openapi.yaml` 生成，組件用生成型別，降契約漂移 |
| 7 | **多小檔 > 少大檔** | 頁與元件依域拆分（94 個 page.tsx，`admin/` 下 36 頁）|

### 1.2 與「理想前端架構」的差距（本子系統特有）

| 差距項 | 現況 | 理想 |
|---|---|---|
| **無 server component** | 全部 94 個 `page.tsx` 標 `"use client"`；`src/app` 內無 `export default async`（零 RSC 資料抓取）| App Router 應用 RSC 做首屏/資料抓取，降 client bundle、把敏感存取移 server |
| **無 BFF / route handler** | `find src/app -name route.ts` 零命中；瀏覽器直連後端 | BFF 層注入認證、隱藏 token/tenant、集中錯誤轉換（如 acme `/api/[...slug]`）|
| **認證全 client-side** | AuthGuard + rolePolicy 全在瀏覽器；token 存 localStorage | server-side 驗簽（middleware/RSC）+ httpOnly cookie |
| **無 Domain Layer** | 業務規則散在頁面與 lib helper | 純業務邏輯獨立成 domain（可無框架測試）|
| **無單元測試** | 只有 Playwright E2E（`tests/e2e/`）；無 Jest/Vitest 單元測試 | 元件/hook/lib 應有單元測試 |

---

## 2. 現有頂層結構（ASCII Tree）

```
web/
├── src/                         # 主要原始碼（見 §3）
├── types/
│   └── api.generated.ts         # 由 openapi.yaml 生成的 API 型別（241KB，勿手改）
├── tests/
│   └── e2e/                     # Playwright E2E（45 個 .spec.ts）
│       ├── account/             # 對帳單 / 佣金對帳
│       ├── admin/               # RBAC / 派工 / 客戶 / 爭議 / SOP 洩漏防護
│       ├── public/              # token 公開頁（track / consumer-track）
│       └── tech/                # 師傅端流程
├── docs/                        # web 內部文件（4 份，見 §6）
├── public/                      # 靜態資源
├── Dockerfile                   # 三階段 standalone build（deps→builder→runtime）
├── next.config.ts               # output: standalone + optimizePackageImports
├── playwright.config.ts         # E2E 設定
├── package.json                 # smartlock-admin v0.1.0
├── package-lock.json            # 依賴鎖定（npm ci）
├── postcss.config.mjs           # Tailwind v4 postcss
└── tsconfig.json                # strict; @/* → ./src/*, @/types/* → ./types/*
```

---

## 3. 原始碼結構分析（`src/`）

```
src/
├── app/                                 # Next.js App Router（全 client component；無 route group）
│   ├── layout.tsx                       # Root Layout：Theme→Locale→Toast→AuthGuard 嵌套 + FOUC script
│   ├── page.tsx                         # landing 一頁式（tech/dispatch build 直接 return null）
│   ├── globals.css                      # Tailwind v4 全域樣式
│   ├── error.tsx / global-error.tsx / not-found.tsx / _error-parts/   # 錯誤邊界
│   │
│   ├── ── 派工/品牌後台（dispatch mode）──
│   ├── dashboard/                       # 營運儀表板
│   ├── admin/                           # 派工/審核/治理（36 個 page.tsx）
│   │   ├── cases/ dispatch-queue/ dispatch-manual/ material-requests/
│   │   ├── quotes/ quote-catalog/ customers/ refunds/ warranty-claims/
│   │   ├── disputes/ payout-rules/ inventory/ roles/ staff/
│   │   ├── config-governance/ audit-events/ sentiment-alerts/ exceptions/
│   │   ├── vendor-approvals/ reports/kpi/ knowledge-base/sop-performance/ …
│   ├── conversations/ [id]/             # 對話
│   ├── problem-cards/ [id]/             # 問題卡
│   ├── work-orders/ (kanban/ map/ [id]/)# 工單列表/看板/地圖/詳情
│   ├── technicians/ [id]/               # 技師管理
│   ├── accounting/ (invoices/ revenue/ vouchers/)  # 帳務
│   ├── knowledge-base/cases/ manuals/ sop-drafts/ family-reviews/     # 知識庫
│   ├── technician-ranking/ revenue/     # 報表
│   ├── login/ register/ vendor-login/ vendor/ settings/ notifications/
│   ├── forgot-password/ reset-password/
│   │
│   ├── ── 師傅工作台（tech mode，前綴 /home /pool /my-orders /account）──
│   ├── home/                            # 師傅儀表板
│   ├── pool/                            # 搶單池（realtime）
│   ├── my-orders/ [id]/                 # 我的工單 + 6 子流程
│   │   └── [id]/{delay,door-check,material-request,reschedule,scope-change,signature}/
│   ├── account/ {schedule,statements,commission-statements}/
│   ├── tech-login/ tech-register/       # 師傅登入 / KYC 註冊（CR-0115）
│   │
│   ├── ── 平台 console（platform mode）──
│   ├── platform/                        # 儀表板（R1 骨架）
│   │   ├── login/ apply/ brand-applications/ technician-approvals/
│   │
│   └── ── 客戶公開頁（token 簽章，跨 portal）──
│       ├── track/[token]/ scope-change/[token]/ quotes/[token]/ consent/[token]/
│
├── components/                          # 依域分類的 UI 元件
│   ├── auth/AuthGuard.tsx               # client-side 路由守衛（掛 root layout）
│   ├── layout/                          # Sidebar / SidebarContext / 版面骨架
│   ├── theme/  (ThemeProvider, ThemeToggle)      # 主題 Context
│   ├── i18n/   (LocaleProvider, LocaleToggle)     # 語系 Context
│   ├── ui/                              # 基礎元件（Radix 自建，非完整 shadcn）
│   │   └── DataTable / Modal / Drawer / Toast / StatusBadge / Spinner / EmptyState …
│   ├── realtime/  (RbacChangedBanner …) # WS 訂閱 UI（權限變更 banner）
│   ├── dashboard/ (SlaAlertBanner …)    # 儀表板 widget
│   ├── tech/   (TechShell, TechBottomNav, TechSidebar)   # 師傅 PWA 殼
│   ├── accounting/ admin/ conversations/ dispatch-queue/ knowledge-base/
│   ├── problem-cards/ quotes/ settings/ technicians/ work-orders/ phase-ii/
│
├── hooks/                               # 自製 hooks（取代 react-query/swr）
│   ├── usePaginatedFetch.ts             # 分頁列表抓取（最大檔）
│   ├── useBroadcast.ts                  # 跨 tab BroadcastChannel 同步
│   ├── useRealtimeChannel.ts            # WS 訂閱 React 封裝
│   ├── useSSEChannel.ts                 # SSE 訂閱（後端未實作，預設關）
│   └── useKbCounts.ts                   # 知識庫計數
│
├── lib/                                 # 橫切關注（單一真相源）
│   ├── api.ts                           # fetch client（auth/header/401 refresh/cache）
│   ├── apiError.ts                      # ApiError → 友善訊息
│   ├── appMode.ts                       # APP_MODE 分站 gate（crossModeRedirect + CTA href）
│   ├── rolePolicy.ts                    # 前端 RBAC（longest-prefix，fail-open）
│   ├── realtime.ts                      # WS 訂閱層（backoff + 靜默降級）
│   ├── sse.ts                           # SSE 訂閱層（解耦 env）
│   ├── cache.ts                         # GET 共享 in-flight + 30s staleTime
│   ├── uatFlags.ts                      # UAT_HIDE_FAKE_FLOWS 假流程隱藏
│   ├── translate.ts / format.ts / dateRange.ts / kb-adapter.ts
│   └── constants/brands.ts
│
└── i18n/                                # 多語系
    ├── config.ts                        # i18n 設定
    └── messages/                        # 語系資源
```

> **與 acme 的結構差異**：acme 有 `src/store/`（Redux Toolkit + Saga 20 域）與 `src/pages/api/`（BFF proxy）；web **兩者皆無**——狀態走 Context + hooks，API 走 `lib/api` 直連。acme 的 `context/` 有 11 個 Context，web 只有 4 個（Theme/Locale/Toast/Sidebar）。

### 3.1 職責邊界

| 目錄 | 職責 | 不該放 |
|---|---|---|
| `app/` | 路由 + 頁面（client component）| 可重用邏輯（抽 hooks/lib）|
| `components/` | UI 渲染（依域）| API 呼叫細節（走 lib/api）|
| `hooks/` | 抓取/訂閱/跨 tab 模式封裝 | 純 UI |
| `lib/` | 橫切：API/gate/RBAC/即時/快取 | 頁面專屬邏輯 |
| `types/` | 生成型別（`api.generated.ts` 勿手改）| 手寫 domain 型別（散在各處）|

### 3.2 App Router client SPA 模式分析

典型頁面模式（如 `platform/page.tsx:23-36`）：

```
"use client"
export default function XxxPage() {
  const [state, setState] = useState(...)
  useEffect(() => {
    let cancelled = false
    api.get(path).then(d => { if (!cancelled) setState(d) })
    return () => { cancelled = true }
  }, [deps])
  return <UI ... />
}
```

- 無 RSC：頁面掛載後才在瀏覽器抓資料（cancelled flag 防 race）。
- 抓取模式進一步封裝在 `usePaginatedFetch`（列表分頁）等自製 hooks。
- 首屏依賴 client bundle 下載 + 執行 → 白屏窗口較 RSC 大（trade-off，見 ADR-002/003）。

---

## 4. 測試結構

### 4.1 現有測試

```
tests/e2e/                       # Playwright（45 個 .spec.ts）— 唯一測試層
├── account/                     # statements / commission-statements
├── admin/                       # rbac / work-orders-reassign / customers /
│                                #   dispute-cosign / sop-internal-id-leak
├── public/                      # track / consumer-track（token 公開頁）
└── tech/                        # tech-flow
playwright.config.ts
```

### 4.2 測試覆蓋缺失

| 測試類型 | 現況 | 缺失 |
|---|---|---|
| 單元測試（hook/lib/元件）| **無**（package.json 無 Jest/Vitest）| `lib/api.ts` 401 refresh、`appMode.crossModeRedirect` 分支、`rolePolicy.canAccessRoute` fail-open 邊界皆無單元測試 |
| E2E | 45 spec（admin/tech/account/public）| 完整覆蓋率 `[待確認]`；平台 console、多數 dispatch 域尚待補 |
| gate 邏輯測試 | 靠 E2E `admin/rbac.spec.ts` 間接覆蓋 | crossModeRedirect 4 mode × 邊界路徑無專門測試 |

> **建議**：gate 三件（appMode/rolePolicy/AuthGuard）為安全關鍵且純函式（`crossModeRedirect`/`canAccessRoute`），最適合先補單元測試（低成本高價值），尤其 fail-open 邊界。

---

## 5. 命名慣例

| 類型 | 慣例 | 範例 |
|---|---|---|
| App Router 路由目錄 | `kebab-case` | `work-orders/`、`tech-register/`、`dispatch-queue/` |
| 動態路由段 | `[camelCase]` | `[id]/`、`[token]/` |
| React 元件檔 | `PascalCase.tsx` | `AuthGuard.tsx`、`DataTable.tsx`、`TechShell.tsx` |
| Next.js 特殊檔 | `camelCase.tsx` | `page.tsx`、`layout.tsx`、`error.tsx` |
| Hook 檔 | `use{名稱}.ts` | `usePaginatedFetch.ts`、`useBroadcast.ts` |
| lib 工具 | `camelCase.ts` | `appMode.ts`、`rolePolicy.ts`、`apiError.ts` |
| Context Provider | `{Name}Provider.tsx` | `ThemeProvider.tsx`、`LocaleProvider.tsx` |
| 生成型別 | `*.generated.ts`（勿手改）| `api.generated.ts` |
| E2E 測試 | `{功能}.spec.ts` | `rbac.spec.ts`、`tech-flow.spec.ts` |

路徑別名（`tsconfig.json:17-20`）：`@/*` → `./src/*`；`@/types/*` → `./types/*`。

---

## 6. web 內部文件（`web/docs/`）

| 文件 | 用途 |
|---|---|
| `system-completion-status.md`（最大）| 跨前後端/Realtime/Workflow 整體進度盤點（更新 2026-07-06，載 CR-0114 收斂、1611 tests passed）|
| `page-status.md`（給業主）| 逐頁功能狀態：✅ 85 / 🟡示意 UI 12 / ⏳待接入 25（更新 2026-06-07）|
| `setup-guide.md` | 環境建置指南 |
| `login-testing-guide.md` | 登入測試指南 |

---

## 7. 重構建議（優先序）

### P1（P0 安全，中風險）：cookie 認證 + server 驗證
**現況**：token 存 localStorage、前端 `atob` 不驗簽、gate 全 client-side（`api.ts:109-118,183-206`）。
**建議**：token 移 httpOnly cookie；引入 Next middleware 或 RSC 在 server 端驗簽 + 驗過期 + gate。屬架構變更，須走 CIA。
**效益**：消除 XSS 竊 token、未授權 bundle 下載；前端首度成為可信邊界的一部分。

### P2（安全，低風險）：rolePolicy 改 deny-by-default
**現況**：`rolePolicy.ts:80` 未列路由 fail-open。
**建議**：catch-all 改拒絕；新增敏感頁強制登記 + CI 檢查漏登記。
**效益**：消除「忘記登記即開放」的靜默風險。

### P3（安全/一致性，需裁決）：fallback tenant 擋下導登入
**現況**：`api.ts:120-135` 無 tenant 靜默退 1 號租戶（TODO 已標資料外洩）。
**建議**：改為擋下導登入。屬跨 12 頁行為變更，先出 CIA 等業主裁決。

### P4（架構，高價值）：評估抽出 BFF / route handler
**現況**：瀏覽器直連後端，token/tenant 全暴露（見 ADR-003）。
**建議**：抽薄 BFF 注入認證、隱藏 token、集中錯誤轉換與 rate limiting。
**效益**：與 P1 合力讓授權可移 server；為 runtime env 注入鋪路。

### P5（可維護，中價值）：補 gate 單元測試 + runtime env 注入
**現況**：無單元測試；`NEXT_PUBLIC_*` build-time 烤入（`Dockerfile:44-73`）。
**建議**：先補 `crossModeRedirect`/`canAccessRoute`/`api.ts refresh` 單元測試；env 改 runtime 注入，4 portal 共用單一 image。

---

## 8. 演進路線

### Phase 1 — 安全基線（低-中風險）
| 任務 | 風險 |
|---|---|
| rolePolicy 改 deny-by-default + 新頁登記 CI | 低 |
| 補 gate 三件單元測試（appMode/rolePolicy/api refresh）| 低 |
| fallback tenant 決策（出 CIA 待裁決）| 中（跨頁行為）|

### Phase 2 — 認證邊界重建（中-高風險）
| 任務 | 風險 |
|---|---|
| token 改 httpOnly cookie | 高 |
| 引入 server-side gate（middleware / RSC）| 高 |
| 抽薄 BFF / route handler | 中 |

### Phase 3 — 架構最佳化（高價值）
| 任務 | 風險 |
|---|---|
| 關鍵頁導入 RSC（降 client bundle）| 中 |
| runtime env 注入（4 portal 共用 image）| 中 |
| E2E 覆蓋補齊 + 平台 console R2/R3 | 中 |

---

*文件結尾 — web 專案結構指南 v1.0 / 2026-07-07*
</content>
