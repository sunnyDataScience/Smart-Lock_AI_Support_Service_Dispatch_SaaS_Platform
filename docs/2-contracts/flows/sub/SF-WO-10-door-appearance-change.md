---
id: SF-WO-10
title: door appearance change (Sub-Flow of Work Order)
tier: 2
status: accepted
last-synced-with: pending
sync-source: doc
synced-at: 2026-05-10
parent_bf: BF-0001-work-order-lifecycle
trace_to_flow: F-008 / F-006
trace_to_fr: TODO
related:
  - "../business/BF-0001-work-order-lifecycle.md"
  - "../../state-machines/work-order.md"
legacy_id: E5x--workflow-work-order §Flow 10
extracted_from: docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md
---

# SF-WO-10 — door appearance change

> Work Order BF 的子流程 10 of 13。

## 13. Flow 10：門外觀變更確認 — 對應 F-008 / F-006

> **Endpoints（Week 4 補完）：** `submitAppearanceNotice`（POST /work-orders/{id}/door-check）, `uploadEvidencePhotos`, `acknowledgeAppearanceNotice`
> **Events Out:** `work_order.appearance.notice_issued`, `work_order.appearance.signed|rejected`
> **Idempotency:** Required on 提交告知書與簽署
> **Error codes:** `APPEARANCE_CHANGE_EVIDENCE_INCOMPLETE`（少於 4 張照片）, `APPEARANCE_CHANGE_SIGNATURE_REJECTED`（拒簽 → 費用結算 §26）
> **Related pages:** T8（19 門面）→ T9 雙簽 → 拒簽則走 §26 費用結算


### 13.1 觸發條件

- 技師到場勘查後發現需切割非標準側板
- 安裝過程可能影響門扇外觀 (烤漆、表面處理)
- 任何可能造成門扇不可逆改變的工序

### 13.2 參與角色

Technician, Customer, Admin

