---
title: CR-0041 M15 異常框架 — exception_case 實體 + return_path + high-risk pause（BR-M15-01/03）
status: implemented
tier: 4-exploration
created: 2026-06-19
owner-decision: ✅ 2026-06-19 業主裁決全採建議預設（見 §8）
related: M15 Exception / BR-M15-01/02/03 / FR-0049(approval inbox) / generated.py Exception model / CR-0038 階段1
---

> ✅ **§8 已裁決（2026-06-19，全採建議預設）+ MVP 已實作（見 §10）。** CR-0038 階段1「公單收尾」最後一塊。

## 1. 動機（WHY）

會議 + spec：缺料/改期/加價拒絕/取消/退款/爭議/安全風險等**異常不能藏在 chat**，每個異常要選 return path 並進核准。現況：
- **BR-M15-01 異常實體：缺**。`generated.py` 已完整設計 `Exception` model（ExceptionType 10 值 / Status 5 態 / Severity / return_to_stage / circuit_breaker），但**無 DB 表、無 service、無真 router**。
- **BR-M15-02 approval inbox：大致有**（FR-0049 `approval_inbox_service.list_pending_approvals` 已聚合 scope_change/refund/dispute/reschedule/recon → 統一 inbox）。但只涵蓋「已有專屬表」的核准，**不涵蓋無專屬表的異常**（no_show / customer_absent / material_shortage / appearance_refused / quality_complaint）。
- **BR-M15-03 high-risk stop：缺**。WO 狀態機只有 created/assigned/accepted/in_progress/completed/cancelled，**無 high_risk_hold**；保固不明/安全/加價拒絕無「暫停到核准」機制。
- **`exceptions_v2.py` 命名誤導**：tag 標「M15 Exceptions」但實際 delegate `technician_schedule_service`（師傅排班請假/待命核准），與 M15 異常無關。

## 2. 觸發面向

| 面向 | 命中 | 說明 |
|---|:-:|---|
| Domain model | ✅ | 新 exception_case 實體（control tower）|
| DB schema | ✅ | exception_case 表（migration）|
| API contract | ✅ | 新 exception 端點；exceptions_v2 改名（路徑/operation_id 變動）|
| Business rule | ✅ | return_path 選項、high-risk 觸發與暫停 |
| Test plan | ✅ | exception lifecycle + high-risk + return_path component 測試 |

## 3. 現況（grounded）

- `generated.py:544` ExceptionType(10) / :557 ExceptionStatus(5) / :584 Exception model（含 return_to_stage / triggers_circuit_breaker）。**只有 model，無表/service/router**。
- `routers/exceptions_v2.py`：`listExceptionsInbox` / `approveException` → 實際呼 `technician_schedule_service`（誤命名）。
- `services/approval_inbox_service.py:63 list_pending_approvals`：聚合 scope_change/refund/dispute/reschedule/recon_exception（FR-0049，BR-M15-02 大致達成）。
- WO 狀態（`work_order_service.py`）：created/assigned/accepted/in_progress/completed/cancelled，無 hold 態。
- 既有 return-path 端點已分散存在：cancel_order / reassign_order / record_scope_change / dispute / refund。

## 4. API 契約變更

- 新 `exception_case` 端點（建議 `/tenants/{tid}/exception-cases`）：open / list / get / resolve（帶 return_path）/ escalate。
- `exceptions_v2.py`（schedule 別名）改名 → `technician_schedule_v2`（路徑 `:schedule-requests`，operation_id 修正）；釋出 `exceptions` 命名給真框架。
- FR-0049 approval_inbox 加入 `exception` type（high-severity open exception 進統一 inbox）。

## 5. 領域 / 資料

- `saas.exception_case`（對齊 generated.py model）：id / tenant_id / work_order_id / exception_type / status / severity / description / **return_path**（HD-4）/ return_to_stage / triggers_circuit_breaker / actor / resolution / resolved_at / resolved_by / created_at / updated_at。
- high-risk（HD-2）：severity in (high, critical) 的 open exception → 需核准；WO 是否加 `high_risk_hold` 旗標/狀態待裁決。

## 6. 測試計畫

