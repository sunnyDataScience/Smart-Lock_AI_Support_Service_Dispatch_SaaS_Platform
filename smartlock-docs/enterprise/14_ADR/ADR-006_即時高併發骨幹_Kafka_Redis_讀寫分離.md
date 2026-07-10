---
title: "ADR-006: 即時高併發骨幹（Kafka 事件 + Redis fanout + 讀寫分離）"
version: 1.0
status: active
owner: 平台架構團隊
last-updated: 2026-07-10
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P007_即時高併發_Kafka_Redis_讀寫分離.md
  - smartlock-docs/api/P2/04_adr/ADR-003_in-memory_WS_hub_與_cron_worker.md
---

# ADR-006: 即時高併發骨幹（Kafka 事件 + Redis fanout + 讀寫分離）

| 欄位 | 內容 |
|---|---|
| 狀態 | 規劃中（分期）|
| 層級 | 平台級 |
| 關聯 ADR | [ADR-002](./ADR-002_per-brand授權部署.md) · [ADR-016](./ADR-016_技師共享池獨立系統.md) · [ADR-017](./ADR-017_技師平台佣金邊界與工單CQRS投影.md) · [ADR-007](./ADR-007_可觀測性分層_SigNoz_OPIK.md) |

## Context（背景與問題）

平台的即時與背景能力有兩類需求：

1. **即時推播**：派工佇列、工單事件、SLA 告警、退款/爭議、低庫存、RBAC 變更等 10 個即時頻道（9 WS + 1 SSE `/realtime/diagnostics`），需推給營運後台（web）與師傅端，畫面免輪詢即時更新。
2. **背景任務**：共 11 個週期任務——LINE outbox push、SLA 監測、對帳異常偵測、爭議自動 escalation、config canary 推進、對帳單 auto-approve、GDPR T+30 硬刪、evidence 保存期軟刪、48h 自動結案等。

業務目標：大量技師同時上工時系統不卡頓、通訊絲滑。這要求即時通道可水平擴展、背景任務多實例不重複執行、讀量可獨立擴展、且跨系統（技師平台）事件整合有持久可重播的骨幹。

## Decision（決策）

三元件分層全導入，各司其職、角色不重疊：

| 元件 | 角色 | 分期 |
|---|---|---|
| **Redis** | WS pub/sub fanout（跨實例低延遲推播）+ 熱讀 cache + 分散式鎖（11 個週期任務去重）+ DB 連線池前置 | **Phase 1** |
| **讀寫分離** | Postgres primary + read replica：清單 / 報表 / 技師查詢走 replica，寫走 primary | **Phase 1/2** |
| **Kafka** | 派工 / 技師 / 工單生命週期**事件骨幹**：持久、可重播、解耦消費；餵 SigNoz 與 technician-platform 跨系統整合（`workorder.*`、`commission.accrued` 等，見 [ADR-017](./ADR-017_技師平台佣金邊界與工單CQRS投影.md)）| **Phase 2** |

**Phase 0 起點**：單實例部署期，WS hub 以進程內單例（`realtime/ws_hub.py`）運作、11 個週期任務以 lifespan 啟停的進程內排程執行，並以 `API_SURFACE` 停用 tech/platform 面 worker 避免同庫雙跑（[ADR-022](./ADR-022_API_SURFACE單體多面塑形.md)）。此為刻意的分期起點：水平擴展（`max-instances > 1`）前必須完成 Phase 1。

## Alternatives（考量的選項）

- **A：只 Redis** — 輕、低延遲，但無持久事件流 / 重播，跨系統事件整合弱。
- **B：只 Kafka** — 持久事件骨幹，但用於 WS 即時推播偏重、延遲較高。
- **C：三者分層全導入（採用）** — 即時層（Redis）、事件層（Kafka）、讀擴展（replica）各解各的問題。

## Consequences（後果）

**正面**：WS 可水平擴展且低延遲；讀量以 replica 擴展；Kafka 解耦消費並支撐技師平台 CQRS 投影與重播；週期任務分散式鎖消除重複推播 / 重複告警。
**風險**：三套基礎設施維運成本；引入最終一致性語義需前端 / 流程配合；DB 需由單一共享連線改造為連線池。
**影響範圍**：api realtime + 週期任務全面改造；DB 拓撲加 replica；新增 Redis / Kafka 基礎設施（集中共用元件，[ADR-002](./ADR-002_per-brand授權部署.md)）。
**重評觸發**：規模證實 Kafka overkill → 退回 Redis Streams 輕量事件；Kafka **per-brand vs 集中**定位屬開放項（建議集中共用），事件量爆增時重評叢集策略。

## Status 附註

- Phase 1（Redis + 連線池 + 分散式鎖）→ Phase 1/2（read replica + 讀路由）→ Phase 2（Kafka 事件骨幹 + 解耦消費者 + 接 SigNoz）。
- 🔜 規劃中：全部三 Phase；Phase 1 為水平擴展（NFR-SCAL）前置硬條件。
- 2026-07-10：Phase 1 之 Redis fanout + cron 互斥已落地（CR-0134；去重鎖 as-built = PG advisory 領導者選舉而非 Redis 鎖，零新增基礎設施）+ CI 雙實例 e2e（CR-0151）；Phase 1 餘項 DB 連線池／熱讀 cache 無 WBS 工作包對映（排程斷鏈待業主，架構稽核 #5）；讀寫分離／Kafka 依 WBS 屬 M3+。
