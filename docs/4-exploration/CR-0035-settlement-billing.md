---
id: CR-0035
title: "Change Impact Analysis — 金流結算收尾（客戶側應收/發票 + 月結 trigger 接線）"
status: draft
tier: 4-exploration
owner: HYBRID
created: 2026-06-19
target-release: TBD（補洞優先）
product-version: null
supersedes: null
superseded-by: null
---

# CR-0035: 金流結算收尾

> **Tier**: 4-exploration → CIA（per-change）
> **Mandated by**: `.claude/rules/change-governance.md`（命中 API contract / Domain model / DB schema / External integration）
> **驅動來源**: 20260617 gap-audit roadmap S5（金流結算）+ 雙領域盤點 + 藍圖 Phase II Finance + esales sheet 13 Q-01~Q-12
> **🛑 mock-first（同 CR-0032/0034）：結構先建、數值/規則用 esales 草稿當預設標 `is_mock`，§8 正式值待業主一次裁決，不卡建置。**

---

## 1. Change Statement

**As-is**（盤點實證）：
- **技師撥款月結已做**（CR-0012 Stage 1/2）：`monthly_settlement_service`（generate_monthly_batch / CSV / 水單 mark_manual_paid）+ `monthly_settlements_v2` 5 端點 + `settlement` / `monthly_settlement_batch` 表。
- **缺口 1**：`settlements_v2 POST /tenants/{tid}/settlements/monthly` 仍回 **501 stub**（與已實作的 `monthly_settlements_v2:generate` 重複，誤導為「未做」）。
- **缺口 2（真核心）**：**客戶側帳單斷層** —— `invoices` 表存在但**只讀**（list/get，無 create path）；報價 `accepted`（CR-0032）後**無任何後續**（無 outbox、無發票、無應收）；`quote.total_amount` 與 `work_orders.customer_final_amount` 無接線。

**To-be**：報價 accepted → 開立客戶應收發票（mock-first，best-effort）；月結 trigger 501 stub 接通既有 service（CR-0012 `generate_monthly_batch`）。**不做**完整 AR 帳齡/AP 拆帳/佣金/傳票自動分錄（藍圖 Phase II + 待 esales，明確 out of scope）；**LINE 報價接受通知亦為 follow-up**（需 outbox resolver + Flex builder，CR-0028 規模，本 CR 不做）。

> **範圍邊界**：技師撥款月結的完整決策見 **CR-0012**（FR-0012，已實作 generate_monthly_batch/CSV/水單）；本 CR 只補「客戶側帳單（invoices create）+ 月結 trigger stub 接線」。

**Driver**：報價主軸（CR-0032 Phase C 已通到客戶確認）的下游 —— 客戶 accept 後需落應收，金流才閉環；月結 stub 是 audit trail 的誤導點。

## 2. Affected Flow

| ID | Action | Description |
|---|---|---|
| `BF` 報價→確認→應收 | New | 客戶 accept 報價 → best-effort 自動開立應收發票（issued）。LINE 通知=follow-up |
| `SF` 月結觸發 | Modified | `settlements/monthly` 不再 501，接 `generate_monthly_batch`（既有 CR-0012）|

## 3. Affected API

| API | Endpoint | Action |
|---|---|---|
| 月結觸發 | `POST .../settlements/monthly` | Modified（501 → 接 generate_monthly_batch）|
| 報價開發票 | `POST .../accounting/invoices:from-quote`（後台手動）| New |
| 報價 accept | （consumer `POST /consumer/quotes/{token}`，CR-0032）| 連動：accept → best-effort 開發票 + outbox |

## 4. Affected Data

| Entity | Action |
|---|---|
| `invoices`（既有，只讀）| 加 `create_from_quote` 路徑：invoice_number、amount/tax/total（稅 mock 0 待 Q-07）、line_items（客戶價，不含 unit_price）、status='issued'、work_order_id（UNIQUE + INSERT ON CONFLICT DO NOTHING 原子冪等）|
| migration 042 | invoices 加 `quote_id`（追溯來源報價，nullable 向後相容）+ `is_mock`（金額 mock 旗標）|

> **不新建**：AR 帳齡表 / 訂金二階段表 / 佣金表 / 傳票自動分錄 —— Phase II（esales Q-08/Q-09 待裁）。
> **不做**：`line_push_outbox` quote_accepted PushKind / LINE 報價接受通知 —— follow-up（需 resolver + Flex builder）。

## 5. Affected Test

invoice create_from_quote（金額/line_items 帶客戶價不含成本 / invoice_number 唯一 / work_order UNIQUE 冪等）；月結 trigger 接通（非 501）；quote accept → 發票出現 + outbox enqueue；RBAC（應收僅後台）。

## 6. Affected Architecture

| Concern | Notes |
|---|---|
| 新 ADR？ | 視需要（最小變更，複用既有 invoices/outbox/settlement）；若有「報價→應收自動開立」決策則補一筆 |
| 複用 | invoice_service（list/get + JOIN tenant 過濾）、monthly_settlement_service（generate_monthly_batch）、line_push_outbox_service、quote_engine_service.transition |
| Multi-tenant | invoices 無 tenant_id，沿 work_order→...→users.tenant_id JOIN（同 invoice_service 既有 pattern）|

