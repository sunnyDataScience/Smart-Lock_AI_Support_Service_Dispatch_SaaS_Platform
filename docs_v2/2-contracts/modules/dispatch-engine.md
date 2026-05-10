---
id: MOD-DISPATCH
title: Dispatch Engine — 派工演算法 + 業務規則
tier: 2
status: accepted
last-synced-with: pending
sync-source: code
source-paths:
  - api/services/dispatch_engine.py
  - api/services/sla_monitor.py
synced-at: 2026-05-10
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
- 師傅分級（[`../../0-principles/glossary.md §3`](../../0-principles/glossary.md) S/A+/A/新人）
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
