---
title: CR-0017 — LINE Flex push 重建 CIA
date: 2026-06-05
status: built
tier: 4
blocks: [Flow 3 last 10%, Flow 11 last 20%, Flow 14 補救流]
---

# CR-0017 — LINE Flex push 重建 CIA

> **狀態補正（2026-06-18，CR-0028）**：本 CR 原誤標 `open-awaiting-decisions`，但 Stage 1-4 已完整 BUILD —— `line_push_outbox_service`（enqueue）+ `line_push_outbox_worker`（main.py 啟動、10s poll）+ `api/templates/line_flex/builders.py`（3 builder + dispatch）+ postback router 皆已落地，並有 `test_cr_0017_outbox_worker.py` / `test_cr_0017_flex_builders.py` 覆蓋。故 status 更正為 `built`。
> CR-0028 接續本基礎建設：(a) 修復 worker resolver 對不存在欄 `work_orders.tenant_id` / `scope_changes.tenant_id` 的 bug（改走 `users.tenant_id`，此前 scope_change push 反查 LINE uid 一直靜默失敗）；(b) 新增 `work_order_assigned` / `work_order_accepted` / `scope_change_result` 三個 push_kind，接通「派工→接單→報價決議」回傳客戶 LINE 的斷鏈。

## 1. 動機

Agent 核心架構重寫（commit `0f037f45`，2026-06-04）刪除舊 ReAct LangGraph agent 與整個 LINE Flex template render module（連帶 `notifications/`、`integrations/`），導致以下三條工作流的「主動 LINE Flex push 客戶」鏈路斷裂：

| Flow | 影響段 | 現況 |
|---|---|---|
| Flow 3 範圍變更 | proposal 建立後 push 客戶 Flex carousel 等待 confirm/reject | scope_changes INSERT 已落地 (commit `239dff9c`) + admin override 已落地 (commit `5f9c333a`) + token mint 已落地，但客戶收不到 LINE 通知 |
| Flow 11 客戶不在場 | propose_reschedule_v2 寫 saas.reschedule_proposal 後 push 客戶 Flex（含 3 個時段選擇 + 都不方便） | backend 完整 + web/track Web Token 路徑完整，LINE Flex 0% |
| Flow 14 排班衝突 | conflict 偵測 → 提建議時段 → push 客戶 Flex | 衝突偵測完整，補救流（含 Flex push）缺失 |

詳見 [`docs/_audit/flow-11-agent-rewrite-impact.md`](flow-11-agent-rewrite-impact.md) 與 [`docs/_audit/flow-12-14-deep-audit.md`](flow-12-14-deep-audit.md)。

## 2. 範圍

**In scope**：決議 LINE Flex template render + push 鏈路的「歸屬」與「觸發機制」。

**Out of scope**：
- payments/billing 相關 LINE Pay flow → CR-0011
- LINE rich menu「查進度」入口 → CR-0013
- 雙向對話 NLU（與「不在場改期 RSVP」業務語意可區分）→ lockcore CS skill 範疇

## 3. 取證

### 3.1 Backend 既有資源 ✅

- `api/services/line_push_service.py` 仍存在，含 `push_to_work_order_customer`（含 retry / backoff / audit），但**只支援 text push，無 Flex template**
- `from linebot import ...` LINE SDK 依賴未刪
- `saas.reschedule_proposal` 表 INSERT 路徑（Flow 11）+ `scope_changes` 表 INSERT 路徑（Flow 3 已補）就緒
- `public_token.generate_token(purpose=..., ttl_days=..., tenant_id=...)` 機制健全

### 3.2 Agent 端（lockcore）狀態 ❌

```
grep -rn "reschedule_proposal\|scope_changes\|FlexMessage\|push_to_work_order" agent/
# → 全空
```

舊 `agent/integrations/line_flex_*.py`、`agent/notifications/`、`agent/skills/tools.py` 全刪。lockcore 工具白名單 (`CS_TOOL_ALLOWLIST`) 為 `{read_file, list_dir, find_files, grep, web_search, transfer_to_human}` — 不含任何 LINE 推送工具。

### 3.3 Outbox / event-driven 觸發點

無既有 outbox pattern；reschedule_proposal / scope_changes INSERT 後**沒有任何 hook**會觸發下游 LINE push。

## 4. Human Decisions Required

### HD-1 — Flex push 歸屬（最關鍵）

| 選項 | 描述 | 優點 | 缺點 |
|---|---|---|---|
| (a) lockcore 工具重建 | 在 `lockcore/agent/tools/` 新增 `line_push_flex` 工具，加入 `CS_TOOL_ALLOWLIST` | 對齊 agent 重寫 architecture lock；LLM 可決定何時 push | 破壞「客服 only 不寫」隔離；agent 需有「為何 push」推理；測試複雜 |
| (b) 純 web only | 不重建 LINE Flex；改 prompt 客戶 (SMS/email/打電話) 引導進 web/track | 最簡單；零 agent 改動；零 LINE 依賴 | UX 退化；reschedule_proposal 改期流失主流量；老人客戶無 web 能力 |
| (c) 獨立 LINE bot service | 新建 `api/services/line_flex_push_service.py` + outbox pattern，**不放回 agent** | 隔離乾淨；triggered by DB outbox 而非 agent 推理；可測試 | 多一個 module；需設計 outbox 表 |
| (d) 階段化 (c)→(a) | 先做 (c) 給 Flow 11/3/14 緊急 UX；後續 lockcore 整合 | 不阻塞既有 BUILD；保留遷移路徑 | 中間態 maintenance |