## 7. Human Decisions Required（§8）

🛑 **mock-first 不卡；以下為 mock→正式的待裁清單（綁 esales sheet 13）。**

| # | Question | mock 預設 | Owner | Status |
|---|---|---|---|---|
| 1 | quote accepted → 發票**自動**開立 vs 人工確認？ | **自動**（best-effort，work_order UNIQUE 冪等）| 業主 | open |
| 2 | 訂金 deposit 二階段（訂金→尾款）優先度？ | **暫不做**（單張全額應收）| 業主 | open |
| 3 | 稅務含稅/未稅 + 稅率？（esales Q-07）| **tax=0、total=amount**（mock）| 業主/會計 | open |
| 4 | 傳票自動分錄時機 + 會計科目對應？ | **暫不做**（待 esales account mapping）| 業主/會計 | open |
| 5 | 月結 trigger 來源（GCP Scheduler vs 手動 vs in-process cron）？ | **手動 POST + internal cron header**（既有）| 業主/SRE | open |
| 6 | settlement 撥款是否需三維 SoD？ | **沿用 X-Initiator 單簽**（既有）| 業主 | open |

## 8. Suggested Implementation Order

1. migration 042：invoices 加 quote_id + is_mock（idempotent）
2. invoice_service.create_from_quote（序列號、客戶價 line_items、冪等）
3. quote_engine_service.transition(accept) → best-effort 開發票 + outbox quote_accepted
4. settlements_v2 月結 stub 接 generate_monthly_batch
5. API：POST .../accounting/invoices:from-quote（後台手動補開）
6. Tests（TDD）
7. Traceability / 三同步

## 9. Risks & Rollback

| Risk | Mitigation |
|---|---|
| esales 數值當正式價 | invoices.is_mock 旗標；正式金額/稅率走 §8 裁決 |
| accept 自動開票誤開 | work_order_id UNIQUE 冪等；best-effort try/except 不阻斷 accept |
| 月結 stub 接線破壞既有月結 | 接的是同一個已測 generate_monthly_batch；回歸 CR-0012 測試 |

**Rollback**：invoices 新欄 nullable、發票路徑新增可逆；月結 stub 還原為 501 即可。

## 10. Out of Scope

完整 AR 帳齡 / 訂金二階段 / 派工佣金 / 品牌結算 / 傳票自動分錄 → **Phase II**（esales Q-08/Q-09，另 CR）。
**LINE 報價接受通知**（outbox quote_accepted + resolver + Flex builder，CR-0028 規模）、**月結 cron 排程**（GCP Scheduler）、**settlement 三維 SoD** → follow-up（與 CHANGELOG / system-completion-status 一致）。

## 11. 實作進度

- ✅ **盤點修正**：技師撥款月結 **CR-0012 已完整做**（generate_monthly_batch / CSV / 水單 + 5 端點）；真缺口=客戶側帳單 + `settlements/monthly` 501 殼。範圍據此收斂為「報價→應收發票 + stub 接線」，完整 AR/AP/佣金/傳票明確 out of scope（Phase II）。
- ✅ **實作（`feat/cr-0035-settlement-billing`）**：
  - migration `042`：invoices 加 `quote_id`（追溯來源報價，nullable）+ `is_mock`（金額 mock 旗標）+ index（idempotent）。
  - `invoice_service.create_from_quote`：accepted 報價 → 開應收發票（invoice_number `INV-<wo8>-<rand6>`、客戶價 line_items **不含 unit_price**、稅 mock 0、status='issued'、is_mock 沿報價）；**work_order_id UNIQUE 天然冪等**（已有則回既有）；非 accepted → 409。
  - `quote_engine_service.transition(accept)` → **best-effort 開票**（catch 廣義 Exception，開票失敗不阻斷客戶接受；db autocommit 不毒化連線）。
  - `settlements_v2 POST /settlements/monthly`：**501 → 202**，接既有 `monthly_settlement_service.generate_monthly_batch`（period 預設當月，body 可指定補跑；UPSERT 冪等）。
  - API `POST .../accounting/invoices:from-quote`（後台手動補開，管理角色 `role_required` + cross-tenant guard）。
- ✅ **測試（部分）**：`test_settlements_v2_endpoint`（501→202 接通，含 period）+ `test_cr_0032_quote_engine`（accept 路徑回歸，best-effort 不破壞）9 pass。
- ⏳ **待 migration 042 套 dev DB**：`test_cr_0035_invoice_billing.py`（create_from_quote / 冪等 / 非 accepted 409 / 無成本外洩 + is_mock）—— 需新欄位，待套用後跑。
- ⏳ §8 正式值：自動開票/訂金/稅務/傳票/月結來源/SoD（綁 esales Q-07/08）—— mock-first 不卡。
- 分支：`feat/cr-0035-settlement-billing`
