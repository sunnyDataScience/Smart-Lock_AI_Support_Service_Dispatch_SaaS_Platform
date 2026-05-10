---
title: 4-exploration — 一次性意圖
tier: 4
status: active
last_updated: 2026-05-10
---

# Tier 4 — Exploration (Per-task Ephemeral Intent)

> 變更頻率：**per-task**。Date-stamp 檔名，shipped 後歸 `archive/`。
> 寫入：HYBRID（AI 草稿 → Human approve），`change-requests/` 必須走 CIA gate。
>
> **AI 警告**：tier 4 是「動機」不是「現況」。不要從 PRD 推論「目前行為」——讀 code 或 tier 2 才知道現況。

## 子目錄

| 子目錄 | 內容 | 來源 |
| :-- | :-- | :-- |
| `change-requests/` | CR-NNNN-*.md（CIA 文件） | 由 `sunnydata-change-impact-analysis` skill 產出。CR-0001 ~ CR-0003 從 `docs/_audit/refactor-plan-*` 演化 |
| `audits/` | 一次性審查報告（架構、code、gap、benchmark） | `docs/_audit/*` + `_gap-analysis/*` + `web_design_spec_prompt_pipeline/references/ui_style_benchmark_report.md` |
| `meetings/` | 會議紀錄（date-stamp） | `docs/_meeting-minutes/*` |
| `archive/` | shipped / superseded 文件歸檔 | `docs/_superseded/*` + `_flows-bdd-test/_archive/*` |
| `multi-tenant-platform/` | V3.0 多租戶藍圖（未啟動，整體 status: draft） | `docs/02-design/platform-multi-tenant/*` + `02-design/specs/{b2b-api,brand-data-api}-spec.md` |
| `agent-harness-v2/` | V2.0 8-layer harness 藍圖（未實作） | `docs/02-design/agent-harness/{harness-architecture,graph-flow-redesign,diagnostic-*,config-evolution,poc-spec,problem-card-spec,migration-roadmap,wbs-harness-development,optimization-strategy,gap-analysis}.md` 中的 V2.0 部分 |
| `data-collection/` | 鎖匠資料蒐集 WBS / status | `docs/_domain-knowledge/requirements/*` + `E2x--wbs-pre-development.md` |

## Top-level 檔（直接放在 `4-exploration/`）

| 檔名 | 角色 | 來源 |
| :-- | :-- | :-- |
| `prd-2026-q1-v1-launch.md` | V1.0 PRD | `docs/00-discover/E1--project-brief-and-prd.md` |
| `wbs-2026-q1-v1.md` | V1.0 WBS | `docs/01-define/E2x--wbs-project-schedule.md` |
| `sow-2026-q1.md` | 工作範圍書 | `docs/01-define/E2--statement-of-work.md` |
| `dispute-case-library.md` | 爭議案例庫 | `docs/_domain-knowledge/locksmith-checklist/18_爭議處理案例.md` |

## frontmatter 範例

```yaml
---
id: CR-0001 / PRD-... / AUDIT-...
status: draft | accepted | shipped | superseded | archived
date: 2026-05-10
shipped-as: ADR-NNNN, src/payments/v2/
shipped-at: 2026-05-10
supersedes: CR-NNNN
superseded_by: CR-MMMM
---
```

## 規則

- 檔名一律含日期或 ID（避免「temp」「draft」這類無時序資訊的命名）
- `status: shipped` 後立刻搬 `archive/`（保留歷史 trace，但不再被 AI 視為 active context）
- `change-requests/` 是 hard gate：實作 code 前必須有對應 CR，且 §8 已拍板
