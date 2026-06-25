---
title: "CR-0101 — 報價先行：從問題卡建立報價草稿（quote-from-problem-card）"
status: draft
tier: 4-exploration
created: 2026-06-25
owner: 啟恆 / Sunny 裁決
trigger: User/Business flow（報價時點前移）+ API contract（報價建立入口）+ Domain model（報價可掛問題卡）+ DB schema（quote_line_items.work_order_id 鬆綁）
related:
  - api/services/quote_engine_service.py（create 目前必填 work_order_id）
  - api/services/quote_service.py（line items 綁 work_order_id）
  - docs/4-exploration/CR-0095-quote-line-approval.md（派工前須 accepted 報價）
  - docs/_audit/diagnosis-engine-doc-trace-20260625.md（同期前端誠實化盤點）
---

# CR-0101 — 報價先行：從問題卡建立報價草稿

> 🛑 **draft —— 觸及 User flow / API contract / Domain / DB schema，動 code 前須業主裁決 §8。** 業主 2026-06-25 測試時提出「報價單想根據問題卡建草稿目前做不到」，裁決開 CIA 評估。

## 1. Change Statement

讓客服能**在問題卡階段（開單前）就建立報價草稿**並送客戶，即「報價先行 / quote-first」。客戶接受後再開單派工。目前**做不到**：報價一律掛在工單下。

## 2. Affected Flow ⚠️（與既有正典流程衝突，須裁決）

**既有正典流程（文件明載）**：
> `①LINE→問題卡 ②確認→開單 ③內部估價 ④外部報價`（CR-0095、system-overview）

—— 報價(③④)在**開單(②)之後**。

**本 CR 提議**：把報價前移到問題卡階段（開單前）。這是**主流程順序變更**，不是補缺口。

| | 既有 | 報價先行 |
|---|---|---|
| 報價時點 | 開單後（工單上） | 問題卡階段（開單前） |
| 開單前置 | — | 客戶已接受 PC 報價 |
| CR-0095 派工閘 | 工單須有 accepted 報價 | PC 報價接受後沿工單帶入 |

→ **§8 須裁決：報價先行是「取代」還是「並存」於既有開單→報價流程。**

## 3. Affected Spec

- 與 `system-overview` + CR-0095 的「開單→報價」順序**矛盾**；若採用，需更新流程描述（或標既有為其一分支）。
- M04 Quote 模組語意擴充：報價的「父」從單一 work_order 變成 work_order **或** problem_card。

## 4. Affected API

| 端點 | 變更 |
|---|---|
| 新：`POST /tenants/{tid}/problem-cards/{pcId}/quotes` | 建 PC-level 報價草稿（或讓既有 quote create 接受 problem_card_id、work_order_id 選填）|
| `quote_engine_service.create` | 目前 `work_order_id: str` 必填 + 沿 WO 取 problem_card_id → 改為「WO 或 PC 二擇一」；version 改沿 PC 遞增 |
| 報價狀態機（draft→pending_approval→approved→sent→accepted）| **可沿用**，與父實體無關 |
| `_quote_number`（目前 `{WO號}-Qn`）| PC 階段無 WO 號 → 需 PC 級編號格式（§8）|
| 開單 `convert-to-work-order` | 須把 PC 上已 accepted 的報價**接續綁定到新工單**（否則 CR-0095 派工閘讀不到）|

> 皆為 additive 為主，但 quote create 的 key 由「WO 必填」改「WO/PC 二擇一」屬 contract 變更。

## 5. Affected Data（DB）

| 表 | 現況 | 需要 |
|---|---|---|
| `quote.work_order_id` | **已 nullable** ✓ | 無需改 |
| `quote.problem_card_id` | **已 nullable** ✓ | 無需改（PC-only 報價直接可存）|
| `quote_line_items.work_order_id` | **NOT NULL** 🔴 | **migration 鬆綁為 nullable**（PC-only 報價的明細無 WO）；明細改以 `quote_id`（已 nullable，但實際都有值）為主 key |
| version 編號 | `MAX(version) WHERE work_order_id` | 改沿 PC（無 WO 時）|

