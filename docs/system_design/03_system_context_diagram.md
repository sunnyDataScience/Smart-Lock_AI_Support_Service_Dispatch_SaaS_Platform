# 03 — System Context Diagram（系統上下文圖）

> **為什麼重要？** 定義系統與外部系統的關係，釐清整合邊界與資料流向。

## 概述

本圖以 C4 Model Level 1 的方式，展示 Smart Lock AI SaaS Platform 與所有外部角色、外部系統之間的關係。

---

## 系統上下文圖

```mermaid
C4Context
    title Smart Lock AI SaaS Platform — System Context Diagram

    Person(consumer, "客戶", "電子鎖終端使用者，透過 LINE 報修諮詢")
    Person(technician, "技師", "外派維修技師，透過 Web App 接單與回報")
    Person(admin, "管理員", "營運/客服主管，透過 Admin Panel 管理系統")

    System(platform, "Smart Lock AI SaaS Platform", "AI 智能客服 + 自動派工 + 帳務結算一站式平台")

    System_Ext(line_api, "LINE Messaging API", "訊息收發、Webhook、Rich Menu、Flex Message")
    System_Ext(gemini, "Google Gemini API", "LLM 推論（意圖識別、對話生成、SOP 生成）")
    System_Ext(embedding, "Google Embedding API", "text-embedding-004 文字向量化（768 維）")
    System_Ext(maps, "Google Maps API", "地理距離計算、技師路線優化（V2.0）")
    System_Ext(duckduckgo, "DuckDuckGo Search", "網路搜尋（市場趨勢、產品比較）")
    System_Ext(order_api, "訂單查詢 API", "外部訂單狀態查詢（sunnie-lock.com）")

    Rel(consumer, platform, "報修諮詢、查詢進度、提供回饋", "LINE")
    Rel(technician, platform, "瀏覽工單、接單、完工回報", "HTTPS / PWA")
    Rel(admin, platform, "監控儀表板、審核 SOP、管理知識庫", "HTTPS")

    Rel(platform, line_api, "接收 Webhook、發送回覆/推播", "HTTPS")
    Rel(platform, gemini, "LLM 推論請求", "HTTPS / gRPC")
    Rel(platform, embedding, "文字向量化", "HTTPS / gRPC")
    Rel(platform, maps, "地理距離查詢", "HTTPS")
    Rel(platform, duckduckgo, "網路搜尋", "HTTPS")
    Rel(platform, order_api, "訂單狀態查詢", "HTTPS")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

---

## 外部系統整合明細

| 外部系統 | 提供者 | 用途 | 協定 | 風險等級 | 階段 |
|:---------|:------|:-----|:-----|:---------|:-----|
| LINE Messaging API | LINE Corp. | 客戶互動通道（Webhook + Reply/Push） | HTTPS + HMAC-SHA256 | 低 | V1.0 |
| Google Gemini 3 Pro | Google | 意圖識別、對話生成、SOP 草稿、ProblemCard 擷取 | HTTPS / gRPC | 中 | V1.0 |
| Google text-embedding-004 | Google | 案例與手冊文本向量化（768 維） | HTTPS / gRPC | 中 | V1.0 |
| Google Maps API | Google | V2.0 地理距離計算、技師路線規劃 | HTTPS | 低 | V2.0 |
| DuckDuckGo Search | DuckDuckGo | 免費網路搜尋（無需 API Key） | HTTPS | 低 | V1.0 |
| 訂單查詢 API | sunnie-lock.com | 外部訂單狀態查詢 | HTTPS + Bearer Token | 中 | V1.0 |

---

## 資料流向摘要

```mermaid
flowchart LR
    subgraph INBOUND["入站資料流"]
        A["LINE Webhook<br/>(使用者訊息)"] --> P["Platform"]
        B["訂單 API<br/>(訂單狀態)"] --> P
        C["DuckDuckGo<br/>(搜尋結果)"] --> P
    end

    subgraph CORE["核心處理"]
        P --> D["Gemini LLM<br/>(推論)"]
        P --> E["Embedding API<br/>(向量化)"]
        D --> P
        E --> P
    end

    subgraph OUTBOUND["出站資料流"]
        P --> F["LINE Reply/Push<br/>(回覆客戶)"]
        P --> G["Admin Panel<br/>(儀表板資料)"]
        P --> H["Technician App<br/>(工單推播)"]
    end

    style INBOUND fill:#e3f2fd,stroke:#1565c0
    style CORE fill:#f3e5f5,stroke:#7b1fa2
    style OUTBOUND fill:#e8f5e9,stroke:#2e7d32
```
