---
id: EVT-0001
title: Domain Event Catalog（事件型錄）
tier: 2
status: accepted
last-synced-with: dccfc0019fa897a3e5b37c4ae1130e6240190d6b
sync-source: doc
synced-at: 2026-05-16
source:
  - "docs/_archive/blueprints/AI鎖匠聊天機器人與工單同步藍圖_v2.xlsx#sheet-10"
source-paths:
  - agent/harness/agent_audit.py
  - agent/harness/pc_creator.py
  - api/services/problem_card_service.py
  - api/services/work_order_service.py
related:
  - "../api/asyncapi.yaml"
  - "../api/openapi.yaml"
  - "../cross-context-ownership.md"
  - "../../1-decisions/ADR-0009-agent-admin-bridge-pattern.md"
  - "../../3-process/PROC-0011-idempotency-dlq-runbook.md"
---

# EVT-0001 — Domain Event Catalog

> 所有跨模組事件統一命名、payload、retention、replay 規格。**新事件必須先進此表才能 build**。本表是 `asyncapi.yaml` 與 audit `event_type` 欄位的 source of truth。

## 1. 事件型錄

| 事件名 | Producer | Consumer(s) | Payload（核心欄）| Retention | Replay 可 | Tenant Key | Audit Trace |
|---|---|---|---|---|---|---|---|
| `conversation.message.received` | LINE webhook | agent runtime, audit | `{conv_id, tenant_id, msg_type, text, media_ref, line_user_id, ts}` | 90d | Yes | `tenant_id` | `audit_logs` (raw) |
| `user_facts.updated` | `update_user_info` tool | PC creator, ERP customer sync | `{user_id, tenant_id, fields, version, source}` | 永久 (SCD2) | Yes | `tenant_id` | `facts.updated` |
| `skill.loaded` | agent runtime | audit, eval, cost | `{conv_id, skill_id, version, brand?, model?}` | 1y | No（純觀察）| `tenant_id` | `skill_loads` |
| `problem_card.create_requested` | agent / `pc_creator` | admin API, audit | `{conv_id, brand, model, symptom, urgency, idempotency_key}` | 1y | Yes（via Outbox）| `tenant_id` | `pc.create_requested` |
| `problem_card.created` | admin API | WS, eval, BI | `{pc_id, conv_id, status=draft, ts}` | 永久 | Yes | `tenant_id` | `pc.created` |
| `problem_card.confirmed` | 客服 / API | WO converter, audit | `{pc_id, actor, ts}` | 永久 | Yes | `tenant_id` | `pc.confirmed` |
| `problem_card.resolved` | 客服 / agent (L1) | BI, SOP feedback | `{pc_id, resolution_layer, summary}` | 永久 | Yes | `tenant_id` | `pc.resolved` |
| `work_order.created` | `convert_to_work_order` API | Dispatch, WS, BI | `{wo_id, pc_id, priority, address}` | 永久 | Yes | `tenant_id` | `wo.created` |
| `work_order.assigned` | dispatch | Technician app, WS, alert | `{wo_id, tech_id, slot, reason}` | 永久 | Yes | `tenant_id` | `wo.assigned` |
| `work_order.accepted` | 技師 | Dispatch, customer notify | `{wo_id, tech_id}` | 永久 | Yes | `tenant_id` | `wo.accepted` |
| `work_order.completed` | Mobile app | Evidence, AR, BI | `{wo_id, summary, photos, amount}` | 永久 | Yes | `tenant_id` | `wo.completed` |
| `evidence.uploaded` | Mobile / 客服 | Audit, RMA, AR | `{wo_id or pc_id, kind, url, sha256}` | 案件結案 + 3y | Yes | `tenant_id` | `evidence.uploaded` |
| `ai_quality.feedback` | 客服修正 / `#資料修正` / 客訴 | AI Ops queue | `{turn_id, conv_id, reason, corrected_answer}` | 1y | Yes | `tenant_id` | `ai_qc.feedback` |
| `policy.decision` | Guardrail / Tool Gateway | Audit, BI | `{conv_id, policy, decision, reason}` | 1y | Yes | `tenant_id` | `policy.decision` |
| `kill_switch.activated` | Admin / SRE | Agent runtime | `{scope=employee\|skill\|tool, target, actor, reason}` | 永久 | — | `tenant_id`（或 global）| `kill_switch.activated` |

## 2. 命名規約

- 格式：`<aggregate>.<verb_past_tense>`（snake_case）；事件代表「事實已發生」，永遠用過去式。
- 變更 payload 欄位 = breaking change，必須 bump 事件版本（`v1`、`v2`），並在本表加新 row（舊事件保留至 retention 到期）。
- `idempotency_key` 必填於 `*.create_requested` 與 `evidence.uploaded`；其餘事件以 aggregate id 為 dedup key。

## 3. Tenant 隔離

- 所有事件 payload 必帶 `tenant_id`（kill_switch 例外可 global）。
- Consumer 訂閱時必須過濾 `tenant_id`，跨租戶讀寫直接 reject。

## 4. Replay 規則

- `Replay 可 = Yes`：可用 audit 重播重建下游狀態。重播時 consumer 必須 idempotent（見 [PROC-0011](../../3-process/PROC-0011-idempotency-dlq-runbook.md)）。
- `Replay 可 = No`：純觀察用，重播沒意義（如 `skill.loaded`）。

## 5. Open items

- AsyncAPI spec（`asyncapi.yaml`）目前未涵蓋所有事件；P1 需把本表 codegen 到 spec。
- Vector DB 事件（如 `knowledge.chunk_embedded`）待 hermes-cs 拍板後新增。

## 6. See also

- [`PROC-0011`](../../3-process/PROC-0011-idempotency-dlq-runbook.md) — 對應的 idempotency / DLQ runbook
- [`cross-context-ownership`](../cross-context-ownership.md) — 跨藍圖（Chatbot ↔ ERP）擁有者規則
- 原始藍圖：sheet「10 Domain Event Catalog」+ sheet「05 事件與Outbox」