**建議**：(d) — Flow 11 reschedule 業務天天用，先用 (c) 解 UX；agent 整合留 lockcore 後續演化。

### HD-2 — INSERT → push 觸發機制

| 選項 | 描述 | 優點 | 缺點 |
|---|---|---|---|
| (a) DB trigger | `AFTER INSERT ON saas.reschedule_proposal` 寫 outbox row + 背景 worker poll | 不依賴 service code；保證 push | DB 邏輯重；偵錯難 |
| (b) Service hook | service `propose_reschedule_v2` / `record_scope_change` 內直接 `await line_push_service.push_flex_...` | 邏輯集中；好測試 | 失敗時 retry 設計需小心 |
| (c) Outbox table + worker | service INSERT outbox row，獨立 worker process poll/push | 解耦；可重試；可批次 | 多一個 worker process |
| (d) Service hook + background task | service `asyncio.create_task` 推送，非阻塞 | 簡單；非阻塞；無需新基礎設施 | task 失敗即遺失 |

**建議**：(c) — 對齊 reconciliation/dispute 既有 audit pattern；可橫向用於 Flow 3/11/14。

### HD-3 — Flex template 歸屬

| 選項 | 描述 |
|---|---|
| (a) lockcore skill artifact | `lockcore/skills/locksmith-cs-sop/references/flex_templates/*.json` |
| (b) 獨立 module | `api/templates/line_flex/{reschedule,scope_change,schedule_conflict}.py` (Python flex builders) |
| (c) DB / runtime config | 進 `saas.config_*` 表，可 runtime 改 |

**建議**：(b) — Flex template 是 backend 渲染邏輯，不是 LLM 知識；放 backend 對齊 line_push_service 既有 import path。

### HD-4 — 多 Flow 整合 vs 分批

| 選項 | 描述 |
|---|---|
| (a) 一次性 BUILD 3 Flows (3/11/14) | 一個 sprint 解完 |
| (b) 優先 Flow 11（改期業務流量最大） | 分階段；先解最急 |
| (c) 與 CR-0013 LINE rich menu 「查進度」一併處理 | 統一 LINE 整合 |

**建議**：(b) — 先解最大業務痛點，其他 Flow follow-up；CR-0013 屬入口非通知，性質不同不必綁。

### HD-5 — webhook / postback handler 路由

Customer 在 LINE 點 Flex 按鈕後產生的 postback，需要哪個服務接？

| 選項 |
|---|
| (a) lockcore agent webhook (`agent/lockcore/integrations/line_webhook.py`) — 走 NLU 路徑 |
| (b) `api/routers/line_webhook.py` 新建 — 純 postback router → service |
| (c) 雙路 — 文字訊息走 agent，postback 走 api router |

**建議**：(c) — agent 處理開放式 NLU，api 處理確定性 postback action（直接呼 `confirm_reschedule_by_customer` 等 service）。

## 5. 不立即 BUILD 的理由

業主拍板前，HD-1 / HD-2 / HD-5 任一改動方向都不同：
- 若 HD-1=(a) → 動 lockcore 工具白名單 + Architecture lock
- 若 HD-1=(c) 或 (d) → 純 backend module 新增
- 若 HD-2=(c) → 需新 outbox table schema
- 若 HD-5=(a) → 需評估 agent webhook 與 admin 工單 lifecycle service 解耦

非業主拍板不可的還包括：是否限定 LINE Pay 客戶 / Flex template 多語版 / Flex retry 政策。

## 6. 推薦立場（如業主全採推薦）

- HD-1=(d) 階段化 (c)→(a)
- HD-2=(c) outbox table + worker
- HD-3=(b) Python flex builders in api/templates/
- HD-4=(b) 優先 Flow 11，Flow 3/14 follow-up
- HD-5=(c) 雙路 (NLU agent + postback api router)

預估 BUILD：Flow 11 階段 4-5 day（outbox schema + worker + flex builder + postback router + e2e test）。

## 7. 依賴與相鄰 CR

- 解凍：Flow 3 (90%→100%) / Flow 11 (80%→100%) / Flow 14 (70%→更高)
- 鏡像：CR-0011 LINE Pay flow（金流，不同 channel 但同 LINE SDK）
- 非衝突：CR-0013 LINE rich menu（入口而非通知）

## 8. status

`open-awaiting-decisions` — 等 5 HD 業主裁決後切 CR-0017-BUILD。
