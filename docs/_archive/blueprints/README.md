---
title: Archived blueprints — 2026-05-16
status: archived
archived-at: 2026-05-16
archived-from: docs/
---

# Archived blueprints

> 這兩份 Excel 是 group leaders 週會的 weekly-review 快照，**不是 source of truth**。實質內容已在 2026-05-16 拆解到對應 tier 的正典文件。保留原檔供歷史追溯與簡報引用。

## 檔案

| 檔案 | 用途 |
|---|---|
| `AI鎖匠聊天機器人系統開發藍圖_v2.xlsx` | AI chatbot 內部架構（系統分層、模組地圖、Memory / Model / Tool / Eval / 風險治理）|
| `AI鎖匠聊天機器人與工單同步藍圖_v2.xlsx` | Chatbot ↔ ERP 同步契約（資料／狀態／API／事件／Idempotency／Gap 決策）|

## 對應正典（請走以下文件，**不要直接引用 xlsx**）

| 原 sheet | 新檔 | Tier |
|---|---|---|
| 系統 10 AI Employee Resume | [`ADR-0028-ai-employee-charter`](../../1-decisions/ADR-0028-ai-employee-charter.md) | 1 |
| 系統 11 Memory Architecture | [`ADR-0026-memory-architecture`](../../1-decisions/ADR-0026-memory-architecture.md) | 1 |
| 系統 12 Model Routing | [`ADR-0027-model-routing-policy`](../../1-decisions/ADR-0027-model-routing-policy.md) | 1 |
| 系統 13 Tool MCP Registry | [`tool-registry.md`](../../2-contracts/tool-registry.md) | 2 |
| 同步 10 Domain Event Catalog | [`EVT-0001-domain-event-catalog`](../../2-contracts/events/EVT-0001-domain-event-catalog.md) | 2 |
| 同步 11 Cross-Blueprint Contract | [`cross-context-ownership.md`](../../2-contracts/cross-context-ownership.md) | 2 |
| 同步 09 Idempotency & DLQ | [`PROC-0011-idempotency-dlq-runbook`](../../3-process/PROC-0011-idempotency-dlq-runbook.md) | 3 |
| **整體快照 + Gap 決策清單** | [`DISC-0001-blueprint-snapshot-2026-05-16`](../../4-exploration/DISC-0001-blueprint-snapshot-2026-05-16.md) | 4 |

其他 sheet（系統分層、模組地圖、端到端流程、RAG 螺旋、API 整合、狀態對照、測試矩陣、Source Trace 等）內容已被既有 tier-1/2/3 文件涵蓋；對照表見 [DISC-0001 §2](../../4-exploration/DISC-0001-blueprint-snapshot-2026-05-16.md#2-內容拆解對照表去重--防-ai-slop-的核心)。

## 不要做

- ❌ 直接編輯 xlsx — 過了 2026-05-16 之後 xlsx 內容**保證過時**
- ❌ 把 xlsx 內容 copy-paste 進新 doc — 違反 [`change-governance`](../../../.claude/rules/change-governance.md)
- ❌ 用 xlsx 內任何 ID（BR-MNN-*, Q001-Q050）當系統識別碼 — 那是 AEOS 模板殘留，本專案的 ID 體系見 [`PRIN-0004-flow-id-conventions`](../../0-principles/PRIN-0004-flow-id-conventions.md)
