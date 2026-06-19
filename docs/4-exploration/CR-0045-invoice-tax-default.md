---
id: CR-0045
title: "Change Impact Analysis — 發票稅 de-hardcode（esales Q-07 預設台灣 5% 含稅）"
status: implemented
tier: 4-exploration
owner: HYBRID
created: 2026-06-19
related: CR-0044（esales 已決定值 de-hardcode）/ CR-0035（invoice from quote）/ esales Q-07 / ERP Q099
---

# CR-0045: 發票稅 de-hardcode

> **驅動**：業主指示「問之前先翻 `20260617資料/`」。窮盡翻查後確認 Q-01~Q-12 多數其實在資料夾且已 seed（決議 5 授權當 mock）；真正待業主縮到 Q-07/Q-11/Q-12。本 CR 接 Q-07。

## 1. 現況
- `invoice_service.create_from_quote`：`tax = 0.0  # mock：未稅（待 esales Q-07）` —— 寫死 mock 0。
- 翻 ERP spec：Q099 已定發票責任（B2C 平台開 / B2B 派工人），但稅率/含稅未明寫。

## 2. 裁決（業主 2026-06-19，選項 1 守會議界線）
- 預設**台灣 VAT 5% 含稅**（inclusive），可動態改。稅屬 money rule → 入 M18 config。

## 3. 實作
- **migration 055**：`tax_policy` config（rate=0.05 / mode=inclusive / source 註明可改）。
- `invoice_service._resolve_tax(gross)`：讀 tax_policy（fallback 5% 含稅）回 (amount, tax, total)。
  - **inclusive 含稅**：amount/total = gross（客戶含稅總價，對外不變），tax = gross×rate/(1+rate)（內含稅額，DB-only）。
  - exclusive 未稅：amount = gross，tax = gross×rate，total = amount+tax。
- `create_from_quote` 改呼 `_resolve_tax(quote.total_amount)` 取代 hardcode 0。

## 4. 影響
- **對外 API amount 不變**（仍露客戶含稅總價）；只是 DB invoices.tax 由 0 → 內含稅額（帳務正確）。
- test_cr_0045 3/3（5% 含稅拆算）+ 回歸全套 789 passed 0 fail。

## 5. 仍待業主（資料夾無）
Q-11 客服優惠權限幅度、Q-12 公司抬頭/客服電話/保固+取消條款**實際文字**。

## 6. P2 守界線（會議定調下輪，資料已備不在本 CR）
報價自動帶 catalog 價、加價（surcharge_rule）套用 quote total、payout reconciliation 改讀 `technician_payout_rule`（045，取代 80/20 寫死）。
