---
title: Integration Test Matrix — Cross-Module Async Flow
phase: V-MODEL RIGHT (Integration Test layer)
gate: TR5
status: SKELETON
last_updated: 2026-05-07
owners: [QA Lead, Tech Lead]
---

# Integration Test Matrix — Cross-Module Async Flow

> **狀態**: 骨架文件（SKELETON）— 框架就位，10 channel 中 2 個有範例，其餘 8 個待補。

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

| Consumer | Provider | 邊界類型 |
| :--- | :--- | :--- |
| tech mobile (React Native) | pool API | external network |
| web admin | api backend | internal network（同 GCP project） |
| TBD | TBD | TBD |

### 1.3 Cross-Module State Consistency

跨模組（agent ↔ api ↔ web）共享狀態的同步測試 — 例：派工狀態變更後，三方視圖在 < 2s 內收斂。

### 1.4 Eventual Consistency Verification

非同步事件（domain events）發送 → 訂閱方收斂時間驗證；超時門檻：5s（p95）。

---

## §2 IT-NNN Matrix（per AsyncAPI Channel）

| IT-ID | Channel | 觸發場景 | 驗證點 | 對應 F-XXX | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| IT-001 | `/realtime/work-orders/{id}` | 訂閱後外部 API 觸發狀態變更（pending → assigned） | (1) envelope shape 符合 schema (2) ordering 嚴格遞增 (3) p95 推送延遲 < 1s | F-016 | ⚠ TBD baseline |
| IT-002 | `/realtime/dispatch-queue` | 派工成功（runDispatch 成功回傳） | envelope `dispatch_assigned` 在 < 500ms 內收到，`assignedTechId` 與 API 回傳一致 | F-017 | TBD |
| IT-003 | TBD（待補：`/realtime/conversations/{id}`） | TBD | TBD | TBD | TBD |
| IT-004 | TBD | TBD | TBD | TBD | TBD |
| IT-005 | TBD | TBD | TBD | TBD | TBD |
| IT-006 | TBD | TBD | TBD | TBD | TBD |
| IT-007 | TBD | TBD | TBD | TBD | TBD |
| IT-008 | TBD | TBD | TBD | TBD | TBD |
| IT-009 | TBD | TBD | TBD | TBD | TBD |
| IT-010 | TBD | TBD | TBD | TBD | TBD |

**規範**：
- ID 格式：`IT-NNN`
- 每個 AsyncAPI channel 至少 1 條 IT；高風險 channel（如 dispatch / payment）至少 3 條（happy path / error / spike）
- `Status` 用語同 north-star（✅ Live / 🚧 In Dev / ⚠ TBD baseline / ❌ Deferred）

---

## §3 Tooling

| 工具 | 用途 | 已建置? |
| :--- | :--- | :--- |
| **respx** | mock HTTPX requests for FastAPI integration tests | TBD |
| **Pact-Python** | consumer-driven contract（tech mobile ↔ pool） | TBD |
| **AsyncAPI parser** | 解析 asyncapi.yaml 產生 channel test stub | ✅ `scripts/ci/asyncapi-validate.mjs` |
| **websockets test client** | 訂閱 channel + assert envelope | TBD |

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
- [ ] QA Lead 與後端 sync `asyncapi.yaml` channel list
- [ ] 每個 channel 補 1-3 條 IT-NNN
- [ ] 在 PR-NNN 加入 CI gate（mock-smoke.yml 延伸）

---

## §5 Change Log

| 日期 | 版本 | 變更內容 | 作者 |
| :--- | :--- | :--- | :--- |
| 2026-05-07 | 0.1.0 | 骨架建立 | Claude / QA Lead |
| TBD | 0.2.0 | 8 個 TBD channel 補完 | QA Lead |
| TBD | 0.3.0 | Pact contract 加入 CI | Tech Lead |
