---
title: F-flow Production Code Disconnect Scan（全盤掃描）
phase: AUDIT
status: IN PROGRESS — Phase 2 Pass 1 完成
last_updated: 2026-05-09
owners: [Sunny, Tech Lead]
related:
  - "[[_flows-bdd-test/_SSOT-alignment-matrix]]"
  - "[[_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness]]"
  - "[[02-design/specs/openapi]]"
trigger:
  - PR f3a5f69 (F-002 production blocker 修補) 揭露 silent gap pattern
  - User 5/9 16:04 拍板：全 23 條 + Playwright + 一次衝完
---

# F-Flow Production Code 斷鏈全盤掃描

## 1. 動機

PR `f3a5f69` 修補 F-002「客服審 PC → 開 WO」時，三層驗證發現：
- Frontend 假設按確認問題卡 → 後端自動建 WO
- Backend `confirm_card()` 只 UPDATE PC.status，不建 WO
- `work_order_service` 無 `create_*` 函式
- Production code 0 處 `INSERT INTO work_orders`（只在 4 個 test + 1 seed）

**Dev 因 seed data 看似 work；production 第一筆 confirmed PC 就會孤立**。

擔心其他 23 條 user flow 同樣有 silent gap → 啟動全盤掃描。

## 2. 斷鏈型態分類

| 型態 | 描述 | F-002 案例 | 偵測方式 |
|------|------|-----------|---------|
| **G1** | Service 函式名 ≠ 實際行為 | `confirm_card()` 不觸發任何 downstream | code review |
| **G2** | Frontend 假設 backend 自動做 X，實際沒做 | UI 沒「開單」按鈕，假設 confirm 自動建 WO | E2E test |
| **G3** | OpenAPI 列了 operationId，router 沒實作 | wiring matrix 列 `convertToWorkOrder` 但 code 沒 | grep operationId |
| **G4** | Router 實作了，但 service 缺對應 function | router 連到的 service 函式不存在 | router → service 圖 |
| **G5** | Service 應 publish WS event，沒 publish | 派工狀態變但 frontend 不更新 | grep `_publish_and_return` |
| **G6** | 應觸發 SQL trigger / outbox，沒設定 | PC.status=confirmed 應有 LISTEN/NOTIFY | inspect `CREATE TRIGGER` |
| **G7** | INSERT path 只在 test/seed，prod 0 處 | `INSERT INTO work_orders` 0 處 | grep INSERT 篩除 test/seed |
| **G8** | Dev seed 掩蓋 missing flow | seed 直接給 WO，整條 PC→WO 斷鏈不顯露 | fresh DB E2E |

## 3. 範圍與時程（5/9 拍板）

- **範圍**: 全 23 條 user flow（F-001~F-023）
- **驗證深度**: API E2E + Playwright frontend E2E（雙驗證）
- **時程**: 一次衝完（重点週）
- **Phase 流**: Phase 1 + Phase 2 同步走

## 4. Phase 2 Static Scan — Pass 1 結果（5/9 16:10）

### 4.1 G3 — OpenAPI operationId vs router

| 項 | 結果 |
|---|------|
| Spec 列 operationId | 106 |
| Router 實作 operation_id | 125 |
| **spec 有但 router 缺** | **0** ✅ |
| **router 有但 spec 缺**（reverse orphan）| **19** ⚠️ |

**19 reverse orphans** — code 有 op 但 spec 沒列，frontend 無 typed 存取：

```
approveScheduleRequest, cancelScheduleRequest, confirmCustomerReschedule,
createLeaveRequest, createStandbyRequest, getMedia, getMySchedule,
listMediaForDispute, listMediaForWorkOrder, listScheduleRequests,
listWorkOrderEvents, recordDelay, recordDoorCheck, recordMaterialRequest,
recordScopeChange, rejectCustomerReschedule, rejectScheduleRequest,
submitDisputeDecision, uploadMedia
```

**Severity**: Medium — 不是 production blocker，但 frontend 用這些 API 必須手寫 type 不享 typed safety；spec 與 code 不一致也影響 mock 與 contract test。

**對應 user flow**:
- 5 個改期/排班相關（F-010 / F-005）— 已透過 router 直接接，frontend 應已能呼叫
- 4 個 schedule/leave 相關（V2.0 技師排班，可能未在 23 條 user flow 內）
- 4 個 media（F-006 拍照、F-008 scope-change media）
- 4 個 work_order 子流程事件（F-007 material / F-008 scope / F-006 door check / F-010 delay）
- 2 個 cross-cutting（disputes / customer reschedule）

