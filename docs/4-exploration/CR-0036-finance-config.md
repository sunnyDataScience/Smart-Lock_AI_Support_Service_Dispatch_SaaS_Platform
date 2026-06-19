---
id: CR-0036
title: "Change Impact Analysis — Phase II 金流參數入 M18 config 治理（訂金/佣金/月結時程）+ 訂金接發票"
status: draft
tier: 4-exploration
owner: HYBRID
created: 2026-06-19
target-release: TBD（補洞優先）
product-version: null
supersedes: null
superseded-by: null
---

# CR-0036: Phase II 金流參數入 config 治理

> **Tier**: 4-exploration → CIA（per-change）
> **Mandated by**: `.claude/rules/change-governance.md`（命中 Domain model / DB schema / Config governance）
> **驅動來源**: 業主指出 esales `PhaseII FinanceSettlement` sheet 24「Finance Config」已有訂金/佣金/月結時程草稿值（我 CR-0035 過度 defer 成「待裁決」）。決議 5 授權當 mock 灌入。
> **🛑 mock-first（同 CR-0032/0034/0035）：sheet 24 值當 mock seed、value 內標 `is_mock`，正式值待業主一次確認；稅務（Q-07）仍真未答故不納入。**

---

## 1. Change Statement

**As-is**：
- esales sheet 24「PhaseII Finance Config」有具體草稿值：訂金 `CFG-DEPOSIT-RATE=0.3`/`MIN=1000`/`MAT-PREPAY=1.0`、派工佣金 `CFG-DISPATCH-COMM=0.08`、月結時程 `3/5/10` 工作日。sheet 24 標題明寫**「所有規則版本化，不可寫死」**。
- 專案已有 **M18 config governance**（`saas.config_*` 表 + `config_m18_service`），但 migration 004 刻意「No pricing namespace — Phase II」**留空未灌**。
- CR-0035 把訂金/佣金 punt 成「Phase II / 待裁決」，`quote.deposit_required` 欄存在但從未設值；invoices 無 deposit 欄。
- **退款 tier**（CFG-REFUND-L1/L2/L3）已在 `refund_service`（ADR-0040 1k/5k/30k/100k）+ namespace `refund_tier_thresholds` 已註冊 —— **不重做**。

**To-be**：把 sheet 24 的 deposit/commission/monthly-close 三組參數**當 mock seed 進 M18 config 治理**（active 版、value 內含 `is_mock`/`esales_status`/`source`），code 從 config 讀（不寫死，符 sheet 24 約束）。並**回頭把訂金接進發票**：`invoice.create_from_quote` 從 config 算 `deposit_required`。

**Driver**：用 esales 既有草稿值（決議 5）取代 CR-0035 的 punt；符合「不可寫死」→ 走既有 config 治理；訂金從畫面/規則到發票打通。

## 2. Affected Flow

| ID | Action | Description |
|---|---|---|
| `SF` 開應收發票 | Modified | create_from_quote 計算 `deposit_required`（max(amount×rate, min) 上限 total），值從 config |

## 3. Affected API

無新增端點。既有 `GET /m18/config-read/{namespace}/{key}`（config_m18_service）即可讀新 namespace。

## 4. Affected Data

| Entity | Action |
|---|---|
| `saas.config_namespace` | 加 `deposit_policy` / `dispatch_commission` / `monthly_close_schedule`（各帶 json_schema）|
| `saas.config_version` | seed 三筆 global active config（key=`default`，value 含 sheet 24 值 + `is_mock`/`esales_status`/`source`）|
| `invoices` | 加 `deposit_required` NUMERIC（從 deposit_policy config 算）|

> **不做**：師傅拆帳逐列表（sheet 21，per service×level，較大 → follow-up，仿 CR-0034 catalog seed）；AR/AP Ledger / Brand Settlement（Phase II 計算引擎）。

## 5. Affected Test

config seed 可讀（read_global_value 回 sheet 24 值）；deposit 計算（30%/最低 1000/上限 total）；config 缺失時 code fallback 不破；is_mock 旗標存在。

## 6. Affected Architecture

