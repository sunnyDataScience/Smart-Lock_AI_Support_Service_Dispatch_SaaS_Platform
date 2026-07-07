# ADR-P008: Model Orchestration Layer（模型編排層，供應商無關）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（target-state 理想態 v2）|
| 日期 | 2026-07-07 |
| 決策者 | 業主 + 架構師 |
| 層級 | 平台級（Platform）|
| 關聯 | [[ADR-002]]（LiteLLM 統一供應商，本 ADR 將其抬升為平台能力層）· [[ADR-P009]] |

## 1. 背景與問題

跨產業是真需求（見 `06_platformization_strategy`）。模型調用若綁單一供應商，換家即改碼，且各產業診斷系統需調不同編排配方。現況 LiteLLM（[[ADR-002]]）已用 model 字串路由多家、CLAUDE.md 亦禁 agent 直接 import 各家 SDK，但仍被視為「agent 內部細節」，未成為明確的可抽換平台層。

## 2. 考量的選項

- **A：維持 LiteLLM 於 agent 內部** — 已解供應商 SDK 耦合，但編排配方、調用效率、eval 分散，非平台一等公民。
- **B：抬升為 Model Orchestration Layer（平台能力層）** — 供應商=配置、編排配方=配置、調用效率與 eval 集中於此層，供應商中立。
- **C：綁定單一供應商 SDK** — 效能/功能貼合，但鎖死、違反跨產業重用。

## 3. 決策

採 **選項 B：Model Orchestration Layer**——平台核心的一層可抽換能力，供 FDE 每產業調（配置面 ①診斷系統的一部分，[[ADR-P009]]），但不需重寫：

1. **供應商 = 配置**：model 字串 + credential；code 不依賴任何家 SDK（沿 CLAUDE.md 鐵律）。
2. **編排配方 = 配置**：prompt / skill 行為 / RAG 檢索 / tool 序列 / fallback / eval，皆 per-industry 可調。
3. **調用效率在本層**：批次、快取、串流、平行工具呼叫、逾時/重試——供應商中立地最佳化。
4. **多供應商 failover**：接 `FallbackProvider`（現況未接），主模型故障走備援而非直接 sentinel。
5. **eval 掛 OPIK**（[[ADR-P002]]，dev 必開 / prod 可關）。

## 4. 後果

**正面**：換供應商零改碼；診斷系統的 model 編排成為可配置產物；調用效率與可靠性集中治理。
**負面/風險**：抽象層可能遮蔽特定供應商的獨門功能 → 保留「原生逃生艙」（特定家進階功能可經配置直通）。
**影響範圍**：agent runtime、knowledge-refinery、MCP-RAG（embedding）皆走本層；`build_provider` 需真正回 Fallback 而非裸 provider。
**重新評估觸發**：某供應商獨門能力成為關鍵競爭力且無法抽象 → 局部深綁 + 隔離。

## 5. 執行計畫

1. 明確化 `LiteLLMProvider` 為 Model Orchestration Layer 邊界；供應商/配方入配置。
2. 接 `FallbackProvider`（多供應商容錯）。
3. 調用效率能力（快取/批次/平行工具/重試）收斂至本層。
4. eval → OPIK；per-industry 編排配方納入 Vertical Pack 的診斷系統配置。

## 6. 選用影響區段
- **架構/依賴**：供應商中立層，零 SDK 耦合。
- **效能**：調用效率集中最佳化。
- **可靠性**：多供應商 failover。
- **配置**：編排配方 = FDE per-industry 可調。
