---
id: PROC-0011
title: Idempotency & DLQ Runbook（冪等性與死信佇列）
tier: 3
status: active
owner: Backend / SRE
last_updated: 2026-05-16
source:
  - "docs/_archive/blueprints/AI鎖匠聊天機器人與工單同步藍圖_v2.xlsx#sheet-09"
related:
  - "../2-contracts/events/EVT-0001-domain-event-catalog.md"
  - "../2-contracts/cross-context-ownership.md"
  - "../1-decisions/ADR-0009-agent-admin-bridge-pattern.md"
  - "./PROC-0009-workflow-manual.md"
---

# PROC-0011 — Idempotency & DLQ Runbook

> Seamless sync 的重點不是「一次成功」，而是「失敗可重試、可補償、不重複」。本 runbook 對應 [`EVT-0001`](../2-contracts/events/EVT-0001-domain-event-catalog.md) 每個事件的 idempotency / retry / DLQ 規格。

## 1. Idempotency 表

| 操作 | Idempotency Key 公式 | Dedup 視窗 | DLQ 名稱 | Retry 策略 | Alert 門檻 | 人工補償 SOP | 主責 |
|---|---|---|---|---|---|---|---|
| `create_problem_card` | `sha256(conv_id + first_unresolved_symptom + brand)` | 24h | `dlq_pc_create` | exp-backoff: 1,2,4,8,16s；max 5 | queue age >5min OR retry>3 | Admin 後台 → 手動建 PC → 寫回 `conv_id` | Backend |
| `pc.confirm` | `pc_id + actor` | no dedup needed（idem on state）| — | API 層 409 即正確 | — | — | Backend |
| `pc.resolve` | `pc_id + resolution_layer` | — | — | API 409 正確 | — | — | Backend |
| `convert_to_work_order` | `pc_id`（PK lookup；已存在回 200）| 永久（1:1）| `dlq_wo_create` | exp-backoff；max 3 + manual | 失敗或 retry>2 | 客服重新確認地址 / 手動建 WO 並回寫 `pc_id` | Backend |
| `wo.assign` | `wo_id + technician_id + sched_slot` | 1h | `dlq_dispatch` | **no auto retry（人工）** | 未派工 >SLA（urgent 5min / normal 10min）| 派工主管手動指派 | 派工 |
| `wo.complete` | `wo_id + completion_hash` | 永久 | `dlq_completion` | max 3 with photo upload retry | 完工資料缺 | 技師補上傳 / 客服協助 | 技師主管 |
| `evidence.upload` | `wo_id + file_hash` | 永久 | `dlq_evidence` | exp-backoff；max 10（大檔 + 網路）| 失敗 >2 | 客服 / 技師後台補上傳 | Backend |
| `audit.write` | auto UUID + monotonic seq | no dedup | `dlq_audit`（高優先）| **no retry（critical，直接 fail loud）** | 任何失敗都 P1 | 立即 ops 介入 + 客戶通知 | SRE |
| `ai_quality.feedback` | `turn_id + corrector_id` | no dedup | — | in-app retry on submit | feedback queue age >24h | AI Ops review | AI Ops |

## 2. 規則

1. **Idempotency key 必須 deterministic**：相同輸入 → 相同 key。不可摻入 `now()` / `uuid4()`。
2. **Audit write 不可 retry**：失敗即 P1 page on-call SRE；retry 會讓 audit 雙寫汙染。
3. **Dispatch 不自動 retry**：派工是人決策，重試只會在派工台爆訊息。觸發 SLA alert，由派工主管手動處理。
4. **DLQ 不可清空**：所有 DLQ 訊息必須有人工補償紀錄才能 ack；保留 ≥30 天供稽核。

## 3. Retry exponential backoff 標準

```
attempt 1: t+0      delay 1s
attempt 2: t+1s     delay 2s
attempt 3: t+3s     delay 4s
attempt 4: t+7s     delay 8s
attempt 5: t+15s    delay 16s    （PC create 至此放 DLQ）
attempt 6: t+31s    delay 32s    （evidence upload 才會走到這）
```

每次 retry 必須帶 `attempt_count` 進 audit；連續 retry 失敗 + alert 一次（不要每次都 page）。

## 4. 監控指標

- **DLQ depth**（per queue）：>0 即 warning；>10 即 P1。
- **DLQ age p95**：>5min（PC / WO）/ >24h（feedback）即 alert。
- **Idempotency hit rate**：>5% 異常（暗示 client retry 過頻或 dedup window 設太短）。
- **Audit write failure rate**：>0 都是 P1。

## 5. 補償 SOP

每個操作的「人工補償 SOP」對應到 Admin 後台一個操作頁面。後台補償時必須：

1. 留下 `compensation_id`（誰、何時、為什麼）。
2. 寫回原始 `idempotency_key` 到 audit（標 `manual_compensation=true`）。
3. 完成後從 DLQ ack（不可直接 delete）。

## 6. See also

- 原始藍圖：sheet「09 Idempotency & DLQ Detail」+ sheet「05 事件與Outbox」
- [`EVT-0001`](../2-contracts/events/EVT-0001-domain-event-catalog.md) — 每個事件對應到本表哪一行
- [`ADR-0009`](../1-decisions/ADR-0009-agent-admin-bridge-pattern.md) — Agent ↔ Admin API Outbox 模式
