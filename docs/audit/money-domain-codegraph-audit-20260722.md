# 金流／結算／對帳 域 codegraph 稽核

- **日期**：2026-07-22
- **範圍**：FR-API-10（消費者付款）／FR-API-11（退款・取消費）／FR-API-12＋BR-Set-001（月結與 7 帳本）
- **方法**：從 `04_SRS.md` 撈金流宣稱 → codegraph／grep 逐條對照實作（直接查證，未開 workflow）
- **原則**：符號存在 ≠ 行為正確；本報告只陳述「查到什麼」與「查不到什麼」，不臆測

> ⚠️ Claude 的稽核分析，非業主 canon。文件 vs code 不一致一律回報待裁決，未擅改 `smartlock-docs`。

---

## 一頁結論

**金流域的實作品質高於文件表面印象**——傳票（voucher）層有**借貸科目 + reason_code + hash chain + 反向沖銷**，
付款三軌、退款分層、對帳例外都在。**唯一實質落差是「7 帳本」的統一 `ledger_type` 結構不存在**，
錢的功能改以「傳票日記帳 + 各域專表」實現。

| 判定 | 項目數 |
|---|---|
| ✅ 具備 | 9 |
| 🟡 drift（數值/維度對不齊） | 2 |
| 🔴 缺（文件宣稱、code 查無） | 1（含 4 個欄位） |

---

## ✅ 具備（codegraph 佐證）

| 宣稱 | 實作 |
|---|---|
| **三軌支付**（cash / Apple Pay / LINE Pay） | `payment_service.py:29` `_VALID_METHODS = {"cash","apple_pay","line_pay"}` — **恰三軌** |
| 付款 idempotency | `create_payment_intent(... idempotency_key)` `payment_service.py:50` |
| fallback 兩次嘗試留 audit | `record_payment_fallback` `payment_service.py:137` |
| 現金爭議進 disputes | `report_cash_dispute` `payment_service.py:167`＋`_CASH_DISPUTE_THRESHOLD_DEFAULT=500.0` |
| 退款責任分層 + 逐層核准角色 | `resolve_tier`（`refund_service.py:473`）＋`approver_role_for_tier`（`:524`）＋`test_refund_sod_5tier.py` |
| **reason code 制** | `saas.voucher.reason_code`（migration `010-vouchers-void.sql:29`）＋`refund_service.py:209`（並作為 `(work_order_id, reason_code)` 業務冪等鍵） |
| **借貸分錄** | `saas.voucher` 具 `debit_account`／`credit_account`／`amount` — 單筆一借一貸，**結構上恆平衡**（非多行日記帳，故無需額外平衡校驗） |
| **更正走反向分錄（append-only）** | `voucher_void_service.py:163-164` 沖銷時**借貸對調**；`:139` 反向分錄本身**不可再沖銷**；hash chain `sha256(voucher_no\|amount\|debit\|credit\|reverses_voucher_id\|hash_prev)` |
| 月結批次 + 對帳例外處理 | `saas.monthly_settlement_batch`、`trigger_monthly_settlement`（`settlements_v2.py:49`）、`reconciliation_exception_service.py`／`reconciliation_v2_service.py` |

---

## 🟡 drift（文件 vs code 對不齊，需裁決）

| 項目 | 文件 | 實作 | 說明 |
|---|---|---|---|
| **取消費階段數** | FR-API-11：「取消費 **5 階段** system 自判」 | `cancellation_service.py:1`：「Cancellation **6-stage** v2（ADR-0102 / FR-0052 / BR-CANCEL-001..008）」 | 數值 drift。ADR-0102 可能已 supersede SRS 的 5 階段——**待業主確認哪個是正**（不擅改 canon） |
| **退款「5×3」責任分層** | FR-API-11：「退款依 **5×3** 責任分層」 | 5 tier 已確認（`resolve_tier`）；「×3」維度疑為 `refund_class`（`validate_refund_class` `refund_service.py:494`） | 5 tier 明確；**×3 那維未逐一對照**，需確認 refund_class 是否即為文件的 3 分類 |

---

## 🔴 缺：7 帳本統一結構（`ledger_type`）

**文件宣稱**
- FR-API-12／BR-Set-001：**7 帳本制**（Customer AR／Tech AP／Cash／Brand Settle／Dispatcher Commission／Refund／Invoice&Tax）
- `04_SRS.md:80`：Settlement entity 應具 **`ledger_type` / `period` / `audit_trail[]` / `partner_id`**

**實作現況**
- **`ledger_type` 全庫零命中**（唯二 "ledger" 為 `inventory` 物料異動與 `saas.technician_penalty_bonus_ledger`，皆屬他域）。
- `Settlement` 模型（`api/models/generated.py:1988`）實際欄位＝`id / reconciliation_id / technician_id /
  technician_name / amount / currency / status / payment_method / paid_at / created_at`
  → **文件指名的 4 個欄位（`ledger_type`／`period`／`audit_trail[]`／`partner_id`）一個都沒有**。
- 7 帳本改以**各域專表**存在（部分對得上）：`invoices`／`vouchers`＋`saas.voucher`／`settlements`＋`saas.settlement`／
  `saas.monthly_settlement_batch`／`saas.dispatcher_commission_statement`／`technician_commission_projection`／
  `technician_payout_rule`／`saas.technician_penalty_bonus_ledger`。

**判讀（待業主裁決，非 AI 決定）**
會計骨架其實是「**傳票日記帳（voucher：借貸科目＋reason_code＋hash chain）＋各域專表**」，
而非「單一帳本表以 `ledger_type` 分七類」。兩種設計都能記帳，差別在：
- 現行設計：查特定帳本要跨表；缺統一 `period`／`partner_id` 維度做跨帳本月結對齊。
- 文件設計：統一維度便於「7 帳本 × period」出表與對平。

→ **需裁決**：(a) 文件對齊實作（把 BR-Set-001 改述為「傳票日記帳＋各域專表」並標注）
　　(b) 實作補上 `ledger_type` 統一維度（屬 domain model + DB schema 變更，需 CIA）。

---

## 建議下一步

1. **先裁決上表 3 項**（取消費階段數／5×3 維度／7 帳本設計取向）——都是「文件 vs 實作」孰為正的問題，不是工程問題。
2. 若選 (b) 補 `ledger_type`：屬 Domain model＋DB schema 變更 → **走 CIA**。
3. 本輪**未**觸及：月結批次的實際對平正確性、金額精度（`numeric(14,2)`）邊界、跨幣別——那需要資料層測試而非靜態稽核。
