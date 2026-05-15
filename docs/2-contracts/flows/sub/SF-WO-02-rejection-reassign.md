---
id: SF-WO-02
title: rejection reassign (Sub-Flow of Work Order)
tier: 2
status: accepted
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
sync-source: doc
synced-at: 2026-05-15
parent_bf: BF-0001-work-order-lifecycle
trace_to_flow: F-005 / F-004 / F-003
trace_to_fr: TODO
related:
  - "../business/BF-0001-work-order-lifecycle.md"
  - "../../state-machines/work-order.md"
legacy_id: E5x--workflow-work-order §Flow 2
extracted_from: docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md
---

# SF-WO-02 — rejection reassign

> Work Order BF 的子流程 2 of 13。

## 5. Flow 2：拒單與逾時重派 — 對應 F-005 / F-004 / F-003

> **Endpoints:** `listDispatchCandidates`, `assignWorkOrder`（強制 Idempotency + reason_code）, `escalateWorkOrder`
> **Events Out:** `work_order.status.changed`（assigned → reassigning → assigned）、`work_order.available`（回池）
> **Idempotency:** Required on `assignWorkOrder`（手動派工）與 `escalateWorkOrder`
> **Error codes:** `DISPATCH_NO_TECHNICIAN_AVAILABLE`, `DISPATCH_OVERRIDE_REQUIRED`（熔斷覆寫雙簽）, `DISPATCH_REASON_MISSING`
> **Related pages:** A11 → A28 → **A37 派工人工介入**（3 次拒單後）


### 5.1 觸發條件

- 技師在收到工單後 15 分鐘內未回應 (逾時)
- 技師主動點擊「拒絕工單」

### 5.2 參與角色

Dispatch_Engine, Technician, Admin, Customer

### 5.3 流程圖

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 客戶 (LINE)
    participant DB as PostgreSQL
    participant Dispatch as 派工引擎
    participant TechApp as 技師 Web App
    actor Tech1 as 技師 A (候選 #1)
    actor Tech2 as 技師 B (候選 #2)
    actor Tech3 as 技師 C (候選 #3)
    participant Admin as 管理員面板
    actor AdminUser as 管理員
    participant LINE as LINE Messaging API

    Note over Dispatch: 工單已建立，開始第 1 輪匹配

    Dispatch->>DB: 查詢候選技師排序列表
    Dispatch->>DB: UPDATE work_orders SET status=assigned, technician_id=Tech_A
    Dispatch->>TechApp: 推播工單至技師 A
    TechApp->>Tech1: 顯示工單 (15 分鐘倒計時)

    Note over Dispatch: 啟動 15 分鐘 SLA 計時器

    alt 情境 A：技師 A 主動拒絕
        Tech1->>TechApp: 點擊「拒絕」+ 選擇原因<br/>(距離太遠 / 時間衝突 / 非專長品牌)
        TechApp->>DB: 記錄拒絕原因至 dispatch_log
        TechApp->>DB: UPDATE technicians 累計拒單次數

        Note over DB: 業務規則：<br/>月拒單率 > 30% → 降級警告<br/>月拒單率 > 50% → 暫停派工
    else 情境 B：技師 A 15 分鐘未回應
        Dispatch->>Dispatch: SLA 計時器到期
        Dispatch->>DB: 記錄逾時至 dispatch_log
        Dispatch->>TechApp: 撤回工單通知
    end

    Note over Dispatch: 第 2 輪匹配：排除技師 A

    Dispatch->>Dispatch: 從候選列表移除技師 A<br/>重新計算排名
    Dispatch->>DB: UPDATE work_orders SET technician_id=Tech_B
    Dispatch->>TechApp: 推播工單至技師 B
    TechApp->>Tech2: 顯示工單 (15 分鐘倒計時)

    alt 技師 B 接受
        Tech2->>TechApp: 點擊「接受工單」
        TechApp->>DB: UPDATE work_orders SET status=accepted
        TechApp->>LINE: 通知客戶已匹配技師
        LINE->>Customer: 「已為您安排技師 B，預計 XX:XX 到達」
    else 技師 B 也拒絕/逾時
        Note over Dispatch: 第 3 輪匹配：排除技師 A + B

        Dispatch->>Dispatch: 候選列表再排除技師 B
        Dispatch->>DB: UPDATE work_orders SET technician_id=Tech_C
        Dispatch->>TechApp: 推播工單至技師 C
        TechApp->>Tech3: 顯示工單 (15 分鐘倒計時)

        alt 技師 C 接受
            Tech3->>TechApp: 點擊「接受工單」
            TechApp->>DB: UPDATE work_orders SET status=accepted
            TechApp->>LINE: 通知客戶已匹配技師
            LINE->>Customer: 「已為您安排技師 C」
        else 技師 C 也拒絕/逾時 (3 次失敗)

            Note over Dispatch: 3 次匹配失敗 → 升級至人工派工

            Dispatch->>DB: 標記工單為 dispatch_failed
            Dispatch->>Admin: 緊急通知：工單 #xxx 3 次匹配失敗
            Admin->>AdminUser: 顯示警報 + 完整拒絕記錄

            AdminUser->>Admin: 手動選擇技師 / 擴大搜尋範圍 / 調整時段
            Admin->>DB: UPDATE work_orders SET technician_id (手動指派)
            Admin->>TechApp: 推播工單 (標記為管理員指派)
            Admin->>LINE: 通知客戶進度更新
            LINE->>Customer: 「正在為您安排最合適的技師，請稍候」
        end
    end
```

### 5.4 狀態轉換表

| 步驟 | 來源狀態 | 目標狀態 | 觸發動作 |
|------|----------|----------|----------|
| 1 | `created` | `assigned` | 派工引擎匹配技師 A |
| 2a | `assigned` | `assigned` | 技師 A 拒絕 → 重新匹配技師 B |
| 2b | `assigned` | `assigned` | 技師 A 逾時 → 重新匹配技師 B |
| 3 | `assigned` | `accepted` | 技師 B (或 C) 接受 |
| 4 (異常) | `assigned` | `assigned` | 3 次失敗 → 管理員手動指派 |

### 5.5 通知清單

| 時機 | 通知方式 | 接收者 | 內容摘要 |
|------|----------|--------|----------|
| 第 2 輪重派 | — | Customer | (不通知客戶，避免焦慮) |
| 第 3 輪重派 | LINE Push | Customer | 「正在為您尋找最合適的技師」 |
| 3 次失敗 | Web Alert | Admin | 緊急：工單 3 次匹配失敗，需人工介入 |
| 人工指派完成 | LINE Flex | Customer | 已安排技師資訊 |
| 技師高拒單率 | Web Alert | Admin | 技師 xxx 月拒單率超過警戒值 |

### 5.6 業務規則

| 規則 | 閾值 | 動作 |
|------|------|------|
| 單次拒單 | — | 記錄原因，下次排序降權 |
| 月拒單率 > 30% | 30% | 系統發出降級警告 |
| 月拒單率 > 50% | 50% | 自動暫停派工 7 天 |
| 連續 3 次逾時未回應 | 3 次 | 標記為「離線」，暫停派工至手動恢復 |

---