**修補建議**：批次補 OpenAPI spec，每個 op 加 5-10 行 yaml；不阻塞 production，可獨立排程。

### 4.2 G7 — Production INSERT path 缺口

掃 16 個關鍵業務表：

| Table | Prod INSERT | Test/Seed | 對應 user flow | 評等 |
|-------|------------|-----------|--------------|------|
| `problem_cards` | 1 | 6 | F-001/F-002 | 🟢 |
| `work_orders` | 1 | 5 | F-002 ~ F-016 | 🟢 (本 PR 補) |
| `users` | 2 | 6 | cross-cutting | 🟢 |
| `user_facts` | 1 | 0 | F-002 profile | 🟢 |
| `technicians` | 1 | 2 | F-005 ~ F-010 | 🟢 |
| `case_entries` | 2 | 0 | F-001 RAG L1 / F-017 | 🟢 |
| **`conversations`** | **0** | 6 | **F-001 LINE 報修** | **🔴 P0** |
| **`refund_requests`** | **0** | 2 | **F-014 退款流程** | **🔴 P0** |
| **`warranty_claims`** | **0** | 1 | **F-015 保固申訴** | **🔴 P0** |
| **`sop_drafts`** | **0** | 1 | **F-017 SOP 草稿審核** | **🔴 P0** |
| `dispute_cases` | 0 | 0 | F-013 對帳爭議 | ⚪ 無 INSERT 路徑（疑似表不存在）|
| `scope_changes` | 0 | 0 | F-008 | ⚪ |
| `material_requests` | 0 | 0 | F-007 | ⚪ |
| `reschedule_requests` | 0 | 0 | F-010 | ⚪ |
| `audit_logs` | 0 | 0 | F-020 | ⚪ |
| `role_definitions` | 0 | 0 | F-019 | ⚪ |

⚪ 待 verify：可能表名不同或不存在於 schema，需 cross-check `SQL/Schema*.sql`。

### 4.3 G7 — 4 個 P0 candidates 細節

#### **C-001: `conversations` 表無 production INSERT** 🔴

對應 **F-001 LINE 報修 → ProblemCard**。

驗證：
```bash
$ rg "INSERT INTO conversations" agent/ api/ data/
# 0 hits in production code
$ rg "FROM conversations" api/services/ | head
api/services/kpi_service.py: SELECT COUNT(*) FROM conversations c
api/services/customer_service.py: ...
api/services/conversation_service.py: ...
# Read-only — 純 SELECT
```

**潛在風險**：LINE webhook 進來，agent module 應建 conversation record，但 production 無任何 INSERT 路徑。可能：
- Agent 用 LangGraph postgres checkpointer，記錄在 `checkpoints` 表而非 `conversations`
- `conversations` 表是 admin dashboard 看的「對話列表」view，由 agent 旁路另寫
- 真的斷裂（production 完全沒建 conversation record）

**Deep verify 待做**：trace agent webhook → DB 寫入路徑。

#### **C-002: `refund_requests` 表無 production INSERT** 🔴

對應 **F-014 退款流程**。

驗證：
```bash
$ rg "INSERT INTO refund_requests" api/ agent/
# 0 hits
$ rg "(SELECT|UPDATE) .* refund_requests" api/services/refund_service.py | head
SELECT ... FROM refund_requests r ...
UPDATE refund_requests SET ...
# 只有讀 + 改 status，沒「建立退款請求」path
```

**潛在風險**：客服在 `/admin/refunds` page 按「審核」按鈕呼 `submitRefundDecision`，但 refund 從哪來？只能透過 SQL seed 灌入，production 客戶申請退款無路徑。

**Deep verify 待做**：look at `web/src/app/admin/refunds/page.tsx` — 是否依賴 mock data；確認預期建立路徑（消費者 LINE 申請？客服代建？）。

#### **C-003: `warranty_claims` 表無 production INSERT** 🔴

對應 **F-015 保固申訴**。

驗證：
```bash
$ rg "INSERT INTO warranty_claims" api/ agent/
# 0 hits
$ rg "(SELECT|UPDATE) .* warranty_claims" api/services/warranty_service.py | head
FROM warranty_claims w
UPDATE warranty_claims SET ...
```

**Deep verify 待做**：F-015 SSOT 標 ✅ aligned「warranty-dispute spec 已有」，spec 有但建立路徑不存在 — 同 F-002 pattern。

#### **C-004: `sop_drafts` 表無 production INSERT** 🔴

對應 **F-017 SOP 草稿審核**。

