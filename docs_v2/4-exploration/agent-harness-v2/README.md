---
title: Agent Harness V2.0 — 8-Layer Framework Blueprint (DRAFT)
status: draft
not_implemented: true
phase: 4-exploration
date: 2026-05-10
related:
  - "../change-requests/CR-0010-agent-harness-v2-migration.md（migration roadmap）"
  - "../../1-decisions/module-boundary/agent-harness.md（V1.0 現況；待建）"
  - "../../2-contracts/modules/problem-card-engine.md（V1.0 已實作部分）"
---

# Agent Harness V2.0

> ⚠️ **未實作**。整個目錄 `status: draft`。
>
> 從 `docs/02-design/agent-harness/` 抽出 V2.0 設計藍圖部分（V1.0 現況另由 `1-decisions/module-boundary/agent-harness.md` 與 `2-contracts/modules/` 對應）。

## V1.0 vs V2.0

| 面向 | V1.0 現況（已上線） | V2.0 設計（本目錄） |
| :-- | :-- | :-- |
| 架構 | FastAPI + LangGraph ReAct Agent (3 tools) + Harness Pipeline (H1-H12) | 8-layer harness (L0 Config → L7 Escalation) |
| 診斷流程 | 隱含於 ReAct loop | 顯式 diagnostic state machine + intent recognition + symptom extraction |
| ProblemCard | V1.0 實作中（見 modules/problem-card-engine.md） | 結構化升級（與 diagnostic-state-machine 整合） |
| Graph orchestration | 單一 ReAct + tool dispatch | LangGraph multi-agent 7 sub-graphs |

## 包含

| 檔案 | 來源 | 內容 |
| :-- | :-- | :-- |
| [`architecture.md`](./architecture.md) | `02-design/agent-harness/harness-architecture.md` | 8-layer (L0-L7) framework definition |
| [`layering-rules.md`](./layering-rules.md) | `02-design/agent-harness/agent-layering-rules.md` | 層間方向性與依賴規則 |
| [`graph-flow.md`](./graph-flow.md) | `02-design/agent-harness/graph-flow-redesign.md` | LangGraph 7 sub-graph 設計 |
| [`diagnostic-architecture.md`](./diagnostic-architecture.md) | `02-design/agent-harness/diagnostic-intelligence-architecture.md` | Software 3.0 診斷引擎 |
| [`diagnostic-state-machine.md`](./diagnostic-state-machine.md) | `02-design/agent-harness/diagnostic-state-machine-spec.md` | 診斷 flow state machine |
| [`config-evolution.md`](./config-evolution.md) | `02-design/agent-harness/config-evolution.md` | 配置管理演進策略 |
| [`poc-spec.md`](./poc-spec.md) | `02-design/agent-harness/poc-spec.md` | PoC scope + success criteria |
| [`optimization.md`](./optimization.md) | `02-design/agent-harness/optimization-strategy.md` | 性能優化路線 |
| [`wbs.md`](./wbs.md) | `02-design/agent-harness/wbs-harness-development.md` | 開發 WBS |

## 對應 CR

[`CR-0010-agent-harness-v2-migration.md`](../change-requests/CR-0010-agent-harness-v2-migration.md) — H-Stage 0-6 漸進式遷移計畫（含 rollback strategies）。

## 升級時機

未定。需先：
1. V1.0 在 prod 穩定 3 個月以上
2. 多租戶基礎已就位（Phase A 多租戶完成）
3. 第一個 OEM 客戶有「客製診斷邏輯」需求
