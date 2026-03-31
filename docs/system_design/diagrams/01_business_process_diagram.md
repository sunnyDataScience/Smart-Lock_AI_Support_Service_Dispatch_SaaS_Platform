# 01 — Business Process Diagram（業務流程圖）

> **為什麼重要？** 先搞清楚業務怎麼跑，才能確保系統設計貼合實際營運。

## 概述

本圖描繪電子鎖售後服務從「客戶報修 → AI 診斷 → 解決/派工 → 結案」的完整業務流程，涵蓋 V1.0 AI 智能客服與 V2.0 技師派工兩大階段。

---

## 業務流程總覽

```mermaid
flowchart TB
    subgraph CUSTOMER["👤 客戶端"]
        A([客戶遇到電子鎖問題]) --> B[透過 LINE 發送報修訊息]
    end

    subgraph AI_SERVICE["🤖 V1.0 AI 智能客服"]
        B --> C{訊息類型判斷}
        C -->|文字訊息| D[對話狀態機啟動]
        C -->|非文字訊息| E[轉接真人表單]

        D --> F[ProblemCard 結構化擷取]
        F --> G{資訊完整？}
        G -->|否| H[追問缺失欄位]
        H --> F
        G -->|是| I[三層解決引擎]

        I --> J{L1: 向量案例搜尋}
        J -->|相似度 ≥ 0.85| K[回傳歷史解決方案]
        J -->|未命中| L{L2: RAG 手冊檢索}
        L -->|找到答案| M[回傳 AI 生成解答]
        L -->|無法解決| N{L3: 升級處理}
        N --> O[轉接真人客服]
        N --> P[建立派工需求]
    end

    subgraph KNOWLEDGE["📚 知識飛輪"]
        K --> Q{客戶回饋}
        M --> Q
        Q -->|正面回饋| R[自動生成 SOP 草稿]
        R --> S[管理員審核]
        S -->|核准| T[發佈至知識庫]
        T --> U[下次查詢命中率提升]
    end

    subgraph DISPATCH["🔧 V2.0 技師派工"]
        P --> V[智慧派工引擎]
        V --> W[匹配最佳技師]
        W --> X[推播工單至技師池]
        X --> Y{技師接單}
        Y -->|接受| Z[前往現場維修]
        Y -->|拒絕/逾時| W
        Z --> AA[完工回報 + 拍照存證]
    end

    subgraph ACCOUNTING["💰 V2.0 帳務結算"]
        AA --> AB[報價引擎自動計價]
        AB --> AC[生成帳單]
        AC --> AD[月結對帳]
        AD --> AE[技師撥款]
    end

    subgraph CLOSURE["✅ 結案"]
        K --> AF[案件結案]
        M --> AF
        O --> AF
        AE --> AF
        AF --> AG[客戶滿意度調查]
    end

    style CUSTOMER fill:#e3f2fd,stroke:#1565c0
    style AI_SERVICE fill:#f3e5f5,stroke:#7b1fa2
    style KNOWLEDGE fill:#e8f5e9,stroke:#2e7d32
    style DISPATCH fill:#fff3e0,stroke:#e65100
    style ACCOUNTING fill:#fce4ec,stroke:#c62828
    style CLOSURE fill:#f1f8e9,stroke:#558b2f
```

---

## 核心業務指標

| 流程環節 | KPI | 目標值 |
|:---------|:----|:------|
| AI 首次回應 | 回應時間 | < 5 秒 |
| L1 案例搜尋 | 命中率 | ≥ 70% |
| L1+L2 自助解決 | 解決率 | ≥ 60% |
| 技師接單 | 接單率 | ≥ 60% |
| 帳單準確度 | 零人工調整率 | ≥ 70% → 95% |
| 整體服務 | 客戶滿意度 | ≥ 4.5 / 5.0 |

---

## 業務角色參與矩陣

| 流程 | 客戶 | AI 系統 | 管理員 | 技師 |
|:-----|:----:|:-------:|:------:|:----:|
| 報修發起 | ●主導 | ○接收 | | |
| 問題診斷 | ○提供資訊 | ●主導 | | |
| 知識庫查詢 | | ●執行 | | |
| SOP 審核 | | ○生成 | ●審核 | |
| 派工分配 | | ●匹配 | ○監控 | ○接收 |
| 現場維修 | ○等待 | | ○追蹤 | ●執行 |
| 帳務結算 | | ●自動化 | ●審核 | ○確認 |

● = 主要負責 ○ = 參與協助
