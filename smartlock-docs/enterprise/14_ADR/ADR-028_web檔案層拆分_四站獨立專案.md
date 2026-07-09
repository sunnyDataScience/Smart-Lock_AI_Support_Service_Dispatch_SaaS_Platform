---
title: "ADR-028: web 檔案層拆分 — 四站台完全獨立專案（複製分家）"
version: 1.1
status: active
owner: web 系統 tech lead
last-updated: 2026-07-09
supersedes:
  - ./ADR-023_單一codebase_APP_MODE多portal.md
---

# ADR-028: web 檔案層拆分 — 四站台完全獨立專案（複製分家）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（業主裁決 2026-07-08「先拆」+ 2026-07-09 三次追加：共用碼「就複製吧，這四個網站本來就是獨立運行的，未來說不定也會用不同的風格重新設計」、web/ 統一收納、compose 與站台同住＋站台改直白名（brand-portal/tech-portal/landing/platform-console）） |
| 層級 | 系統級（web） |
| 關聯 ADR | supersedes [ADR-023](./ADR-023_單一codebase_APP_MODE多portal.md) · [ADR-022](./ADR-022_API_SURFACE單體多面塑形.md) · [ADR-024](./ADR-024_client_SPA_無BFF_Context狀態_OIDC.md) |

## Context（背景與問題）

ADR-023 以單一 Next.js app + `APP_MODE` build-time 塑形服務四 portal。0707 會議 AI #2 要求 UI 拆獨立 web app；業主檢視後認定部署層拆分不足（每 image 含全站 code、無檔案層界線），且四站定位為**各自獨立運行、未來可能各自改版重設計**——站間 runtime 僅以資料庫與超連結相連。

## Decision（決策）

**四站台 = 四個完全自足的 Next.js 專案，收納於 `web/` 資料夾；compose 集中 `compose/`：**

```
repo/
└── web/
    ├── brand-portal/      # 品牌後台 :3000（自有 package.json/lockfile/Dockerfile/tests/docker-compose.yml）
    ├── tech-portal/       # 師傅站   :3001（同上）
    ├── landing/           # 導流站   :3002（同上）
    └── platform-console/  # 平台 console :3003（同上）
# 各站 stack 的 docker-compose.yml 與站台同住（業主裁決「compose 跟網站放一起」）；
# mock compose 屬 api 開發工具 → api/docker-compose.mock.yml；根目錄只留大功能包
# （agent / api / data / web / SQL / scripts…，對齊 0707 §十二 微服務結構）。
```

- **共用碼複製分家**（業主裁決）：ui/i18n/theme/auth/realtime/layout/phase-ii 元件、hooks、lib、i18n messages 各站自持一份於自身 `src/`——這是刻意 fork（各站將獨立演化風格），非漂移風險。
- **無 workspaces、無共用套件**：各站獨立 `npm install`／lockfile／`tsc`／`next build`，可單獨搬離 repo 零解耦成本。
- **例外——`src/types/api.generated.ts` 不算 fork**：四份由 `scripts/ci/generate-api-types.sh` 從單一 `api/openapi.yaml` 一次生成同步寫入（api-types-sync CI `--check` 擋漂移）。
- 每站自有 Dockerfile（單站三階段 standalone，context = repo 根）與 `docker-compose.yml`（相對路徑 `context: ../..`）；各站 `.env` 為指向根 `.env` 的 symlink（compose interpolation 與 env_file 解析用；注意 next dev 也會讀到，屬已知取捨）。
- `APP_MODE`／`appMode.ts` 各站保留（跨站 CTA 與 AuthGuard 導向解析仍需 env 烤入）。
- e2e 隨站走：admin/public specs → `web/brand-portal/tests`；tech/account → `web/tech-portal/tests`；各站自有 playwright.config。

## Consequences（後果）

- ✅ 檔案層完全隔離：站產物只含自身路由；改一站不觸其他站（build/deploy/test 全獨立）
- ✅ 各站可自由改版重設計、未來可各自搬 repo（一品牌一 GCP 專案路線）
- ✅ CI 監看 `web/**` 路徑延續；根目錄僅增 `web/`、`compose/` 兩入口
- ⚠️ **共用碼修 bug 需同步四份**（例：ui 元件缺陷、rolePolicy 調整）——接受此成本換取獨立性；建議修跨站缺陷時 grep 四站同名檔
- ⚠️ i18n messages 各站全量副本（2723 鍵），各站可自行裁剪
- api.generated.ts 永不手改，一律走生成腳本

## 重評觸發

- 跨站同步修復頻率高到不可忍受 → 重評共用套件（回 workspaces）或抽 npm registry 私包
- 某站搬離 repo → 該站 compose/CI 條目隨遷