`test_cr_0041_exception_framework.py`（component）：
- open exception → status=open；high severity 進 approval inbox。
- resolve 帶 return_path（continue/requote/reschedule/reassign/cancel/refund/rma/dispute 之一）→ status=resolved + return_path 記錄。
- escalate → status=escalated。
- 非法 return_path → 422。
- （若 HD-2 選 WO hold）WO 進 high_risk_hold → 擋 dispatch/complete 直到 exception resolved。

## 7. 風險

- exceptions_v2 改名 = breaking（前端/caller 須改）。緩解：grep caller、同 PR 改前端、保留舊路徑一段（deprecation）。
- 過度設計：return_path 9 選項多數已有端點 → 框架先做「記錄 + 路由提示」，實際動作仍走既有端點（不重寫）。
- high_risk_hold 若改狀態機 = 影響既有完工/派工 gate（須回歸測試）。

---

## 8. 🛑 Human Decisions Required

| # | 決策 | 建議預設 | 業主裁決（2026-06-19）|
|:-:|---|---|---|
| **HD-1** | 範圍 | MVP 框架 | ✅ **MVP 框架**（return_path 記錄+提示，不重寫各動作）|
| **HD-2** | high-risk 暫停模型 | WO `high_risk_hold` 旗標 | ✅ **WO 旗標**（不改主狀態機）|
| **HD-3** | exceptions_v2 改名 | 改名 + 讓位 + 30d | ✅ **改名 + 讓位**（真框架用 /exception-cases、舊路徑 deprecated 30d）|
| **HD-4** | return_path 模型 | 加 action enum | ✅ **加 return_path action enum**（9 動作）|
| **HD-5** | 自動觸發 | 手動 + 半自動（未另問，採預設）| ✅ **手動 open 為主**，半自動/各動作串接 follow-up |

## 9. Suggested Implementation Order（裁決後）

1. migration 049：`saas.exception_case` 表（對齊 model + return_path）+ （HD-2）work_orders 加 high_risk_hold 旗標。
2. `exception_service`：open / list-inbox / get / resolve(return_path) / escalate；high severity 標記。
3. 改名 `exceptions_v2` → `technician_schedule_v2`（grep caller + 前端同步）；新 `exception_cases_v2` router。
4. approval_inbox 加 exception type。
5. （HD-2）dispatch/complete gate 檢查 high_risk_hold。
6. `test_cr_0041` component。
7. redeploy smoke + 更新 CHANGELOG / 完成度 / 本 CR §進度。

---

## 10. 進度

✅ **MVP done（2026-06-19，branch `feat/cr-0041-exception-framework`）**：
- **migration 049**：`saas.exception_case`（對齊 generated.py model + `return_path` action 欄 + status/severity CHECK）+ `work_orders.high_risk_hold` 旗標。
- **`exception_service`**：open（high/critical + WO → 設 high_risk_hold）/ list（status·severity filter）/ get / resolve（選 return_path 9 動作之一；無其他 open high-risk → 解除 hold）/ escalate。
- **`exception_cases_v2` router**：`/exception-cases` open/list/get/`:resolve`/`:escalate`（resolve/escalate 限管理角色）。
- **BR-M15-03 high_risk_hold gate**：`work_order_service._assert_not_high_risk_hold` 接入 `assign_order`（派工）+ `complete_order`（完工，含 override）→ hold 時 422 `HIGH_RISK_HOLD`。
- **改名（HD-3）**：`exceptions_v2.py`（實為排班別名）加 DEPRECATED 註記，真框架讓位 `/exception-cases`；main.py mount 註明。
- **測試** `test_cr_0041` **6/6 pass**（無效 type/return_path 422 / medium 不 hold / high→hold + gate 擋 / resolve 解除 hold + 記 return_path / escalate + list）+ 回歸 51 工單/完工 + 226 unit 全綠。

⏳ **follow-up**：(a) `exceptions_v2` 正式改名 `technician_schedule_v2` + 遷 `admin/schedule-requests` 前端（30d deprecation 內）；(b) approval_inbox 加入 exception type（high-severity open 進統一 inbox，BR-M15-02 補強）；(c) 既有事件半自動 open exception（appearance_refused/no_show/material_shortage）；(d) return_path 各動作與既有端點（cancel/refund/reassign）串接執行；(e) 前端異常 inbox 頁。
