# 06 高階端到端參考架構 — 生成規格

> 此 prompt 已把工業視覺的 Video／Metadata／Control／Storage 語意，轉譯為 Smart Lock AI 客服與派工 SaaS 的四條資料路徑。不得新增攝影機、Video Streaming、Edge GPU 或影像辨識等不存在的能力。

## 06-1 High-Level End-to-End Reference Architecture

由左至右五個 L1 Zone：

1. Actors & Inbound Signals
2. Channel & AI Runtime
3. Interaction & Event Distribution
4. Domain Services & Data
5. Applications & External Systems

底部放一條 Cross-Cutting Management Zone：

- Control Plane
- Configuration
- Channel & Client Management
- Security & Governance
- Observability & Operations

只畫 L2 主要元件。四條資料路徑：

- 藍色實線：即時互動／交易請求；標 LINE webhook、REST、WebSocket、Flex／LIFF 等協定或格式。
- 綠色虛線：AI metadata／domain event；標 Internal JSON、AsyncAPI、Kafka topic family。
- 紫色虛線：License／configuration／OIDC／RBAC／S2S／tenant policy。
- 橘色虛線：SQL／JSONB、Outbox、pgvector、evidence object、event replay。

所有外部整合須通過明確 adapter／gateway；品牌 api 不得直連技師庫；AI 不得直接開單、派工、final quote 或觸發金流。

## 06-2 Component Catalog

將 06-1 的每個 L2 component 畫成獨立卡片，卡片包含：

- 元件名稱
- 單一句責任
- 主要協定／資料

不畫內部 class、function、endpoint、pod、table 或 UI 頁面。元件卡依 L1 Zone 分組，供簡報、ADR、SAD 與後續細化圖重用。

## 視覺規格

- 白底、扁平化、低裝飾、矩形元件、無 3D icon。
- Zone 使用淡色表頭與灰色邊界；Component 使用白底加語意色框。
- 連線採正交路由並保留獨立 lane；不可把即時互動與事件 metadata 混成同一條線。
- 圖例必須同時說明四種線型、同步／非同步、`🔜` 參考目標狀態。

