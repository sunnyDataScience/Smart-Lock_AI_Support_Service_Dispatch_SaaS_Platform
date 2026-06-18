---
id: CR-0030
title: "Change Impact Analysis — 派工模式切換（租戶手動派 / 平台代派）"
status: built
tier: 4-exploration
owner: HYBRID
created: 2026-06-18
target-release: TBD（Lite 版 / Beta 前）
product-version: null
supersedes: null
superseded-by: null
---

# CR-0030: 派工模式切換

> **Tier**: 4-exploration → CIA（per-change，實作後歸檔）
> **Mandated by**: `.claude/rules/change-governance.md`（命中 Business flow / Domain model / DB schema / API contract）
> **驅動來源**: 2026-06-17 會議 Action #7「派工模式切換 UI（租戶手動派 / 平台代派付費）」+ §三.4（Sunny：兩家師傅都沒空時叫平台派→收費點）
> **依賴**: CR-0026 work_orders；single-tenant（multi-tenant 真正派工權隔離 → CR-0031）

---

## 1. Change Statement

**As-is**：`assign_order` 無條件直接派工，無 tenant 層派工模式設定，平台代派的「付費」事件無法記帳追蹤；`dispatch:auto-match` 僅回候選不自動執行。

**To-be**：租戶層 `dispatch_mode` 三檔（manual / platform_paid / auto_match）；本輪做**前兩檔**（自動媒合留 Report 2）。assign_order 依模式標記 `work_orders.dispatched_via`（platform_paid → `platform` = 可計費事件）；後台 dispatch-queue 頁可切換模式。

**Driver**：會議定調平台代派為收費點，需 tenant 設定 + 可計費標記。

## 2. Affected Flow / 3. Spec

| Flow / Spec | Action | Description |
|---|---|---|
| `BF` 派工 | Modified | assign 依 dispatch_mode 標記 dispatched_via |
| `UF` dispatch-queue | Modified | header 加派工模式切換（管理角色）|
| `FR` 計費點 | New（佔位）| platform_paid 標記 billable；計費規則待業主（本輪不扣款）|

## 4. Affected API

| API | Endpoint | Action |
|---|---|---|
| `getDispatchModeV2` | `GET /tenants/{tid}/dispatch-mode` | New |
| `setDispatchModeV2` | `POST /tenants/{tid}/dispatch-mode` | New（admin/operations_manager/tenant_admin；audit log）|

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `saas.tenant.dispatch_mode` | New 欄 | migration 039：VARCHAR(20) DEFAULT 'manual'（app 驗證列舉）|
| `work_orders.dispatched_via` | New 欄 | migration 039：manual/platform/auto_match（platform=可計費）|

## 6. Affected Test

`test_cr_0030_dispatch_mode.py`：via_for_mode 映射（純）；set/get round-trip + 非法 422；platform_paid 模式下 assign_order → dispatched_via='platform'（end-to-end，含還原共享租戶設定）。回歸 work_orders v2。

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| 計費 gate | 佔位 | platform_paid 僅標記 dispatched_via='platform'，**不硬扣 credit**（計費規則待業主，§8）|
| 自動媒合 | 延後 | auto_match 設定值保留，但不自動執行（複用既有 `auto_match_dispatch` 候選，Report 2 接）|
| 複用 | 既有 | assign_order（manual 分支）/ audit_log / RBAC `role_required` |
| Multi-tenant | 可逆 | dispatch_mode 存 tenant 層（saas.tenant），multi-tenant 時各租戶各自設定 |

## 8. Human Decisions Required

✅ **會議授權用預設先做（Action #7 拍板）。** 採用：

| # | Question | Status | Decision（預設）|
|---|---|---|---|
| 1 | 平台代派「付費」計費規則（單價/credit/月結）| ⏳ 待業主 | 本輪只標記 dispatched_via='platform' 供日後對帳，**不硬扣款**；計費規則待業主定（移後續 CR）|
| 2 | 模式切換權限 | ✅ 預設 | admin/operations_manager/tenant_admin 可切；audit log 留痕 |
| 3 | 自動媒合（auto_match）本輪做不做 | ✅ 預設 | 不做（會議定調 Report 2）；enum 保留、不自動執行 |
| 4 | manual vs platform_paid 在 single-tenant 的行為差異 | ✅ 預設 | single-tenant 下兩者派工動作相同，差異在 dispatched_via 標記（billable）；真正派工權隔離待 CR-0031 multi-tenant |

## 9. Implementation Order（已實作）

1. ✅ migration 039（saas.tenant.dispatch_mode + work_orders.dispatched_via）
2. ✅ `dispatch_mode_service`（get/set + via_for_mode）
3. ✅ `assign_order` 依模式標記 dispatched_via
4. ✅ API GET/POST `/tenants/{tid}/dispatch-mode`（dispatch_v2.py）
5. ✅ `test_cr_0030_dispatch_mode.py` 3 pass + work_orders 回歸
6. ✅ UI dispatch-queue header DispatchModeSelector + i18n
7. ⏳ Docs sync（commit 時）

## 10. Risks & Rollback

| Risk | Mitigation |
|---|---|
| 計費規則未定即扣款 | 本輪只標記不扣款；§8-Q1 待業主 |
| 切換共享租戶設定影響測試 | 測試 finally 還原 manual |
| auto_match 模式被選但不執行 | enum 保留、assign 仍可手動；自動執行 Report 2 補（UI hint 標「下一階段」）|

**Rollback**：新欄（有預設/nullable）+ 新端點 + UI，可逆。

## 11. Out of Scope

- 平台代派計費引擎（credit 扣款/月結對帳）；自動媒合自動執行（Report 2）；multi-tenant 真正派工權隔離（CR-0031）。

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product（業主）| Sunny | 2026-06-17 | ✅ 會議授權用預設先做 |

## 13. 實作進度

- ✅ migration 039 + dispatch_mode_service + assign_order 標記 + GET/POST 端點 + UI 切換 + 測試 3 pass + 回歸 + tsc 0；migration 039 套 dev DB 驗證
- ⏳ follow-up：平台代派計費引擎（§8-Q1）、自動媒合自動執行（Report 2）、CR-0031 multi-tenant 派工權
- 分支：`feat/cr-0030-dispatch-mode`
