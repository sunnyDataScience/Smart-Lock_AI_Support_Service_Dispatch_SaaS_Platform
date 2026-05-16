---
id: MOD-DISPATCH
title: Dispatch Engine — 派工演算法 + 業務規則
tier: 2
status: accepted
last-synced-with: dccfc0019fa897a3e5b37c4ae1130e6240190d6b
sync-source: code
source-paths:
  - api/services/dispatch_service.py
  - api/realtime/sla_monitor.py
synced-at: 2026-05-16
related:
  - "./dispatch-engine-weights.md (權重表)"
  - "./sla-monitor.md"
  - "./rbac.md (dispatch_officer role)"
  - "../flows/business/_pending-split_BF-dispatch.md"
  - "../../1-decisions/ADR-0013-pm-alignment-q1.md (派工員角色)"
  - "../../1-decisions/ADR-0018-pm-alignment-q6.md (客服繞過)"
  - "../../1-decisions/ADR-0022-pm-alignment-q10.md (rollback policy)"
sources_merged:
  - "_pending-merge-triage-rules.md (09_「電話可解決」vs「需派工」分類)"
  - "_pending-merge-dispatch-business-rules.md (14_派工業務規則)"
---

# Dispatch Engine — 派工演算法 + 業務規則

## §1 Triage Rule（電話可解決 vs 需派工）

> 從 `09_「電話可解決」vs「需派工」分類` 抽出。

**核心原則**：需維修，或文字 / 語音對話無法處理，即派工。

| 場景 | 判定 |
| :-- | :-- |
| 純資訊問題（如何操作 APP）| 電話 / 對話可解決 |
| 設定錯誤可遠端引導 | 電話 / 對話可解決 |
| 物理故障（鎖卡、電池） | 派工 |
| 安裝品質問題（門縫、鎖歪）| 派工 |
| 緊急（被鎖在外）| 派工（高優先）|
| 對話無法判斷（多次來回仍模糊）| 升 L3 → 派工或客服 |

實作：`agent/skills/data/_common/dispatch-guide.md` SKILL.md。

## §2 派工優先順序

> 從 `14_派工業務規則` 抽出。

```
維修（緊急） > 安裝 > 教學
```

## §3 報價邏輯

| 案件類型 | 報價策略 |
| :-- | :-- |
| 一般案件 | 工資 1000 + 車馬費 + 零件費（依報價單）|
| **建案 / 保固期案件** | **AI 嚴禁報價**；必須由真人查詢「建案資料庫」後回覆。涉及建商點交日爭議（例如建商 3/30 點交，保固即起算）|

## §4 派工演算法

依 [`./dispatch-engine-weights.md`](./dispatch-engine-weights.md) 權重表計算候選技師排序：

維度（節錄）：
- 區域（geofence + 距離）
- 品牌技能（technician.skills 與 problem_card.brand 匹配）
- 師傅分級（[`../../0-principles/GLOS-0001-glossary.md §3`](../../0-principles/GLOS-0001-glossary.md) S/A+/A/新人）
- 即時 availability（schedule + 當下 work_orders.in_progress count）
- SLA 緊急度（red code 派最高分技師）

## §5 角色與權限（per ADR-0013/0018）

- `dispatch_officer` 為 V1.0 獨立角色（ADR-0013 拍板 A）
- `support_agent` 可繞過自動派工，但**強制 audit log**（ADR-0018 拍板 A）
- 升級路徑：`dispatch_officer` → `operations_manager` → `operations_director`

## §6 失敗 Rollback Policy

依 [`ADR-0022 PM-Q10`](../../1-decisions/ADR-0022-pm-alignment-q10.md) 預設方案：
- 派工失敗 → 進 `dispatch_pending` 狀態 + alert dispatcher
- 接單失敗（技師 30 min 未回應）→ 自動 reassign + alert
- 3 次拒單 → 進「派工人工介入」（A37 頁面）

## §7 金流與會計（簡述，詳見 accounting）

- **現狀**：師傅收現金 → 公司月結 → 扣材料費後撥款
- **V2.0**：串接虛擬帳戶，師傅 App 內顯示「預計收入」，減少人工對帳
- **V1.0a/b 拆分**：見 [ADR-0019](../../1-decisions/ADR-0019-pm-alignment-q7.md)

## §8 測試情境與案例 (DispatchEngine)

<!-- TC-ID: IT-0039 -->
#### 情境 1: 正常路徑 — 一般案件依權重派發給最高分技師

*   **描述**: 案件 brand=Yale、location=台北市信義區、severity=normal，候選池有 3 名技師，應派給權重總分最高者。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 建立 ProblemCard `pc-001`，brand=Yale、location 經緯度 (25.033, 121.564)、severity=normal。
        - 候選技師：T1 (Yale 認證，距 2km，A 級，availability=true)、T2 (Yale 認證，距 8km，A+ 級，availability=true)、T3 (無 Yale 認證，距 1km，S 級，availability=true)。
        - 載入 `dispatch-engine-weights.md` 預設權重。
    2.  **Act**: 呼叫 `dispatch_engine.assign(problem_card_id="pc-001")`。
    3.  **Assert**:
        - 派工結果 `assigned_technician_id` 為 T1（品牌技能匹配 + 距離次優，總分高於 T2/T3）。
        - `work_orders` 表新增 1 筆，狀態 `assigned`。
        - `audit_logs` 新增 `dispatch.assigned` 事件，含候選池與分數明細。

