---
title: Flow 12-14 deep audit
date: 2026-06-05
status: active
tier: 4
---

# Flow 12-14 deep audit — 校正 WBS 60-80% 粗估

## 1. 對應 spec

| Flow | 名稱 | 對應頁面 |
|---|---|---|
| Flow 12 | 金流與支付 | A9 帳務、客戶 LINE 支付頁 |
| Flow 13 | 帳款異常 EX5 | A9, A20 |
| Flow 14 | 技師排班衝突 | T10, A25, A28, A37 |

來源：`docs/ui/web_design_spec_prompt_pipeline/pages/MAPPING.md:378-380`

## 2. Flow 12 金流與支付 — 真實 **0%**

| 元件 | 狀態 |
|---|---|
| `api/routers/payments*.py` | ❌ 不存在 |
| `payments` table | ❌ Schema.sql 無 INSERT 路徑 |
| LINE Pay webhook | ❌ 無 |
| 客戶 LINE 支付頁 | ❌ 無 |

**對齊 CR-0011 FR-0011 消費者付款 CIA**（`docs/_audit/CR-0011-fr-0011-consumer-payment-cia.md`）— 8 個 HD 待業主裁決（provider 選型 / ≥50000 強制簽章 / fallback / 現金 dispute / 7y voucher retention / webhook idempotency_key / 簽章驗證 / M11 vs M12 金流關係）。**BUILD blocked by CR-0011 裁決**。

## 3. Flow 13 帳款異常 EX5 — 真實 **~50%**

| 元件 | 狀態 |
|---|---|
| Reconciliation dual-sign 正常流（CSM → ops_manager） | ✅ Track B S2，100% |
| `disputes_v2` 客訴流 (filed → in_review → ...) | ✅ Track B S2，100% |
| EX5 異常 endpoint（帳款金額不符、缺單、雙簽超時） | ❌ 無獨立 endpoint |
| EX5 admin 介入流（補單 / 註銷 / 推回客戶） | ❌ 無流程 |

**結論**：reconciliation 正常流 100%，但 EX5 例外流（spec 指明的「帳款異常」分支）後端 0 endpoint，僅靠 admin 手動進 disputes 介面。WBS 60-80% 粗估偏高。

## 4. Flow 14 技師排班衝突 — 真實 **~70%**

| 元件 | 狀態 |
|---|---|
| slot 衝突偵測 | ✅ `technician_service.py:208` — 同日 work_orders.scheduled_at 落在 slot → hard_conflict |
| `models/generated.py:530 schedule_conflict` enum | ✅ 存在 |
| 客戶 reschedule_proposal multi-slot | ✅ CR-0007 已落地 |
| **conflict → WS publish 至 admin** | ❌ 無觸發 |
| **conflict → 自動補救流（提建議時段 / 改派 / 升級）** | ❌ 無 |
| **A37 衝突告警頁** | ⏳ 未 grep 到對應 page，疑似缺 |

## 5. 校正後 WBS

| Flow | 原估 | 校正 | 理由 |
|---|---|---|---|
| Flow 12 | 60-80% | **0%** | 對齊 CR-0011 — blocked by 業主裁決 |
| Flow 13 | 60-80% | **50%** | reconciliation 正常流完整，EX5 例外流 0% endpoint |
| Flow 14 | 60-80% | **70%** | 偵測+ enum + reschedule_proposal 有，但無 WS publish / 自動補救 / A37 頁 |

## 6. 不立即 BUILD

- **Flow 12** blocked by CR-0011（業主裁決待）
- **Flow 13 EX5** 牽涉 reconciliation 額外狀態機 — 涉及 Domain model 變動 + Test plan，須開 CIA
- **Flow 14** 補救流牽涉 Flex push（與 Flow 11 同病）+ 客戶決定鏈路 — 等 CR-0017 LINE Flex 重建一併處理

## 7. 後續

- 本 audit doc → `docs/_audit/`
- WBS Flow 12-14 整列改為 0% / 50% / 70%
- Flow 12 補引用 CR-0011（避免重複開新 CR）
- Flow 13 / Flow 14 補一句「待 CIA」