| Concern | Notes |
|---|---|
| 新 ADR？ | 否（複用既有 M18 config governance + invoice service；無新架構決策）|
| 複用 | config_m18_service（read）、invoice_service.create_from_quote、refund namespace（既有，不動）|
| 設計約束 | sheet 24「不可寫死」→ 值走 config_version 非 code 常數；fallback 常數僅防 config 缺失 |

## 7. Human Decisions Required（§8）

🛑 **mock-first 不卡；以下為 mock→正式待裁（esales sheet 24 草稿 → 業主確認）。**

| # | Question | mock 值（sheet 24）| esales 狀態 | Status |
|---|---|---|---|---|
| 1 | 訂金比例 / 最低（Q-08）| 0.3 / 1000（取高）| Draft | open |
| 2 | 材料預收比例 | 1.0（100%）| Draft | open |
| 3 | 派工佣金率（Q-09 分潤一環）| 0.08（5-10% 可調）| Draft | open |
| 4 | 月結時程（初/覆/付）| 3 / 5 / 10 工作日 | Accepted default | 近確定 |
| 5 | 哪些服務/金額需訂金（Q-08 政策）| **全部**（mock：一律算）| Draft | open |
| 6 | 稅務（Q-07）| **不納入本 CR**（全檔無值，真未答）| 待會計 | out |

## 8. Suggested Implementation Order

1. migration 044：config_namespace ×3 + seed config_version ×3（global active，value 含 is_mock）+ invoices.deposit_required
2. config_m18_service.read_global_value helper（全域 active 讀，無則 None 不丟 404）
3. invoice_service：_resolve_deposit（從 deposit_policy config，fallback 常數）+ create_from_quote 計算存 deposit_required
4. Tests（TDD）
5. 三同步 / registry

## 9. Risks & Rollback

| Risk | Mitigation |
|---|---|
| sheet 24 草稿值當正式 | value 內 `is_mock`/`esales_status`；正式走 config 改版（M18 既有 rollout）|
| config 缺失致 deposit 計算炸 | read_global_value 回 None → _resolve_deposit fallback 常數（0.3/1000）|
| 直接 SQL seed 繞過 schema 驗證 | seed 值人工對齊 namespace json_schema；migration 註解標來源 |

**Rollback**：config_version 可 retire；invoices.deposit_required nullable 可逆；namespace 保留無害。

## 10. Out of Scope

師傅拆帳逐列表（sheet 21）、AR/AP Ledger 計算、Brand Settlement、佣金實際計算引擎、稅務（Q-07 真未答）→ follow-up / Phase II。

## 11. 實作進度

- ✅ **實作（`feat/cr-0036-finance-config`）**：
  - migration `044`：config_namespace ×3（deposit_policy / dispatch_commission / monthly_close_schedule，帶 json_schema）+ seed 三筆 global active config_version（value 含 sheet 24 值 + `is_mock`/`esales_status`/`source`，idempotent NOT EXISTS）+ `invoices.deposit_required`。
  - `config_m18_service.read_global_value`（全域 active 讀，無則 None 不丟 404，供 code 內部讀治理參數）。
  - `invoice_service._resolve_deposit`（從 deposit_policy config 算 max(amount×rate, min) 上限 total；config 缺失 fallback 0.3/1000 常數）+ create_from_quote 計算並存 `deposit_required`。
- ✅ **誠實釐清**（業主指正後重查 esales）：訂金/佣金/月結時程 sheet 24 **有草稿值**（我 CR-0035 過度 defer）→ 本 CR 補灌 config；**稅務 Q-07 全檔無值真未答**（不納入）；**退款 tier 已在 ADR-0040 + refund namespace**（不重做）。
- ⏳ **待 migration 044 套 dev DB**：`test_cr_0036_finance_config.py`（config seed 可讀 / deposit 計算 rate·min·上限 / 缺失 fallback）+ 回歸 `test_cr_0035_invoice_billing`（now 帶 deposit）。
- ⏳ §8 正式值：訂金/佣金率（綁 esales Q-08/Q-09）—— mock-first，走 M18 config 改版流程（非改 code/migration）。
- 分支：`feat/cr-0036-finance-config`
