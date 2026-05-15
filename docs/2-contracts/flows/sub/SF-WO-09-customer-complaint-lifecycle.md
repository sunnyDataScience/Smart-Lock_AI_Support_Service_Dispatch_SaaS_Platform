---
id: SF-WO-09
title: customer complaint lifecycle (Sub-Flow of Work Order)
tier: 2
status: accepted
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
sync-source: doc
synced-at: 2026-05-15
parent_bf: BF-0001-work-order-lifecycle
trace_to_flow: F-018 / F-016
trace_to_fr: TODO
related:
  - "../business/BF-0001-work-order-lifecycle.md"
  - "../../state-machines/work-order.md"
legacy_id: E5x--workflow-work-order §Flow 9
extracted_from: docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md
---

# SF-WO-09 — customer complaint lifecycle

> Work Order BF 的子流程 9 of 13。

## 12. Flow 9：客訴處理完整生命週期 — 對應 F-018 / F-016（admin G4 升級）

> **Endpoints（Week 4 補完）：** `createComplaint`, `classifyComplaint`, `proposeResolution`, `escalateComplaint`, `acknowledgeComplaint`
> **Events In:** LINE webhook `message.text`（含 anger_level 分析）
> **Events Out:** `complaint.created`, `complaint.escalated`, `complaint.resolved`, `complaint.reopened`
> **Idempotency:** Required on 升級 / resolve / acknowledge
> **Error codes:** `COMPLAINT_ALREADY_IN_DISPUTE`, `DISPUTE_MERGE_FAILED`
> **Related pages:** A12 客訴升級 indicator + A22 爭議（§27.2 併入規則） + G4 爭議仲裁
> **Note:** 與 G4 銜接規則見 §27（Flow 9 補遺）


### 12.1 觸發條件

- 客戶透過 LINE 或電話提出投訴
- 系統自動偵測客戶負面情緒 (anger level >= 3)
- 其他流程升級 (如保固爭議、範圍變更糾紛)

### 12.2 參與角色

Customer, AI_System, Admin, Finance

### 12.3 客訴狀態機

```mermaid
stateDiagram-v2
    [*] --> filed : 客戶提出投訴

    filed --> classified : 分類完成
    classified --> assigned : 指派處理人
    assigned --> investigating : 開始調查
    investigating --> resolution_proposed : 提出解決方案
    resolution_proposed --> resolution_accepted : 客戶接受
    resolution_proposed --> resolution_rejected : 客戶拒絕
    resolution_rejected --> investigating : 重新調查/調整方案
    resolution_rejected --> escalated : 升級處理
    escalated --> investigating : 上級介入重新調查
    resolution_accepted --> executing : 執行解決方案
    executing --> closed : 執行完成
    closed --> reopened : 客戶不滿意再次投訴
    reopened --> escalated : 自動升級
    closed --> [*]
```

