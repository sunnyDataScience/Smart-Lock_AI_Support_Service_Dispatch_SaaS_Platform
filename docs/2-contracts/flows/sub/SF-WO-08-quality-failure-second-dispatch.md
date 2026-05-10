---
id: SF-WO-08
title: quality failure second dispatch (Sub-Flow of Work Order)
tier: 2
status: accepted
last-synced-with: pending
sync-source: doc
synced-at: 2026-05-10
parent_bf: BF-0001-work-order-lifecycle
trace_to_flow: F-015 / F-008
trace_to_fr: TODO
related:
  - "../business/BF-0001-work-order-lifecycle.md"
  - "../../state-machines/work-order.md"
legacy_id: E5x--workflow-work-order §Flow 8
extracted_from: docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md
---

# SF-WO-08 — quality failure second dispatch

> Work Order BF 的子流程 8 of 13。

## 11. Flow 8：品質不合格與二次派工 — 對應 F-015 / F-008

> **Endpoints:** `createReworkOrder`（Week 4）, `listDispatchCandidates`（篩選 S 級）, `assignWorkOrder`
> **Events Out:** `work_order.rework.required`, `work_order.status.changed`
> **Idempotency:** Required on 建立二次工單
> **Error codes:** `WORK_ORDER_CONFLICT`（原工單已結案）, `DISPATCH_OVERRIDE_REQUIRED`（強制 S 級可能需 override）
> **Related pages:** A12 → **A37 派工人工介入**（S 級快篩）→ 原技師扣分（A20 稽核）


### 11.1 觸發條件

- 客戶在完工後 7 天內反映相同故障症狀 (「修了又壞」)
- 系統自動偵測：同一客戶 + 同一症狀 + 7 天內

### 11.2 參與角色

Customer, AI_System, Dispatch_Engine, Technician, Admin

### 11.3 流程圖

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 客戶 (LINE)
    participant LINE as LINE Messaging API
    participant AI as AI 系統
    participant DB as PostgreSQL
    participant Dispatch as 派工引擎
    participant TechApp as 技師 Web App
    actor OrigTech as 原技師
    actor SGradeTech as S 級技師
    participant Admin as 管理員面板
    actor AdminUser as 管理員

    Customer->>LINE: 「昨天才修好今天又壞了」
    LINE->>AI: 客戶訊息

    AI->>DB: 查詢客戶近期工單<br/>(user_id, completed_at > NOW() - 7 days)
    DB-->>AI: 找到工單 WO-xxx (3 天前完工)

    AI->>AI: 比對症狀相似度<br/>(current_symptoms vs WO-xxx.symptoms)

    Note over AI: 偵測規則：<br/>同一客戶 + 相似症狀 (cosine >= 0.80)<br/>+ 前工單完工 7 天內<br/>→ 觸發「二次客訴」流程

    AI->>DB: INSERT complaint<br/>(type=quality_rework, linked_work_order=WO-xxx)
    AI->>DB: UPDATE work_orders (WO-xxx)<br/>SET status=rework_required

    AI->>LINE: 通知客戶
    LINE->>Customer: 「非常抱歉造成不便」<br/>+「已自動建立優先處理案件」<br/>+「將安排資深技師免費上門維修」

    Note over Dispatch: === 強制 S 級技師派工 ===

    AI->>Dispatch: 建立二次派工請求<br/>(priority=high, grade_required=S,<br/>free_service=true)

    Dispatch->>DB: 查詢 S 級技師列表<br/>(WHERE grade='S' AND status='active')

    Note over Dispatch: 業務規則：<br/>1. 排除原技師<br/>2. 僅匹配 S 級或 A+ 級<br/>3. 標記為免費服務<br/>4. 優先派工（插隊）

    Dispatch->>DB: INSERT work_orders<br/>(priority=high, technician_grade=S,<br/>is_free=true, parent_work_order=WO-xxx)
    Dispatch->>TechApp: 推播工單至 S 級技師
    TechApp->>SGradeTech: 顯示二次派工工單<br/>(標記：品質回訪、免費、優先)

    SGradeTech->>TechApp: 接受工單
    TechApp->>LINE: 通知客戶
    LINE->>Customer: 「資深技師 陳師傅 將於 XX:XX 到達」

    Note over SGradeTech: === S 級技師現場處理 ===

    SGradeTech->>SGradeTech: 到場全面檢查<br/>找出根本原因 (Root Cause)

    Note over SGradeTech: 案例：前技師僅調整受口片<br/>根本原因為門扇下沉導致反覆錯位<br/>S 級技師調整鉸鏈 + 受口片

    SGradeTech->>TechApp: 提交完工報告<br/>(root_cause, actual_fix, photos)
    SGradeTech->>TechApp: 填寫根本原因分析<br/>(RCA: 原技師未完整診斷)

    TechApp->>DB: UPDATE work_orders SET status=completed
    TechApp->>DB: UPDATE 原工單 diagnostic_result=incomplete

    Note over Admin: === 原技師考核 ===

    TechApp->>Admin: 提交根本原因分析報告
    Admin->>AdminUser: 顯示 RCA 報告

    AdminUser->>DB: UPDATE technicians (原技師)<br/>SET incomplete_diagnosis_count += 1

    Note over AdminUser: 考核規則：<br/>1 次未完整診斷 → 記錄觀察<br/>3 次 → 降級警告<br/>5 次 → 降級處分

    alt 原技師累計 >= 3 次
        AdminUser->>DB: 發出降級警告
        AdminUser->>OrigTech: 通知降級警告 + 改善要求
    end

    Note over Customer: === 客戶補償 ===

    TechApp->>LINE: 完工通知 + 補償方案
    LINE->>Customer: 「維修已完成」<br/>+ 根本原因說明<br/>+「贈送 $200 折扣碼表示歉意」<br/>+ 滿意度調查
```

### 11.4 狀態轉換表

| 步驟 | 來源狀態 | 目標狀態 | 觸發動作 |
|------|----------|----------|----------|
| 1 | `confirmed` / `completed` (原工單) | `rework_required` | 系統偵測 7 天內同症狀 |
| 2 | — (新工單) | `created` | 建立二次派工工單 |
| 3 | `created` | `assigned` | 強制 S 級技師匹配 |
| 4 | `assigned` | `accepted` | S 級技師接受 |
| 5 | `accepted` | `in_progress` | S 級技師到場 |
| 6 | `in_progress` | `completed` | 提交完工報告 + RCA |

### 11.5 通知清單

| 時機 | 通知方式 | 接收者 | 內容摘要 |
|------|----------|--------|----------|
| 二次客訴偵測 | LINE Push | Customer | 已建立優先案件 + 免費維修 |
| 二次客訴偵測 | Web Alert | Admin | 品質問題警報 + 原工單資訊 |
| S 級技師接單 | LINE Flex | Customer | 資深技師資訊 + 到達時間 |
| 完工 + RCA | Web Alert | Admin | 根本原因報告 |
| 原技師考核 | Web Push | 原技師 | 記錄通知 / 降級警告 |
| 客戶補償 | LINE Flex | Customer | 完工通知 + 折扣碼 |

### 11.6 偵測規則

| 參數 | 閾值 | 說明 |
|------|------|------|
| 時間窗口 | 7 天 | 前工單完工後 7 天內 |
| 症狀相似度 | cosine >= 0.80 | 使用 text-embedding-004 向量比對 |
| 客戶匹配 | 同一 user_id | 同一客戶帳號 |
| 自動觸發 | 是 | 無需人工介入 |

---