> **好消息**：quote 主表本來就允許「只綁 PC、無 WO」（兩欄皆 nullable）→ 阻擋只在 service 與路由，不在 schema。唯一 DB 改動是 `quote_line_items.work_order_id` 鬆綁（migration 080）。

## 6. Affected Test

- 新：PC-level 建報價草稿 / 加明細（work_order_id 為 null）/ 送客戶 / 接受。
- 開單時把 PC 已接受報價接續綁 WO；CR-0095 派工閘能讀到（QUOTE_NOT_ACCEPTED 不誤擋）。
- 回歸：既有「工單上建報價」全套不破壞（若採並存）。

## 7. Affected Architecture

M04 Quote 模組：報價父實體由「work_order 專屬」變「work_order 或 problem_card（polymorphic parent）」。無新模組/服務，沿用 quote_engine_service + 報價狀態機。

## 8. 🛑 Human Decisions Required（待業主裁決）

| # | 決策 | 選項 / 說明 |
|---|---|---|
| **1** | **取代 or 並存** | (a) **並存**：保留「工單上報價」+ 新增「問題卡報價」兩入口（推薦，回歸風險低）；(b) **取代**：報價一律前移到問題卡，開單後不再單獨報價（大改、破壞 CR-0095 既有測試）|
| **2** | **流程正典更新** | 採用後，system-overview / CR-0095 的「開單→報價」順序要改寫，或標為「報價先行為另一分支」。哪邊是正典？|
| **3** | **開單時報價接續** | PC 上已 accepted 的報價，開單時是否**自動綁到新工單**並滿足 CR-0095 派工閘？（推薦：是，否則報價先行無意義）|
| **4** | **報價編號格式** | PC 階段無 WO 號（現 `TP-000001-Qn`）。PC 級編號用什麼？（如 `PC號-Qn`，開單後是否改號）|
| **5** | **明細 key 鬆綁** | 同意 migration 080 把 `quote_line_items.work_order_id` 改 nullable（PC-only 報價明細）？ |

## 9. Suggested Implementation Order（待 §8 後）

1. **migration 080**：`quote_line_items.work_order_id` → nullable（明細改以 quote_id 為主）。
2. **quote_engine_service / quote_service**：create 與 add_line 接受 PC（work_order_id 選填）；version、編號依 §8-4 調整。
3. **API**：新增 `POST /problem-cards/{pcId}/quotes`（或既有 create 接 pc）；OpenAPI 重生。
4. **convert-to-work-order**：把 PC 已 accepted 報價接續綁新 WO；CR-0095 閘對齊（§8-3）。
5. **前端**：問題卡頁加「建立報價」入口（目前無）；報價編輯沿用。
6. **測試**（TDD）+ 更新 system-overview/CR-0095 流程（§8-2）+ traceability。

## 10. Risks & Rollback

- **流程衝突風險（最高）**：與既有正典「開單→報價」矛盾，若未先裁決 §8-1/§8-2 直接做，會造成 source-of-truth 漂移。
- DB 改動小（僅 line_items 鬆綁，可重套）；rollback 為 migration down + service 還原。
- 並存方案（§8-1a）回歸風險低；取代方案（§8-1b）會動 CR-0095 既有測試。

## 11. Out of Scope

- 自動估價/AI 報價（pricing 引擎自動帶價）—— 本 CR 只談「報價可從問題卡建草稿」，不含自動定價邏輯變更。
- 報價狀態機本身（draft→…→accepted）不變。

## 12. Sign-off

- [ ] 業主裁決 §8 五項（重點 §8-1 取代/並存、§8-2 正典）
- [ ] 依 §9 實作
- [ ] 更新流程文件 + traceability + 測試
