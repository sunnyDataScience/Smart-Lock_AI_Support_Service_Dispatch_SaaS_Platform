---
id: CR-0121
title: "LINE Webhook 事件分流機制釐清（方案 A：agent 單一入口 fan-out）"
status: accepted
tier: 4-exploration
owner: HYBRID
created: 2026-07-07
target-release: dev_new_arch
product-version: null
supersedes: null
superseded-by: null
related: [ADR-005, CR-0017, CR-0095, CR-0013, R-06]
---

# CR-0121：LINE Webhook 事件分流機制釐清

> **Tier**: 4-exploration → Change Impact Analysis
> **Mandated by**: `.claude/rules/change-governance.md`（觸發面向：External integration + API contract + Architecture boundary）
> **前身決策**：`CR-0017 §HD-5`（雙路路由，postback→api）／`CR-0095`（quote postback→agent）／風險登記 `00_platform/P2/09 §6 R-06`
> **原則依據**：`ADR-005`（三類整合：本橋接屬「類別 2 — 確定性接線 → HTTP」）

---

## 1. Change Statement

**As-is**：平台有兩個 LINE webhook 接收端（agent `POST /callback`、api `POST /api/v1/line/webhook`），掛在**同一個 LINE 官方帳號、共用同一組 `LINE_CHANNEL_SECRET`**。LINE 規定一 channel 只能設定一個 webhook URL，實際只有 agent `/callback` 被掛上。api 的 `/line/webhook`（處理 `r:*` 改約、`s:*` 範圍變更、binding）是**收不到 LINE 流量的孤兒端點**；這些 postback 實際落到 agent，被 agent 明確丟棄「走網頁 fallback」。

**To-be（方案 A）**：確立 **agent `/callback` 為 LINE 唯一入站門**，postback 按前綴 deterministic fan-out——`q:*` 本地處理 + 旁路寫回；`r:*`/`s:*`/binding → 旁路呼 api `/internal/*`（新增對應端點）。api `/api/v1/line/webhook` 退役（標 `superseded`）。

**Driver**：`R-06`（分流機制未明）＋ code review 發現 `api/routers/line_webhook.py:221` 與 `agent/lockcore/channels/line_gateway.py:360` 對「誰收哪些事件」有**物理上不可能同時成立**的假設。這是架構缺口，非單純文件漂移。

## 2. 佐證（現況勘查，grounded）

### 2.1 決定性證據：兩端點同 channel、只有 agent 被掛上

| 事項 | 現況 | 佐證 |
|---|---|---|
| 兩服務簽章密鑰 | 同一組 `LINE_CHANNEL_SECRET` / `LINE_CHANNEL_ACCESS_TOKEN`，無第二組 channel 密鑰 | `agent/.env.example:8`、`api/routers/line_webhook.py:40` |
| 實際掛上的 URL | 只有 agent `/callback`（本機 `ngrok http 8000`）| `docker-compose.dispatch.yml:23`、`agent/P2/06 §1` |
| 互斥假設 | api：「message/follow 由 agent 處理，本 router 只收 postback」；agent：「`s:*`/`r:*` 本 CR 未接，走網頁 fallback」 | `api/routers/line_webhook.py:221`、`agent/lockcore/channels/line_gateway.py:360` |
| 反證 | 若 URL 指 api，客戶文字訊息會進 api 卻被忽略（不轉發）→ AI 永不回話；但 AI 會回話 → URL 必指 agent，`/line/webhook` 對入站是孤兒 | `line_webhook.py:216-223`（非 postback 直接略過）|

### 2.2 handover / 報價流程佐證：正確模式已存在且能動（強化方案 A）

業主回憶的「關掉 Agent 轉人工 + 報價確認」流程，經 code 驗證**全靠 agent 單一入站 + api Push 出站 + `/internal/*` 橋接**，且能動：

| 流程 | 方向 | 實際路徑 | 用到 api `/line/webhook`？ |
|---|---|---|---|
| 轉人工 / 交還 AI | Agent 暫停 | agent 每輪查 `/internal/conversations/handover-state`（`line_gateway.py:240`）；`resolve-handover`（`conversations_v2.py:254`）交還 | ❌ |
| 人工回覆 push 回聊天室 | 出站 | 客服後台送訊息（`conversations_v2.py:208`）→ **LINE Push**（`conversation_service.py:432`）| ❌ |
| 報價卡回傳 LINE | 出站 | `quote_engine_service.py:345`（CR-0095）→ LINE Push | ❌ |
| 客戶按報價「同意 / 拒絕」 | **入站 postback** | `q:a`/`q:r` → **agent `/callback`** → `_route_quote_postback_safe`（`line_gateway.py:351`）→ `/internal/quotes/…` | ❌ 走 agent，非 api webhook |

**洞察**：報價確認（業主印象最深、確實在運作的那條）**刻意繞開** api `/line/webhook`、走 agent `/callback`（CR-0095）。這證明「單一入站 + 橋接」才是實際可用的模式；改約 / 範圍（CR-0017 的 api webhook）是唯一沒照這模式接的，故成孤兒。方案 A 即把它補成跟報價一樣。