驗證：
```bash
$ rg "INSERT INTO sop_drafts" api/ agent/ data/
# 0 hits
$ rg "FROM sop_drafts" api/services/
api/services/family_review_service.py: ...
api/services/sop_draft_service.py: ...
# 只讀
```

**Deep verify 待做**：SOP 應由 AI agent 自動產出（F-104 自進化知識庫），檢查 agent harness 是否有產生 SOP draft 入庫的路徑。可能是 outbox / 異步 job 而非直接 INSERT。

### 4.4 5 個 ⚪ 表 — 待驗證

`dispute_cases / scope_changes / material_requests / reschedule_requests / audit_logs / role_definitions` —
不確定表是否存在或表名不同。需 cross-check SQL schema 全檔。

下一步：grep `CREATE TABLE` 全部，比對。

## 5. Phase 1 Inventory — 23 條 chain 文件（待產出）

下一步：dispatch 3 個 Explore subagent 平行處理 V1.0 (F-001~F-018)：
- Agent A: F-001 ~ F-006（LINE/PC/派工/技師接單前段）
- Agent B: F-007 ~ F-012（材料/scope/簽名/改約/付款/撥款）
- Agent C: F-013 ~ F-018（對帳/退款/保固/SLA/SOP/接管）

V2.0 (F-019~F-023) 等核心做完再 dispatch（避免一次 explore 範圍爆）。

每條 flow 產出：
```
F-XXX: <flow name>
  Frontend trigger: <button or webhook>
  → API: <operationId>
  → Service: <module.function>
  → DB writes: <table>.<columns>
  → Side effects: <WS publish / outbox / next flow trigger>
  → Verification: <expected DB state>
  Status: 🟢 verified / 🟡 partial / 🔴 broken
```

## 6. Severity 統計（Phase 2 Pass 1 後）

```
🔴 P0 production blocker  : 4 (待 deep verify) + 1 (F-002 已修)
🟡 P1 contract drift      : 19 (G3 reverse orphan)
⚪ Pending verify          : 5 (G7 表名待對)
🟢 OK                      : 6 (G7 表有 prod path)
```

## 7. Phase 2 Deep Verify — Pass 2 結果（5/9 16:30）

### 7.1 4 個 P0 candidates 全 confirmed（非 grep 假陽性）

#### C-001 `conversations` — F-001 LINE 報修 → ProblemCard

**結論：Production 完全斷鏈**。

- `agent/` 全模組沒有任何 raw SQL INSERT/UPDATE/DELETE（已在 profiles/storage 確認）
- agent 用 LangGraph checkpointer 寫到 `checkpoints` / `checkpoint_writes` 表（managed by langgraph）
- agent **完全不寫 `conversations` 表**
- agent 與 admin API 之間**只有一個 bridge**：F-010 reschedule postback (`agent/app.py:291-340`) 會 POST `/api/v1/work-orders/{id}/reschedule/customer-confirm`
- 其他 22 條 user flow 都沒有 agent → admin API 的橋接

**API 層**：
- `createConversation` operationId **不存在於 OpenAPI**
- `conversation_service.py` 全 functions：`list_conversations` / `get_conversation` / `list_messages` / `send_message` — **沒有 `create_conversation`**
- 0 處 production INSERT INTO conversations

**衝擊**：admin dashboard 看到的 conversations / messages 全靠 SQL seed；production 環境消費者透過 LINE 互動，所有對話資料都在 LangGraph checkpoint，admin 看不到。

#### C-002 `refund_requests` — F-014 退款流程

**結論：spec 缺「建立退款」endpoint**。

- spec 只有 3 個 ops：`listRefundRequests` / `getRefundRequest` / `submitRefundDecision`
- **沒有 `createRefundRequest`** 或類似的 endpoint
- Web `/admin/refunds/page.tsx` 用 GET + submitDecision，但**從沒「建立退款」按鈕**
- 客服只能對既存 refund 做 approve/reject，沒有任何方式建立 refund_requests row
- 消費者在 LINE 申請退款（如有此 flow）—— 0 個 production path 對應

**衝擊**：`/admin/refunds` page 永遠空白；F-014 流程「退款申請」這步在 production 沒入口。

#### C-003 `warranty_claims` — F-015 保固申訴

**結論：同 refund pattern — spec 缺 `createWarrantyClaim`**。

- spec 只有 `listWarrantyClaims` / `getWarrantyClaim` / `submitWarrantyDecision`
- 客服只能審核既存申訴
- 消費者透過 LINE 申訴的 path 不存在

