---
title: Workday SLA Policy — 月結爭議工作日計時規則
phase: DESIGN
gate: TR4
status: Active
owners:
  - PM
  - Tech Lead
  - Finance
related:
  - "[[_flows-bdd-test/v-model-right/E7--bdd-scenarios]]"
  - "[[02-design/specs/sla-policy]]"
  - "[[decision-log/E7x--pm-alignment-Q1-Q10]]"
last_reviewed: 2026-05-07
---

# Workday SLA Policy — 月結爭議工作日計時規則

## 0. Purpose

本文件為 V1.0 月結爭議 SLA（F-013）之 **工作日計時唯一規則**，提供：
1. `agent/core/workday.py` helper 之語意契約
2. Dispute service 寫入 `disputes.sla_deadline` 時的計算依據
3. 跨週末 / 跨春節等邊界情境的範例

**對應 PM 拍板**：
- [[decision-log/E7x--pm-alignment-Q1-Q10|Q4=C]]：月結爭議 SLA 7 日改為 **工作日** 計算（跳過週末 + 台灣國定假日）

## 1. 工作日定義

| 條件 | 是否工作日 |
|---|---|
| 週一 ~ 週五 且 不在台灣國定假日清單 | ✅ 是 |
| 週六 / 週日 | ❌ 否 |
| 國定假日（含 元旦 / 春節 / 清明 / 端午 / 中秋 / 國慶 / 勞動節 等） | ❌ 否 |
| 補班日（如「補春節後第一週週六上班」） | ❌ 否（V1.0 不處理；以 `holidays` 套件為準） |

**唯一資料來源**：[`holidays`](https://pypi.org/project/holidays/) Python 套件 `country_holidays('TW')` — 由套件作者維護年度更新。

## 2. Helper 契約（`agent/core/workday.py`）

```python
def is_workday(d: date) -> bool: ...
def add_workdays(start: datetime, n_workdays: int) -> datetime: ...
def workday_sla_deadline(filed_at: datetime, n_workdays: int) -> datetime: ...
```

**邊界語意**：
- `add_workdays(start, n)` **不把 start 當天計入**，從次日開始往後找 N 個工作日
- 例：`start = 2026-05-04 (週一 10:00)`、`n = 1` → `2026-05-05 (週二 10:00)`
- 例：`start = 2026-05-08 (週五 10:00)`、`n = 1` → `2026-05-11 (週一 10:00)`（跳週末）

## 3. 範例

### Case 1：跨週末
- 爭議受理：`2026-05-08 (週五) 14:00`
- SLA：7 工作日
- 截止：`2026-05-19 (週二) 14:00`（跳 5/9 5/10 5/16 5/17 兩個週末）

### Case 2：跨春節（2026 年春節 2/16–2/22 共 7 天）
- 爭議受理：`2026-02-13 (週五) 09:00`
- SLA：7 工作日
- 截止：`2026-02-26 (週四) 09:00`（跳 2/14 2/15 週末 + 2/16–2/22 春節 7 天 + 2/14 為週六不重複扣）

### Case 3：跨國慶連假
- 爭議受理：`2026-10-08 (週四) 16:00`
- SLA：7 工作日
- 截止：`2026-10-21 (週三) 16:00`（跳 10/10 國慶 + 兩個週末）

## 4. 維護流程（年度更新）

| 時點 | 動作 | 負責 |
|---|---|---|
| 每年 12 月 | 行政院核定次年國定假日後，升級 `holidays` 套件至最新版 | DevOps |
| `pyproject.toml` | `holidays = "^X.Y"` pin major version；自動接 minor / patch | DevOps |
| CI | 跑 `tests/unit/test_workday.py` 含 12 個 golden case 涵蓋 4 個季節 | CI |
| 變更通知 | 若年度假日有調整（如補班 / 補休）→ 須 PR 調整本文件 §3 範例 | PM |

## 5. 影響範圍

- **後端**：`api/services/dispute_service.py` 之 `submit_dispute` / `create_settlement_dispute` 呼叫 `workday_sla_deadline(filed_at, 7)` 取代 `filed_at + timedelta(days=7)`
- **DB**：`disputes.sla_deadline` 欄位語意 = 工作日截止點（非自然日）
- **前端**：客戶看到的「截止日」格式：`YYYY-MM-DD（工作日制）`，hover tooltip 顯示 calculation
- **稽核**：sla_deadline 寫入時 audit log 須含 `calc_method = "workday"` 標記

## 6. Verification

- [ ] `agent/core/workday.py` 存在且 export 上述 3 helper
- [ ] `tests/unit/test_workday.py` 12+ golden case（跨週末 / 跨春節 / 跨國慶）
- [ ] `dispute_service.py` 不含 `timedelta(days=7)` 寫法（grep 殘留）
- [ ] `holidays` 套件版本 pin 在 `pyproject.toml`

## 7. Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-07 | Claude (assisted) | 初版：工作日定義 + helper 契約 + 3 邊界範例 + 年度維護流程（Q4=C 拍板） |
