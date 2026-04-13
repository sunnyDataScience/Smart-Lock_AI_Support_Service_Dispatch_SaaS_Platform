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

---

## 異常處理業務流程 (Exception Handling Business Process)

本圖描繪從工單建立到結案歸檔過程中，所有可能發生的異常路徑，包含拒單重派、範圍變更、缺料、延遲、品質不合格、客訴、保固爭議、門外觀變更，以及 Red_Code 緊急路徑與知識沉澱閉環。

```mermaid
flowchart TB
    subgraph NORMAL["正常路徑 (參照上方)"]
        A([工單建立]) --> B[派工匹配]
        B --> C[技師接單]
        C --> D[到場施工]
        D --> E[完工回報]
        E --> F[客戶確認]
        F --> G([結案歸檔])
    end

    subgraph EXCEPTIONS["異常路徑"]
        B -->|逾時/拒單| EX1{重新匹配}
        EX1 -->|成功| C
        EX1 -->|3次失敗| EX1A[人工派工]
        EX1A --> C

        C -->|技師取消| EX2[退回案件池]
        EX2 --> B

        D -->|範圍變更| EX3[範圍變更申請]
        EX3 -->|客戶同意| D
        EX3 -->|客戶拒絕| EX3A{改期或取消}
        EX3A -->|改期| EX3B[建立新工單]
        EX3A -->|取消| EX3C[收車馬費結案]

        D -->|缺料| EX4[缺料回報]
        EX4 --> EX4A[部分完工 + 改期]
        EX4A --> EX3B

        D -->|延遲| EX5[延遲通知客戶]
        EX5 -->|到場| D
        EX5 -->|嚴重延遲| EX5A[管理員介入]

        E -->|品質不合格| EX6[二次派工]
        EX6 -->|S級技師 免費| C

        F -->|客訴| EX7[客訴處理]
        EX7 -->|解決| G
        EX7 -->|升級| EX7A[營運主管]
        EX7A -->|需退款| EX8[退款審批]
        EX8 -->|>$100K| EX8A[雙簽核准]
        EX8A --> G
        EX8 -->|≤$100K| G

        F -->|保固爭議| EX9[保固驗證]
        EX9 -->|有效| EX9A[免費維修派工]
        EX9A --> C
        EX9 -->|過期| EX9B[提供折扣方案]
        EX9B --> G

        D -->|門外觀變更| EX10[變更同意書]
        EX10 -->|客戶同意| D
        EX10 -->|客戶拒絕| EX3A
    end

    subgraph EMERGENCY["緊急路徑 Red_Code"]
        RED([Red_Code 觸發]) -->|30秒| RED1[緊急回應]
        RED1 -->|15分鐘| RED2[緊急派工]
        RED2 -->|2小時| RED3[技師到場]
        RED3 --> D
    end

    subgraph KNOWLEDGE["知識沉澱閉環"]
        G --> K1[完工報告入庫]
        K1 --> K2[AI 預測 vs 實際比對]
        K2 --> K3{ai_prediction_hit?}
        K3 -->|Yes| K4[強化故障樹權重]
        K3 -->|No| K5[修正故障樹權重]
        K4 --> K6[診斷正確率提升]
        K5 --> K6
        EX7 --> K7[OCAP 異常監測]
        K7 --> K8[知識缺口偵測]
        K8 --> K9[專家補充故障樹]
    end

    style NORMAL fill:#e8f5e9,stroke:#2e7d32
    style EXCEPTIONS fill:#fff3e0,stroke:#e65100
    style EMERGENCY fill:#ffebee,stroke:#c62828
    style KNOWLEDGE fill:#e3f2fd,stroke:#1565c0
```

---

## 異常類型摘要表

| 異常類型 | 觸發點 | 處理方式 | 對應流程 |
|:---------|:-------|:---------|:---------|
| 拒單/逾時 | 派工後 15 分鐘 | 自動重派 → 3 次失敗 → 人工 | Flow 2 |
| 範圍變更 | 技師到場 | 重新報價 → 客戶核准 | Flow 3 |
| 缺料 | 技師到場 | 部分完工 + 改期 | Flow 4 |
| 延遲 | 技師出發後 | 通知客戶新 ETA | Flow 5 |
| 退款 | 客訴/爭議後 | 分級審批 (≤$10K/$100K/>$100K) | Flow 6 |
| 保固爭議 | 客戶主張 | 查交屋日 → 有效/過期/爭議 | Flow 7 |
| 品質不合格 | 完工後 7 天 | S 級技師免費回訪 | Flow 8 |
| 客訴 | 任何時點 | 立案→調查→解決→閉環 | Flow 9 |
| 門外觀變更 | 施工前 | 書面同意 → 方可施工 | Flow 10 |
| Red_Code 緊急 | 被鎖門外等 | 30 秒回應→15 分鐘派工→2 小時到場 | Emergency |