**衝擊**：F-015「保固爭議」隨 SSOT 標 ✅ aligned「warranty-dispute spec 已有」是錯的 — spec 有但建立路徑不存在。

#### C-004 `sop_drafts` — F-017 SOP 自進化

**結論：自進化機制完全沒實作**。

- agent/harness 提到 SOP 都是註解（`load_skill` behavior reference）
- data pipeline `data/pipeline/silver_to_skill/` 0 處 INSERT sop_drafts
- F-104 BDD「自進化知識庫」spec 有，模組 5 SOPGenerator 規格存在，但**production code 0 處實作**
- Web `/knowledge-base/sop-drafts` 永遠空清單

### 7.2 Zoom-out 觀察 — 系統性 pattern

整個系統的 admin-side 表「create」端 endpoint 缺失：

| Flow | Create endpoint 存在？ | Status mutation endpoint 存在？ |
|------|--------------------|-----------------------------|
| F-001 conversation | ❌ `createConversation` 不存在 | ✅ status update |
| F-001 problem_card | ✅ `createProblemCard` 存在但無人呼叫（agent 不呼）| ✅ confirm/resolve |
| F-002 work_order | ✅ `convertToWorkOrder`（**本 PR 5/9 14:00 補**）| ✅ assign/accept/complete |
| F-014 refund | ❌ `createRefundRequest` 不存在 | ✅ submitDecision |
| F-015 warranty | ❌ `createWarrantyClaim` 不存在 | ✅ submitDecision |
| F-017 sop_draft | ❌ `createSopDraft` 不存在（自進化機制應自動產出）| ✅ review/adopt |

**模式**：spec 與 implementation 圍繞「客服管理已存在的記錄」設計，但**忽略了「記錄怎麼進來」**。`createProblemCard` 有但無人呼，`convertToWorkOrder` 5/9 補上 — 其他都缺。

### 7.3 系統架構真相

**System is essentially two disconnected halves**：

```
   ┌─ Agent (LangGraph) ─────────────┐         ┌─ Admin API + Web ────────┐
   │  • LINE webhook                  │         │  • REST API on :8001     │
   │  • LangGraph checkpoints (DB)    │         │  • SELECT conversations  │
   │  • profiles/user_facts (SCD)     │   ❌    │  • SELECT problem_cards  │
   │  • storage/audit_logs            │  bridge │  • SELECT work_orders    │
   │  • notifications/ (V1.5+)        │         │  • SELECT refund / etc.  │
   │                                  │         │  • Web dashboard         │
   └─ 0 INSERT to admin-side tables ──┘         └──────────────────────────┘
                  │
                  └── 唯一橋: F-010 reschedule postback
                              (agent → POST /work-orders/{id}/reschedule/customer-confirm)
```

**Dev 環境靠 SQL seed 把 admin tables 灌滿**，所以前端看似正常。**Production 第一筆 LINE 訊息**：
- agent 處理對話，寫 LangGraph checkpoint
- admin tables 永遠空白
- 沒有 PC、沒有 WO、沒有 refund／warranty／sop_draft、admin 看不到任何客戶活動

**這比 F-002 嚴重 N 倍** — F-002 是斷在中段（PC→WO），這是斷在源頭（LINE→Conversation/PC）。

### 7.4 Severity 重訂

```
🔴 P0 production blocker  : 5
   - F-001 (C-001 conversations + 連帶 PC 不會建立)
   - F-002 (✅ 已修 5/9 14:00)
   - F-014 (C-002 refund_requests 無 create endpoint)
   - F-015 (C-003 warranty_claims 無 create endpoint)
   - F-017 (C-004 sop_drafts 無自進化產出機制)

🟡 P1 contract drift      : 19 (G3 reverse orphan)
⚪ Pending verify          : 5 (G7 表名待對)
🟢 OK                      : 6 (G7 表有 prod path)
```

## 8. Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-09 16:00 | Sunny + Claude | 啟動全盤掃描；建分支 docs/audit-flow-disconnect-scan |
| 2026-05-09 16:10 | Sunny + Claude | Phase 2 Pass 1 完成：G3 + G7 自動 grep；4 個 P0 candidates 浮現（conversations / refund_requests / warranty_claims / sop_drafts）|
| 2026-05-09 16:30 | Sunny + Claude | Phase 2 Pass 2 deep verify：4 candidates 全 confirmed；發現系統性 pattern — admin-side 表「create」endpoint 全缺；agent 與 admin 之間唯一橋為 F-010 reschedule postback；P0 列表更新為 5 條（含 F-002 已修）|
