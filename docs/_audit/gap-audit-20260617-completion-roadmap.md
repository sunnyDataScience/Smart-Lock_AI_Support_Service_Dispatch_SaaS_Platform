---
title: 20260617資料 工項缺口盤點 + 補完 Roadmap
status: active
tier: 4
date: 2026-06-18
source: 20260617資料/（會議記錄 + ERP 藍圖 + esales 報價 + 派工單 PDF + 測試計畫）
method: 5 源平行盤點（程式碼 vs 藍圖）→ 綜整
---

# 20260617資料 工項缺口盤點 + 補完 Roadmap

> 程式碼 vs `20260617資料/` 全源比對的單一事實來源。判斷「還有哪些工項沒做」與補完順序。
> **數值/規則不可信來源（esales xlsx / PDF）一律經人工轉寫 + 業主決策，禁止直接 seed。**

## 一句話

**廣度夠、深度淺**：ERP 藍圖 M01-M20 每個模組都有 router/service 骨架（無整模組缺），但會議「100% 不可信」成立 —— **金流結算 / 報價引擎 / 報價主檔 / 免責合規 / 報表 KPI / Partner Portal / 測試**只有殼或 stub，業務規則/gate/帳本是空的。

## 盤點數字（2026-06-18）

| 資料源 | 已做 | 部分 | 未做 |
|---|---|---|---|
| ERP 藍圖 M01-M20 + 14 角色 | 9 | 12 | 0 |
| esales 報價/成本模型（34 sheets） | 2 | 16 | 17 |
| 派工單 PDF（6 模組 25 欄） | 17 | 6 | 4 |
| 測試計畫（194 項） | 0 | 8 | 20 |
| 會議 13 Action Items | 5 | 5 | 3 |

## 已完成基準（不重列）

CR-0020~0030 + 收尾：公單編號 / 五角色 RBAC / LINE→工單 HITL / agent 記憶 / handover / 自助密碼 / 公單標準化欄位 / 報價成本明細 quote_line_items + 電子工單 PDF / LINE 公單回傳 / 廠商+師傅雙路註冊+登入 / 派工模式切換。single-tenant by Chairlock。

## 最痛缺口（CRITICAL，藍圖 ID）

| 缺口 | 現況 | 規模 |
|---|---|---|
| M12 月結 | `POST /settlements/monthly` = **501 stub**；無 trigger/扣款/爭議冷卻 | XL |
| M11 + M27-M32 金流帳本 | 付款驗證/AR 催收/退款分層/AP 細項/佣金明細/月結狀態機 全缺（只有彙總 statement 表）| XL |
| 報價引擎 | 只有 quote_line_items；缺 quote 主表/核准 gate/snapshot 凍結/14d 過期/訂金 | L |
| 報價基礎主檔 | service_catalog/material_catalog/BOM/加價規則/拆帳 全未建（依 esales 12 項業主決策）| XL |
| 免責合規 | work_order_consents（新機/破壞鎖/個資三段）未建；電子工單無免責欄 | M |
| 報表 KPI 治理 | 只有框架，缺毛利率/未收逾期/績效 + KPI 定義 UI | L |
| Partner Portal（M14）| 只有 B2B statement 報表，無廠商帳號/專案合約/品牌隔離 | L |
| 測試 | AI 評測 pipeline / K8 corpus / 10 前端 e2e / cross-tenant / NFR 多為 0 | XL |

## 補完計劃（CIA-gated，接 CR-0032 起）

依會議定調「補洞 → 測試 → multi-tenant」：

| 階段 | CR | 範圍 | 規模 | CIA | 依賴 |
|---|---|---|---|---|---|
| S1 立即收尾 | （無新 CR）| vendor 核准 UI、自助密碼 prod SMTP、發 URL/QR(Action 8)、document usage(Action 10)、LINE 接入文檔(Action 13)、測試計畫對接(Action 2) | S | ❌ | — |
| S2 報價引擎 | CR-0032 | saas.quote 主表 + 核准 gate + snapshot 凍結 + 14d 過期 + 欄位級 RBAC | L | ✅ | S1 |
| S3 免責合規 | CR-0033 | work_order_consents 三段法律文本 + work_orders 補欄 + 電子工單免責版面 | M | ✅ | S1 |
| S4 報價主檔 | CR-0034 | **先做 esales 12 項業主決策表** → seed service/material/BOM/加價/拆帳主檔 | XL | ✅ | S2 |
| S5 金流結算 | CR-0035 | 月結 trigger 接 501 stub + AR/AP/佣金/取消費分層/月結狀態機 | XL | ✅ | S4 |
| S6 報表+Partner+風控 | CR-0036/37 | KPI 治理 + Partner Portal + 14 角色 enforcement | L | ✅ | S5 |
| S7 測試補完 | CR-0038 | service 單測 + 10 前端 e2e + AI 評測 corpus + NFR/cross-tenant | XL | ✅ | S2-S6 |
| S8 multi-tenant | CR-0031 | 三類租戶分庫 + RLS（待 ADR-0030）—— **最後一輪** | XL | ✅ | S7 |

## Quick wins（不需 CIA）

1. 廠商核准 UI（後端 CR-0029 已完整，缺 admin 審核頁）—— **本輪做**。
2. 自助忘記密碼 prod 啟用（配 SMTP secret + api.sh，email_provider.py 已 fail-safe）—— **業主 ops**。
3. 發上線 URL + QR 給 Irene（Action 8）—— **業主 ops**。
4. document usage（Action 10）+ LINE 租戶接入文檔（Action 13）。

## 治理紅線

- **esales 數值不可信**：S4 報價主檔的價格/加價/訂金/分潤必須先走 esales sheet 13 的 Q-01~Q-12 業主決策表人工轉寫，**禁止直接 seed xlsx 原值**。
- 每個大工項先跑 `sunnydata-change-impact-analysis` 產 CIA，停 §8 等業主裁決。
- **multi-tenant 留最後**（會議決議 11）：single-tenant 報價/金流/測試穩定前橫切，會把未完功能乘上租戶維度。先補洞 → 測試綠燈 → 一次橫切。需先 DLD/ERA + ADR-0030 RLS 裁決。

## 進度

- ✅ 2026-06-18 本盤點 + roadmap
- ✅ S1 vendor 核准 UI（CR-0029 收尾，本輪）
- ✅ S2 CR-0032 報價引擎 CIA 產出（停 §8 等裁決）
- ⏳ S1 其餘（SMTP/QR=ops）、S3-S8 依序
