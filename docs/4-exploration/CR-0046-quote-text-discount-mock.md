---
id: CR-0046
title: "Q-11/Q-12 假資料生成（公司報價文案 + 客服優惠權限，待業主確認替換）"
status: implemented
tier: 4-exploration
owner: HYBRID
created: 2026-06-19
related: esales Q-11 / Q-12 / 會議決議 5（mock 先做可動態改）/ CR-0045
---

# CR-0046: Q-11/Q-12 假資料生成

> **驅動**：翻遍 `20260617資料/` 後確認 Q-11/Q-12 資料夾確實沒有（公司專屬）。業主指示「先生成假資料，確認後再替換」。值入 M18 config → 業主改 config_version 即替換，不改 code。

## 1. 生成的假資料（全標 is_mock，文字含「（範例…）」）

**company_profile（Q-12）**：
- company_name：`Chairlock 智慧鎖到府服務（範例待業主確認）`
- customer_service_phone：`0800-000-000（範例待替換）`
- warranty_text：本店購買安裝享原廠+安裝保固 12 個月；自備鎖代工僅保固安裝品質…（範例待法務）
- cancellation_clause：派工後取消依階段 300/500/800；已施工依實際或報價 50%（依 ADR-0102，範例）
- surcharge_clause：報價外工項須客戶重新確認同意才施作（範例）

**discount_policy（Q-11）**：approval_threshold=10000、cs_max_discount_pct=10、supervisor_required_above_pct=10。

## 2. 接線
- `work_order_document_service`：客戶電子工單 PDF 頂部加公司抬頭 + 客服專線；總價後加「服務條款」段（保固/取消費/追加價，讀 company_profile，缺則佔位文字）。
- `quote_engine_service._approval_threshold`：報價送審門檻讀 discount_policy（fallback 10000），取代 hardcode。

## 3. 測試
test_cr_0046 3/3（門檻讀 config + company_profile/discount_policy 齊全且標 mock）+ 回歸 792 passed 0 fail（PDF render/quote engine 不破）。

## 4. 業主如何替換真值
改 `saas.config_version`（namespace=company_profile / discount_policy）的 value JSON 即生效（M18 config 動態，無需改 code / 重部署）。確認真值後把 is_mock 改 false、移除「（範例…）」字樣。

## 5. 仍屬下輪 P2（會議定調）
報價自動帶 catalog 價 / 加價套用 / payout reconciliation 讀 045 表（資料已備，引擎下輪金流）。
