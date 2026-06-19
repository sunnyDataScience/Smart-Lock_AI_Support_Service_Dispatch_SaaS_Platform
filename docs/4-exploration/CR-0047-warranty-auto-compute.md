---
id: CR-0047
title: "保固期動態計算 — 序號/購買日 → 保固到期 + 保內/保外自動回填"
status: implemented
tier: 4-exploration
owner: HYBRID
created: 2026-06-20
related: CR-0043 OPT.2（延後項）/ 派工單 PDF §四優化「保固期動態計算」/ ADR-0044 v2 warranty / CR-0026 warranty_status
---

# CR-0047: 保固期動態計算

> **驅動**：派工單 PDF §四「保固期動態計算：輸入序號→系統自動帶保固截止日→保內/保外即刻自動化，避免人為誤判」。CR-0043 OPT.2 標延後（warranty_service 引擎存在但未接 work_order）。

## 1. 現況
- `work_orders` 有 serial_number/purchase_date/install_date/brand，但 `warranty_status` 人工填（migration 036:31），無到期日落地欄。
- `warranty_service` 已有完整引擎：`resolve_start_date`（5-mode 錨點）、`resolve_period_months`（brand override：Yale 36/Dormakaba 60/預設 24 月）、`compute_warranty_end`、`is_within_warranty` —— 但只 warranty_claims 用，未接 work_order。

## 2. 實作
- **migration 057**：`work_orders.warranty_expiry_date` DATE（nullable）。
- `work_order_service._auto_warranty(brand, purchase_date, install_date)`：錨點優先 purchase_date 缺則 install_date；無錨點 → (None, None)；期間查 brand override；回 (到期日, in/out_warranty)。
- `update_wo_fields`：patch 動到 serial_number/purchase_date/install_date/brand 且**未手動指定** warranty_status → 自動回填 warranty_status + warranty_expiry_date（手動優先）。
- API：`warranty_expiry_date` 補 _WO_SELECT(index 35) + WorkOrder model + TS 型別 + 後台 sidebar「保固到期日」。

## 3. 測試
test_cr_0047 6/6：純函式（過保/保內/install fallback/無錨點）+ component（update 自動回填，Yale 36 月 brand override 端到端 → 2010-01-01+36mo=2013-01-01；手動 warranty_status 不被覆蓋）。回歸全套 794 passed 0 fail + tsc 0。

## 4. 仍延後
- 序號→品牌/型號自動反查（需 SKU/品牌序號主檔，sheet15-17，P2）。
- warranty_start_mode 進階（handover/contract/brand_warranty_date 錨點）目前只用 purchase/install。
