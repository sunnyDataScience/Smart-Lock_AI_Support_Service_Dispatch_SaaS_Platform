---
title: "ADR-028: web 檔案層拆分 — npm workspaces monorepo（apps × 4 + packages/shared）"
version: 1.0
status: active
owner: web 系統 tech lead
last-updated: 2026-07-08
supersedes:
  - ./ADR-023_單一codebase_APP_MODE多portal.md
---

# ADR-028: web 檔案層拆分 — npm workspaces monorepo（apps × 4 + packages/shared）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（業主裁決 2026-07-08：「沒關係先拆吧」——0707 會議 AI #2 的完整版執行） |
| 層級 | 系統級（web） |
| 關聯 ADR | supersedes [ADR-023](./ADR-023_單一codebase_APP_MODE多portal.md) · [ADR-022](./ADR-022_API_SURFACE單體多面塑形.md) · [ADR-024](./ADR-024_client_SPA_無BFF_Context狀態_OIDC.md) |

## Context（背景與問題）

ADR-023 以單一 Next.js app + `APP_MODE` build-time 塑形服務四 portal。0707 會議 AI #2 要求「三種 UI 拆成獨立 web app」；業主 2026-07-08 檢視後認定部署層拆分不足——每個 image 都含全部頁面 code（品牌站 bundle 可見平台頁 chunk）、無法檔案層界定各站範圍——裁決檔案層真拆。

同時 ADR-023 的核心顧慮仍成立：共用元件 / gate / api client / i18n / 型別（`api.generated.ts` 90 檔引用）不可複製四份。

## Decision（決策）

**repo 內單一 `web/` npm workspaces monorepo**：

```
web/
├── package.json            # workspaces: apps/*, packages/*（root devDeps: playwright/typescript）
├── apps/dispatch|tech|landing|platform/   # 各站台獨立 Next.js app（各自 package.json / next.config / tsconfig / layout / globals.css）
└── packages/shared/        # @smartlock/shared：components/{ui,i18n,theme,realtime,auth,layout,phase-ii,tech}、hooks、lib、i18n messages、types/api.generated.ts
```

- 頁面歸屬以原 `crossModeRedirect` 路由表為 ground truth：tech＝home/pool/my-orders/account/tech-login/tech-register；landing＝`/`；platform＝/platform/*；dispatch＝其餘。跨站公開頁（忘記/重設密碼）落 shared 成組件，兩站薄包裝。
- shared 以 **tsconfig paths（`@shared/* → ../../packages/shared/src/*`）+ next `experimental.externalDir`** 原始碼直引，不經 build/publish；Tailwind v4 各 app `@source` 指向 shared。
- **同一份參數化 `web/Dockerfile`（`ARG APP`）** 建四站 image；compose 加 `APP` build arg；Cloud Run `deploy/web.sh` 以 `WEB_APP`（預設 dispatch）選站。
- `APP_MODE` 與 `appMode.ts` 保留（跨站 CTA/導向解析仍需）；未知路由由各 app `not-found` 兜底。
- e2e（Playwright）留 `web/tests` 中央（打運行容器 URL，不綁 app）。

## Consequences（後果）

- ✅ 檔案層界線清楚：build 產物只含本站路由（tech image 16 條路由，不再帶品牌後台 chunk）
- ✅ 共用面單一維護（shared 套件）；型別/設計系統不複製
- ✅ 單站改版只重建單站 image（deps layer cache 共用）
- ⚠️ 新增共用元件須放 shared（跨 app import 會被各 app tsc 擋下）；新 workspace 需同步 Dockerfile deps COPY 清單
- ⚠️ globals.css 各 app 一份（全量 token 複製），後續可抽 shared styles 瘦身 `[待議]`
- i18n messages 暫維持單包（2723 keys 全量進 shared），per-app 拆分屬後續優化 `[待議]`

## 重評觸發

- 一品牌一 GCP 專案（M3/M4）需要 per-app 版本獨立發佈 → 評估 shared 改 versioned package
- app 數量 > 6 或 shared 邊界頻繁被打穿 → 評估 turborepo / nx
