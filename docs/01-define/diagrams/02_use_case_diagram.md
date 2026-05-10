---
status: superseded
superseded_by: docs_v2/1-decisions/architecture-overview.md (use-cases)
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# 02 — Use Case Diagram（使用案例圖）

> **為什麼重要？** 定義角色與功能邊界，確保每個角色的需求都被系統覆蓋。

## 概述

本圖定義四大角色（客戶、技師、管理員、AI 系統）與各自可操作的功能邊界，明確區分 V1.0 與 V2.0 的功能範圍。

---

## 使用案例圖

```mermaid
flowchart LR
    subgraph ACTORS_LEFT["角色"]
        Consumer["👤 客戶<br/>(LINE User)"]
        Technician["🔧 技師<br/>(Web App)"]
    end

    subgraph SYSTEM["Smart Lock AI SaaS Platform"]
        subgraph V1["V1.0 AI 智能客服"]
            UC001["UC-001<br/>報修問題諮詢"]
            UC002["UC-002<br/>接收 AI 診斷建議"]
            UC003["UC-003<br/>確認 ProblemCard"]
            UC004["UC-004<br/>查詢維修進度"]
            UC005["UC-005<br/>提供服務回饋"]
            UC006["UC-006<br/>接收轉接真人通知"]
            UC201["UC-201<br/>監控營運儀表板"]
            UC202["UC-202<br/>審核 SOP 草稿"]
            UC203["UC-203<br/>上傳產品手冊"]
            UC204["UC-204<br/>審計對話紀錄"]
            UC207["UC-207<br/>管理知識庫"]
        end

        subgraph V2["V2.0 技師派工與帳務"]
            UC101["UC-101<br/>瀏覽工單池"]
            UC102["UC-102<br/>接受工單"]
            UC103["UC-103<br/>完工回報"]
            UC104["UC-104<br/>查看個人帳務"]
            UC105["UC-105<br/>客戶滿意度評分"]
            UC205["UC-205<br/>手動指派技師"]
            UC206["UC-206<br/>生成月結報表"]
        end
    end

    subgraph ACTORS_RIGHT["角色"]
        Admin["👔 管理員<br/>(Admin Panel)"]
        AISystem["🤖 AI 系統<br/>(Internal)"]
    end

    Consumer --- UC001
    Consumer --- UC002
    Consumer --- UC003
    Consumer --- UC004
    Consumer --- UC005
    Consumer --- UC006

    Technician --- UC101
    Technician --- UC102
    Technician --- UC103
    Technician --- UC104
    Technician --- UC105

    UC201 --- Admin
    UC202 --- Admin
    UC203 --- Admin
    UC204 --- Admin
    UC205 --- Admin
    UC206 --- Admin
    UC207 --- Admin

    UC001 --- AISystem
    UC002 --- AISystem
    UC003 --- AISystem

    style V1 fill:#e8eaf6,stroke:#283593
    style V2 fill:#fff8e1,stroke:#f57f17
```

---

## Use Case 清單

### V1.0 — 客戶 Use Cases

| ID | 名稱 | 說明 | 介面 |
|:---|:-----|:-----|:-----|
| UC-001 | 報修問題諮詢 | 客戶透過 LINE 描述電子鎖故障，AI 啟動對話狀態機 | LINE Bot |
| UC-002 | 接收 AI 診斷建議 | 接收 L1 案例 / L2 RAG / 影片卡片等解決方案 | LINE Flex Message |
| UC-003 | 確認 ProblemCard | 確認 AI 擷取的品牌、型號、故障現象是否正確 | LINE Flex Message |
| UC-004 | 查詢維修進度 | 查詢已建立工單的處理狀態 | LINE Bot |
| UC-005 | 提供服務回饋 | 對 AI 解答或技師服務給予評分與回饋 | LINE Bot |
| UC-006 | 接收轉接通知 | 接收 L3 升級後的真人客服轉接表單 | LINE Bot |

### V2.0 — 技師 Use Cases

| ID | 名稱 | 說明 | 介面 |
|:---|:-----|:-----|:-----|
| UC-101 | 瀏覽工單池 | 依距離、品牌、價格篩選可接工單 | Web App (PWA) |
| UC-102 | 接受工單 | 一鍵接單並提供預估到達時間 | Web App (PWA) |
| UC-103 | 完工回報 | 提交維修照片、使用零件、工時紀錄 | Web App (PWA) |
| UC-104 | 查看個人帳務 | 查看收入明細、撥款狀態 | Web App (PWA) |
| UC-105 | 客戶滿意度評分 | 維修後收集客戶滿意度並回饋 | Web App (PWA) |

### V1.0 + V2.0 — 管理員 Use Cases

| ID | 名稱 | 說明 | 介面 |
|:---|:-----|:-----|:-----|
| UC-201 | 監控營運儀表板 | 查看 KPI、警報、趨勢圖表 | Admin Panel |
| UC-202 | 審核 SOP 草稿 | 審核 AI 自動生成的 SOP，核准/退回 | Admin Panel |
| UC-203 | 上傳產品手冊 | 上傳 PDF → 分段 → 向量嵌入 | Admin Panel |
| UC-204 | 審計對話紀錄 | 監控情緒、升級危急案件 | Admin Panel |
| UC-205 | 手動指派技師 | 逾時工單手動指定技師 | Admin Panel |
| UC-206 | 生成月結報表 | 技師對帳、撥款報表 | Admin Panel |
| UC-207 | 管理知識庫 | 案例 CRUD、分類管理 | Admin Panel |

---

## V2.0 異常處理擴展 Use Cases

