---
title: "ADR-039: web 共享契約套件——四站獨立專案的窄例外"
version: 1.0
status: active
owner: web 系統 tech lead
last-updated: 2026-07-27
refines:
  - ./ADR-028_web檔案層拆分_四站獨立專案.md
  - ./ADR-031_契約工件三分層_型別SoT為runtime_export.md
---

# ADR-039: web 共享契約套件——四站獨立專案的窄例外

| 欄位 | 內容 |
|---|---|
| 狀態 | 已實作（2026-07-27；固定版本 vendored tarball 模式） |
| 層級 | 系統級（web / tooling） |
| 關聯 ADR | refines [ADR-028](./ADR-028_web檔案層拆分_四站獨立專案.md) · [ADR-031](./ADR-031_契約工件三分層_型別SoT為runtime_export.md) · [ADR-034](./ADR-034_前端Mutation一致性_偏好分層_Capability導覽.md) |
| 來源規劃 | [Plane 借鏡架構優化規劃](../規格統控整理/Plane借鏡架構優化規劃_2026-07-27.md) H |

## Context（背景與問題）

ADR-028 接受四站完全獨立、共用碼複製分家，以換取獨立部署與未來不同風格；同時留下
「跨站同步修復頻率不可忍受時重評共享套件」的觸發。ADR-031 之後已把前端型別 SoT
定為 FastAPI runtime export，並以 CI 同步四份 generated type。

Plane 借鏡盤點顯示，安全／契約行為（RFC7807 decode、mutation conflict、capability type）
若四份複製，修復漏站會直接影響錯誤處理與授權 UX；但這不構成共享 UI、theme、i18n
或 route policy 的理由。

## Decision（決策）

在 ADR-028 的「無共用套件」上開一個**僅限契約與安全行為**的窄例外：

1. 建立版本化 `web/shared-contract` package，內容只允許：
   - 由 `api/openapi-runtime.json`／ADR-031 pipeline 生成的 API types；
   - RFC7807／legacy error decoder；
   - ADR-034 mutation、idempotency、conflict contract types/helpers；
   - capability、session facade 的型別與無 UI 的驗證 helper；
   - contract fixture 與相容性測試。
2. 明確禁止納入 UI component、theme、i18n message、layout、page、route policy、
   portal-specific business workflow 與 portal navigation。
3. 四站保留各自 `package.json`、lockfile、build、test、Dockerfile 與 release；package
   使用 immutable semantic version，由 CI `npm pack` 驗證。現階段將該 tarball
   vendored 進 repo，四站以精確 `file:` 版本及 lockfile integrity 固定；Artifact Registry
   npm repository 可用後，發布**相同 tarball**，不得重包不同內容。
4. 不以 npm workspace/Turbo 作第一階段前置；production build 可從版本化 vendored
   tarball／lockfile 離線解析，確保單站可獨立搬離；轉 registry 不改 package boundary。
5. runtime export 仍是 API type SoT；shared package 不允許手改 generated type，也不把
   `api/openapi.yaml` 設計稿誤升為 runtime type SoT。
6. package 變更需 semantic-version impact、四站 typecheck／contract test 與 consumer
   matrix；breaking change 先發布新 major，不要求四站同時 deploy。

## Alternatives（考量的選項）

- **A：維持全部複製** — 最獨立，但安全／契約 bug 容易漏站；觸發條件已出現，故不採。
- **B：整併為 monorepo workspace + 共用 design system** — 改寫 ADR-028 的產品獨立性，
  範圍過大，不採。
- **C：只共享 generated type，其他仍複製** — 現況即如此，無法集中 mutation/error/
  capability 契約，不足。
- **D：版本化 shared-contract 窄例外（採用）** — 集中不可漂移的契約，保留 UI 與部署獨立。

## Consequences（後果）

- ＋四站的 API 型別、錯誤、衝突與 capability 語意有單一版本來源。
- ＋UI／品牌風格仍可完全分家，單站仍可獨立 build、deploy、搬 repo。
- ＋共享契約可逐站升版，不造成四站 lockstep deployment。
- －新增 package publish、版本治理、consumer matrix 與 registry availability 責任。
- －邊界需要 codeowners／lint 守門，否則 shared-contract 容易再次膨脹成共享 UI。

**完成門檻**：package boundary lint 可阻擋 React/UI/i18n 依賴；四站可各自從固定版本完成
離線 lockfile build；breaking contract 有 consumer matrix；移除四份重複契約後 tsc／build
全綠。

## 實作與驗證證據（2026-07-27）

- `web/shared-contract@0.1.0` 已包含 runtime OpenAPI types、RFC7807 error、mutation/conflict、
  capability 與 session contract；boundary lint 禁止 React/Next/UI/i18n/theme。
- `smartlock-shared-contract-0.1.0.tgz` 為固定 vendored 工件；四站 package/lockfile 精確
  pin，其 Dockerfile 明確複製 tarball。
- `api-types-sync.yml`、`shared-contract.yml`、`generate-api-types.sh` 與
  `vendor-shared-contract.sh` 固定 runtime SoT、consumer matrix、pack integrity 與四站
  typecheck。
- shared package boundary/test/build、四站 `tsc --noEmit` 與四站 production build
  已於 2026-07-27 通過。

## 重評觸發

- UI/theme 的跨站同步成本也達不可接受程度時，另開 ADR；不得直接擴大本 package。
- 私有 registry 建立後只改 distribution reference；若可用性低於 build SLO，維持
  vendored tarball，immutable version 與單站可搬移不變。
