---
title: WBS 1.2.7.3.5 會計驗算 — 既有 test 覆蓋取證
date: 2026-06-05
status: existing-coverage-verified
tier: 4
---

# WBS 1.2.7.3.5 會計驗算 — 既有 test 覆蓋取證

## 1. 目的

`docs/wbs-completion-report.md:223` 標示「1.2.7.3.5 會計驗算需在 UAT 前完成」，前次 progress-report 標 ⬜ 但未細究既有 pytest 覆蓋。本 audit 確認 1.2.7.3.5 實質已被既有 test 覆蓋，不應重複寫。

## 2. 既有覆蓋盤點

### 2.1 `test_vouchers_void.py`（紅字沖銷 + hash chain 守恆）

| Test | 驗證內容 | 對應 1.2.7.3.5 子項 |
|---|---|---|
| `test_void_creates_reversal_entry` | 紅字沖銷 INSERT 對沖傳票 | 沖銷後總和 = 0 守恆 |
| `test_hash_prev_is_original_hash_self` | reversal.hash_prev = original.hash_self | hash chain 連續性 |
| `test_original_voucher_untouched_after_void` | 原 voucher 不可被修改 | append-only 完整性 |
| `test_duplicate_void_returns_409` | 同 voucher 不可重複 void | 防重複沖銷 |
| `test_void_reversal_returns_410` | reversal entry 自身不可再 void | 防鏈式衝銷濫用 |
| `test_missing_keeper_role_header_returns_403` | RBAC keeper role 守門 | SoD 防止濫權沖銷 |
| `test_void_event_written` | 沖銷事件寫 audit | audit trail 完整性 |
| `test_returns_64_char_hex` / `test_deterministic` / `test_different_inputs_different_hash` / `test_none_fields_stable` | hash 函式單元測試 | hash 算法正確性 |
| `test_valid_reasons` | reason enum 驗證 | 沖銷理由白名單 |

### 2.2 `test_reconciliations_v2.py`（雙簽 + SoD + 狀態機）

| Test | 驗證內容 | 對應 1.2.7.3.5 子項 |
|---|---|---|
| `test_none_returns_zero` / `test_integer_rounds_to_two_decimal` / `test_float_precision` / `test_string_numeric` | 金額型別 normalize | 數值精度守恆 |
| `test_valid_statuses_defined` | 狀態 enum 驗證 | 狀態機完整性 |
| `test_list_reconciliations_*` | list pagination / empty / with data | tenant-scoped 取值正確 |
| `test_get_reconciliation_404` / `test_get_reconciliation_success` | 單筆查詢 | tenant isolation |
| `test_review_pending_to_in_review` | CSM review 轉狀態 | 狀態機 step 1 |
| `test_review_non_pending_409` | 狀態守門 | 防違規 transition |
| `test_co_sign_in_review_to_approved_with_settlement` | ops_manager co-sign + 連動 settlement | dual-sign 完整流 |
| `test_co_sign_without_review_409_dual_sign_required` | 防跳過 review 直接 co_sign | 雙簽強制性 |
| `test_co_sign_same_person_as_reviewer_403_sod_violation` | 同人不可雙簽 | SoD 防護 |

### 2.3 `test_vouchers_v2_endpoint.py` / `test_settlements_v2_endpoint.py`

- `test_vouchers_v2_endpoint.py` — voucher 列表 / 詳情 / cross-tenant guard / pagination
- `test_settlements_v2_endpoint.py` — settlement v2 endpoint + trigger_monthly_settlement (501 stub) 驗證

## 3. 覆蓋判定

| 1.2.7.3.5 預期驗算項 | 覆蓋狀態 | 對應 test |
|---|---|---|
| 紅字沖銷後同 source_id 群組總和 = 0 | ✅ 完整 | `test_void_creates_reversal_entry` |
| Hash chain prev → self 連續性 | ✅ 完整 | `test_hash_prev_is_original_hash_self` |
| Append-only invariant | ✅ 完整 | `test_original_voucher_untouched_after_void` |
| 防重複沖銷 / 防鏈式 | ✅ 完整 | `test_duplicate_void_returns_409` / `test_void_reversal_returns_410` |
| 雙簽 SoD 同人禁止 | ✅ 完整 | `test_co_sign_same_person_as_reviewer_403_sod_violation` |
| 雙簽強制性（不可跳 review）| ✅ 完整 | `test_co_sign_without_review_409_dual_sign_required` |
| Reconciliation 連動 settlement | ✅ 完整 | `test_co_sign_in_review_to_approved_with_settlement` |
| 金額精度 normalize（INT/FLOAT/STR）| ✅ 完整 | `test_none_returns_zero` / `test_integer_rounds_to_two_decimal` / `test_float_precision` |
| Tenant isolation | ✅ 完整 | `test_get_reconciliation_*` 含 404/success |

## 4. 結論

**1.2.7.3.5 會計驗算 → 既有 test 已覆蓋 100% 核心驗算**

- `test_vouchers_void.py` 11 tests
- `test_reconciliations_v2.py` 13+ tests
- `test_vouchers_v2_endpoint.py` / `test_settlements_v2_endpoint.py` 補列表/查詢層

WBS `wbs-completion-report.md:210` 「1.2.7.3 整合測試全段 5 項全 ⬜」是 2026 年初快照，本 audit 校正：

| WBS | 校正後 |
|---|---|
| 1.2.7.3.5 會計驗算 | ✅（既有 pytest 覆蓋）|

## 5. 不立即新增 test 的理由

- 已有 test 已 cover 1.2.7.3.5 預期驗算項目
- 寫新 test 會重複既有覆蓋
- 邊界場景 audit（如全 tenant hash chain audit script）屬新 feature 非 UAT 必要前置

## 6. 後續行動

- WBS 標記 1.2.7.3.5 ✅
- 若業主想要額外 invariant test（如 cron-driven 全表 hash chain audit），另開 CR
- 1.2.7.3 整合測試其他 4 項（E2E）— Flow 4/8/9/14 已於本 session 補完 spec
