---
id: CR-0024
title: 對話轉真人 handover 生命週期 — AI 條件式暫停 + 交還 AI
status: draft
created: 2026-06-16
tier: 4
related: [CR-0022, ADR-0112, ADR-0031, fix/escalation-set-conversation-status]
---

# CR-0024 — 對話轉真人 handover 生命週期

## 1. 背景與動機

CR-0022 / ADR-0112 落地了「轉真人 → AI 草擬問題卡」的正向流程;`fix/escalation-set-conversation-status`
補上了「escalation → 對話翻 `escalated`」讓客服發訊框啟用。但 handover 的**生命週期只有去程、沒有回程**,
且存在一個更根本的缺口:

### 現況缺口(實機追查)

1. **AI 從來沒有真的停過 🚨** —— `agent/lockcore/channels/line_gateway.py:201-228` 對**每一則**進來的
   LINE 訊息都跑 `handle_text_turn` 並回覆,**從不查對話是否 escalated**。轉真人後 AI 仍自動回每一句,
   結果是「AI 與真人同時回同一個客人」。`escalated` 狀態只讓後台發訊框亮起,並未讓 AI 閉嘴。
2. **沒有「交還 AI」機制** —— API 無任何 endpoint 能把對話從 `escalated` 改回 `active`/`resolved`;
   對話一旦轉真人就永遠卡在 escalated。
3. **工單結案不連動對話** —— `completeWorkOrderV2` / cancel 與對話狀態無 linkage。

## 2. 觸發面向(CIA gate）

| 面向 | 命中 | 說明 |
|---|---|---|
| User/Business flow | ✅ | handover 回程(交還)為新流程分支 |
| API contract | ✅ | 新增 resolve-handover endpoint + internal handover-state GET |
| Domain model | ✅ | 對話生命週期新增 `escalated → active` 轉換 + WO 結案連動 |
| External integration | ✅ | agent gateway 行為改變(回覆前查狀態 + 條件式回覆) |
| Architecture boundary | ⚠️ | agent 改在 **channel 層**(`lockcore/channels/`),不碰 core runner、不加工具白名單 |
| Test plan | ✅ | 新增 agent gateway 條件式回覆 + API lifecycle 測試 |

## 3. 業主裁決(§8,已於 2026-06-16 對話確認)

| # | 決策點 | 裁決 |
|---|---|---|
| D1 | 接管期間 AI 行為 | **條件式回覆** —— AI 先判斷客人這句是否與「轉接處理中的議題」相關;**相關 → 不回(交真人)**,**不相關(新議題) → AI 照常回答**。 |
| D2 | 「交還 AI」觸發方式 | **兩者都要** —— (a) 對話詳情頁專屬按鈕「結束接管/交還 AI」(b) 工單 complete/cancel 時連動。 |
| D3 | 交還後對話結束狀態 | **回 `active`**,AI 接手(客人下次發話 AI 正常接待)。 |

## 4. 設計

### 4.1 Agent（channel 層,Architecture Lock 合規）
- **回覆前查接管狀態**:gateway 在 `handle_text_turn` 前,以 `INTERNAL_API_TOKEN` 打新 internal GET
  `/internal/conversations/handover-state?session_id=&line_user_id=` → `{escalated: bool, reason: str|null}`。
  **fail-soft**:查不到/逾時/錯誤 → 當作「非接管」照常回(絕不阻斷客人)。
  *Source of truth = API DB*(因為交還由後台觸發,agent 本地 escalation_store 不知道交還事件)。
- **條件式回覆(D1)**:`escalated == true` 時,用**既有 `LiteLLMProvider`** 跑一次輕量分類
  (prompt:客人這句 vs 處理中議題 `reason` → 相關/延續? yes/no)。
  - `related` → **不回**(或回一次性 holding line「專員處理中…」),交真人。
  - `unrelated` → 照常 `handle_text_turn` 回答。
  - **不新增 tool、不改 `CS_TOOL_ALLOWLIST`** —— 只是一次 provider 推論呼叫。
- turn 持久化(方案 A)維持不變。

### 4.2 API
- **新 endpoint**(對外,RBAC admin/CS + tenant guard + audit):
  `POST /tenants/{tid}/conversations/{id}/resolve-handover` —— `escalated → active`;非 escalated → no-op/409。
- **新 internal GET**(`require_internal_token`):`/internal/conversations/handover-state` —— 供 agent gateway。
- **WO 結案連動(D2-b)**:`work_order_service.complete_order` / `cancel_order` 成功後,
  若 `work_order.problem_card_id → problem_cards.conversation_id` 且該對話 escalated → set `active`
  (**fail-soft**,不阻斷結案;寫 audit)。

### 4.3 Web
- 對話詳情頁(`/conversations/[id]`):escalated 時顯示「結束接管 / 交還 AI」按鈕 →
  呼叫 resolve-handover → 成功 toast + refetch(發訊框轉唯讀、狀態 badge 更新)。

## 5. 影響範圍

| 檔案 | 變更 |
|---|---|
| `api/routers/conversations_v2.py` | + resolve-handover endpoint |
| `api/routers/internal_ingest.py` | + handover-state GET |
| `api/services/conversation_service.py` | + `resolve_handover()`(escalated→active) |
| `api/services/work_order_service.py` | complete/cancel 後連動 un-escalate(fail-soft) |
| `agent/lockcore/channels/line_gateway.py` | 回覆前查狀態 + 條件式回覆 + relatedness 分類 |
| `agent/lockcore/providers/litellm_provider.py` | (復用,不改)分類走既有 completion |
| `web/src/app/conversations/[id]/page.tsx` + 元件 | 交還按鈕 |
| tests(api + agent) | lifecycle + 條件式回覆 |

## 6. 不在範圍 / 風險
- relatedness 分類用 LLM,有誤判風險(把相關判成不相關 → AI 插話)。緩解:prompt 保守(預設相關/不回)、
  保留 holding line。可加開關 `HANDOVER_AI_SIDE_ANSWER`(預設關 = 全暫停,開 = 條件式)。
- gateway 每輪多一次 API GET + 可能一次分類 LLM call → 延遲略增;fail-soft 保證不阻斷。

## 7. 建議實作順序(§9)

- **Phase 1(核心生命週期,交還能用)**:API resolve-handover + WO 結案連動 + Web 按鈕
  + gateway「escalated 就全暫停」(先不分類)。→ 「轉真人→AI停→交還→AI恢復」閉環可用。
- **Phase 2(D1 智慧路由)**:gateway 加 relatedness 分類,讓 AI 在接管期間仍能回答不相關的新問題。

> Phase 1 先把回程閉環做出來(風險低、價值高);Phase 2 疊加智慧路由(較高風險、可獨立驗證)。

## 進度

- ✅ **Phase 1 done**（branch `feat/handover-lifecycle-phase1`，2026-06-16）：
  - API：`resolve-handover` endpoint（escalated→active）+ internal `handover-state` GET + WO complete/cancel 連動 un-escalate（fail-soft）
  - Agent：`line_gateway.py` 回覆前查 handover-state，escalated → AI 全暫停（只持久化客人訊息）
  - Web：對話詳情頁「結束接管/交還 AI」按鈕
  - 測試 `test_handover_lifecycle.py` 8 passed + 回歸 32 passed；Playwright 實證按鈕翻狀態
- ⏳ **Phase 2 pending**：D1 智慧路由（relatedness 分類，接管期間 AI 仍答無關新問題）。
