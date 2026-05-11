---
title: Test Case Registry — Human-Readable Index
status: active
last_updated: 2026-05-11
owners: [QA Lead]
related:
  - "./CONVENTION.md"
  - "./registry.yaml"
  - "../../5-views/traceability-matrix.md"
---

# Test Case Registry — Human-Readable Index

> 本檔是 `registry.yaml` 的人讀總覽。**CI 用的 SSOT 是 `registry.yaml`**（由 `extract-test-cases.py` 從各原始檔的 `<!-- TC-ID: XXX -->` 標記自動產生）。
>
> 想查具體 case → 看 `registry.yaml` 或對應的 source file。
> 想看覆蓋率儀表板 → 看本檔 §3。
> 想知道編號規則 → 看 `CONVENTION.md`。

## §1 概覽（自動更新由 CI）

> ⚠️ **下方數字會由 CI 在每次 push 後自動更新。Commit 1 時為初始 0；後續 6 commits 填充。**

| Type | Prefix | Count | Source |
| :-- | :-- | --: | :-- |
| BDD scenario | `BDD-` | 0 | `docs/3-process/bdd/all-features.md` |
| Integration test | `IT-` | 0 | `docs/2-contracts/modules/*.md` |
| Unit test | `UT-` | 0 | `docs/2-contracts/modules/*.md` |
| AI eval | `EVAL-` | 0 | `agent/evals/*.jsonl` |
| End-to-end | `E2E-` | 0 | `web/playwright/` |
| **Total** | | **0** | |

## §2 覆蓋率儀表板

### §2.1 FR 覆蓋率（每個 FR 至少 1 個 TC）

> 目標：25/25 FR 至少 1 個 TC trace。

| FR | Title | TC Count | TC IDs |
| :-- | :-- | --: | :-- |
| FR-0001 | LINE 客服報修受理 | TBD | TBD |
| FR-0002 | ProblemCard 生成 | TBD | TBD |
| ... | ... | ... | ... |

（CI 每次 push 後重新產生。）

### §2.2 Module 覆蓋率（每個 module 至少 5 個 TC）

> 目標：23/23 module 至少 5 個 TC。

| Module | TC Count | Status |
| :-- | --: | :-- |
| conversation-manager | TBD | TBD |
| dispatch-engine | TBD | TBD |
| ... | ... | ... |

### §2.3 Flow 覆蓋率（每個 F-XXX 至少 1 個 TC）

> 目標：23/23 user flow 至少 1 個 TC trace。

| Flow | F-XXX | TC Count | TC IDs |
| :-- | :-- | --: | :-- |
| F-001 | LINE 報修受理 | TBD | TBD |
| ... | ... | ... | ... |

## §3 Derived Views

由 `check-test-case-coverage.py` 在 CI 產生：

### §3.1 Uncovered FR

未被任何 TC trace 的 FR：

| FR | Title | Suggested TC type |
| :-- | :-- | :-- |
| TBD | TBD | TBD |

### §3.2 Orphan TC

`trace: {}` 為空的 TC（孤兒）：

| TC ID | Title | Source |
| :-- | :-- | :-- |
| TBD | TBD | TBD |

### §3.3 Duplicate source

兩個以上 TC 宣稱同一 source line range：

| Source | Conflicting TCs |
| :-- | :-- |
| TBD | TBD |

## §4 撰寫新 case

1. 讀 [`CONVENTION.md`](./CONVENTION.md) §6 撰寫範例 + §7 撰寫順序
2. 在 source file（BDD/module/state-machine）的 case 第一行加 `<!-- TC-ID: PLACEHOLDER -->`
3. 跑 `python scripts/ci/extract-test-cases.py --assign-ids` 自動分配 ID
4. 跑 `python scripts/ci/check-test-case-coverage.py` 驗證 trace 完整
5. PR 帶 `tc-coverage` label，CI 會在 PR comment 報告 coverage delta

## §5 Change Log

| Date | Change |
| :-- | :-- |
| 2026-05-11 | Initial — 骨架建立，待 commit 2-7 填充 |