## 3. Affected Flow

| Flow | Action | 說明 |
|---|---|---|
| Flow 3（範圍變更）| 修復 | `s:*` postback 補經 agent → `/internal/scope-change`，LINE 一鍵確認真正生效 |
| Flow 11（不在場改約）| 修復 | `r:*` postback 同上 |
| CR-0013（LINE 綁定 / 查進度）| 修復 | binding postback 同上 |
| 報價回覆（CR-0095，quote）| 不變 | `q:*` 現況已通 |

## 4. Affected API

| Endpoint | 服務 | Action | Breaking? | Notes |
|---|---|---|---|---|
| `POST /callback` | agent | 擴充 postback fan-out | 否（對 LINE 契約不變）| 新增 `r:*`/`s:*`/binding 前綴分派 → bridge |
| `POST /internal/*` | api | +N | 否 | 新增 reschedule / scope_change / binding 對應 internal 端點（`require_internal_token`）|
| `POST /api/v1/line/webhook` | api | **退役（superseded）** | 否（本就無 LINE 流量）| 保留 CAS 冪等 service 邏輯，入口改由 `/internal/*` 觸發 |

## 5. Affected Data

無 schema 變更。`reschedule_proposal` / `scope_changes` / line-binding 表已存在（CR-0017 / CR-0028 / CR-0013）。本 CR 只改**事件如何抵達 service**，不改資料形狀。

## 6. Affected Test

| Test | Action | 說明 |
|---|---|---|
| `test_line_gateway.py`（agent）| 擴充 | `r:*`/`s:*` postback 分派 + bridge mock |
| `test_cr_0017_*`（api）| 調整 | `/line/webhook` service 入口改為內部呼叫路徑 |
| E2E（新）| 新增 | 「LINE 按範圍變更同意 → service CAS 冪等生效」端到端（目前 0 覆蓋，因到不了）|

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| 模組邊界 | 動 | 明確定義「agent = LINE 唯一入站門」（記入 ADR-005 §3.2）|
| 新 ADR？ | **是** | `ADR-005`（三類整合原則 + 本方案 A 邊界決策）已立 |
| External integration | 核心 | LINE 單 channel 單 URL 硬約束——方案 A 在此前提下唯一自洽 |

## 8. Human Decisions Required（✅ 已裁決 2026-07-07）

| # | 問題 | 裁決 |
|---|---|---|
| 1 | 採哪個方案？ | ✅ **方案 A**（agent 單一入口 fan-out）|
| 2 | 確認全平台只有一個 LINE OA/channel？ | ✅ 現況單一 `LINE_CHANNEL_SECRET`；**實作前請 ops 再確認生產無第二 OA**（守衛檢查）|
| 3 | `r:*`/`s:*`/binding 橋接走哪？ | ✅ agent → api **新 `/internal/*` 端點**（對齊 quote 先例，屬 ADR-005 類別 2）|
| 4 | quote postback 是否收斂同一路徑？ | ✅ 全留 **agent 一處 fan-out**（`q:*` 現況 + `r:*`/`s:*`/binding 新增），消除命名空間分裂 |
| 5 | LINE 原生改約 / 範圍按鈕是否必要？ | ✅ **必要**——報價經 LINE 一鍵確認既被珍視，改約 / 範圍同等需求（排除方案 C 退役）|

## 9. Suggested Implementation Order

1. **ADR** → ✅ `ADR-005` 已立（三類整合 + 方案 A 邊界）
2. **文件（本步）** → 更新 `agent/P1/05`、`agent/P2/06`、`api/P1/05`、`api/P2/06`、`00_platform/P2/09`（R-06 收斂）
3. **api** → 補 reschedule / scope_change / binding 的 `/internal/*` 端點（`require_internal_token`）
4. **agent** → `line_gateway` postback fan-out 擴充：`r:*`/`s:*`/binding → bridge；移除誤導性「走網頁 fallback」註解
5. **api** → `/api/v1/line/webhook` 改 internal-only 或退役；修正 `line_webhook.py:221` 錯誤註解
6. **Tests** → agent postback 分派 + bridge mock；新增端到端
7. **Traceability / CHANGELOG** → 更新對應矩陣與 `[Unreleased]`

## 10. Risks & Rollback

| Risk | 可能性 | 影響 | 緩解 |
|---|---|---|---|
| agent 成單點：掛掉→所有 LINE（含派工 postback）中斷 | 中 | 高 | fail-soft（bridge 失敗只 log 不阻斷）；agent 部署 min-instances=1 |
| 誤判單 channel，生產實有兩個 OA | 低 | 高 | §8-#2 ops 確認 + 啟動守衛檢查 |

**Rollback**：postback fan-out 以旗標包住，出事關旗即回現況（quote 仍通、其餘回 web fallback）。無 schema 變更，天然可逆。

## 11. Out of Scope

- LINE Pay 金流 postback（CR-0011）
- rate limiting / webhook debounce（R-02、安全 checklist C-11）
- 雙向 NLU 對話語意（lockcore CS skill 範疇）

---

*CR-0121 — 2026-07-07 | 方案 A 已裁決，docs 先行，code 依 §9 後續實作*
