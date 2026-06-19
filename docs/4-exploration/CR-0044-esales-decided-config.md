---
id: CR-0044
title: "Change Impact Analysis — esales 已決定值 de-hardcode + 取消費 SoT 衝突裁決"
status: implemented
tier: 4-exploration
owner: HYBRID
created: 2026-06-19
related: CR-0036（finance config 治理）/ CR-0038 桶4 / esales 03 加價規則 + 24 Finance Config / ADR-0102
---

# CR-0044: esales 已決定值 de-hardcode

> **驅動**：盤點 `20260617資料/AI_Blue_鎖匠ERP_報價資料庫_PhaseII_FinanceSettlement_v1.xlsx` 後校正一個誤判——
> 先前把「正式價待業主」過度推廣成「整個 finance 待業主」。實際 esales `13 待決策 Q&A` 只列 **Q-01~Q-12 待回答**，
> 其餘在 `03 加價規則`/`24 Finance Config` 標 **已知規格 / Accepted default**（已決定）。

## 1. 校正後的真實分類

**已決定（esales 已知規格 / Accepted default）**：
- 區域加價 同/跨/偏遠 500/800/1200（已在 `surcharge_rule` 表）
- **取消費 S1-S4 0/0/300/500/800**（ADR-0102；code 原值 s3/s4=300 **錯**）
- 報價有效期 14/3（**原寫死** `quote_engine_service.py`）
- 退款 tiers 1000/5000/30000（已在 config）、月結 3/5/10、訂金 30%/1000（CR-0036 已 config）
- 派工佣金 0.08（已在 `dispatch_commission` config）

**仍待業主（esales Q-01~Q-12 待回答）**：服務/材料基礎價（Q-01/02）、急件/夜間/假日加價**方法**（固定額 vs %，Q-03/04/05）、S5 取消費算法（Q-06）、稅務顯示（Q-07）、優惠權限（Q-11）、客戶報價文字（Q-12）。

## 2. 🛑 Source-of-Truth 衝突（已裁決）

- `cancellation_service.py:43-44`（code，note ADR-0102 v2 2026-05-28）：S3=300、S4=300
- esales `03 區域與加價規則` CNL-S3/S4（2026-06-03，標已知規格 ADR-0102）：S3=500、S4=800

**業主 2026-06-19 裁決：採 esales 500/800**（較新且與加價表自洽）。

## 3. 實作（本 CR 只動「已決定 ∩ 仍寫死」者）

> 區域加價（已在 surcharge_rule 表）、佣金（已在 config）不需再「接 config」——它們缺的是 P2 **計算引擎**（套加成 / 算 base），仍 P2 下輪。本 CR 不碰 payment 子系統。

| 項目 | 變更 |
|---|---|
| 取消費 S3/S4 | `DEFAULT_CANCELLATION_CONFIG` 300→500/800 + **migration 054** UPDATE `system_config.cancellation.fees`（DB override 也修）|
| 報價有效期 | `quote_engine_service._validity_days` 讀 M18 config `quote_validity_policy`（fallback 14/3）；migration 054 seed |

## 4. 測試

`test_cr_0044`：default fees 校正（純函式）+ get_cancellation_config 反映 500/800 + 有效期讀 config 14/3（component）。回歸修 3 個 stale 取消費斷言（S3 300→500、S4 600→1100、endpoint S3 300→500）。786 passed 0 fail。

## 5. 仍 P2 下輪（不在本 CR）
出勤/夜間/假日加價**自動計算引擎**（surcharge_rule→quote total，且方法 Q-03/04/05 待業主）、佣金引擎（讀 0.08 算 base）、payment 核心/AR ledger/月結 batch。

## 6. 進度
✅ done（2026-06-19，branch `feat/cr-0044-esales-decided-config`）：取消費 S3/S4 校正（code+DB override，migration 054）+ 有效期入 config + test 3/3 + 回歸修 3 stale + 786 passed。