```mermaid
flowchart LR
    subgraph ACTORS_LEFT["角色（左）"]
        Consumer["👤 客戶<br/>(LINE User)"]
        Technician["🔧 技師<br/>(Web App)"]
    end

    subgraph SYSTEM["Smart Lock AI SaaS Platform — 異常處理"]
        subgraph EX_COMPLAINT["客訴處理"]
            UC301["UC-301<br/>客戶投訴"]
            UC302["UC-302<br/>審查客訴"]
            UC303["UC-303<br/>升級客訴"]
        end

        subgraph EX_SCOPE["範圍變更"]
            UC304["UC-304<br/>回報範圍變更"]
            UC305["UC-305<br/>審核範圍變更"]
        end

        subgraph EX_MATERIAL["缺料處理"]
            UC306["UC-306<br/>回報缺料"]
        end

        subgraph EX_DISPUTE["爭議與退款"]
            UC307["UC-307<br/>提出爭議"]
            UC308["UC-308<br/>仲裁爭議"]
            UC309["UC-309<br/>申請退款"]
            UC310["UC-310<br/>審批退款<br/>(含大額雙簽)"]
        end

        subgraph EX_WARRANTY["保固與同意"]
            UC311["UC-311<br/>提出保固索賠"]
            UC312["UC-312<br/>驗證保固"]
            UC313["UC-313<br/>同意門外觀變更"]
        end

        subgraph EX_DISPATCH["二次派工"]
            UC314["UC-314<br/>觸發二次派工"]
        end
    end

    subgraph ACTORS_RIGHT["角色（右）"]
        CSManager["📋 客服主管<br/>(Admin Panel)"]
        OpsManager["📊 營運主管<br/>(Admin Panel)"]
        FinanceManager["💰 財務主管<br/>(Admin Panel)"]
        AISystem["🤖 AI 系統<br/>(Internal)"]
    end

    Consumer --- UC301
    Consumer --- UC307
    Consumer --- UC309
    Consumer --- UC311
    Consumer --- UC313

    Technician --- UC304
    Technician --- UC306

    UC302 --- CSManager
    UC303 --- CSManager
    UC308 --- CSManager
    UC312 --- CSManager

    UC303 --- OpsManager
    UC305 --- OpsManager
    UC310 --- OpsManager
    UC314 --- OpsManager

    UC310 --- FinanceManager

    UC314 --- AISystem

    style EX_COMPLAINT fill:#ffebee,stroke:#c62828
    style EX_SCOPE fill:#fff8e1,stroke:#f57f17
    style EX_MATERIAL fill:#e3f2fd,stroke:#1565c0
    style EX_DISPUTE fill:#fce4ec,stroke:#880e4f
    style EX_WARRANTY fill:#e8f5e9,stroke:#2e7d32
    style EX_DISPATCH fill:#f3e5f5,stroke:#7b1fa2
```

### V2.0 異常處理 — Use Case 清單

#### 客訴處理

| ID | 名稱 | 說明 | 角色 | 介面 |
|:---|:-----|:-----|:-----|:-----|
| UC-301 | 客戶投訴 | 客戶針對服務品質或技師表現提出客訴 | Consumer | LINE Bot |
| UC-302 | 審查客訴 | 客服主管審查客訴內容，指派負責人調查 | CSManager | Admin Panel |
| UC-303 | 升級客訴 | 客服/營運主管將嚴重客訴升級至上級處理 | CSManager, OpsManager | Admin Panel |

#### 範圍變更與缺料

| ID | 名稱 | 說明 | 角色 | 介面 |
|:---|:-----|:-----|:-----|:-----|
| UC-304 | 回報範圍變更 | 技師到場後發現實際維修範圍與原工單不符，回報變更 | Technician | Web App (PWA) |
| UC-305 | 審核範圍變更 | 營運主管審核技師提出的範圍變更申請 | OpsManager | Admin Panel |
| UC-306 | 回報缺料 | 技師回報現場缺少所需材料，觸發請購流程 | Technician | Web App (PWA) |

#### 爭議與退款

| ID | 名稱 | 說明 | 角色 | 介面 |
|:---|:-----|:-----|:-----|:-----|
| UC-307 | 提出爭議 | 客戶對維修結果或費用提出爭議 | Consumer | LINE Bot |
| UC-308 | 仲裁爭議 | 客服主管依據舉證資料進行爭議仲裁 | CSManager | Admin Panel |
| UC-309 | 申請退款 | 客戶申請部分或全額退款 | Consumer | LINE Bot |
| UC-310 | 審批退款 | 依金額分級審批：≤$10K 客服主管、≤$100K 營運主管、>$100K 營運+財務雙簽 | OpsManager, FinanceManager | Admin Panel |

#### 保固與同意

| ID | 名稱 | 說明 | 角色 | 介面 |
|:---|:-----|:-----|:-----|:-----|
| UC-311 | 提出保固索賠 | 客戶針對保固期內產品問題提出索賠 | Consumer | LINE Bot |
| UC-312 | 驗證保固 | 客服主管驗證保固資格（購買日期、保固條款） | CSManager | Admin Panel |
| UC-313 | 同意門外觀變更 | 維修涉及門面外觀變更時，客戶簽署同意書 | Consumer | LINE Bot |

#### 二次派工

| ID | 名稱 | 說明 | 角色 | 介面 |
|:---|:-----|:-----|:-----|:-----|
| UC-314 | 觸發二次派工 | AI 偵測 7 日內同一症狀再次報修，自動觸發二次派工 | AISystem, OpsManager | System / Admin Panel |
