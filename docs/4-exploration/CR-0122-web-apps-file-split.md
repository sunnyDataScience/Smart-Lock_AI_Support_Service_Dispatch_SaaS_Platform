---
id: CR-0122
title: "web 檔案層拆分——四站台完全獨立專案（CIA 紀錄）"
status: done
date: 2026-07-09
decision: "業主三段裁決：檔案層真拆（07-08）→ 共用碼複製分家（07-09）→ web/ 收納 + compose/ 集中（07-09）"
---

# CR-0122 web 檔案層拆分（Change Impact Analysis 紀錄）

> 事後紀錄型 CIA（方向由業主直接裁決）。命中面向：Architecture boundary。
> 正式決策見 `smartlock-docs/enterprise/14_ADR/ADR-028_web檔案層拆分_四站獨立專案.md`。

## 變更

單一 Next.js app（ADR-023）→ `web/{dispatch,tech,landing,platform}` 四個完全自足專案
（各自 package.json/lockfile/Dockerfile/tests；共用碼各站自持副本＝刻意分家）；
五份 docker-compose 集中 `compose/`。

## 影響面

- **前端**：頁面依 crossModeRedirect 路由表歸站；共用元件/hooks/lib/i18n 複製四份；
  `api.generated.ts` 例外——由 generate-api-types.sh 從 api/openapi.yaml 一次生成四份同步
- **建置**：每站自有 Dockerfile（單站 standalone，context=repo 根）；compose 相對路徑上移
  （context: ..）；`compose/.env` symlink 指根 .env（interpolation/env_file 解析）
- **CI**：docker-build-smoke 矩陣 4 web app、i18n lint 逐站比對、api-types-sync 四路徑；
  mock-smoke 改 compose/ 路徑
- **部署**：deploy/web.sh 以 `WEB_APP`（預設 dispatch）選站目錄，Cloud Run 現況不變
- **文件**：WBS 遷 `docs/system-completion-status.md`（web/docs 隨拆分解散）
- **零 API / DB / agent 變更**

## §8 Human Decisions

- ✅ 檔案層真拆（07-08）；✅ 共用碼複製分家——「未來說不定用不同風格重新設計」（07-09）；
  ✅ web/ 統一收納 + compose 集中（07-09）
- 跨站共用碼缺陷修復需同步四站（ADR-028 Consequences 明載，接受）

## 驗證

四站獨立 npm install + tsc 0 + next build 全綠；五份 compose config 過；
Docker image ×4 + 各站 smoke 於 merge 前補驗（Docker daemon 需啟動）。
