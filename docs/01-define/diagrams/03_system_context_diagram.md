---
status: superseded
superseded_by: docs_v2/1-decisions/architecture-overview.md (C4-context)
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# 03 — System Context Diagram（系統上下文圖）

> **為什麼重要？** 定義系統與外部系統的關係，釐清整合邊界與資料流向。

## 概述

本圖以 C4 Model Level 1 的方式，展示 Smart Lock AI SaaS Platform 與所有外部角色、外部系統之間的關係。

---

## 系統上下文圖

```mermaid
flowchart TB
    subgraph Users["Users"]
        consumer["客戶\n電子鎖終端使用者\n透過 LINE 報修諮詢"]
        technician["技師\n外派維修技師\n透過 Web App 接單"]
        admin["管理員\n營運/客服主管\n透過 Admin Panel"]
    end

    platform["Smart Lock AI SaaS Platform\nAI 智能客服 + 自動派工\n+ 帳務結算一站式平台"]

    subgraph External["External Systems"]
        line_api["LINE Messaging API\n訊息收發 / Webhook\nRich Menu / Flex Message"]
        gemini["Google Gemini API\nLLM 推論"]
        embedding["Google Embedding API\ntext-embedding-004\n768 維向量化"]
        maps["Google Maps API\n地理距離計算 V2.0"]
        duckduckgo["DuckDuckGo Search\n網路搜尋"]
        order_api["訂單查詢 API\nsunnie-lock.com"]
    end

    consumer -->|"LINE 報修諮詢"| platform
    technician -->|"HTTPS/PWA 接單回報"| platform
    admin -->|"HTTPS 管理監控"| platform

    platform -->|"HTTPS Webhook"| line_api
    platform -->|"HTTPS/gRPC"| gemini
    platform -->|"HTTPS/gRPC"| embedding
    platform -->|"HTTPS"| maps
    platform -->|"HTTPS"| duckduckgo
    platform -->|"HTTPS"| order_api

    style Users fill:#e3f2fd,stroke:#1565c0
    style platform fill:#fff3e0,stroke:#e65100
    style External fill:#f3e5f5,stroke:#7b1fa2
```

---

## 外部系統整合明細

| 外部系統 | 提供者 | 用途 | 協定 | 風險等級 | 階段 |
|:---------|:------|:-----|:-----|:---------|:-----|
| LINE Messaging API | LINE Corp. | 客戶互動通道（Webhook + Reply/Push） | HTTPS + HMAC-SHA256 | 低 | V1.0 |
| Google Gemini 2.5 Flash | Google | 意圖識別、對話生成、SOP 草稿、ProblemCard 擷取 | HTTPS / gRPC | 中 | V1.0 |
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
