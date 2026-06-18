---
id: CR-0032
title: "Change Impact Analysis — 報價引擎收尾（quote 主表 + 核准 gate + snapshot 凍結）"
status: draft
tier: 4-exploration
owner: HYBRID
created: 2026-06-18
target-release: TBD（補洞優先）
product-version: null
supersedes: null
superseded-by: null
---

# CR-0032: 報價引擎收尾

> **Tier**: 4-exploration → CIA（per-change）
> **Mandated by**: `.claude/rules/change-governance.md`（命中 Domain model / DB schema / API contract）
> **驅動來源**: 20260617 盤點（gap-audit roadmap S2，補洞優先最痛上游）+ ERP 藍圖 M04 + esales sheet 05-08
> **🛑 本 CIA 停在 §8 等業主裁決後才動 code。**

---

## 1. Change Statement

**As-is**：CR-0027 只建了 `quote_line_items`（work_order 層成本拆項），**無報價主表/核准/版本/凍結**。報價無 approval gate、無訂金 enforcement、無有效期自動過期（BR-M04-05 14d/3d）、internal vs customer 報價分離不完整、`is_mock` 無覆核 workflow。

**To-be**：完整報價引擎 —— `saas.quote` 主表（狀態機 + 版本鏈）+ `quote_approval`（核准 gate）+ `pricing_rule_snapshot`（customer_sent 時凍結價格規則，append-only）+ `quote_adjustment` + `quote_customer_summary`（客戶可見 view）+ 欄位級 RBAC（成本僅後台）。

**Driver**：藍圖 M04「AI 可給 range、不可 final price；報價 gate = ProblemCard clear + evidence + customer confirm」；金流（S5）與報價主檔（S4）的上游依賴。

## 2. Affected Flow / 3. Spec

| ID | Action | Description |
|---|---|---|
| `BF` 報價→確認→付款 gate | New/Modified | Inquiry→PC→Internal Quote→Customer Confirm→Payment Gate（藍圖 Q009）|
| `FR` 報價核准規則 | New | 高金額/特定服務需主管核准；AI 只能 draft/range（M04 Q021）|
| `FR` 報價有效期 | New | BR-M04-05：14d 一般 / 3d 急件，過期自動失效 |

## 4. Affected API

| API | Endpoint | Action |
|---|---|---|
| quote CRUD | `POST/GET/PATCH .../work-orders/{id}/quote` | New（含 internal 成本，RBAC）|
| quote 送客戶 | `POST .../quotes/{id}:send`（凍結 snapshot + mint customer view）| New |
| quote 核准 | `POST .../quotes/{id}:approve`（gate）| New |
| customer 報價查看 | `GET /consumer/quotes/{token}`（只露 customer 金額）| New（複用 public_token）|

## 5. Affected Data

| Entity | Action |
|---|---|
| `saas.quote`（新主表）| pc_id / work_order_id / version / state(draft→pending_approval→approved→sent→accepted→expired→superseded) / total / deposit_required / expiry_at / snapshot_hash / supersedes_quote_id |
| `quote_line_items`（CR-0027 既有）| 加 quote_id FK（從 work_order 層升為 quote 層）|
| `quote_approval`（新）| quote_id / approver / decision / threshold_reason |
| `pricing_rule_snapshot`（新，append-only）| 送客戶當下凍結的價格規則 JSON + hash |

State machine：quote `draft → pending_approval → approved → sent → accepted | expired | superseded`。

## 6. Affected Test

quote 狀態機轉換；核准 gate（超門檻擋）；14d/3d 過期；snapshot 凍結後改規則不影響已送報價；RBAC 客戶看不到成本；customer view 只露最終價。

## 7. Affected Architecture

| Concern | Notes |
|---|---|
| 新 ADR？ | **Yes** — 報價快照不可變（snapshot_hash append-only）+ 報價狀態機 |
| 複用 | CR-0027 quote_line_items / public_token / RBAC `_COST_VISIBLE_ROLES` / work_order_document_service |
| Multi-tenant | tenant_id 預留（saas.* 慣例）|

