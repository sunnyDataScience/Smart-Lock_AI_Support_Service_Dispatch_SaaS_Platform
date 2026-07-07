---
title: "ADR-017: 技師平台佣金邊界 + 工單可見性（CQRS 投影）"
version: 1.0
status: active
owner: 平台架構團隊
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P014_技師平台佣金邊界與工單CQRS投影.md
---

# ADR-017: 技師平台佣金邊界 + 工單可見性（CQRS 投影）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 平台級 · tier-1 契約級 |
| 關聯 ADR | **refines** [ADR-016](./ADR-016_技師共享池獨立系統.md) · [ADR-002](./ADR-002_per-brand授權部署.md) · [ADR-006](./ADR-006_即時高併發骨幹_Kafka_Redis_讀寫分離.md) |

## Context（背景與問題）

per-brand 物理隔離（[ADR-002](./ADR-002_per-brand授權部署.md)）下有兩個 tier-1 邊界問題：

1. **佣金主體邊界**：per-job 金額計算依賴工單金額 / 料件 / 完工——皆品牌側資料；但技師需要跨品牌單一對帳 / statement / payout。「佣金」一詞須拆開界定歸屬。
2. **技師工單可見性**：技師平台不得直連品牌庫讀工單，技師如何看到跨品牌的派工？

共同本質：技師平台是品牌事件的 **CQRS 消費端**——命令端（工單 / 計費）真相在品牌庫，查詢端（技師視角 / 結算）在技師平台。

## Decision（決策）

### 佣金：Billing（品牌）/ Settlement（技師平台）分離

| 邊界 | 歸屬 | 職責 | 資料 |
|---|---|---|---|
| **計費（Billing）** | 品牌庫 | 算「該工單付技師多少」（per-job 佣金明細，依工單金額 / 料件 / 完工）→ 發 **`commission.accrued` 事件**（Kafka）| 品牌側 per-job 明細 |
| **結算（Settlement）** | 技師平台 | 訂閱各品牌 `commission.accrued` → **技師跨品牌單一對帳 / statement / payout** 主體 | `lock_tech` 自有（statement / payout rule 等結算資料）|

→ [ADR-016](./ADR-016_技師共享池獨立系統.md) 的「佣金主體」精確界定為**結算 / 對帳 / payout 主體**；**per-job 計費引擎留品牌**（貼近資料源，避免跨庫依賴）。

### 技師工單可見性：Kafka-fed read-model（CQRS 投影）

- 品牌 api 發**工單生命週期事件**（`workorder.dispatched` / `workorder.updated` / `workorder.completed`，含該技師派工）→ Kafka。
- 技師平台**訂閱並維護「技師視角工單投影」**（技師平台自有庫）→ 師傅 web 從投影讀跨品牌派工。
- **投影欄位最小化**（隱私 / 最小權限）：工單摘要 / 地址 / 狀態 / 時窗 / 金額 / 該技師派工——**不整包複製品牌敏感資料**，且帶租戶標記。

### 統一視圖

technician-platform = **品牌事件的 CQRS read-model + 結算主體**：命令端（工單 / 計費）在品牌庫、查詢端（技師工單視圖）+ 結算（佣金彙總）在技師平台，靠 **Kafka 事件骨幹**（[ADR-006](./ADR-006_即時高併發骨幹_Kafka_Redis_讀寫分離.md)）同步。兩個問題共用同一事件流。

## Alternatives（考量的選項）

- **A：技師平台直連品牌庫** — 違反 per-brand 物理隔離，否決。
- **B：師傅 web 逐一打 N 個品牌 api 聚合** — 慢且脆（N 品牌可用性相乘），否決。
- **C：Kafka-fed CQRS 投影 + Billing/Settlement 分離（採用）** — 隔離不破、單一視圖、計費貼資料源。

## Consequences（後果）

**正面**：per-brand 物理隔離不破；技師跨品牌單一工單視圖 + 單一結算對帳；計費貼近資料源、結算貼近技師；跨庫雙寫改為事件驅動。
**風險**：
- **最終一致性**：投影 / 對帳有事件延遲——技師看工單可接受；金流結算需**對帳閘門**（期末 reconcile 品牌計費 vs 技師平台彙總）。
- **事件 schema 治理**：`commission.accrued` / `workorder.*` 需 schema registry + consumer-driven 契約測試。
- **投影隱私**：欄位最小化 + 租戶標記，防品牌資料外洩至跨租戶技師平台。
**影響範圍**：品牌 api 發兩類事件（沿用 outbox）；技師平台建投影表 + 佣金彙總 / 對帳 / statement；事件契約見 [17_AsyncAPI](../17_AsyncAPI.yaml)。
**重評觸發**：事件延遲影響結算正確性事故 → 收緊對帳頻率或改同步查詢混合模式。

## Status 附註

- 依賴 [ADR-006](./ADR-006_即時高併發骨幹_Kafka_Redis_讀寫分離.md) Phase 2 Kafka 事件骨幹。🔜 規劃中：事件契約定義 → 品牌 api 計費 + 發事件 → 技師平台投影 + 結算遷入 → 對帳閘門 → 契約測試 + 投影隱私審查。
