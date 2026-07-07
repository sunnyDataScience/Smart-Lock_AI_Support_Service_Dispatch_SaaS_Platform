---
title: "ADR-002: per-brand 授權部署（大單體 + 內部容器 + 集中共用元件）"
version: 1.0
status: active
owner: 平台架構團隊
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P005_per-brand授權部署_大單體內部容器.md
---

# ADR-002: per-brand 授權部署（大單體 + 內部容器 + 集中共用元件）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 平台級 |
| 關聯 ADR | [ADR-004](./ADR-004_Casdoor統一IdP租戶License.md) · [ADR-016](./ADR-016_技師共享池獨立系統.md) · [ADR-020](./ADR-020_三庫物理隔離租戶模型.md) · [ADR-006](./ADR-006_即時高併發骨幹_Kafka_Redis_讀寫分離.md) |

## Context（背景與問題）

商業模式為品牌授權：**品牌商需平台方授權（License）才能部署，並綁定自己的 LINE channel 與設定**。品牌之間互為競爭對手，資料主權與隔離是硬需求；同時技師（鎖匠）是跨品牌身分，不能被切進單一品牌部署。需要一種部署拓撲同時滿足：品牌隔離、授權開通可控、跨品牌能力（技師池、知識精煉、身分）不重複建置。

## Decision（決策）

採 **per-brand 物理隔離 bundle + 集中共用元件雙層**：

1. **部署單元 = per-brand bundle（可完整獨立部署）**：每品牌一套授權部署，內部容器包含 web（僅品牌營運 dispatch portal）/ api / agent / 品牌 DB / Redis / MCP-RAG server，**物理隔離、一品牌一庫**（[ADR-020](./ADR-020_三庫物理隔離租戶模型.md)）。師傅端 web **不在此 bundle**（屬技師平台，[ADR-016](./ADR-016_技師共享池獨立系統.md)），故品牌不依賴任何共享元件即可獨立上線。
2. **大單體 + 內部容器**：單一部署邏輯內含容器化的內部服務，非分散式微服務網——維運心智以「一個品牌一套」為單位。
3. **License 開通 → provisioning**：品牌經 Casdoor subscription 授權（[ADR-004](./ADR-004_Casdoor統一IdP租戶License.md)）→ provisioning 流程：License 驗證 → 部署 bundle → 建庫 → 綁定品牌 LINE channel 與設定 → 健康檢查。
4. **集中共用元件（跨品牌集中部署，非 per-brand）**：Casdoor、SigNoz、technician-platform（含獨立師傅 web）、平台維運 console、共享訊息 bus（Kafka）、knowledge-refinery（License 附加系統，含獨立 web）。**「開通哪些附加模組」由 License 決定**。

## Alternatives（考量的選項）

- **A：單一多租戶雲端部署（RLS 邏輯隔離）** — 資源共用省成本，但資料主權弱、競品同庫信任成本高，且與「一品牌一庫」隔離模型相悖。
- **B：per-brand 獨立部署（物理隔離，採用）** — 每品牌一套授權部署，資料 / LINE 完全隔離。
- **C：混合（共用控制面 + per-brand 資料面）** — 部分優點被吸收為本決策的「集中共用元件」分層。

## Consequences（後果）

**正面**：物理隔離 → 資料主權 / 隔離 / 授權可控；直接對齊品牌授權商業模式；集中元件避免每品牌重複建置。
**風險**：per-brand 部署運維隨品牌數擴散 → 需 provisioning 自動化（IaC / 腳本）與統一升級 / 回滾策略（[ADR-003](./ADR-003_工程治理排程_API收斂_migration_CD.md)）；集中元件成跨品牌單點，需 HA；per-brand 與集中元件之間的網路 / 認證邊界須明確設計。
**影響範圍**：部署拓撲、provisioning 流程、[23_Deployment_Guide](../23_Deployment_Guide.md)。
**重評觸發**：品牌數成長到 per-brand 運維不可持續 → 評估共用控制面 + namespace 隔離。

## Status 附註

- 🔜 規劃中：provisioning 全自動化（License → 部署 → 建庫 → 綁 LINE → 健康檢查一鍵完成），依賴 CD 基盤（[ADR-003](./ADR-003_工程治理排程_API收斂_migration_CD.md)）。
- 雲端起步期允許以單一 bundle（`API_SURFACE=all`，[ADR-022](./ADR-022_API_SURFACE單體多面塑形.md)）承載首個品牌，拓撲隨品牌數成長展開為 per-brand。