## 8. Human Decisions Required

🛑 **CIA blocks code until decided（部分綁 esales sheet 13 Q-01~Q-12，須與 S4 報價主檔一起裁）。**

| # | Question | Options | Owner | Status |
|---|---|---|---|---|
| 1 | **報價核准門檻**：哪些需主管核准？(金額上限/特定服務/折扣%) | (a) 金額門檻 (b) 服務類別 (c) 都要 | 業主 | open |
| 2 | **訂金規則**：固定金額 vs 比例？門檻？（esales Q-08）| (a) 比例 (b) 固定 (c) 取高 | 業主 | open |
| 3 | **有效期**：採 BR-M04-05 的 14d/3d 還是另定？ | (a) 14d/3d (b) 自訂 | 業主 | open |
| 4 | **AI 報價權限**：AI draft/range 上限金額？哪些固定價可免核（藍圖：新機安裝）| (a) 全需真人 (b) 固定價免核 | 業主 | open |
| 5 | **稅務**：報價含稅 vs 未稅？（esales Q-07）| (a) 含稅 (b) 未稅 | 業主/會計 | open |
| 6 | **與 S4 主檔依賴**：報價引擎可先用 mock 主檔上線，還是等 S4 service_catalog seed？ | (a) 先 mock (b) 等 S4 | 業主/架構 | open |

## 9. Suggested Implementation Order（§8 裁決後）

1. ADR：報價快照不可變 + 狀態機
2. migration：saas.quote + quote_approval + pricing_rule_snapshot + quote_line_items.quote_id
3. quote_service：狀態機 + 核准 gate + 過期 + snapshot 凍結
4. API：quote CRUD / send / approve + consumer view
5. Tests（TDD）
6. UI：後台報價編輯（成本 RBAC）+ 客戶報價查看
7. Traceability / docs sync

## 10. Risks & Rollback

| Risk | Mitigation |
|---|---|
| esales 數值不可信當正式價 | 主檔走 S4 業主決策；本 CR 結構先行、數值 mock 待覆核 |
| 報價送出後價格被改 | snapshot 凍結（append-only hash chain）|
| 核准 gate 擋住正常流程 | 門檻可配置（M18 config）；§8-Q1 裁決 |

**Rollback**：新表 + 新端點，可逆；quote_line_items.quote_id nullable 向後相容。

## 11. Out of Scope

- 報價主檔（service_catalog/material_catalog/BOM）→ **CR-0034（S4）**；金流結算 → **CR-0035（S5）**。

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product（業主）| Sunny | | 🛑 待 §8 裁決 |

## 13. 實作進度

**改採 mock-first（同 CR-0034）**：報價資料已在 esales、決議 5 授權當 mock，故結構先建、§8 門檻用 esales 草稿當預設，正式值待業主回 esales Q-01~Q-12（不卡建置）。

- ✅ **Phase A（schema + service 核心，`feat/cr-0032-quote-engine`）**：migration 041（`quote` 主表狀態機 + `quote_approval` + `pricing_rule_snapshot` append-only + `quote_line_items.quote_id`/`service_code`/`material_code`）；`quote_engine_service`（create_quote 有效期 14d/3d、add_line **從 CR-0034 catalog 帶價**、recompute total、狀態機 submit→approve→send→accept、送單**凍結 pricing snapshot + sha256 hash**、過期擋 accept、cost RBAC 遮蔽）。`test_cr_0032_quote_engine.py` 3 pass（catalog 帶價 total / 狀態機+snapshot / RBAC）+ migration 041 套 dev DB。
- ⏳ **Phase B**：API 端點（quote CRUD/submit/approve/send + consumer view）+ 後台報價編輯 UI + 客戶報價查看 + **核准門檻 enforcement**（金額/服務類別，esales Q-11）+ ADR（快照不可變）。
- ⏳ §8 正式值：核准門檻/訂金/稅務/有效期（綁 esales Q-03~Q-11）—— mock-first 不卡，待業主一次確認。
- 分支：`feat/cr-0032-quote-engine`
