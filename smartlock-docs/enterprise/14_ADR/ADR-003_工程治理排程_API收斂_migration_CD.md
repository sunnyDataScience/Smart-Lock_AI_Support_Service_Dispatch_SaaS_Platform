---
title: "ADR-003: 平台工程治理排程（migration 防漂移・API 版本收斂・CD 自動化）"
version: 1.0
status: active
owner: 平台架構團隊
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P012_執行債清償排程_cutover_migration_CD.md
---

# ADR-003: 平台工程治理排程（migration 防漂移・API 版本收斂・CD 自動化）

| 欄位 | 內容 |
|---|---|
| 狀態 | 排程中 |
| 層級 | 平台級 |
| 關聯 ADR | [ADR-002](./ADR-002_per-brand授權部署.md) · [ADR-021](./ADR-021_psycopg3_rawSQL與純SQL_migration.md) · [ADR-022](./ADR-022_API_SURFACE單體多面塑形.md) |

## Context（背景與問題）

平台有三項**方向明確、無設計分叉**的工程治理工作，需要的不是新架構決策，而是正式的優先序、負責面與驗收條件：

1. **migration 套用狀態防漂移**：schema 演進採純 SQL forward-only（[ADR-021](./ADR-021_psycopg3_rawSQL與純SQL_migration.md)），「已套用」唯一真相源為 `public.schema_migrations` 表；人工登記簿（`MIGRATION_REGISTRY.md`）僅為意圖註記。若無自動比對，登記與各環境實況會漂移並直接咬到測試與生產可靠性。
2. **API 版本收斂**：對外 API 以 v2 為正典面；v1 相容面僅供既有 caller 過渡（約 42 個 caller [待確認]），須凍結新增並排程遷移，避免相容面持續長大。
3. **CD 自動化**：CI（test / lint / smoke / loadtest，13 條 workflow）已就緒，部署自動化（build → deploy → health check）須補齊；per-brand provisioning（[ADR-002](./ADR-002_per-brand授權部署.md)）沒有 CD 基盤即無法規模化交付。

## Decision（決策）

以單一排程 ADR 統一裁定三項工作的優先序（依風險而非工作量排序）：

**優先序 1 — migration drift-check（可靠性風險最高）**
1. 正典化：`public.schema_migrations` 為「已套用」唯一真相源。
2. CI drift-check：對 migration 檔 fresh-apply + 比對 `schema_migrations`，漂移即 fail。
3. 一次性 reconcile：歷史編號補登。
負責面：api / data。

**優先序 2 — API v1 → v2 收斂（先凍結、再遷移）**
1. **凍結 v1 新增**：`/api/v1` 不再掛新 router，新功能一律走 v2 正典前綴。
2. 盤點 v1 caller，依 cutover 5 gate 逐一遷 v2（涉 contract 者逐案過 CIA）。
3. caller 歸零後移除 v1 相容面與 `DeprecationMiddleware`。
負責面：api。

**優先序 3 — CD（分兩段）**
1. **基礎 CD**：三個 Cloud Run 服務（agent / api / web）接 GitHub Actions tag/merge 觸發 build → deploy。
2. **per-brand provisioning 自動化**：License → 部署 → 建庫 → 綁 LINE，隨 [ADR-002](./ADR-002_per-brand授權部署.md) 落地。
負責面：platform / deploy。

## Alternatives（考量的選項）

- **A：ad-hoc backlog** — 無排程、無驗收，三項工作無限期漂浮。
- **B：本 ADR 集中排程（採用）** — 三者皆為執行項、無設計分叉，一份排程 ADR 即可治理。
- **C：各拆一份獨立 ADR** — 三份過重；無設計分叉的工作不值各自一份。

## Consequences（後果）

**正面**：三項工作有優先序 / 負責面 / 驗收；migration 可靠性風險止血；API 面收斂；CD 為 per-brand 交付解鎖前置。
**風險**：本 ADR 只排程不實作，仍需 sprint 認領；v1 caller 遷移含業主逐案裁決 gate；provisioning 自動化被 [ADR-002](./ADR-002_per-brand授權部署.md) 落地進度 gate。
**影響範圍**：CI workflow（新增 drift-check + CD job）、api 路由治理、部署腳本。
**重評觸發**：任一項排程後仍無 sprint 認領 → 升級為阻塞議題單獨追蹤。

## Status 附註

- 🔜 排程中三項皆未完成；近期低風險先行：drift-check、基礎 CD；跨 sprint：v1 caller 遷移、provisioning 自動化。