### 13.3 流程圖

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 客戶 (現場)
    participant LINE as LINE Messaging API
    participant TechApp as 技師 Web App
    actor Technician as 技師
    participant DB as PostgreSQL
    participant Admin as 管理員面板
    actor AdminUser as 管理員

    Note over Technician: 技師到場，工單狀態為 in_progress

    Technician->>Technician: 現場勘查：門扇為非標準韓規側板<br/>安裝需切割，可能影響門板外觀

    Note over Technician: 業務規則（鐵律）：<br/>任何可能改變門扇外觀的工序<br/>必須在施工前取得客戶書面同意<br/>否則：師傅承擔全部損害賠償

    Technician->>TechApp: 拍攝門扇原始狀態照片<br/>(全貌 + 側板特寫 + 現有鎖孔)

    Note over Technician: 必拍照片：<br/>1. 門扇全貌（含門框）<br/>2. 側板特寫<br/>3. 將進行切割的區域標記<br/>4. 現有鎖孔/孔位

    Technician->>TechApp: 提交「外觀變更確認申請」<br/>(change_type, affected_area, risk_description)

    TechApp->>DB: INSERT appearance_change_notice<br/>(work_order_id, photos, description, status=pending)

    TechApp->>TechApp: 自動生成「門外觀變更告知書」<br/>(含：變更原因、風險說明、<br/>原始狀態照片、客戶簽名欄)

    TechApp->>Technician: 顯示告知書<br/>→ 請客戶過目並簽署

    Technician->>Customer: 展示告知書<br/>說明切割必要性與風險

    Note over Technician, Customer: 面對面說明：<br/>1. 為什麼需要切割<br/>2. 切割範圍與位置<br/>3. 可能的風險（油漆起泡、變色）<br/>4. 公司不承擔外觀損害責任

    alt 客戶同意簽署
        Customer->>TechApp: 在螢幕上簽名確認
        TechApp->>DB: UPDATE appearance_change_notice<br/>SET status=signed,<br/>customer_signature, signed_at
        TechApp->>DB: 保存原始狀態照片 (時間戳 + GPS)

        Note over TechApp: 業務規則：<br/>簽署記錄包含：<br/>- 客戶電子簽名<br/>- 簽署時間戳<br/>- GPS 定位<br/>- 原始狀態照片 hash

        Technician->>Technician: 開始切割/加工作業
        Technician->>TechApp: 拍攝施工中照片
        Technician->>Technician: 完成施工
        Technician->>TechApp: 拍攝完工照片

    else 客戶拒絕簽署
        Customer->>Technician: 「我不同意切割門板」

        Technician->>TechApp: 記錄客戶拒絕
        TechApp->>DB: UPDATE appearance_change_notice<br/>SET status=rejected

        TechApp->>DB: UPDATE work_orders SET status=scope_changed

        Note over Technician: 提供替代方案

        Technician->>Customer: 說明替代選項

        TechApp->>LINE: 發送替代方案
        LINE->>Customer: 「了解您的顧慮，以下是替代方案」<br/>+ [方案 A：更換其他不需切割的鎖款]<br/>+ [方案 B：使用轉接片（可能略凸）]<br/>+ [方案 C：取消本次安裝]

        alt 客戶選擇替代方案 A/B
            Customer->>LINE: 選擇替代方案
            LINE->>DB: 記錄客戶選擇

            Note over Technician: 替代方案可能涉及：<br/>1. 更換鎖款 → 需重新報價<br/>2. 使用轉接片 → 調整安裝方式

            Technician->>TechApp: 依替代方案調整工項
            TechApp->>DB: UPDATE work_orders<br/>(updated scope + pricing)

        else 客戶選擇取消
            Customer->>LINE: 選擇 [取消本次安裝]
            LINE->>DB: UPDATE work_orders SET status=cancelled,<br/>cancel_reason=appearance_change_refused

            Note over DB: 業務規則：<br/>因客戶拒絕外觀變更而取消<br/>→ 收取車馬費，免收工資

            LINE->>Customer: 「已取消本次安裝」<br/>+「僅收取車馬費 $XXX」
        end

        TechApp->>Admin: 通知管理員：外觀變更被拒
        Admin->>AdminUser: 記錄 + 後續跟進
    end
```

### 13.4 狀態轉換表

| 步驟 | 來源狀態 | 目標狀態 | 觸發動作 |
|------|----------|----------|----------|
| 1 | `in_progress` | `in_progress` (暫停) | 技師偵測到外觀變更需求 |
| 2a | `in_progress` | `in_progress` (繼續) | 客戶簽署同意書 → 繼續施工 |
| 2b | `in_progress` | `scope_changed` | 客戶拒絕 → 討論替代方案 |
| 3a | `scope_changed` | `in_progress` | 客戶選擇替代方案 |
| 3b | `scope_changed` | `cancelled` | 客戶取消安裝 |

### 13.5 通知清單

| 時機 | 通知方式 | 接收者 | 內容摘要 |
|------|----------|--------|----------|
| 外觀變更申請 | — | Customer (面對面) | 告知書面對面說明 |
| 客戶簽署 | Web Push | Admin | 記錄存檔 |
| 客戶拒絕 | LINE Flex | Customer | 替代方案選項 |
| 客戶拒絕 | Web Alert | Admin | 外觀變更被拒通知 |
| 取消安裝 | LINE Flex | Customer | 取消確認 + 車馬費 |

### 13.6 證據保存規範

| 項目 | 要求 | 說明 |
|------|------|------|
| 原始狀態照片 | 最少 4 張 | 全貌、側板、切割區域、現有孔位 |
| 電子簽名 | 含時間戳 + GPS | 不可事後補簽 |
| 照片 hash | SHA-256 | 防止事後篡改 |
| 施工中照片 | 最少 1 張 | 記錄加工過程 |
| 完工照片 | 最少 2 張 | 記錄最終結果 |
| 保存期限 | 永久 | 作為爭議處理依據 |

---
