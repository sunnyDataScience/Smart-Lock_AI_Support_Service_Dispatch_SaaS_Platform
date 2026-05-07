---
title: Dispatch Matching Weights and Tie-Breaker Rules
phase: DESIGN
gate: TR4
status: Active
owners:
  - Tech Lead
  - Operations Manager
  - PM
related:
  - "[[_flows-bdd-test/E5x--dispatch-operations]]"
  - "[[_flows-bdd-test/E5x--work-order-interaction-flows]]"
  - "[[_flows-bdd-test/E7x--test-plan-and-readiness]]"
last_reviewed: 2026-05-07
---

# 派工演算法權重與 Tie-Breaker 規則

> **目的**：為派工媒合演算法提供唯一且可機械驗證的計分公式，作為 [[_flows-bdd-test/E7x--test-plan-and-readiness|E7x test plan]] §7.1 property test 與 50 case golden dataset 的單一真相來源（SSOT）。
>
> **預期讀者**：派工後端工程師、QA、PM。
>
> **與既有文件關係**：本文件取代 [[_flows-bdd-test/E5x--dispatch-operations]] §2.2–§2.3 的舊版權重描述（0.35 / 0.30 / 0.20 / 0.15 + bonus 0.10 / 0.05）。新版以 5 因子（含 fairness）取代 bonus 結構，所有實作以本文件為準。

## 1. 概念

派工引擎在收到工單後，從候選技師清單中計算每位技師的綜合分數，由高至低推送，並依 §3 規則做 3 輪擴大搜尋。

## 2. 五因子權重

| # | 因子 | 權重 | 計算方式 | 數值範圍 | 備註 |
|---|-----|------|---------|---------|------|
| 1 | 距離 (distance) | **0.35** | （依公式 X，見 §2.1） | [0, 1] | 用 Google Maps 直線距離；快取 24 小時 |
| 2 | 技能匹配 (skill_match) | **0.30** | （依公式 Y，見 §2.2） | {0, 0.5, 1} | 品牌 + 鎖型雙維匹配 |
| 3 | 評分 (rating) | **0.15** | 近 60 天平均評分 / 5 | [0, 1] | 不滿 5 單視為 0.6 baseline |
| 4 | 負載 (load) | **0.10** | 1 - (今日已派 / 上限) | [0, 1] | 上限預設 6 |
| 5 | 公平 (fairness) | **0.10** | 1 - (近 7 日總派工 / 50) clamped | [0, 1] | 防壟斷，新進加成 |

> 加總權重必為 1.0；綜合分數 = ∑(因子值 × 權重)。
> 加權後分數理論範圍 [0, 1]。

### 2.1 距離分數公式
- 0–5 km：1.0
- 5–10 km：1 - (d - 5) × 0.06 → 線性 1.0 → 0.7
- 10–20 km：0.7 - (d - 10) × 0.04 → 0.7 → 0.3
- 20–30 km：0.3 - (d - 20) × 0.025 → 0.3 → 0.05
- 30 km 以上：0.05（仍可被指派，但分數極低）

### 2.2 技能匹配計算
- 品牌 + 鎖型完全匹配：1.0
- 僅品牌匹配：0.5
- 都不匹配但有「通用」技能：0.3
- 完全不匹配：**直接從候選名單剔除**（不計分）

### 2.3 評分 fallback
- 完工數 < 5：rating_normalized = 0.6（保守 baseline）
- 完工數 ≥ 5：取最近 60 天評分平均除以 5（5 分制）

## 3. 三輪擴大搜尋規則

| 輪次 | 半徑 | 等待時長 | 加價 | 觸發條件 |
|------|-----|---------|------|---------|
| 1 | 30 km | 5 分鐘 | 0 | 首發 |
| 2 | 50 km | 5 分鐘 | NT$200 車馬費 | 第 1 輪逾時 / 全拒 |
| 3 | 80 km | 10 分鐘 | NT$500 車馬費 | 第 2 輪逾時 / 全拒 |
| 升級 | — | — | — | 第 3 輪後仍無接單 → 自動升級客服手動派工 |

## 4. Tie-Breaker 順序

當兩位技師綜合分數差異 ≤ 0.02 視為平手，依下列**嚴格順序**判定優先：

1. **vip_priority**：客戶若標記 VIP，且某技師曾服務該客戶並滿意 → 優先
2. **distance**：距離較近者優先（已在主分數內，但 tie 時再次比較精確值）
3. **rating**：評分較高者優先
4. **fairness**：近 7 日派工數較少者優先
5. **last_dispatch_at**：上次派工時間較早者優先
6. **technician_id ASC**：最終決定，確保 deterministic

## 5. 紅色警報（Emergency）覆寫規則

當工單 `urgency = critical`（紅色警報）：
- 跳過 §3 三輪擴大，直接以 50 km 半徑 + on_call 技師為池
- 等待時長改為 90 秒；逾時即升級客服
- 加價統一 NT$500（不分輪次）
- 評分權重提升至 0.20，距離降至 0.30，其餘比例不變
- skill_match 仍要求至少 0.5（品牌匹配），避免緊急時派錯技能

## 6. 範例：5 個 Golden Test Cases

下列為 [[_flows-bdd-test/E7x--test-plan-and-readiness|E7x test plan]] §7.1 派工計分 50 case golden dataset 的種子範例。
完整 50 case 將存於 `tests/golden/dispatch_scoring/`，本文件提供 5 個代表性 case 作為實作參考：

### Case G-01：標準距離權重
- 工單：台北市信義區、Yale 密碼鎖、urgency=normal
- 技師 A：距離 4 km、Yale 品牌密碼鎖技能、rating 4.6（30 單）、今日 2 / 6、近 7 日 12 / 50
- 預期分數：0.35×1.0 + 0.30×1.0 + 0.15×0.92 + 0.10×0.67 + 0.10×0.76 = **0.937**

### Case G-02：tie-breaker — 同分但 VIP 優先
- 兩位技師綜合分都 0.821；客戶為 VIP；技師 B 過去 3 個月服務過該客戶且 5 星
- 預期：技師 B 排前

### Case G-03：紅色警報模式
- urgency=critical；技師 X 距離 35 km on_call、rating 4.9；技師 Y 距離 8 km off_duty
- 預期：技師 X 排前（off_duty 不在 on_call pool）

### Case G-04：評分 baseline
- 新進技師（4 完工）vs 老技師（80 完工，平均 4.0）
- 新進 rating_normalized = 0.6；老技師 = 0.8
- 在其他條件相同情況下，老技師勝出

### Case G-05：完全技能不匹配剔除
- Dormakaba 工單；技師只有 Samsung 品牌技能、無通用 → 不計分、剔除

## 7. 變更控制

任何權重 / 公式 / tie-breaker 順序變動：
1. 必須伴隨此文件 PR
2. 必須更新 `tests/golden/dispatch_scoring/` 的相應 expected score
3. 用 `--update-golden` flag 重生 golden，PR review 必須驗證每筆變動的合理性
4. CI 跑 `tests/property/dispatch.py` 驗單調性（更近不會排更後等）

## 8. Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-07 | Claude (assisted) | 初版：5 因子權重、tie-breaker 6 級、3 輪擴大、紅色警報覆寫、5 case 種子 |
