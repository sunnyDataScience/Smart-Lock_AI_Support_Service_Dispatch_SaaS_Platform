---

## title: Integration Test Matrix — Cross-Module Async Flow
phase: V-MODEL RIGHT (Integration Test layer)
gate: TR5
status: Initial Content (待 SME 補充細節)
last_updated: 2026-05-07
owners: [QA Lead, Tech Lead]

# Integration Test Matrix — Cross-Module Async Flow

> **狀態**: 骨架文件（SKELETON）— 框架就位，10 channel 中 2 個有範例，其餘 8 個待補。

status: superseded
superseded_by: docs_v2/3-process/test-plan.md (appendix)
superseded_at: 2026-05-10
supersede_cr: CR-0007
---

## §0 Purpose

補齊 V-Model 右翼 **整合測試層** 的 reliability 覆蓋率（**20% → 80%**），對應：

- **ISO/IEC 25010**: Reliability（Maturity / Availability / Fault Tolerance / Recoverability）
- **ISTQB Foundation Level**: Integration Test（component integration + system integration）
- **AsyncAPI 2.6**: 10 個 channel 的訊息合約一致性

整合測試的關鍵差異於單元測試 — **不在驗證個別模組正確性**，而在驗證 **跨模組 / 跨服務 / 跨網路邊界** 的：

1. 訊息合約（envelope shape）
2. 順序保證（ordering）
3. 最終一致性（eventual consistency）
4. 失敗注入下的回復（fault tolerance）

---

## §1 Test Categories

### 1.1 Async Channel Tests

對應 `docs/02-design/specs/asyncapi.yaml` 的 10 個 channel，每個 channel 至少 1 條 `IT-NNN`。

### 1.2 Pact Contract Tests

跨信任邊界（trust boundary）的 consumer-driven contract testing：


| Consumer                   | Provider    | 邊界類型                            |
| -------------------------- | ----------- | ------------------------------- |
| tech mobile (React Native) | pool API    | external network                |
| web admin                  | api backend | internal network（同 GCP project） |
| TBD                        | TBD         | TBD                             |


### 1.3 Cross-Module State Consistency

跨模組（agent ↔ api ↔ web）共享狀態的同步測試 — 例：派工狀態變更後，三方視圖在 < 2s 內收斂。

### 1.4 Eventual Consistency Verification

非同步事件（domain events）發送 → 訂閱方收斂時間驗證；超時門檻：5s（p95）。

---

## §2 IT-NNN Matrix（per AsyncAPI Channel）


| IT-ID  | Channel                             | 觸發場景（GIVEN-WHEN）                                   | 驗證點                                                                                  | 對應 F-XXX      | Status             |
| ------ | ----------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------ | ------------- | ------------------ |
| IT-001 | `/realtime/work-orders/{id}`        | GIVEN 訂閱 WO channel WHEN API 觸發 pending → assigned | (1) envelope shape 符合 schema (2) ordering 嚴格遞增 (3) p95 推送延遲 < 1s                     | F-005 / F-016 | ⚠ TBD baseline     |
| IT-002 | `/realtime/dispatch-queue`          | GIVEN dispatcher 訂閱 queue WHEN runDispatch 成功      | `dispatch_assigned` < 500ms 內收到；`assignedTechId` 與 API 回傳一致；ordering by `created_at` | F-003 / F-004 | ⚠ TBD baseline     |
| IT-003 | `/realtime/pool/{tech_id}`          | GIVEN 技師訂閱個人 pool WHEN 系統推派新案                      | 技師端 < 1s 收到 push event；payload 含 work_order_id + customer_address；dedup by event_id  | F-005         | ⚠ TBD              |
| IT-004 | `/realtime/refunds`                 | GIVEN Manager 訂閱 refunds WHEN Director 完成第二簽       | event sequence: `refund_submitted → manager_approved → director_approved`；不可逆序       | F-013 / F-014 | ⚠ TBD              |
| IT-005 | `/realtime/disputes`                | GIVEN admin 訂閱 disputes WHEN G4 仲裁觸發               | `dispute_opened` → `dispute_resolved` event chain；含 reviewer_id 與 resolution         | F-013         | ⚠ TBD              |
| IT-006 | `/realtime/sla-alerts`              | GIVEN supervisor 訂閱 SLA WHEN WO 距派工已 > 2hr 未到場     | Soft 警報 envelope 含 `severity=red`；單一 WO 同一日去重；無賠償欄位（V1.0）                            | F-016         | ⚠ pending Q5=B     |
| IT-007 | `/realtime/rbac`                    | GIVEN admin 變更角色 WHEN updateRolePermissions 完成     | 受影響使用者於 < 2s 內收到 `role_changed`；前端 reactive 重新計算可見頁面                                 | F-019         | ⚠ TBD              |
| IT-008 | `/realtime/inventory/low-stock`     | GIVEN 倉管訂閱 WHEN 庫存扣減後低於 threshold                  | `low_stock_alert` event 含 sku + 當前庫存；同 sku 4hr 內去重                                   | F-007         | ⚠ pending F-210 規格 |
| IT-009 | `/realtime/diagnostics/{conv_id}`   | GIVEN web admin 訂閱 conversation WHEN AI 進行多輪診斷     | 每個 reasoning step 即時推送；含 step_index、tool_call、confidence                             | F-001 / F-018 | ⚠ TBD              |
| IT-010 | `/realtime/notifications/{user_id}` | GIVEN 任意 user 訂閱 WHEN 系統觸發通知（任意類型）                 | envelope shape unified；`type` 必填（system / dispatch / payment / refund）               | F-018 / F-022 | ⚠ TBD              |


