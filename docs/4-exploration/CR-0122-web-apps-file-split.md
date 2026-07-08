---
id: CR-0122
title: "web 檔案層拆分——npm workspaces monorepo（CIA 紀錄）"
status: done
date: 2026-07-08
decision: "業主 2026-07-08 裁決：不滿足於 APP_MODE 部署層拆分，檔案層真拆"
---

# CR-0122 web 檔案層拆分（Change Impact Analysis 紀錄）

> 本檔為事後紀錄型 CIA（方向由業主直接裁決）。命中面向：Architecture boundary。
> 驗收後依 0707 決議可清除；正式決策見 `smartlock-docs/enterprise/14_ADR/ADR-028`。

## 變更

單一 Next.js app（ADR-023）→ `web/` npm workspaces monorepo：
`apps/{dispatch,tech,landing,platform}` + `packages/shared`（@smartlock/shared）。

## 影響面

- **前端**：183 檔 import 改寫 `@shared/*`；頁面依 crossModeRedirect 路由表歸位四 app；
  忘記/重設密碼落 shared 元件、StatusBadge/UrgencyBadge 提升 `shared/components/tech`
- **建置**：`web/Dockerfile` 參數化（ARG APP）；四 compose 加 `APP` build arg；
  `deploy/web.sh` 加 `WEB_APP`（預設 dispatch，Cloud Run 現況不變）
- **CI**：i18n-keys-sync-lint / api-types-sync / docker-build-smoke 路徑更新；
  generate-api-types.sh 輸出改 `web/packages/shared/src/types/`
- **零 API / DB / agent 變更**

## §8 Human Decisions

- ✅ 拆（業主 2026-07-08）；結構（workspaces、4 app、shared 邊界）＝工程裁量
- `[待議]` globals.css 全量複製四份的瘦身、i18n messages per-app 拆分

## 驗證

四 app `tsc --noEmit` + `next build` 全綠（tech 產物僅 16 條路由，檔案層拆分生效）；
Docker image × 4 + Playwright 各站 smoke 於 merge 前補驗（Docker daemon 需啟動）。