### 12.4 流程圖

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 客戶 (LINE)
    participant LINE as LINE Messaging API
    participant AI as AI 系統
    participant DB as PostgreSQL
    participant Admin as 管理員面板
    actor CSR as 客服人員
    actor CSRMgr as 客服主管
    actor OpsMgr as 營運主管
    participant Finance as 財務系統

    Note over Customer, AI: === 階段一：客訴受理 ===

    Customer->>LINE: 投訴訊息
    LINE->>AI: 客戶訊息

    AI->>AI: 情緒分析 (anger_level: 1~5)
    AI->>AI: 意圖識別 → intent=complaint

    alt anger_level >= 4 (高度不滿)
        AI->>Admin: 立即轉人工 + 標記高優先
        Note over AI: 業務規則：<br/>anger_level 4-5 → 跳過 AI 回覆<br/>直接轉真人 + 主管通知
    else anger_level < 4
        AI->>LINE: 安撫回覆 + 表示會處理
        LINE->>Customer: 「非常抱歉造成不便，已為您建立處理案件」
    end

    AI->>DB: INSERT complaint<br/>(status=filed, severity, anger_level)

    Note over Admin, CSR: === 階段二：分類與指派 ===

    Admin->>CSR: 新客訴通知
    CSR->>DB: 查詢工單 + 對話紀錄 + 技師報告 + 照片

    CSR->>DB: UPDATE complaint SET category<br/>(service / quality / pricing / attitude)
    CSR->>DB: UPDATE complaint SET status=classified

    Note over CSR: 客訴分類：<br/>service — 服務流程問題<br/>quality — 維修品質問題<br/>pricing — 收費爭議<br/>attitude — 技師態度問題

    CSR->>DB: UPDATE complaint SET assigned_to=CSR_id,<br/>status=assigned

    Note over CSR: === 階段三：調查 ===

    CSR->>DB: UPDATE complaint SET status=investigating
    CSR->>DB: 調閱完整證據鏈<br/>(工單記錄、完工照片、LINE 對話、技師報告、帳單)

    CSR->>CSR: 分析問題根本原因
    CSR->>CSR: 評估責任歸屬<br/>(技師/公司/客戶/設備)

    Note over CSR: === 階段四：提出解決方案 ===

    CSR->>DB: UPDATE complaint SET status=resolution_proposed

    Note over CSR: 解決方案選項池：<br/>1. 道歉 + 說明<br/>2. 折扣碼 / 優惠券<br/>3. 部分退款<br/>4. 全額退款<br/>5. 免費二次服務<br/>6. 技師處分 + 換人重做

    CSR->>LINE: 提出解決方案
    LINE->>Customer: 「經調查，針對您的問題」<br/>+ 調查結論<br/>+ 解決方案<br/>+ [接受] [不接受] 按鈕

    alt 客戶接受方案
        Customer->>LINE: 點擊 [接受]
        LINE->>DB: UPDATE complaint<br/>SET status=resolution_accepted

        Note over CSR: === 階段五：執行方案 ===

        CSR->>DB: UPDATE complaint SET status=executing

        alt 方案涉及退款
            CSR->>Finance: 發起退款流程<br/>(→ 參見 Flow 6 退款審批)
        end

        alt 方案涉及重新服務
            CSR->>DB: INSERT work_orders (免費)
            Note over DB: → 參見 Flow 8 二次派工
        end

        alt 方案涉及技師處分
            CSR->>Admin: 提交技師考核記錄
        end

        CSR->>DB: UPDATE complaint SET status=closed
        CSR->>LINE: 結案通知 + 滿意度再調查
        LINE->>Customer: 「您的案件已處理完成」<br/>+ 滿意度調查

    else 客戶不接受方案
        Customer->>LINE: 點擊 [不接受] + 說明原因
        LINE->>DB: UPDATE complaint<br/>SET status=resolution_rejected

        alt 首次拒絕 → 調整方案
            CSR->>CSR: 調整方案 (加大補償力度)
            CSR->>LINE: 提出修改後方案
            LINE->>Customer: 調整後的方案
        else 二次拒絕 → 升級
            CSR->>DB: UPDATE complaint SET status=escalated
            CSR->>CSRMgr: 升級至客服主管

            CSRMgr->>Customer: 主管致電溝通
            CSRMgr->>DB: 記錄溝通結果

            alt 主管解決
                CSRMgr->>DB: UPDATE complaint SET status=executing
            else 主管無法解決 → 再升級
                CSRMgr->>OpsMgr: 升級至營運主管
                OpsMgr->>Customer: 營運主管介入
                OpsMgr->>DB: 最終裁決
            end
        end
    end

    Note over DB: === 結案後監控 ===

    alt 結案後 30 天內客戶再次投訴
        Customer->>LINE: 再次投訴相同問題
        AI->>DB: 偵測到重複投訴
        AI->>DB: UPDATE complaint SET status=reopened
        AI->>Admin: 自動升級至主管層級

        Note over Admin: 重開案件 → 直接指派主管處理<br/>不重複走一線客服
    end
```

### 12.5 狀態轉換表

| 步驟 | 來源狀態 | 目標狀態 | 觸發動作 |
|------|----------|----------|----------|
| 1 | — | `filed` | 客戶投訴 / AI 偵測 |
| 2 | `filed` | `classified` | 客服分類 (service/quality/pricing/attitude) |
| 3 | `classified` | `assigned` | 指派客服人員 |
| 4 | `assigned` | `investigating` | 開始調查 |
| 5 | `investigating` | `resolution_proposed` | 提出方案 |
| 6a | `resolution_proposed` | `resolution_accepted` | 客戶接受 |
| 6b | `resolution_proposed` | `resolution_rejected` | 客戶拒絕 |
| 7a | `resolution_rejected` | `investigating` | 調整方案 |
| 7b | `resolution_rejected` | `escalated` | 二次拒絕 → 升級 |
| 8 | `escalated` | `investigating` | 上級介入重查 |
| 9 | `resolution_accepted` | `executing` | 執行方案 |
| 10 | `executing` | `closed` | 方案執行完成 |
| 11 | `closed` | `reopened` | 30 天內同問題再投訴 |
| 12 | `reopened` | `escalated` | 自動升級 |

### 12.6 通知清單

| 時機 | 通知方式 | 接收者 | 內容摘要 |
|------|----------|--------|----------|
| 投訴受理 | LINE Push | Customer | 已建立案件，處理中 |
| anger_level >= 4 | Web Alert (緊急) | CSR + 主管 | 高優先客訴 |
| 方案提出 | LINE Flex | Customer | 調查結論 + 方案 + 接受/拒絕 |
| 方案被拒 (2次) | Web Alert | 客服主管 | 需主管介入 |
| 升級至營運 | Web Alert | 營運主管 | 客訴升級 |
| 結案 | LINE Flex | Customer | 處理結果 + 滿意度調查 |
| 重開案件 | Web Alert | 主管 | 重複投訴自動升級 |

### 12.7 各類型客訴 SLA

| 客訴類型 | 嚴重度 | 首次回應 SLA | 解決 SLA | 升級時限 |
|----------|--------|-------------|----------|----------|
| 態度問題 | 中 | 2 小時 | 3 個工作日 | 24 小時 |
| 服務流程 | 中 | 2 小時 | 3 個工作日 | 24 小時 |
| 維修品質 | 高 | 1 小時 | 2 個工作日 | 12 小時 |
| 收費爭議 | 高 | 1 小時 | 2 個工作日 | 12 小時 |
| anger_level >= 4 | 緊急 | 15 分鐘 | 24 小時 | 4 小時 |
| anger_level = 5 | 危機 | 立即 | 12 小時 | 2 小時 |

---
