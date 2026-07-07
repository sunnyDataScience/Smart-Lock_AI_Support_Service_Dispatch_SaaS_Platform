# ADR-P014: 技師平台佣金邊界 + 工單可見性（CQRS 投影）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（業主 2026-07-07 裁決）|
| 日期 | 2026-07-07 |
| 決策者 | 業主 + 架構師 |
| 層級 | 平台級（Platform）· tier-1 契約級 |
| 關聯 | **refines** [[ADR-P004]]（技師共享池；本 ADR 補其 2 個 [待確認]，不改 ADR-P004）· [[ADR-P005]]（per-brand 物理隔離）· [[ADR-P007]]（Kafka）|

## 1. 背景與問題

technician-platform target SAD 標出 2 個 tier-1 待裁缺口：
1. **佣金主體邊界**：[[ADR-P004]] 訂技師平台擁「佣金主體」，但現況金額計算 + statement（`saas.technician_statement` / `dispatcher_commission_statement` / `technician_payout_rule`）落在**品牌庫**。
2. **技師工單可見性**：per-brand 物理隔離（[[ADR-P005]]）下技師平台**無法直連品牌庫讀工單**，技師如何看到跨品牌的派工。

**共同本質**：技師平台是品牌事件的 **CQRS 消費端**——命令端（工單/計費）真相在品牌庫，查詢端（技師視角/結算）在技師平台。

## 2. 決策

### 2.1 佣金：Billing（品牌）/ Settlement（技師平台）分離
- **品牌庫 = 計費（Billing）**：算「該工單付技師多少」（per-job 佣金明細，依賴工單金額/料件/完工，皆品牌側資料）→ 發 **`commission.accrued` 事件**（Kafka）。
- **技師平台 = 結算主體（Settlement）**：訂閱各品牌 `commission.accrued` → **技師跨品牌單一對帳/statement/payout** 主體（`lock_tech` 自有）。
- → [[ADR-P004]]「佣金主體」精確界定為**結算/對帳/payout 主體**（技師平台）；**per-job 計費引擎留品牌**（貼近資料源，避免跨庫依賴）。

### 2.2 技師工單可見性：Kafka-fed read-model（CQRS 投影）
- 品牌 api 發**工單生命週期事件**（`workorder.dispatched/updated/completed`，含該技師派工）→ Kafka。
- 技師平台**訂閱並維護「技師視角工單投影」**（技師平台自有庫）→ 技師 web 從投影讀跨品牌派工。
- **投影欄位最小化**（隱私/最小權限）：工單摘要 / 地址 / 狀態 / 時窗 / 金額 / 該技師派工——**不整包複製品牌敏感資料**。
- 選項 A（技師平台直連品牌庫）違反 [[ADR-P005]] 物理隔離 → 否決；選項 B（技師 web 逐一打 N 品牌 api 聚合）慢且脆 → 否決。

### 2.3 統一視圖
technician-platform = **品牌事件的 CQRS read-model + 結算主體**：命令端（工單/計費）在品牌庫、查詢端（技師工單視圖）+ 結算（佣金彙總）在技師平台，靠 **Kafka 事件骨幹**（[[ADR-P007]]）同步。兩缺口共用同一事件流。

## 3. 後果

**正面**：per-brand 物理隔離不破；技師跨品牌單一工單視圖 + 單一結算對帳；計費貼近資料源、結算貼近技師；解 G-08 跨庫雙寫（改事件驅動）。
**負面/風險**：
- **最終一致性**：投影/對帳有事件延遲 → 技師看工單可接受；金流結算需對帳閘門（期末 reconcile）。
- **事件 schema 治理**：`commission.accrued` / `workorder.*` 需 schema registry + 契約測試（[[ADR-P007]] R-02）。
- **投影隱私**：欄位最小化 + 租戶標記，避免品牌資料外洩至跨租戶技師平台。
**影響範圍**：品牌 api 發 2 類事件；技師平台建投影表 + 對帳；technician-platform SAD 的 R-03/R-04/§5.3 由 [待確認] → 定案（指向本 ADR）。

## 4. 執行計畫

1. 定義事件契約：`workorder.{dispatched,updated,completed}`、`commission.accrued`（schema + registry）。
2. 品牌 api：per-job 佣金計費 + 發事件（沿用 outbox）。
3. 技師平台：工單投影 read-model（消費者 + 投影表）+ 佣金彙總/對帳/statement（由品牌庫 `saas.technician_statement` 等遷入）。
4. 對帳閘門（期末 reconcile 品牌計費 vs 技師平台彙總）。
5. 契約測試（consumer-driven）+ 投影欄位隱私審查。

## 5. 選用影響區段
- **架構**：技師平台 = CQRS read-model + 結算主體；事件驅動取代跨庫雙寫。
- **資料**：佣金 statement/ledger 遷入技師平台；工單投影最小化欄位。
- **整合**：品牌 api → Kafka（工單/佣金事件）→ 技師平台。
- **安全**：投影欄位最小化 + 租戶隔離；最終一致性需對帳閘門。
