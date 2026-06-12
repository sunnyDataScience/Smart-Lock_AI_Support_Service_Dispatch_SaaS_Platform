---
id: CR-0020
title: "公單 ID 改地區縮寫前綴 + 流水號（Change Impact Analysis）"
status: draft
tier: 4-exploration
owner: HYBRID
created: 2026-06-12
target-release: Phase 8 上線前
product-version: null
supersedes: null
superseded-by: null
---

# CR-0020: 公單 ID 改地區縮寫前綴 + 流水號

> **Tier**: 4-exploration → Change Impact Analysis（per-change，實作後歸檔）
> **Mandated by**: `.claude/rules/change-governance.md`（觸發面向：Domain model / DB schema / Architecture boundary）
> 🛑 §8 未全部裁決前，不得動 code。

---

## 1. Change Statement

**As-is**：
- 單據編號走統一 DB 函式 `generate_doc_number(prefix, seq)`（`SQL/Schema_doc_numbering.sql`），格式 **`{類型前綴}-{YYYYMMDD}-{4碼流水}`**（如 `ST-20260612-0042`）。前綴語意 = **文件類型**（ST=ServiceTicket / WO=WorkOrder / RM=RefundMemo / WC=WarrantyClaim / SOP）。
- 對話 intake 時生成 `ST-…`（`conversation_service.py:227`，用 `doc_seq_st`）。
- **`work_orders.document_number` 目前 83 筆全 NULL**——工單根本還沒在發號（`doc_seq_wo` 已存在但無人呼叫）。

**To-be**（業主 Sunny 2026-06-12 裁決）：
- 公單 ID 改 **`{2碼地區縮寫}-{流水號}`**（如 `XX-XXXXXX`）。去掉日期與類型字母前綴，前綴改為**服務地區**。

**Driver**：2026-06-10 lock-AI 會議 Action #8 + 決議 #10。Sunny 2026-06-12 拍板格式。

> ⚠️ **立場分歧（治理留痕）**：會議記錄中 **啟恆明確主張「ID 不放英文字母、留純流水號」並否決 Irene 的地區前綴**；Sunny 本次裁決改採**地區縮寫前綴**，覆蓋啟恆立場。實作前建議讓啟恆知悉此覆蓋，避免日後混淆。

---

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| Flow S2（AI→客服→派工→工單）| Modified | 工單建立階段新增「依地區發公單號」步驟（地址此時已知）|
| Flow S1（LINE intake）| Clarify | 對話 `ST-` 號是否一併改？（見 §8-Q1：公單 = WO 號 還是 ST 號）|

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| 公單編號規則（新）| New | `{region}-{serial}` 格式、地區碼來源、流水號範圍 |
| FR-0041（customer-site-device）| Check | 地址→地區碼解析可能複用既有 site/地址欄位 |

## 4. Affected API

| API | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| Work Order 系列 | `GET /tenants/{tid}/work-orders`、`/work-orders/{id}` | Response 值變化 | No | `document_number` 欄位 model 已存在（`constr(max_length=30)`）;由全 NULL → 有值。前端 sop-drafts 已有顯示 document_number 的慣例 |
| OpenAPI | `docs/architecture/api/openapi.yaml` | Doc | No | document_number 欄位描述需更新格式說明 |

> `constr(max_length=30)` 容得下 `XX-XXXXXX`;但若流水號會超過 6 位需確認上限。

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `generate_doc_number()` 函式 | **格式衝突** | 現函式硬寫 `{prefix}-{YYYYMMDD}-{LPAD4}`;地區前綴 + 去日期 + 6 碼 → 需新函式或改寫（見 §7 ADR）|
| sequences | New/Reuse | 全域單一序列 vs per-region 序列（§8-Q4）|
| `work_orders.document_number` | Backfill | 83 筆現存 NULL 要不要回填地區號？回填需要每筆的地址→地區碼 |
| 既有 `ST-…` 對話號 | Decide | 是否改格式 / 是否動既有資料（§8-Q1, Q5）|
| 地區碼對應表 | New | 縣市 → 2 碼 的對應（台北 TP / 新北 NT / 桃園 TY / …）需定義為設定或常數表 |

## 6. Affected Test

