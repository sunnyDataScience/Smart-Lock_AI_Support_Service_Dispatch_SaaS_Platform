# Agent Harness -- AI Agent Framework

> **重要說明**
> 本目錄下的文件分為兩類：
> - **V1.0 現行架構**：`gap-analysis.md`、`optimization-strategy.md`、`migration-roadmap.md`、`wbs-harness-development.md`（含現況追蹤）
> - **V2.0 設計藍圖**（尚未實作）：`harness-architecture.md`、`graph-flow-redesign.md`、`poc-spec.md`、`diagnostic-*`、`problem-card-spec.md`、`config-evolution.md`、`knowledge-asset-review-checklist.md`
>
> V1.0 實際架構：FastAPI + LangGraph ReAct Agent（3 tools）+ Harness Pipeline（H1-H12）
> 最後審查日期：2026-04-21

The Agent Harness is the complete operating environment for model-as-agent operations. This sub-zone documents the 8-layer harness framework (L0-L7), its migration from the current implementation, and diagnostic intelligence architecture.

---

## Relationship to Other Zones

- **Parent:** [[02-design/_MOC]]
- **Design basis:** [[01-define/E3--architecture-and-design]] (5-layer Agent architecture section)
- **Domain input:** [[_domain-knowledge/_MOC]] provides the knowledge assets the harness orchestrates
- **Gap tracking:** [[harness gap-analysis|gap-analysis]] is scoped to this framework only (separate from [[_gap-analysis/gap-analysis-report]])

---

## Documents

### Architecture & Design (TR3-TR4)
| Gate | File | Description | MVD |
|------|------|-------------|-----|
| TR3 | [[harness-architecture]] | 8-layer framework definition (L0 Config through L7 Escalation) | ext-E3 |
| TR4 | [[diagnostic-intelligence-architecture]] | Software 3.0 diagnostic engine: intent recognition, symptom extraction, decision tree | ext-E5 |
| TR4 | [[diagnostic-state-machine-spec]] | State machine for diagnosis flow transitions | ext-E5 |
| TR4 | [[graph-flow-redesign]] | LangGraph workflow redesign for agent orchestration | ext-E5 |
| TR4 | [[config-evolution]] | Configuration management evolution strategy | ext-E5 |
| TR4 | [[problem-card-spec]] | ProblemCard data structure specification | ext-E5 |

### Planning & Migration (TR5)
| Gate | File | Description | MVD |
|------|------|-------------|-----|
| TR5 | [[gap-analysis]] | Layer-by-layer gap analysis: current state vs 8-layer target | ext-E6 |
| TR5 | [[migration-roadmap]] | H-Stage 0-6 phased migration with rollback strategies | ext-E6 |
| TR5 | [[wbs-harness-development]] | Work breakdown structure for harness development | ext-E6 |
| TR4 | [[poc-spec]] | Proof-of-concept scope and success criteria | ext-E5 |
| TR5 | [[optimization-strategy]] | Performance optimization roadmap | ext-E6 |
| TR5 | [[knowledge-asset-review-checklist]] | Knowledge base validation checklist | ext-E7 |

---

## Reading Order

1. [[harness-architecture]] -- Understand the 8-layer model.
2. [[gap-analysis]] -- See where we are vs where we need to be.
3. [[migration-roadmap]] -- The plan to get there.
4. [[diagnostic-intelligence-architecture]] -- The core AI brain.
5. [[graph-flow-redesign]] -- How LangGraph orchestrates it all.