**規範**：

- ID 格式：`IT-NNN`
- 每個 AsyncAPI channel 至少 1 條 IT；高風險 channel（如 dispatch / payment）至少 3 條（happy path / error / spike）
- `Status` 用語同 north-star（✅ Live / 🚧 In Dev / ⚠ TBD baseline / ❌ Deferred）

### §2.1 Pact Contract Tests（tech mobile ↔ pool boundary）


| Pact-ID  | Consumer                   | Provider                         | 互動契約                                                                                         | Status |
| -------- | -------------------------- | -------------------------------- | -------------------------------------------------------------------------------------------- | ------ |
| PACT-001 | tech mobile (React Native) | pool API `GET /pool/orders`      | response schema：order_id / customer_addr / sla_due_at；空 pool 回傳 `[]` 而非 404                  | ⚠ TBD  |
| PACT-002 | tech mobile (React Native) | pool API `POST /pool/{id}/claim` | request body：`{tech_id}`；response：`{status: claimed, work_order_id}`；併發 claim → 409 Conflict | ⚠ TBD  |


---

## §3 Tooling


| 工具                         | 用途                                                | 已建置?                                 |
| -------------------------- | ------------------------------------------------- | ------------------------------------ |
| **respx**                  | mock HTTPX requests for FastAPI integration tests | TBD                                  |
| **Pact-Python**            | consumer-driven contract（tech mobile ↔ pool）      | TBD                                  |
| **AsyncAPI parser**        | 解析 asyncapi.yaml 產生 channel test stub             | ✅ `scripts/ci/asyncapi-validate.mjs` |
| **websockets test client** | 訂閱 channel + assert envelope                      | TBD                                  |


CI 流程：每次 PR 觸發 → `asyncapi-validate.mjs`（schema 合規） → `pytest -m integration`（IT-NNN 套件）。

---

## §4 TBD — 8 Channels Pending

對應 PR #31 commit `887f252`：目前僅 2 channel（work-orders, dispatch-queue）有 IT 範例，剩餘 8 channel 待 QA Lead 與後端對齊後補上。

清單（從 `asyncapi.yaml` 解析，待 QA Lead 確認）：

1. TBD（channel 名稱待確認）
2. TBD
3. TBD
4. TBD
5. TBD
6. TBD
7. TBD
8. TBD

**動作項**：

- QA Lead 與後端 sync `asyncapi.yaml` channel list
- 每個 channel 補 1-3 條 IT-NNN
- 在 PR-NNN 加入 CI gate（mock-smoke.yml 延伸）

---

## §5 Change Log


| 日期         | 版本    | 變更內容                                                          | 作者               |
| ---------- | ----- | ------------------------------------------------------------- | ---------------- |
| 2026-05-07 | 0.1.0 | 骨架建立                                                          | Claude / QA Lead |
| 2026-05-07 | 0.2.0 | Initial Content：IT-001~010 + PACT-001/002 填入（待實際 baseline 跑通） | Claude           |
| TBD        | 0.3.0 | k6 / pytest -m integration baseline 數字確認                      | QA Lead          |
| TBD        | 0.4.0 | Pact contract 加入 CI                                           | Tech Lead        |