| Test | Action | Description |
|---|---|---|
| `api/tests/test_doc_numbering`（若無則新增）| New | 地區前綴格式、流水遞增、地址缺地區的 fallback |
| work_order 建立測試 | Update | 斷言建立後 document_number 符合 `^[A-Z]{2}-\d+$` |
| 前端 work-orders E2E | Update | 列表/詳情顯示公單號 |

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| 編號前綴語意 | **衝突** | 現方案前綴 = 文件類型（ST/WO/RM/WC/SOP，用於區分單據種類）。改成地區後，**無法再從前綴分辨服務單/工單/退款單**。需 ADR 決定：是否保留「類型」在別處、或接受地區前綴只用於工單 |
| 生成時機 | Move | `ST-` 在對話 intent 生成（無地址）;地區號需地址 → 必須移到**工單建立**時生成 |
| New ADR? | **Yes** | `ADR-NNNN`：document numbering 從「類型前綴」改「地區前綴」的取捨 + 地區碼對應來源 |
| 地址→地區解析 | New | 從 `work_orders.customer_address` 解析縣市;台灣地址格式不一,需 robust 解析 + fallback |

## 8. Human Decisions Required

🛑 **每列都要有裁決才動 code。**

| # | 問題 | 選項 | Owner | Status | 建議 |
|---|---|---|---|---|---|
| 1 | 「公單」指哪個號？ | (a) 工單 WO 號（work_orders.document_number，現全 NULL）(b) 對話 ST 號 (c) 兩者都改 | Sunny/啟恆 | open | **(a)** — 「公單」= 工單;ST 是服務單(對話)層,且地區號需工單階段才有地址 |
| 2 | 地區碼對應表 | (a) 台灣縣市標準 2 碼（TP/NT/TY/TC/TN/KH/KL/HC…）(b) 自訂 (c) 用服務區設定檔 | 啟恆 | open | (a) 給一版標準表;地址解析不到 → fallback `ZZ` 或 `00` |
| 3 | 生成時機 | (a) 工單建立時 (b) 派工時 | 啟恆 | open | **(a)** 建立時(地址已具備) |
| 4 | 流水號範圍 | (a) 全域單一序列 (b) per-region 序列 (c) per-region per-year | Sunny | open | (b) per-region（同地區連號,口語溝通直覺）|
| 5 | 既有資料 | (a) 不回填(只新單發號) (b) 回填 83 筆現有工單 | 啟恆 | open | (a) demo 可只新單發;要好看再回填 |
| 6 | 類型前綴語意衝突 | (a) 地區前綴只用工單,其他單據(RM/WC/SOP)維持類型前綴 (b) 全面改地區 | 架構 | open | (a) 範圍限工單,降衝擊 |
| 7 | 流水號位數 | (a) 6 碼(XX-000001) (b) 不補零遞增 | Sunny | open | (a) 6 碼補零;`max_length=30` 容得下 |

## 9. Suggested Implementation Order（§8 裁決後）

1. **ADR** → 記錄 §8 裁決（前綴語意改變 + 地區碼來源 + 生成時機）
2. **地區碼對應** → 常數表 / 設定（縣市→2碼 + fallback）
3. **DB** → 新增地區感知的編號函式（或 app 層生成）+ per-region sequence（依 Q4）
4. **Domain/Service** → 工單建立流程接「依 customer_address 解析地區 → 發號」
5. **Backfill**（若 Q5=b）→ 一次性 script 回填現有工單
6. **API/OpenAPI** → 更新 document_number 格式描述
7. **Tests** → 編號格式 + 遞增 + fallback + 工單建立斷言
8. **前端** → work-orders 列表/詳情顯示公單號（複用 sop-drafts 的 document_number 顯示慣例）
9. **Seed** → realistic_demo_seed 為工單發地區號（對齊新格式）
10. **Docs sync** → CHANGELOG + 完成度文件;traceability 若正式化為 FR 則重生

## 10. Risks & Rollback

- **風險**：地址解析不到地區 → 號碼 fallback 不一致;台灣地址格式雜需 robust 解析。
- **風險**：前綴語意從類型改地區,若未限範圍(Q6=b)會讓既有 RM/WC/SOP 號意義混亂。
- **Rollback**：新單發號為 additive(work_orders.document_number 本來就 NULL),不回填(Q5=a)時 rollback = 停止發號,既有資料不受影響。
- **DB 函式**：保留舊 `generate_doc_number`(ST/RM/WC/SOP 仍用),新增地區版,降低 blast radius。
