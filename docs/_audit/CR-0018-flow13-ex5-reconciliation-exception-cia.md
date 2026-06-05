---
title: CR-0018 — Flow 13 帳款異常 EX5 CIA
date: 2026-06-05
status: open-awaiting-decisions
tier: 4
blocks: [Flow 13 last 50%]
---

# CR-0018 — Flow 13 帳款異常 EX5（Reconciliation Exception）CIA

## 1. 動機

Flow 12-14 deep audit（[`docs/_audit/flow-12-14-deep-audit.md`](flow-12-14-deep-audit.md)）取證確認 Flow 13 真實狀態 50%：reconciliation 正常流（CSM → ops_manager dual-sign，Track B S2）與 disputes_v2 客訴流均 100% 落地，但 **EX5 例外流**（帳款金額不符 / 缺單 / 雙簽超時 / 對帳差異無對應 invoice）**無獨立 endpoint**，admin 只能手動進 disputes 介面繞道處理。

EX5 異常與 dispute 性質不同：
- dispute 是「兩造爭執」需仲裁，狀態機 filed → in_review → resolved/escalated/closed_withdrawn
- EX5 是「帳務技術錯誤」需 ops 補單 / 註銷 / 衝銷，無消費者參與

不開立獨立例外流 → admin 借用 disputes 表會污染 dispute 統計與分析（business OKR 看不到「異常」與「客訴」差別）。

## 2. 範圍

**In scope**：EX5 異常 endpoint 設計 + 狀態機 + 補單/註銷/衝銷三路徑。

**Out of scope**：
- reconciliation 正常雙簽流（Track B S2 已 100%）
- dispute 客訴流（Track B S2 disputes_v2 已 100%）
- voucher 紅字沖銷機制本身（Track B S7 已 100%，本 CR 將 leverage）

## 3. 取證

### 3.1 ✅ 既有資源

- `api/services/reconciliation_service.py` 雙簽流（CSM→ops_manager co-sign） 100%
- `api/services/dispute_v2_service.py` 客訴流狀態機 100%
- `api/services/voucher_service.py` 紅字沖銷 + hash chain 100%（ADR-VCH-001/002）
- `reconciliations` 表 schema 含 status / approver / amount_match 欄位
- audit_log_service 通用 audit pattern

### 3.2 ❌ EX5 例外路徑 0%

```
grep -rn "reconciliation_exception\|recon_exception\|account_exception\|EX5" api/ 2>/dev/null
# → 全空
```

無 reconciliation_exceptions 表 / endpoint / service / state machine。

### 3.3 業務場景觸發點

| 觸發場景 | 偵測點 | 目前處置 |
|---|---|---|
| 銀行對帳金額 ≠ invoice 金額 | reconciliation 上傳對帳檔時 | 拒收上傳檔（缺乏柔性處理） |
| 對帳檔有 invoice_id 但 invoice 不存在 | 同上 | 同上 |
| 對帳檔金額有但 invoice_id 為空 | 同上 | 同上 |
| 雙簽超時（24h CSM 未簽） | 無自動偵測 | 無 |
| recon 已 approved 但發現後查金額錯 | 無 unwind 機制 | 走 voucher 紅字沖銷？ — 需 endpoint |

## 4. Human Decisions Required

### HD-1 — EX5 表獨立 vs 共用 disputes

| 選項 | 優點 | 缺點 |
|---|---|---|
| (a) 新建 `reconciliation_exceptions` 表 + 獨立狀態機 | 業務語意清晰；OKR 報表 dispute / exception 分離 | 多一張表；多一組 endpoint |
| (b) 共用 disputes 表加 `dispute_kind` 欄位區分 | 重用 dispute 狀態機；少一張表 | 污染 dispute 統計；reopen 邏輯耦合 |
| (c) reconciliations 表內加 exception 欄位 + 自己跑狀態機 | 最簡 | 表責任不純；reconciliation 不該管異常生命週期 |

**建議**：(a) — 業務上 dispute / exception 是兩件事，OKR 看「客訴率」和「對帳異常率」要分開。

### HD-2 — 例外狀態機

| 選項 |
|---|
| (a) `detected → assigned → resolved` 三態（最小）|
| (b) `detected → ops_review → fix_proposed → fix_approved → applied → closed` 六態 |
| (c) `detected → reproduce → root_cause → fix → verify → closed` 六態（incident style）|

**建議**：(b) — 六態符合金融 reconciliation 行業慣例 + 對 audit 友善。

### HD-3 — 三路徑（補單 / 註銷 / 衝銷）

EX5 修正路徑：
1. **補單**：缺 invoice → 補建 invoice 補進 reconciliation
2. **註銷**：對帳檔錯誤項 → reconciliation 該行標 void（要 audit）
3. **衝銷**：已 approved 的 recon 發現金額錯 → 走 voucher 紅字沖銷 → 重新 reconciliation

| 選項 |
|---|
| (a) 一個 endpoint 帶 path enum |
| (b) 三個獨立 endpoint |
| (c) 路徑 1+2 共用 endpoint，路徑 3 走 voucher_service 既有 reverse |

**建議**：(c) — 路徑 3 重用 voucher 已成熟機制（ADR-VCH-001/002 hash chain），路徑 1+2 是 ops 補資料純 CRUD。

### HD-4 — SoD 雙簽要求

EX5 修正涉及金額 — 是否仍要雙簽？

| 選項 |
|---|
| (a) 一律雙簽（CSM 提議 + ops_manager 核准）— 對齊 reconciliation |
| (b) 補單路徑單簽，註銷/衝銷雙簽 |
| (c) 全部單簽 — 信賴 ops 角色 |

**建議**：(a) — 對齊既有 reconciliation 雙簽防錯。

### HD-5 — 觸發偵測時機

| 選項 |
|---|
| (a) reconciliation upload 時即時偵測（即時拒收 + 寫 exception row）|
| (b) Cron 跑差異對帳 (e.g. daily 02:00) 寫 exception |
| (c) 雙保險 (a)+(b) |

**建議**：(c) — 即時偵測解 upload-time UX，cron 兜底 catch 漏網之魚。

## 5. 不立即 BUILD 的理由

- HD-1 表結構決議差異大（新建 / 共用 / 內嵌）影響後續 BUILD 範圍 5x
- HD-2 狀態機選擇直接影響 endpoint 數量（3 vs 6 endpoints）
- HD-3 路徑 3 衝銷涉 voucher reverse 已有機制 — 確認重用方式需業主確認 audit trail 連動
- HD-5 即時 vs cron 偵測涉新 background job 部署

非業主拍板皆不可推進方向。

## 6. 推薦立場

- HD-1=(a) 新表 reconciliation_exceptions
- HD-2=(b) 六態 detected→ops_review→fix_proposed→fix_approved→applied→closed
- HD-3=(c) 補單/註銷單 endpoint + 衝銷走 voucher reverse
- HD-4=(a) 雙簽對齊 reconciliation
- HD-5=(c) 雙保險

預估 BUILD 5-7 day（schema migration + 6 態狀態機 + 2 endpoint + voucher reverse 整合 + cron job + e2e test）。

## 7. 依賴

- 解凍：Flow 13 (50%→100%)
- 鏡像：reconciliation_v2 + voucher_void 既有機制（Track B S2/S7）
- 相鄰：CR-0011 / CR-0012 金流流（如業主決議金流 provider 後，EX5 觸發場景可能變）

## 8. status

`open-awaiting-decisions` — 等 5 HD 業主裁決後切 CR-0018-BUILD。