<!-- TC-ID: IT-0040 -->
#### 情境 2: 正常路徑 — 緊急案件（SLA red code）派給最高分技師

*   **描述**: 案件 severity=urgent（被鎖在外）觸發 SLA red code，應跳過一般權重，派給整個池中 S 級且可用的技師。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - 建立 ProblemCard `pc-urgent-001`，severity=urgent，distance 不限。
        - 候選技師：T1 (A 級，距 1km)、T2 (S 級，距 6km)、T3 (S 級，距 12km，availability=false)。
    2.  **Act**: 呼叫 `dispatch_engine.assign(problem_card_id="pc-urgent-001")`。
    3.  **Assert**:
        - `assigned_technician_id` 為 T2（S 級且 available，距離次要）。
        - `audit_logs` 含 `dispatch.urgent_path` 標記。
        - 派工建立到分配完成 < 30s（per FR-0016 SLA）。

<!-- TC-ID: IT-0041 -->
#### 情境 3: 邊界情況 — Triage 多輪模糊對話升級至 L3

*   **描述**: 對話 4 輪後仍無法判斷「電話可解決 vs 派工」，應升 L3 → 人工介入而非自動派工。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - Conversation `conv-fuzzy` 已進行 4 輪 Q&A，最後一輪 LLMGateway 仍回傳 `triage_confidence=0.42`（低於閾值 0.7）。
    2.  **Act**: 呼叫 `dispatch_engine.triage(conversation_id="conv-fuzzy")`。
    3.  **Assert**:
        - 回傳決策 `escalate_to_l3`，**未**呼叫 `assign()`。
        - `conversations` 表狀態更新為 `awaiting_human_review`。
        - `notifications` 表新增 1 筆，target=`support_agent` role。

<!-- TC-ID: IT-0042 -->
#### 情境 4: 邊界情況 — 派工失敗轉 dispatch_pending

*   **描述**: 候選池為空（半夜無可用技師）時應進 `dispatch_pending` 狀態並 alert 派工員，而非靜默失敗（per ADR-0022）。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - ProblemCard `pc-night-001` 建立於凌晨 03:00。
        - 候選池查詢回傳空集（所有技師 availability=false）。
    2.  **Act**: 呼叫 `dispatch_engine.assign(problem_card_id="pc-night-001")`。
    3.  **Assert**:
        - 回傳 `DispatchResult(status="pending", reason="no_available_technician")`，不丟例外。
        - `work_orders` 狀態為 `dispatch_pending`（非 `failed`）。
        - `notifications` 含 alert，target=`dispatch_officer` role。

<!-- TC-ID: IT-0043 -->
#### 情境 5: 異常處理 — 技師 30 分鐘未回應觸發 auto-reassign

*   **描述**: 派工後技師未於 30 min 內 accept，應自動 reassign 給下一位候選並 alert dispatcher（per ADR-0022）。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - WorkOrder `wo-001` 於 T 時刻分配給 T1，狀態 `assigned`。
        - 排程器在 T+30min 觸發 `check_pending_acceptance` job。
    2.  **Act**: `sla_monitor` 偵測 T+30min 未 accept，呼叫 `dispatch_engine.reassign(work_order_id="wo-001")`。
    3.  **Assert**:
        - WorkOrder `assigned_technician_id` 從 T1 → T2（次優候選）。
        - 原 T1 收到 `dispatch.timeout` 通知，且該技師當日 reassignment_count +1（影響未來權重 -10）。
        - `audit_logs` 含 `dispatch.auto_reassigned` 事件。

<!-- TC-ID: IT-0044 -->
#### 情境 6: 業務規則 — 建案/保固期案件 AI 拒絕報價

*   **描述**: ProblemCard 偵測到 brand=Samsung 且 install_date 在建案點交日 6 個月內（保固期），AI 報價邏輯應拒絕並升真人查詢「建案資料庫」。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - ProblemCard `pc-warranty-001`，brand=Samsung、model=SHP-DP609、install_date=2025-12-01。
        - 系統當前日期 2026-04-15（< 6 個月）。
        - 建案資料庫查詢 mock 回傳 `is_in_warranty=true`，建商 ABC 點交日 2025-12-01。
    2.  **Act**: 呼叫 `dispatch_engine.estimate_quote(problem_card_id="pc-warranty-001")`。
    3.  **Assert**:
        - 回傳 `QuoteResult(status="rejected", reason="warranty_period")`，**未**回傳金額。
        - WorkOrder 狀態為 `awaiting_human_quote`，target_role=`support_agent`。
        - LINE 對話自動回覆「此案件為建案保固期，已轉專人協助查詢」。
        - `audit_logs` 含 `quote.refused.warranty` 事件。
