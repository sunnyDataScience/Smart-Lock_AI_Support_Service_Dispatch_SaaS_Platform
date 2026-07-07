# ADR-P007: 即時通道高併發強化（Kafka + Redis + 讀寫分離）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（target-state / 理想態 v2）|
| 日期 | 2026-07-07 |
| 決策者 | 業主（授權架構師定案）|
| 層級 | 平台級（Platform）|
| 關聯缺口 | G-03（即時通道 in-memory 單機）、部分 G-01（水平擴展）|

## 1. 背景與問題

現況 G-03：api 即時通道為 **in-memory pub-sub hub（`ws_hub.py` 單例）+ 11 個進程內 cron worker**，Cloud Run 多實例會**跨實例事件遺失、cron 重複跑**（重複 LINE 推播/告警），DB 為單一共享 AsyncConnection（非連線池）。業主目標：**後續大量技師上工，系統不能卡頓，通訊要絲滑**。

## 2. 考量的選項

- **選項 A：只 Redis**（pub/sub + cache）— 輕、低延遲，但無持久事件流/重播，跨系統事件整合弱。
- **選項 B：只 Kafka** — 持久事件骨幹，但單看 WS 即時推播偏重、延遲較高。
- **選項 C：三者分層全導入**（Kafka + Redis + 讀寫分離）— 各司其職。

## 3. 決策

採 **選項 C：三者分層全導入**（架構師判斷，角色不重疊）：

| 元件 | 角色 | 分期 |
|---|---|---|
| **Redis** | WS pub/sub fanout（取代 in-memory hub，低延遲「絲滑」推播）+ 熱讀 cache + 分散式鎖（cron 去重）+ 連線池前置 | **Phase 1**（即時見效）|
| **讀寫分離** | Postgres primary + read replica，清單/報表/技師查詢走 replica，寫走 primary | **Phase 1/2** |
| **Kafka** | 派工/技師/工單生命週期**事件骨幹**：持久、可重播、解耦消費，餵 SigNoz 與 technician-platform 跨系統整合 | **Phase 2** |

## 4. 後果

**正面**：WS 可水平擴展且低延遲（絲滑）；讀量可用 replica 擴展；Kafka 事件骨幹解耦並支撐跨系統（技師平台）整合與重播；cron 改分散式鎖消除重複。
**負面/風險**：三套基礎設施維運成本；Kafka 運維較重（per-brand vs 集中需定位——建議集中共用，見 [[ADR-P005]]）；引入最終一致性語義需前端/流程配合；連線池 + 讀寫分離需改造現況單一共享 connection。
**影響範圍**：api realtime + cron 全面改造；DB 拓撲加 replica；新增 Redis / Kafka 基礎設施。
**重新評估觸發**：規模證實 Kafka overkill → 退回 Redis Streams 做輕量事件；或 log/事件量爆增 → 強化 Kafka 叢集。

## 5. 執行計畫

1. **Phase 1**：Redis 上線 → `ws_hub` 遷 Redis pub/sub；cron 加分散式鎖去重；DB 前置連線池（取代單一 AsyncConnection）；熱讀 cache。
2. **Phase 1/2**：read replica + 讀路由（讀走 replica、寫走 primary）。
3. **Phase 2**：Kafka 事件骨幹（dispatch/技師/工單 domain 事件）；解耦消費者（通知/SLA/結算/技師平台）；接 SigNoz。
4. cron worker 由進程內 → 分散式排程。

## 6. 選用影響區段

- **效能/可擴展**：WS 水平擴展 + 讀寫分離 + 事件解耦。
- **架構**：事件驅動骨幹（Kafka）+ 即時層（Redis）。
- **部署**：新增 Redis / Kafka（集中共用，見 [[ADR-P005]]）+ DB replica。
- **可靠性**：cron 分散式鎖消除重複副作用。
