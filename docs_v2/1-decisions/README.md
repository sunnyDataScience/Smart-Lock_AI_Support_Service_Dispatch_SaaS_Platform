---
title: 1-decisions — append-only 判斷
tier: 1
status: active
last_updated: 2026-05-10
---

# Tier 1 — Append-only 判斷 (Decisions)

> 變更頻率：**新增決策才寫新檔；既存檔一旦 accepted 不再編輯**。
> 寫入：HYBRID（AI 草稿 → Human approve）。

## 包含

| 檔案 | 角色 | 來源 |
| :-- | :-- | :-- |
| `architecture-overview.md` | C4 Context/Container/Component；DDD 概覽；deployment topology | 整合 `docs/01-define/E3--*` + `diagrams/02~10`（除 ERD/sequence/api-interface） |
| `domain-model.md` | DDD aggregates、ERD、invariants、domain events | from `docs/01-define/diagrams/E4--06_erd.md` + DDD 化 |
| `frontend-tech-stack.md` | 框架 / 建置工具 / 專案結構選型 | from `docs/02-design/E5x--frontend-architecture §Stack` |
| `module-boundary/agent.md` | Agent 模組 charter（owns / NOT owns / deps / ACL） | from `docs/01-define/E3x--module-breakdown` + `02-design/agent-harness V1.0 sections` |
| `module-boundary/api.md` | API 模組 charter | 同上 |
| `module-boundary/data-pipeline.md` | Data pipeline 模組 charter | 同上 |
| `module-boundary/web.md` | Web 模組 charter | 同上 |
| `ADR-NNNN-*.md` | 個別架構決策 | rename from `docs/01-define/adrs/adr-NNN-*` |

## ADR 命名

`ADR-NNNN-short-description.md`，N 從 0001 起遞增不重用。

舊 `adr-001` ~ `adr-009` → 新 `ADR-0001` ~ `ADR-0009`（Phase 2 git mv）。
新 ADR 透過 `vibecoding-write-architecture` skill 草稿，user approve 後 commit。

預計新增（Phase 3-4）：

| 新 ADR | 主題 | 來源 |
| :-- | :-- | :-- |
| ADR-0010 | Multi-tenant isolation strategy | 拍板後從 `4-exploration/multi-tenant-platform/architecture.md` 升級 |
| ADR-0011 | i18n strategy | from `docs/02-design/specs/i18n-strategy.md` |
| ADR-0012 | Notification channels | from `docs/02-design/specs/notification-channel-strategy.md` |
| ADR-0013~0022 | PM Q1-Q10 alignment 拍板 | from `docs/_flows-bdd-test/decision-log/E7x--pm-alignment-Q1-Q10.md` |
| ADR-0023 | Payment provider | from `docs/_flows-bdd-test/decision-log/Q7-followup--payment-provider-decision.md` |

## 規則

- ADR 一旦 status: accepted **永遠不編輯**；要改寫 → 開新 ADR + `supersedes: ADR-NNNN`
- 修 frontmatter（typo / link rot）允許，但要 PR review
- 每個 ADR 應有 `status` (proposed/accepted/deprecated/superseded)、`date`、`deciders`、`related`
- ADR 用 [VibeCoding ADR template](../../VibeCoding_Workflow_Templates/1-decisions/adr.template.md)
